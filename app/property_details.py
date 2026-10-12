"""Optional, explicitly sourced property attributes; never infer rooms from PPD."""
import csv,re,math
from urllib.parse import urlencode,urlparse
from .core import DATA

def identity(value):
    return re.sub(r'[^A-Z0-9]','',str(value).upper())

def value(raw,integer=False):
    try:
        n=float(raw)
        if not math.isfinite(n) or n<0 or (not integer and n==0) or (integer and not n.is_integer()):return None
        return int(n) if integer else round(n,2)
    except (ValueError,TypeError):return None

def enrich(rows,postcode,path=None):
    path=path or DATA/'property-details.csv'
    index={}
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                # Require source and observation date; ambiguous matches are not used.
                if not r.get('source') or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',r.get('observed_date','')):continue
                key=(identity(r.get('postcode','')),identity(r.get('address','')))
                if all(key):index.setdefault(key,[]).append(r)
    for r in rows:
        r['google_maps_url']='https://www.google.com/maps/search/?'+urlencode({'api':'1','query':f"{r.get('address','')}, {postcode}, UK"})
        matches=index.get((identity(postcode),identity(r.get('address',''))),[])
        detail=matches[0] if len(matches)==1 else {}
        r.update(floor_area_m2=value(detail.get('floor_area_m2')),bedrooms=value(detail.get('bedrooms'),True),bathrooms=value(detail.get('bathrooms'),True),details_date=detail.get('observed_date'),details_source=detail.get('source'),details_note='多筆資料配對，請核實' if len(matches)>1 else ('補充資料非成交當日規格' if detail else '成交來源沒有提供；尚未有核實補充資料'))
    return rows
