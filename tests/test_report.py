import asyncio,json,time,csv
import httpx
import pytest
from fastapi.testclient import TestClient
from app import core,providers
from app.main import app
from scripts.import_data import import_file

@pytest.fixture(autouse=True)
def isolated_db(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DB',tmp_path/'test.sqlite3');core.init_db()

@pytest.mark.parametrize('raw,expected',[('rg109rz','RG10 9RZ'),(' SW1A  1AA ','SW1A 1AA'),('BT1 5GS','BT1 5GS'),('GIR0AA','GIR 0AA')])
def test_postcode(raw,expected):assert core.postcode(raw)==expected

@pytest.mark.parametrize('raw',['RG10','bad','<script>','RG109RZ" UNION SELECT','https://example.com'])
def test_invalid_postcode(raw):
    with pytest.raises(ValueError):core.postcode(raw)

def test_distance():
    assert core.haversine(51,-1,51,-1)==0
    assert 110<core.haversine(51,-1,52,-1)<112

def test_geospatial_radius_and_order():
    with core.connect() as db:
        for id,lat in [('near',51.0001),('far',52.0),('second',51.005)]:
            db.execute('INSERT INTO points VALUES(?,?,?,?,?,?)',('transport',id,id,lat,-1,'{}'))
    assert [x['id'] for x in core.nearby('transport',51,-1,1)]==['near','second']

def test_cache_and_coalescing():
    async def run():
        calls=[]
        async def handler(request):
            calls.append(1);await asyncio.sleep(.01);return httpx.Response(200,json={'ok':True})
        f=core.Fetcher();f.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results=await asyncio.gather(*(f.get('https://public.test/data') for _ in range(5)))
        assert len(calls)==1
        assert results[0][1]['cache']=='live'
        assert results[-1][1]['cache']=='cached'
        await f.close()
    asyncio.run(run())

def test_auth_error_never_reuses_stale_cache():
    async def run():
        f=core.Fetcher();status=200
        def handler(request):return httpx.Response(status,json={'ok':True})
        f.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await f.get('https://public.test/data',ttl=1)
        with core.connect() as db:db.execute('UPDATE cache SET fetched=?',(time.time()-5,))
        status=401
        with pytest.raises(core.UpstreamError):await f.get('https://public.test/data',ttl=1)
        await f.close()
    asyncio.run(run())

def test_stale_has_timestamp_and_explicit_flag(monkeypatch):
    async def run():
        f=core.Fetcher();status=200
        def handler(request):return httpx.Response(status,json={'ok':True})
        f.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await f.get('https://public.test/data',ttl=1)
        with core.connect() as db:db.execute('UPDATE cache SET fetched=?',(time.time()-5,))
        status=503
        result,meta=await f.get('https://public.test/data',ttl=1)
        assert meta['cache']=='stale' and result=={'ok':True}
        await f.close()
    asyncio.run(run())

def test_country_coverage_does_not_call_england_sources(monkeypatch):
    async def denied(*a,**kw):raise AssertionError('Wrong-country request')
    monkeypatch.setattr(providers.fetch,'get',denied)
    async def run():
        for name in ('crime','flood','prices','demographics','planning','epc'):
            d=await providers.safe_provider(name,{'country':'Scotland'})
            assert d['status']=='coverage_gap'
    asyncio.run(run())

def test_epc_live_history_includes_requested_address(monkeypatch):
    from app import epc_property,epc_session
    async def mock(url,params=None,**kw):
        if url.endswith('/search'):
            return {'data':[{'certificate_number':x,'uprn':1,'registration_date':y,'current_energy_efficiency_band':band,'address_line_1':'PRIVATE ADDRESS','postcode':'RG10 9RZ'} for x,y,band in [('old','2020-01-01','E'),('new','2025-01-01','C')]]},{}
        if url.endswith('/certificate'):return {'data':{'total_floor_area':77,'dwelling_type':'Mid-terrace house','habitable_room_count':5}},{}
        return {'data':[]},{}
    monkeypatch.setattr(epc_property,'private_get',mock)
    async def run():
        ctx=epc_session.TOKEN.set('test-session-only')
        try:return await providers.epc({'country':'England','postcode':'RG10 9RZ'})
        finally:epc_session.TOKEN.reset(ctx)
    d=asyncio.run(run())
    assert len(d['rows'])==2 and d['rows'][0]['band']=='C'
    assert d['rows'][0]['floor_area_m2']==77 and d['rows'][0]['habitable_rooms']==5
    assert d['rows'][0]['address']=='PRIVATE ADDRESS'


def test_provider_failure_isolation(monkeypatch):
    async def broken(p):raise core.UpstreamError('Temporary outage')
    monkeypatch.setitem(providers.PROVIDERS,'crime',broken)
    d=asyncio.run(providers.safe_provider('crime',{}))
    assert d['status']=='unavailable' and d['sources'][0]['id']=='police'

def test_ppd_update_delete_and_rollback(tmp_path):
    p=tmp_path/'ppd.csv'
    def row(id,price,flag):return [id,str(price),'2025-01-01 00:00','RG10 9RZ','D','N','F','1','','ROAD','','READING','WOKINGHAM','BERKSHIRE','A',flag]
    def write(rows):
        with p.open('w') as f:csv.writer(f).writerows(rows)
    write([row('one',100,'A'),row('two',200,'A')]);import_file('prices',p,'source','2025','OGL')
    write([row('one',300,'C'),row('two',200,'D')]);import_file('prices',p,'source','2025','OGL')
    result=core.local_records('prices',pc='RG10 9RZ');assert len(result)==1 and result[0]['price']==300
    write([row('one',400,'C'),['malformed']])
    with pytest.raises(ValueError):import_file('prices',p,'source','2025','OGL')
    assert core.local_records('prices',pc='RG10 9RZ')[0]['price']==300

def test_routes_validation_and_security(monkeypatch):
    with TestClient(app) as c:
        assert c.get('/health').json()=={'status':'ok'}
        r=c.get('/');assert r.status_code==200 and 'Content-Security-Policy' in r.headers
        assert len(c.get('/api/catalog').json()['options'])==15
        assert c.get('/api/location/not-a-postcode').status_code==422
        assert c.get('/api/report/RG109RZ/bogus').status_code==404

# Official release parsing and no-key coverage paths.
def test_ofcom_no_key_and_scope(tmp_path,monkeypatch):
    from scripts.import_ofcom import import_fixed,import_mobile,FIELDS
    import zipfile,io
    def packed(path,name,headers,rows):
        out=io.StringIO();w=csv.writer(out);w.writerow(headers);w.writerows(rows)
        with zipfile.ZipFile(path,'w') as z:z.writestr(name,out.getvalue())
    fixed=tmp_path/'fixed.zip';mobile=tmp_path/'mobile.zip'
    packed(fixed,'release/postcode_files_r2/202601_fixed_pc_coverage_r2_RG.csv',['postcode']+FIELDS,[['RG109RZ',100,90,80,75,'']])
    packed(mobile,'202601_mobile_coverage_laua_r01.csv',['laua','laua_name','4G_prem_in_0','4G_prem_in_4','4G_prem_out_0','5G_high_confidence_prem_out_0'],[['E06000041','Wokingham','',97,0,3]])
    assert import_fixed(fixed)==1 and import_mobile(mobile)==1
    monkeypatch.delenv('OFCOM_API_KEY',raising=False);monkeypatch.delenv('OFCOM_MOBILE_KEY',raising=False)
    result=asyncio.run(providers.broadband({'postcode':'RG10 9RZ','codes':{'admin_district':'E06000041'}}))
    assert result['status']=='ok' and result['rows'][3]['coverage_pct']==75
    assert result['rows'][4]['coverage_pct'] is None
    assert result['mobile_status']=='area_snapshot'
    assert result['mobile_rows'][0]['at_least_one_pct'] is None
    assert result['mobile_rows'][1]['at_least_one_pct']==100
    assert result['mobile_rows'][2]['at_least_one_pct']==97
    assert 'Wokingham' in result['mobile_rows'][0]['scope']
    # Invalid replacement is rolled back, including previous dataset and metadata.
    packed(fixed,'release/postcode_files_r2/202601_fixed_pc_coverage_r2_RG.csv',['postcode']+FIELDS,[['RG109RZ',101,90,80,75,0]])
    with pytest.raises(ValueError):import_fixed(fixed)
    with core.connect() as db:assert db.execute('SELECT sfbb FROM ofcom_fixed').fetchone()[0]==100
    missing=asyncio.run(providers.broadband({'postcode':'SW1A 1AA','codes':{}}))
    assert missing['status']=='setup_required' and missing['rows']==[]

def test_official_epc_csv_privacy(tmp_path):
    path=tmp_path/'epc.csv'
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['CERTIFICATE_NUMBER','POSTCODE','CURRENT_ENERGY_RATING','POTENTIAL_ENERGY_RATING','LODGEMENT_DATE','UPRN','ADDRESS1'])
        w.writerow(['CERT-1','RG109RZ','C','B','2026-01-02','12345','Private address must not be stored'])
    assert import_file('epc',path,'official','2026','OGL')==1
    row=core.local_records('epc',pc='RG10 9RZ')[0]
    assert row['certificate']=='CERT-1' and row['band']=='C'
    assert row['potential_band']=='B' and row['uprn']=='12345'
    assert 'Private address' not in json.dumps(row)

