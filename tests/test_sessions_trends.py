import asyncio,json,time
import httpx,pytest
from fastapi.testclient import TestClient
from app import core,epc_session,epc_property,main
from app.demography import annual_trend,ethnic_comparison,ethnic_history


def test_session_cookie_isolation_csrf_clear_and_no_echo(monkeypatch):
    main.requests_by_ip.clear()
    async def fake_location(pc):return {'postcode':pc,'country':'England'}
    async def fake_provider(name,p,radius_km=None):return {'has_session':epc_session.TOKEN.get()=='fixture-session-secret'}
    monkeypatch.setattr(main,'get_location',fake_location);monkeypatch.setattr(main,'safe_provider',fake_provider)
    with TestClient(main.app) as a,TestClient(main.app) as b:
        assert a.post('/api/epc/session',json={'token':'fixture-session-secret'},headers={'Origin':'https://elsewhere.invalid'}).status_code==403
        r=a.post('/api/epc/session',json={'token':'fixture-session-secret'},headers={'Origin':'http://testserver'})
        assert r.status_code==200 and 'fixture-session-secret' not in r.text+r.headers['set-cookie']
        assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
        assert a.get('/api/report/RG109RZ/epc').json()['has_session'] is True
        assert b.get('/api/report/RG109RZ/epc').json()['has_session'] is False
        assert a.delete('/api/epc/session',headers={'Origin':'http://testserver'}).status_code==200
        assert a.get('/api/epc/session').json()['active'] is False
    assert epc_session.TOKEN.get() is None


def test_expired_session_is_unusable_and_removed():
    epc_session.SESSIONS['expired']=('fixture-expired',time.monotonic()-1)
    assert epc_session.resolve('expired') is None
    assert 'expired' not in epc_session.SESSIONS


