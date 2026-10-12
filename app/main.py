import shapely.geometry
import shapely.ops
import asyncio
import time
from collections import defaultdict,deque
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,Query,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from .core import ROOT, fetch, postcode, UpstreamError, now
from .catalog import OPTIONS,SOURCES,source
from .providers import location,safe_provider,PROVIDERS,journey

@asynccontextmanager
async def lifespan(app):
    from .epc_session import purge,SESSIONS
    async def expire_sessions():
        while True:
            await asyncio.sleep(30)
            purge()
    await fetch.start()
    expiry=asyncio.create_task(expire_sessions())
    try:yield
    finally:
        expiry.cancel()
        try:await expiry
        except asyncio.CancelledError:pass
        SESSIONS.clear()
        await fetch.close()

app=FastAPI(title='免費仔 free rider — UK postcode reports',version='1.0.0',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
requests_by_ip=defaultdict(deque)

@app.middleware('http')
async def protect(request:Request,call_next):
    if request.url.path.startswith('/api/'):
        stamp=time.monotonic();key=request.client.host if request.client else 'local'
        q=requests_by_ip[key]
        while q and q[0]<stamp-60:q.popleft()
        if len(q)>=90:return JSONResponse({'detail':'Too many requests; try again in a minute.'},status_code=429,headers={'Retry-After':'60'})
        q.append(stamp)
    from .epc_session import TOKEN,resolve
    context=TOKEN.set(resolve(request.cookies.get('epc_session')))
    try:response=await call_next(request)
    finally:TOKEN.reset(context)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'

    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; frame-src https://www.openstreetmap.org; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response

@app.get('/')
async def index():return FileResponse(ROOT/'app/static/index.html')

@app.get('/health')
async def health():return {'status':'ok'}

@app.get('/api/catalog')
async def catalog():
    return {'options':[{'id':i,'label':c,'english':e} for i,c,e in OPTIONS], 'sources':[source(k) for k in SOURCES]}

async def get_location(pc):
    try:return await location(pc)
    except ValueError as e:raise HTTPException(422,str(e))
    except UpstreamError as e:raise HTTPException(404 if e.status==404 else 503,'搵唔到呢個 postcode，或定位服務暫時未能連線。')

@app.get('/api/location/{pc}')
async def locate(pc:str):return await get_location(pc)

@app.get('/api/report/{pc}/{name}')
async def part(pc:str,name:str,radius_km:float|None=Query(None,ge=0.1,le=50),bbox:str|None=Query(None,max_length=160),flood_years:int=Query(1,ge=0,le=100),flood_radius_km:float=Query(5,ge=.1,le=20),crime_month:str|None=Query(None,pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    if name not in PROVIDERS:raise HTTPException(404,'Unknown report section')
    p=await get_location(pc)
    if name=='flood':p={**p,'_flood_years':flood_years,'_flood_radius':flood_radius_km}
    if name=='crime':
        if crime_month:
            dates,_=await fetch.get('https://data.police.uk/api/crimes-street-dates',ttl=86400)
            if crime_month not in {x['date'] for x in dates}:raise HTTPException(422,'警方未發布所選月份。')
            p={**p,'_crime_month':crime_month}
        if radius_km is not None and radius_km>16.1:raise HTTPException(422,'治安半徑最多 16.1 km / 10 miles。')
        if bbox:
            from .crimegeo import bounds
            try:p={**p,'_crime_bbox':bounds(bbox,p)}
            except ValueError as e:raise HTTPException(422,str(e))
    return await safe_provider(name,p,radius_km)

@app.get('/api/report/{pc}')
async def report(pc:str,
                 schools_radius_km:float=Query(10,ge=0.1,le=50),
                 transport_radius_km:float=Query(5,ge=0.1,le=50),
                 amenities_radius_km:float=Query(3.218688,ge=0.1,le=50),
                 green_radius_km:float=Query(5,ge=0.1,le=50),
                 crime_radius_km:float=Query(1.609344,ge=0.1,le=16.1),crime_bbox:str|None=Query(None,max_length=160),flood_years:int=Query(1,ge=0,le=100),flood_radius_km:float=Query(5,ge=.1,le=20),crime_month:str|None=Query(None,pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    p=await get_location(pc)
    p={**p,'_flood_years':flood_years,'_flood_radius':flood_radius_km}
    if crime_month:
        dates,_=await fetch.get('https://data.police.uk/api/crimes-street-dates',ttl=86400)
        if crime_month not in {x['date'] for x in dates}:raise HTTPException(422,'警方未發布所選月份。')
        p={**p,'_crime_month':crime_month}
    names=list(PROVIDERS)
    if crime_bbox:
        from .crimegeo import bounds
        try:p={**p,'_crime_bbox':bounds(crime_bbox,p)}
        except ValueError as e:raise HTTPException(422,str(e))
    radii={'crime':crime_radius_km,'schools':schools_radius_km,'transport':transport_radius_km,'amenities':amenities_radius_km,'green':green_radius_km}
    parts=await asyncio.gather(*(safe_provider(n,p,radii.get(n)) for n in names))
    return {'generated_at':now(),'location':p,'search_radii_km':radii,'sections':dict(zip(names,parts))}

@app.get('/api/journey')
async def commute(origin:str=Query(...,max_length=12),destination:str=Query(...,max_length=12)):
    p=await get_location(origin)
    try:
        postcode(destination)
        return await journey(p,destination)
    except ValueError as e:raise HTTPException(422,str(e))
    except UpstreamError:raise HTTPException(503,'目的地定位暫時未能連線。')

@app.get('/api/school/{urn}')
async def school_profile(urn:str):
    if not urn.isdigit() or len(urn)!=6:raise HTTPException(422,'請使用六位數學校 URN。')
    from .schooldata import profile
    result=await profile(urn)
    if result is None:raise HTTPException(404,'未在已匯入 GIAS 開放學校名單找到此 URN。')
    return result

@app.get('/api/schools/search')
async def school_search(q:str=Query(...,min_length=2,max_length=100)):
    from .core import connect
    from .schooldata import school
    pattern=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    with connect() as db:
        rows=db.execute("SELECT id FROM points WHERE kind='schools' AND name LIKE ? ESCAPE '\\' ORDER BY name LIMIT 25",('%'+pattern+'%',)).fetchall()
    return {'rows':[school(r['id']) for r in rows],'limit':25,'scope':'England open GIAS establishments'}

@app.get('/api/schools/nearby')
async def schools_at_point(lat:float=Query(...,ge=49,le=61),lon:float=Query(...,ge=-9,le=2),radius_km:float=Query(10,ge=.1,le=50)):
    from .core import nearby,import_info
    rows=nearby('schools',lat,lon,radius_km,None)
    return {'rows':[{**r,'urn':r['id']} for r in rows[:1000]],'matching_count':len(rows),'truncated':len(rows)>1000,'radius_km':radius_km,'center':[lat,lon],'imported':import_info('schools')}

@app.get('/api/school/{urn}/context/{section}')
async def school_context(urn:str,section:str):
    from .schooldata import school
    from .school_context import context
    if not urn.isdigit() or len(urn)!=6:raise HTTPException(422,'Invalid URN')
    if section not in {'pupils','benchmarks','admissions','workforce','destinations'}:raise HTTPException(404,'Unknown school section')
    if not school(urn):raise HTTPException(404,'Unknown school')
    return await context(urn,section)


@app.post('/api/updates/check')
async def check_updates(request:Request):
    # Avoid cross-origin pages triggering large background imports.
    origin=request.headers.get('origin')
    if origin and origin!=str(request.base_url).rstrip('/'):
        raise HTTPException(403,'Same-origin request required')
    from .updates import start
    return await start()

@app.get('/api/updates')
async def update_status():
    from .updates import status
    return status()


def require_same_origin(request):
    if request.headers.get('origin')!=str(request.base_url).rstrip('/'):
        raise HTTPException(403,'Same-origin request required')

@app.post('/api/epc/session')
async def epc_session_start(request:Request):
    require_same_origin(request)
    from .epc_session import create,forget
    try:
        if int(request.headers.get('content-length','0') or 0)>22000:raise ValueError()
        body=await request.body()
        if len(body)>22000:raise ValueError()
        import json
        value=json.loads(body)
        sid=create(value.get('token'))
    except (ValueError,TypeError,AttributeError):raise HTTPException(400,'Invalid token input') from None
    forget(request.cookies.get('epc_session'))
    response=JSONResponse({'active':True,'expires_in_seconds':3600})
    response.set_cookie('epc_session',sid,httponly=True,samesite='strict',secure=request.url.scheme=='https',path='/api')
    response.headers['Cache-Control']='no-store'
    return response

@app.get('/api/epc/session')
async def epc_session_status(request:Request):
    from .epc_session import resolve
    return {'active':bool(resolve(request.cookies.get('epc_session'))),'storage':'memory_only','expires_in_seconds_max':3600}

@app.delete('/api/epc/session')
async def epc_session_end(request:Request):
    require_same_origin(request)
    from .epc_session import forget
    forget(request.cookies.get('epc_session'))
    response=JSONResponse({'active':False});response.delete_cookie('epc_session',path='/api');return response

@app.get('/api/crime/months')
async def crime_months():
    try:
        dates,_=await fetch.get('https://data.police.uk/api/crimes-street-dates',ttl=86400)
        return {'months':sorted({x['date'] for x in dates},reverse=True)}
    except UpstreamError:raise HTTPException(503,'警方可選月份暫不可用')

@app.get('/api/epc/certificate/{number}')
async def epc_certificate(number:str):
    import re
    from .epc_session import TOKEN
    from .epc_property import certificate_details
    if not re.fullmatch(r'\d{4}(?:-\d{4}){4}',number):raise HTTPException(422,'請使用官方 20 位證書編號。')
    if not TOKEN.get():raise HTTPException(401,'請按 EPC 授權輸入本次 token。')
    try:
        fields,meta=await certificate_details(number)
        return {'certificate':number,'fields':fields,**meta}
    except UpstreamError:raise HTTPException(503,'EPC 授權失效或官方暫時未能提供證書。')