def test_epc_session_never_persists_token(tmp_path):
    from app.epc_session import create,resolve,forget
    sid=create('test-session-only-token')
    assert resolve(sid)=='test-session-only-token'
    forget(sid)
    assert resolve(sid) is None
    assert all(b'test-session-only-token' not in f.read_bytes() for f in tmp_path.iterdir() if f.is_file())
    with pytest.raises(ValueError):create('bad\ntoken')


def test_radius_api_validation(monkeypatch):
    async def fake_location(pc):return {'postcode':pc}
    calls=[]
    async def fake_provider(name,p,radius_km=None):
        calls.append((name,radius_km));return {'status':'ok','radius_km':radius_km}
    from app import main
    monkeypatch.setattr(main,'get_location',fake_location);monkeypatch.setattr(main,'safe_provider',fake_provider)
    with TestClient(app) as c:
        for value in ['0','-1','51','nan','inf']:
            assert c.get('/api/report/RG109RZ/schools',params={'radius_km':value}).status_code==422
        assert c.get('/api/report/RG109RZ/schools?radius_km=1.609344').json()['radius_km']==1.609344
        d=c.get('/api/report/RG109RZ?schools_radius_km=2&green_radius_km=1').json()
        assert d['search_radii_km']['schools']==2 and d['sections']['green']['radius_km']==1