def test_private_epc_http_never_uses_disk_cache_or_redirects(monkeypatch,tmp_path):
    monkeypatch.setattr(core,'DB',tmp_path/'db.sqlite3');core.init_db()
    original=httpx.AsyncClient
    def handler(request):
        assert request.headers['authorization']=='Bearer fixture-private'
        return httpx.Response(200,json={'data':{'total_floor_area':77}})
    monkeypatch.setattr(epc_session.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    async def run():
        ctx=epc_session.TOKEN.set('fixture-private')
        try:
            d,meta=await epc_session.get(epc_session.BASE+'/api/certificate')
            assert d['data']['total_floor_area']==77 and meta['cache']=='session_live_no_disk'
            with pytest.raises(core.UpstreamError):await epc_session.get('https://example.org/api/certificate')
        finally:epc_session.TOKEN.reset(ctx)
    asyncio.run(run())
    with core.connect() as db:assert db.execute('SELECT count(*) FROM cache').fetchone()[0]==0
    assert all(b'fixture-private' not in p.read_bytes() for p in tmp_path.iterdir() if p.is_file())


def test_modern_epc_main_dwelling_not_roof_or_completion_date():
    d=epc_property.measurements({'data':{'total_floor_area':55,'dwelling_type':'Mid-terrace house','habitable_room_count':5,'completion_date':'2025-04-04','schema_type':'RdSAP-Schema-21.0.1','sap_building_parts':[{'building_part_number':1,'construction_age_band':'M','sap_room_in_roof':{'construction_age_band':'B','total_floor_area':100}},{'building_part_number':2,'construction_age_band':'J'}]}})
    assert d['floor_area_m2']==55 and d['construction_age_band']=='M' and d['property_type']=='Mid-terrace house'
    assert d['habitable_rooms']==5 and d['date'] is None


def test_annual_trend_does_not_treat_missing_year_as_annual_change():
    raw=[{'DATE_NAME':y,'OBS_VALUE':str(n),'GENDER':'0','C_AGE':'200'} for y,n in [('2021',100),('2023',120),('2024',108)]]
    rows=annual_trend(raw)
    assert rows[1]['change'] is None
    assert rows[2]['change']==-12 and rows[2]['change_percent']==-10


def test_ethnic_mapping_denominators_and_percentage_points():
    old=[{'C_ETHNICID':c,'OBS_VALUE':str(v),'RURAL_URBAN':'0'} for c,v in [('0',100),('100',80),('300',10)]]
    new=[{'C2021_ETH_20':'1001','OBS_VALUE':'30','C2021_ETH_20_NAME':'Asian'},{'C2021_ETH_20':'1004','OBS_VALUE':'100','C2021_ETH_20_NAME':'White'}]
    rows=ethnic_comparison(old,new,200)
    assert rows[0]['count_2011']==10 and rows[0]['percentage_points']==5
    assert rows[1]['change']==20 and rows[1]['percentage_points']==-30


def test_ethnic_changed_geography_not_compared():
    rows,note=asyncio.run(ethnic_history({'country':'England','codes':{'lsoa':'old','lsoa21':'new'}},[],0))
    assert rows==[] and '代碼不同' in note


def test_crime_month_validation_and_propagation(monkeypatch):
    main.requests_by_ip.clear()
    async def loc(pc):return {'postcode':pc}
    async def dates(*a,**k):return [{'date':'2025-01'}],{}
    async def provider(n,p,radius=None):return {'month':p.get('_crime_month')}
    monkeypatch.setattr(main,'get_location',loc);monkeypatch.setattr(main.fetch,'get',dates);monkeypatch.setattr(main,'safe_provider',provider)
    with TestClient(main.app) as c:
        assert c.get('/api/report/RG109RZ/crime?crime_month=2025-01').json()['month']=='2025-01'
        assert c.get('/api/report/RG109RZ/crime?crime_month=2025-13').status_code==422
        assert c.get('/api/report/RG109RZ/crime?crime_month=2099-01').status_code==422


def test_gias_native_socket_reset_retried_but_disk_errors_not(monkeypatch):
    import scripts.bootstrap_data as bootstrap
    calls=[]
    def transient(client):
        calls.append(1)
        if len(calls)==1:raise ConnectionResetError(54,'Connection reset by peer')
        return 'validated.csv'
    monkeypatch.setattr(bootstrap,'_gias_once',transient)
    monkeypatch.setattr(time,'sleep',lambda seconds:None)
    assert bootstrap.gias(None)=='validated.csv' and len(calls)==2
    def disk_error(client):raise PermissionError(13,'Read-only data directory')
    monkeypatch.setattr(bootstrap,'_gias_once',disk_error)
    with pytest.raises(PermissionError):bootstrap.gias(None)


def test_epc_area_priority_keeps_supplementary_provenance():
    record=epc_property.normalize({'address':'1 HIGH STREET','postcode':'RG10 0EU','total_floor_area':90,'date':'2025-01-01'})
    row=epc_property.apply([{'address':'1 HIGH STREET','price':180000,'floor_area_m2':80,'bedrooms':3,'details_source':'Verified listing','details_date':'2020-01-01'}],[record],'RG10 0EU')[0]
    assert row['floor_area_m2']==90 and row['price_per_m2']==2000
    assert row['bedrooms']==3 and row['supplementary_details_source']=='Verified listing'


def test_epc_certificate_details_require_session_and_validate_id(monkeypatch):
    main.requests_by_ip.clear()
    async def detail(number):return {'floor_area_m2':77,'property_type':'Mid-terrace house'},{}
    monkeypatch.setattr(epc_property,'certificate_details',detail)
    with TestClient(main.app) as c:
        assert c.get('/api/epc/certificate/1111-2222-3333-4444-5555').status_code==401
        assert c.get('/api/epc/certificate/not-a-certificate').status_code==422
        c.post('/api/epc/session',json={'token':'fixture-token'},headers={'Origin':'http://testserver'})
        r=c.get('/api/epc/certificate/1111-2222-3333-4444-5555')
        assert r.status_code==200 and r.json()['fields']['floor_area_m2']==77
        assert 'fixture-token' not in r.text and r.headers['cache-control']=='no-store'


def test_epc_code_decoding_is_schema_specific(monkeypatch):
    async def codes(url,params):return {'data':[{'key':'M','values':[{'value':'2023 onwards','schemaVersion':'new'},{'value':'Wrong vintage','schemaVersion':'old'}]}]},{}
    monkeypatch.setattr(epc_property,'private_get',codes)
    row={'construction_age_band':'M','schema_type':'new'}
    asyncio.run(epc_property.decode_codes([row]))
    assert row['construction_age_band']=='2023 onwards'


def test_sale_address_matches_only_known_locality_and_preserves_flat():
    sale={'address':'FLAT 2 66 HANWOOD CLOSE','locality':'WOODLEY','town':'READING','price':400000}
    record=epc_property.normalize({'addressLine1':'Flat 2, 66 Hanwood Close','addressLine2':'Woodley','addressLine3':'Reading','postcode':'RG5 3AB','uprn':'1','total_floor_area':77,'habitable_room_count':4,'dwelling_type':'Flat','date':'2025-01-01'})
    result=epc_property.apply([sale],[record],'RG5 3AB')[0]
    assert result['floor_area_m2']==77 and result['habitable_rooms']==4
    assert result['epc_type']=='Flat' and result['epc_match_status']=='已配對 EPC'
    other={**sale,'address':'FLAT 1 66 HANWOOD CLOSE','floor_area_m2':None}
    assert epc_property.apply([other],[record],'RG5 3AB')[0]['epc_match_status']=='EPC 地址未配對'


def test_epc_budget_prioritises_distinct_properties_before_old_certificates():
    records=[{'uprn':'1','date':f'2025-{m:02d}-01','certificate':str(m)} for m in range(1,13)]
    records.append({'uprn':'2','date':'2020-01-01','certificate':'other'})
    result=epc_property.detail_priority(records)
    assert [r['uprn'] for r in result[:2]]==['1','2']
    assert result[0]['date']=='2025-12-01'


def test_epc_localised_type_is_plain_text():
    result=epc_property.normalize({'dwelling_type':{'value':'Mid-terrace house','language':'1'},'total_floor_area':78})
    assert result['property_type']=='Mid-terrace house'
    assert result['floor_area_m2']==78

@pytest.mark.parametrize('status',[404,500])
@pytest.mark.parametrize('coordinates',[[-.85,51.45],[51.45,-.85]])
def test_air_spatial_failure_uses_official_inventory_and_filters_distance(monkeypatch,status,coordinates):
    from app import providers
    monkeypatch.setattr(providers,'nearby',lambda *a:[])
    calls=[]
    async def get(url,params,**kwargs):
        calls.append(params)
        if 'near' in params:raise core.UpstreamError('upstream unavailable',status)
        return [{'geometry':{'coordinates':coordinates},'properties':{'label':'Nearby station','id':1}},
                {'geometry':{'coordinates':[-3,55]},'properties':{'label':'Far station','id':2}}],{}
    monkeypatch.setattr(providers.fetch,'get',get)
    result=asyncio.run(providers.air({'latitude':51.45,'longitude':-.85}))
    assert [r['station_id'] for r in result['rows']]==[1]
    assert len(calls)==2 and 'near' not in calls[1]
    assert '官方完整清單' in result['notes'][1]


def test_epc_details_preserve_address_zero_and_nested_components():
    r=epc_property.measurements({'data':{'address_line_1':'16 Example Road','post_town':'Reading','postcode':'RG1 1AA','energy_rating_current':73,'extensions_count':0,'roofs':[{'description':'Insulated roof','energy_efficiency_rating':0}], 'sap_energy_source':{'mains_gas':'Y'},'private_unknown':'not shown'}})
    assert r['address']=='16 Example Road Reading'
    text=json.dumps(r['detail_groups'])
    assert 'Insulated roof' in text and '73' in text and 'not shown' not in text
    assert any(f['value']==0 for g in r['detail_groups'] for f in g['rows'])
