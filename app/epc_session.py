"""EPC credentials and authenticated responses stay in process memory only."""
import asyncio,secrets,time,re
from contextvars import ContextVar
import httpx
from .core import UpstreamError,now
TOKEN=ContextVar('epc_token',default=None)
SESSIONS={}
TTL=3600
BASE='https://api.get-energy-performance-data.communities.gov.uk'

def create(token):
    if not isinstance(token,str) or not 1<=len(token)<=20000 or re.search(r'[\s\x00-\x1f\x7f]',token):raise ValueError('Invalid token')
    purge();sid=secrets.token_urlsafe(32);SESSIONS[sid]=(token,time.monotonic()+TTL);return sid

def purge():
    for k,(_,expiry) in list(SESSIONS.items()):
        if expiry<=time.monotonic():SESSIONS.pop(k,None)

def resolve(sid):
    purge();return SESSIONS.get(sid,(None,0))[0]

def forget(sid):SESSIONS.pop(sid,None)

async def get(url,params=None,**unused):
    token=TOKEN.get()
    if not token:raise UpstreamError('EPC session required',401)
    if not url.startswith(BASE+'/api/'):raise UpstreamError('Invalid EPC endpoint')
    try:
        async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
            r=await client.get(url,params=params,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
            r.raise_for_status();data=r.json()
        return data,{'fetched_at':now(),'cache':'session_live_no_disk'}
    except (httpx.HTTPError,ValueError):
        # Never include request headers, body or credential in exception/log output.
        raise UpstreamError('EPC 授權失效或官方服務未能回應；請重新輸入 token。') from None