def test_radius_changes_local_results_and_empty_green(monkeypatch):
    with core.connect() as db:
        for kind in ['schools','greenspace']:
            db.execute('INSERT INTO imports VALUES(?,?,?,?,?,?)',(kind,'official','2026',core.now(),2,'OGL'))
            for id,lat in [('near',51.001),('far',51.02)]:
                db.execute('INSERT INTO points VALUES(?,?,?,?,?,?)',(kind,id,id,lat,-1,json.dumps({'site_id':id})))
        for urn in ['136449','136891']:
            db.execute('INSERT INTO points VALUES(?,?,?,?,?,?)',('schools',urn,urn,52,-1,'{}'))
    p={'latitude':51,'longitude':-1,'country':'England'}
    small=asyncio.run(providers.safe_provider('schools',p,1));large=asyncio.run(providers.safe_provider('schools',p,3))
    assert small['matching_count']==1 and large['matching_count']==2
    assert len(small['favourites'])==2 and small['radius_km']==1
    empty=asyncio.run(providers.safe_provider('green',p,0.1))
    assert empty['status']=='ok' and empty['rows']==[] and empty['matching_count']==0
    assert '_radius_km' not in p

def test_fsa_radius_conversion_and_filter(monkeypatch):
    async def fake_get(url,params,**kwargs):
        assert params['maxDistanceLimit']==2
        return {'establishments':[{'BusinessName':'near','BusinessType':'Cafe','FHRSID':1,'Distance':1.99},{'BusinessName':'far','BusinessType':'Cafe','FHRSID':2,'Distance':2.01}]},{}
    monkeypatch.setattr(providers.fetch,'get',fake_get)
    d=asyncio.run(providers.safe_provider('amenities',{'latitude':51,'longitude':-1},3.218688))
    assert d['status']=='ok' and [r['name'] for r in d['rows']]==['near']

