"""Configuration, SQLite response cache and bounded public API requests."""
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data')))
if not DATA.is_absolute():
    DATA = ROOT / DATA
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'report.sqlite3'


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    return db


def init_db():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, body TEXT NOT NULL, fetched REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS points (kind TEXT NOT NULL,id TEXT NOT NULL,name TEXT NOT NULL,lat REAL NOT NULL,lon REAL NOT NULL,meta TEXT NOT NULL,PRIMARY KEY(kind,id));
        CREATE INDEX IF NOT EXISTS spatial ON points(kind,lat,lon);
        CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL,id TEXT NOT NULL,postcode TEXT,area TEXT,meta TEXT NOT NULL,PRIMARY KEY(kind,id));
        CREATE INDEX IF NOT EXISTS by_postcode ON records(kind,postcode);
        CREATE INDEX IF NOT EXISTS by_area ON records(kind,area);
        CREATE TABLE IF NOT EXISTS imports (kind TEXT PRIMARY KEY, source TEXT NOT NULL, vintage TEXT NOT NULL, imported TEXT NOT NULL, count INTEGER NOT NULL, license TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS polygons (kind TEXT NOT NULL,id TEXT NOT NULL,minx REAL,miny REAL,maxx REAL,maxy REAL,geometry TEXT,meta TEXT,PRIMARY KEY(kind,id));
        ''')


init_db()


class UpstreamError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class Fetcher:
    def __init__(self):
        self.client = None
        self.revalidate_since = 0
        self.semaphore = asyncio.Semaphore(5)
        self.locks = {}

    async def start(self):
        self.client = httpx.AsyncClient(timeout=float(os.getenv('REQUEST_TIMEOUT', '20')), follow_redirects=True,
                                        headers={'User-Agent': 'OpenNeighbourhood/1.0 (personal open-data research)', 'Accept': 'application/json'})

    async def close(self):
        if self.client:
            await self.client.aclose()

    async def get(self, url, params=None, ttl=86400, headers=None, text=False, stale=True):
        # Include credential hash so changing subscriptions cannot share private responses.
        signature = json.dumps([url, params, headers], sort_keys=True)
        key = hashlib.sha256(signature.encode()).hexdigest()
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock:
            with connect() as db:
                cached = db.execute('SELECT body,fetched FROM cache WHERE key=?', (key,)).fetchone()
            if cached and cached['fetched'] >= self.revalidate_since and time.time() - cached['fetched'] < ttl:
                return json.loads(cached['body']), self.meta(cached['fetched'], 'cached')
            if self.client is None:
                await self.start()
            error = None
            for attempt in range(2):
                try:
                    async with self.semaphore:
                        response = await self.client.get(url, params=params, headers=headers)
                    if response.status_code == 429:
                        retry = response.headers.get('Retry-After', '2')
                        if attempt == 0 and retry.isdigit() and int(retry) <= 5:
                            await asyncio.sleep(max(1, int(retry)))
                            continue
                    response.raise_for_status()
                    body = response.text if text else response.json()
                    stamp = time.time()
                    with connect() as db:
                        db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', (key, json.dumps(body), stamp))
                    return body, self.meta(stamp, 'live')
                except (httpx.HTTPError, ValueError) as exc:
                    status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                    error = UpstreamError(f'Source returned HTTP {status}' if status else 'Source unavailable or response unreadable', status)
                    if status and status < 500:
                        break
                    if attempt == 0:
                        await asyncio.sleep(0.6)
            # Never silently reuse authentication errors or indefinitely old data.
            if stale and cached and time.time() - cached['fetched'] < max(ttl * 7, 86400) and error.status not in (401, 403):
                return json.loads(cached['body']), self.meta(cached['fetched'], 'stale')
            raise error

    @staticmethod
    def meta(stamp, mode):
        return {'fetched_at': datetime.fromtimestamp(stamp, timezone.utc).isoformat(), 'cache': mode}


fetch = Fetcher()


def postcode(value):
    value = re.sub(r'\s+', '', value).upper()
    if not re.fullmatch(r'(GIR0AA|[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2})', value):
        raise ValueError('請輸入完整 UK postcode，例如 RG10 9RZ。')
    return value[:-3] + ' ' + value[-3:]


def haversine(lat, lon, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    a, b, c, d = map(radians, [lat, lon, lat2, lon2])
    return 6371.0088 * 2 * asin(min(1, sqrt(sin((c-a)/2)**2 + cos(a)*cos(c)*sin((d-b)/2)**2)))


def import_info(kind):
    with connect() as db:
        row = db.execute('SELECT * FROM imports WHERE kind=?', (kind,)).fetchone()
    return dict(row) if row else None


def nearby(kind, lat, lon, radius=5, limit=50):
    from math import cos, radians
    dy, dx = radius / 110.5, radius / (111.32 * max(.1, cos(radians(lat))))
    with connect() as db:
        rows = db.execute('SELECT * FROM points WHERE kind=? AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?',
                          (kind, lat-dy, lat+dy, lon-dx, lon+dx)).fetchall()
    result = []
    for row in rows:
        distance = haversine(lat, lon, row['lat'], row['lon'])
        if distance <= radius:
            result.append({**json.loads(row['meta']), 'id': row['id'], 'name': row['name'], 'lat': row['lat'], 'lon': row['lon'],
                           'distance_km': round(distance, 3), 'distance_miles': round(distance / 1.609344, 2)})
    return sorted(result, key=lambda x: x['distance_km'])[:limit]


def local_records(kind, pc=None, area=None):
    with connect() as db:
        rows = db.execute('SELECT meta FROM records WHERE kind=? AND (postcode=? OR area=?) LIMIT 5000', (kind, pc, area)).fetchall()
    return [json.loads(x['meta']) for x in rows]