def test_crime_geometry_and_bounds():
    from app.crimegeo import query_shape,contains,bounds
    p={'latitude':51.474451,'longitude':-.880651,'_radius_km':2.2*1.609344}
    shape,poly=query_shape(p)
    assert len(poly.split(':'))==32 and len(poly)<4094
    assert contains(shape,51.474451,-.880651)
    assert not contains(shape,51.55,-.880651)
    assert bounds('-.89,51.47,-.87,51.48',p)==[-.89,51.47,-.87,51.48]
    for raw in ['nan,51,-1,52','-2,50,1,60','bad','-.87,51.47,-.89,51.48','-1,55,-.99,55.01']:
        with pytest.raises(ValueError):bounds(raw,p)

def test_crime_counts_anonymous_points_and_asb(monkeypatch):
    from app.crimegeo import contains
    async def fake_get(url,params=None,**kwargs):
        if 'dates' in url:return [{'date':'2026-07'}],{}
        assert 'poly' in params and 'lat' not in params
        def row(id,category,lat):return {'id':id,'category':category,'location':{'latitude':str(lat),'longitude':'-1','street':{'name':'On or near Test'}},'month':'2026-07','outcome_status':None}
        return [row(1,'burglary',51),row(2,'anti-social-behaviour',51),row(3,'burglary',52),{'id':4,'category':'burglary','location':None}],{}
    monkeypatch.setattr(providers.fetch,'get',fake_get)
    p={'latitude':51,'longitude':-1,'country':'England'}
    d=asyncio.run(providers.safe_provider('crime',p,1.609344))
    assert d['status']=='ok' and len(d['incidents'])==2
    assert [m['value'] for m in d['metrics'][:3]]==[2,1,1]
    assert sum(r['count'] for r in d['rows'])==2
    assert d['incidents'][0]['location']=='On or near Test'
    assert all(contains(d['shape'],r['lat'],r['lon']) for r in d['incidents'])
    rect={**p,'_crime_bbox':[-1.001,50.999,-.999,51.001]}
    d=asyncio.run(providers.safe_provider('crime',rect))
    assert d['shape']['mode']=='rectangle' and len(d['incidents'])==2

def test_crime_excessive_query_is_not_zero(monkeypatch):
    async def fake_get(url,*args,**kwargs):
        if 'dates' in url:return [{'date':'2026-07'}],{}
        raise core.UpstreamError('too many',503)
    monkeypatch.setattr(providers.fetch,'get',fake_get)
    d=asyncio.run(providers.safe_provider('crime',{'latitude':51,'longitude':-1,'country':'England'}))
    assert d['status']=='unavailable' and 'incidents' not in d and '10,000' in d['summary']

def test_crime_api_limits_and_export_bbox(monkeypatch):
    from app import main
    async def fake_location(pc):return {'postcode':pc,'latitude':51.474451,'longitude':-.880651}
    async def fake_provider(name,p,radius_km=None):return {'bbox':p.get('_crime_bbox'),'radius_km':radius_km}
    monkeypatch.setattr(main,'get_location',fake_location);monkeypatch.setattr(main,'safe_provider',fake_provider)
    with TestClient(app) as c:
        assert c.get('/api/report/RG109RZ/crime?radius_km=20').status_code==422
        assert c.get('/api/report/RG109RZ/crime?bbox=bad').status_code==422
        box='-.89,51.47,-.87,51.48'
        d=c.get('/api/report/RG109RZ/crime',params={'bbox':box}).json()
        assert d['bbox']==[-.89,51.47,-.87,51.48]
        d=c.get('/api/report/RG109RZ',params={'crime_bbox':box,'crime_radius_km':3.5405568}).json()
        assert d['sections']['crime']['bbox']==[-.89,51.47,-.87,51.48]

def test_school_total_cohort_and_suppression():
    from app.schooldata import normalise_results
    meta={'filters':[{'id':'sex','column':'sex','options':[{'id':'all','label':'Total'}]},{'id':'dis','column':'disadvantage_status','options':[{'id':'all','label':'Total'}]}], 'indicators':[{'id':'p8','column':'progress8_average','label':'Progress 8','unit':''}]}
    rows=[{'filters':{'sex':'all','dis':dis},'values':{'p8':value},'timePeriod':{'period':'2024/25'}} for dis,value in [('all','z'),('other','0.8')]]
    result=normalise_results({'results':rows},meta,{'sex':'Total','disadvantage_status':'Total'},['progress8_average'])
    assert len(result)==1 and result[0]['value']=='z'

def test_ofsted_preserves_framework_and_predecessor():
    from scripts.import_ofsted import parse
    r=parse({'URN':'136449','Inspection start date':'NULL','Inspection start date of latest OEIF graded inspection':'21/11/2023','URN at time of latest OEIF graded inspection':'100001','Latest OEIF overall effectiveness':'1','Date of latest ungraded inspection':'01/01/2025','Ungraded inspection overall outcome':'School remains Good'})
    assert [x['framework'] for x in r['reports']]==['Earlier EIF','Ungraded']
    assert r['reports'][0]['inspection_urn']=='100001'
    assert r['reports'][0]['grades'][0]['value']=='Outstanding'
    assert len(r['reports'][1]['grades'])==1

def test_school_search_literal_and_missing():
    with core.connect() as db:
        db.execute('INSERT INTO points VALUES(?,?,?,?,?,?)',('schools','136449','Reading School',51,-1,'{}'))
    with TestClient(app) as client:
        assert client.get('/api/schools/search',params={'q':'Reading'}).json()['rows'][0]['urn']=='136449'
        assert client.get('/api/schools/search',params={'q':'%%'}).json()['rows']==[]
        assert client.get('/api/school/noturn').status_code==422
        assert client.get('/api/school/999999').status_code==404

def test_school_pin_radius_and_validation():
    with core.connect() as db:
        db.execute('INSERT INTO points VALUES(?,?,?,?,?,?)',('schools','147379','School',51.47,-.90,'{}'))
    with TestClient(app) as client:
        near=client.get('/api/schools/nearby',params={'lat':51.47,'lon':-.90,'radius_km':1}).json()
        far=client.get('/api/schools/nearby',params={'lat':51.47,'lon':-.95,'radius_km':1}).json()
        assert near['matching_count']==1 and near['rows'][0]['urn']=='147379'
        assert far['matching_count']==0
        assert client.get('/api/schools/nearby',params={'lat':0,'lon':0}).status_code==422
        assert client.get('/api/schools/nearby',params={'lat':'nan','lon':0}).status_code==422

def test_offers_exact_urn_and_phase(tmp_path):
    from scripts.import_school_context import import_offers,OFFER_FIELDS
    from app.school_context import offers
    path=tmp_path/'offers.csv';fields=['school_urn','time_period','school_phase','entry_year','school_name',*OFFER_FIELDS.values()]
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for urn,phase,year in [('147379','Primary','202627'),('100001','Primary','202627'),('147379','Secondary','202627')]:
            w.writerow({'school_urn':urn,'time_period':year,'school_phase':phase,'entry_year':'R','school_name':'Test',**{v:'z' for v in OFFER_FIELDS.values()}})
    import_offers(path);r=offers('147379')
    assert len(r['rows'])==2 and all(x['total_offers']=='z' for x in r['rows'])
    assert {x['phase'] for x in r['rows']}=={'Primary','Secondary'}

def test_pupils_total_filter_and_codes(monkeypatch):
    from app import school_context as c
    async def fake(*args):return {},{},{}
    monkeypatch.setattr(c,'dataset',fake)
    monkeypatch.setattr(c,'decoded_rows',lambda *a:iter([
        {'year':'2025/2026','sex':'Total','attendance_pattern':'Total','breakdown':'First language other than English','pupil_count':'c','pupil_percent':'z'},
        {'year':'2025/2026','sex':'Male','attendance_pattern':'Total','breakdown':'Total','pupil_count':'10'},
        {'year':'2025/2026','sex':'Total','attendance_pattern':'Full-time','breakdown':'Total','pupil_count':'20'}]))
    result=asyncio.run(c.pupils('147379'))
    assert len(result['rows'])==1 and result['rows'][0]['count']=='c' and result['rows'][0]['percent']=='z'

def test_ofsted_no_invented_overall_and_early_years():
    from scripts.import_ofsted import parse
    result=parse({'URN':'147379','Inspection start date of latest OEIF graded inspection':'08/07/2025','URN at time of latest OEIF graded inspection':'147379','Latest OEIF overall effectiveness':'Not judged','Latest OEIF early years provision (where applicable)':'1'})
    grades=result['reports'][0]['grades']
    assert grades[0]['value']=='Not judged' and grades[1]['value']=='Outstanding'

def test_each_use_revalidates_cached_api():
    async def run():
        calls=[]
        def handler(request):calls.append(1);return httpx.Response(200,json={'version':len(calls)})
        f=core.Fetcher();f.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        assert (await f.get('https://test.gov.uk/data',ttl=999999))[0]['version']==1
        assert (await f.get('https://test.gov.uk/data',ttl=999999))[0]['version']==1
        f.revalidate_since=time.time()
        assert (await f.get('https://test.gov.uk/data',ttl=999999))[0]['version']==2
        await f.close()
    asyncio.run(run())

def test_flood_history_dates_spatial_and_overlap():
    from datetime import date
    from app.flood_history import select_features,cutoff_date
    from shapely.geometry import mapping,box
    def feature(id,start,end,lon=-.9):return {'id':id,'geometry':mapping(box(lon-.001,51.469,lon+.001,51.471)),'properties':{'rec_out_id':id,'start_date':start,'end_date':end}}
    fs=[feature('recent','2026-01-01','2026-01-03'),feature('old','2024-01-01','2024-01-03'),feature('overlap','2025-09-01','2025-10-01'),feature('unknown',None,None),feature('outside','2026-01-01','2026-01-02',-1.5)]
    rows,geo,unknown=select_features(fs,51.47,-.9,1,1,date(2026,9,22))
    assert {r['id'] for r in rows}=={'recent','overlap'} and all(r['point_within'] for r in rows)
    assert unknown==1 and len(geo['features'])==2
    assert len(select_features(fs,51.47,-.9,1,0,date(2026,9,22))[0])==4
    assert cutoff_date(1,date(2024,2,29))==date(2023,2,28)

def test_conditional_download_and_unchanged_hash(tmp_path):
    from app.updates import download
    seen=[]
    def handler(req):
        seen.append(req)
        if req.headers.get('If-None-Match')=='"v1"':return httpx.Response(304)
        return httpx.Response(200,content=b'real official data',headers={'ETag':'"v1"'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        p,meta,changed=download(c,'https://example.gov.uk/data',tmp_path/'data.csv',{})
        assert changed and p.read_bytes()==b'real official data'
        _,same,changed=download(c,'https://example.gov.uk/data',p,meta)
        assert not changed and same['sha256']==meta['sha256']
        with pytest.raises(ValueError):download(c,'https://untrusted.example/file',p,{})

def test_bad_school_update_preserves_previous_index(tmp_path):
    from scripts.import_school_context import import_offers,OFFER_FIELDS
    with core.connect() as db:db.execute('INSERT INTO records VALUES(?,?,?,?,?)',('school_offers','old',None,'147379','{}'))
    path=tmp_path/'empty.csv'
    with path.open('w') as f:csv.writer(f).writerow(['school_urn','time_period',*OFFER_FIELDS.values()])
    with pytest.raises(ValueError):import_offers(path)
    with core.connect() as db:assert db.execute("SELECT count(*) FROM records WHERE kind='school_offers'").fetchone()[0]==1

def test_flood_query_bounds_and_update_origin():
    with TestClient(app) as client:
        assert client.get('/api/report/RG109RZ/flood?flood_years=-1').status_code==422
        assert client.get('/api/report/RG109RZ/flood?flood_radius_km=nan').status_code==422
        assert client.post('/api/updates/check',headers={'Origin':'https://attacker.example'}).status_code==403

def test_ofsted_latest_date_discovery_handles_short_months():
    from app.updates import ofsted
    html=''.join(f'<a href="https://assets.publishing.service.gov.uk/media/x/Management_information_-_state-funded_schools_-_latest_inspections_as_at_{d}.csv">data</a>' for d in ['31_Dec_2023','31_August_2026','31_July_2026'])
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text=html))) as c:
        assert ofsted(c)['vintage']=='2026-08-31'

def test_gias_daily_download_and_conditional_cache(tmp_path,monkeypatch):
    from scripts import bootstrap_data as b
    monkeypatch.setattr(b,'DATA',tmp_path);requests=[]
    content='URN,EstablishmentName,Easting,Northing,EstablishmentStatus (name)\n147379,École,100,100,Open\n'.encode('cp1252')
    def handler(r):
        requests.append(r)
        if r.headers.get('If-None-Match')=='"today"':return httpx.Response(304)
        return httpx.Response(200,content=content,headers={'etag':'"today"'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        path=b.gias(c);assert path.read_bytes()==content
        assert b.gias(c)==path and requests[-1].headers['If-None-Match']=='"today"'
    assert '/downloads/public/edubasealldata' in str(requests[0].url)

def test_gias_rejects_html_preserves_download(tmp_path,monkeypatch):
    from scripts import bootstrap_data as b
    monkeypatch.setattr(b,'DATA',tmp_path);old=tmp_path/'gias-current.csv';old.write_text('existing')
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text='<html>temporarily unavailable</html>'))) as c:
        with pytest.raises(ValueError):b.gias(c)
    assert old.read_text()=='existing'

def test_ethnicity_denominator_and_no_double_counting():
    from app.demography import ethnicity_rows
    def r(code,n):return {'C2021_ETH_20':str(code),'C2021_ETH_20_NAME':str(code),'OBS_VALUE':str(n),'OBS_STATUS':'A','DATE_NAME':'2021'}
    total,broad,detail=ethnicity_rows([r(0,100),r(1001,30),r(10,20),r(11,10),r(1004,70),r(1,70)])
    assert total==100 and len(broad)==2 and len(detail)==3
    assert broad[0]['percent']==30 and sum(x['count'] for x in detail)==100
    assert all(x['year']=='2021' for x in detail)

def test_demography_missing_values_and_wrong_geography():
    from app.demography import number,csv_rows
    assert number({'OBS_VALUE':'0','OBS_STATUS':'A'})==0
    assert number({'OBS_VALUE':'0','OBS_STATUS':'S'}) is None
    assert number({'OBS_VALUE':'nan','OBS_STATUS':'A'}) is None
    with pytest.raises(core.UpstreamError):csv_rows('GEOGRAPHY_CODE,OBS_VALUE\nE000,100\n','E001')


def test_ofsted_discovery_excludes_html_preview():
    from app.updates import ofsted
    url='https://assets.publishing.service.gov.uk/media/x/Management_information_-_state-funded_schools_-_latest_inspections_as_at_31_August_2026.csv'
    html=f'<a href="https://www.gov.uk/csv-preview/x/Management_information_-_state-funded_schools_-_latest_inspections_as_at_31_August_2026.csv">Preview</a><a href="{url}/preview">Preview</a><a href="{url}">Download</a>'
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text=html))) as c:
        assert ofsted(c)['url']==url+'?download=1'


def test_property_details_exact_match_and_maps(tmp_path):
    from app.property_details import enrich
    from urllib.parse import parse_qs,urlparse
    p=tmp_path/'details.csv'
    p.write_text('postcode,address,floor_area_m2,bedrooms,bathrooms,observed_date,source\nRG10 0EU,1 HIGH STREET,120.5,3,2,2026-09-23,Verified floorplan\n')
    rows=enrich([{'address':'1 High Street'},{'address':'11 High Street'}],'RG10 0EU',p)
    assert rows[0]['floor_area_m2']==120.5 and rows[0]['bedrooms']==3 and rows[0]['bathrooms']==2
    assert rows[1]['bedrooms'] is None
    assert parse_qs(urlparse(rows[0]['google_maps_url']).query)['query']==['1 High Street, RG10 0EU, UK']

def test_property_details_reject_invalid_values_and_ambiguity(tmp_path):
    from app.property_details import enrich,value
    assert value('nan') is None and value('-1',True) is None and value('2.5',True) is None
    assert value('0',True)==0
    p=tmp_path/'details.csv'
    p.write_text('postcode,address,bedrooms,observed_date,source\nRG10 0EU,1 HIGH STREET,3,2026-09-23,A\nRG10 0EU,1 HIGH STREET,4,2026-09-23,B\n')
    assert enrich([{'address':'1 HIGH STREET'}],'RG10 0EU',p)[0]['bedrooms'] is None


def test_epc_property_latest_area_history_and_no_bedroom_inference():
    from app.epc_property import normalize,apply
    raw={'ADDRESS1':'39 BROADWATER ROAD','POSTCODE':'RG10 0EU','UPRN':'123','TOTAL_FLOOR_AREA':'100','NUMBER_HABITABLE_ROOMS':'5','LODGEMENT_DATE':'2025-01-01','CURRENT_ENERGY_RATING':'C','LMK_KEY':'a'}
    new=normalize(raw);old=normalize({**raw,'TOTAL_FLOOR_AREA':'80','LODGEMENT_DATE':'2010-01-01','LMK_KEY':'b'})
    row=apply([{'address':'39 BROADWATER ROAD','price':440000,'bedrooms':None}], [old,new], 'RG10 0EU')[0]
    assert row['floor_area_m2']==100 and row['price_per_m2']==4400
    assert row['floor_area_sqft']==1076.4 and row['habitable_rooms']==5
    assert row['bedrooms'] is None and len(row['epc_history'])==2


def test_epc_property_preserves_units_and_rejects_conflicts():
    from app.epc_property import key,apply,measurements
    assert key('1 2 HIGH STREET','RG10 0EU')!=key('12 HIGH STREET','RG10 0EU')
    assert key('FLAT 1, 2 HIGH STREET','RG10 0EU')!=key('2 HIGH STREET','RG10 0EU')
    assert measurements({'data':{'Total-Floor-Area':90,'Number-Habitable-Rooms':4}})['floor_area_m2']==90
    assert measurements({'a':{'Total-Floor-Area':90},'b':{'Total-Floor-Area':100}})['floor_area_m2'] is None
    r={'address_key':key('1 HIGH STREET','RG10 0EU'),'date':'2025-01-01','floor_area_m2':90,'uprn':'1'}
    row=apply([{'address':'1 HIGH STREET','price':100000}], [r,{**r,'uprn':'2'}],'RG10 0EU')[0]
    assert row.get('floor_area_m2') is None and not row['epc_history']
