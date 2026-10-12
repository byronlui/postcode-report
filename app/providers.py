import asyncio
import csv
import io
import json
import os
import statistics
from collections import Counter, defaultdict
from urllib.parse import quote, urlparse, urlencode

from .catalog import source
from .core import fetch, postcode, nearby, import_info, local_records, connect, haversine, UpstreamError


def section(key, *, status='ok', summary='', rows=None, metrics=None, notes=None, links=None, **extra):
    return {'status': status, 'summary': summary, 'rows': rows or [], 'metrics': metrics or [],
            'notes': notes or [], 'links': links or [], 'sources': [source(key)], **extra}


def metric(label, value, unit=''):
    return {'label': label, 'value': value, 'unit': unit}


def link(label, url):
    return {'label': label, 'url': url}


def unavailable(key, message, status='unavailable', **extra):
    return section(key, status=status, summary=message, links=[link('官方資料及查詢', source(key)['url'])], **extra)


async def location(pc):
    body, meta = await fetch.get('https://api.postcodes.io/postcodes/' + quote(postcode(pc)), ttl=2592000)
    p = body.get('result')
    if not p or p.get('latitude') is None or p.get('longitude') is None:
        raise UpstreamError('Postcode has no usable coordinates', 404)
    return {**p, 'provenance': meta}


async def crime(p):
    if p['country'] == 'Scotland':
        return unavailable('police', 'Scotland：Police.uk 主要只有 British Transport Police 資料，不能用作地區整體犯罪比較。', 'coverage_gap')
    from .crimegeo import query_shape,contains
    shape,poly=query_shape(p)
    dates,_=await fetch.get('https://data.police.uk/api/crimes-street-dates',ttl=86400)
    month=p.get('_crime_month') or max(x['date'] for x in dates)
    if month not in {x['date'] for x in dates}:return unavailable('police','警方未發布所選月份。')
    try:
        data,meta=await fetch.get('https://data.police.uk/api/crimes-street/all-crime',{'poly':poly,'date':month},ttl=86400)
    except UpstreamError as e:
        if e.status==503:return unavailable('police','警方暫未能完成查詢，可能因範圍超過 10,000 宗上限。請縮小範圍或稍後再試。',shape=shape)
        raise
    if not isinstance(data,list):raise UpstreamError('警方資料格式暫未能讀取。')
    incidents=[];unlocated=0
    for x in data:
        pos=x.get('location') or {}
        try:lat,lon=float(pos['latitude']),float(pos['longitude'])
        except (ValueError,TypeError,KeyError):unlocated+=1;continue
        if not contains(shape,lat,lon):continue
        incidents.append({'id':x.get('id'),'category':x['category'].replace('-',' ').title(),
                          'category_id':x['category'],'lat':lat,'lon':lon,'location':(pos.get('street') or {}).get('name','未提供'),
                          'month':x.get('month',month),'outcome':(x.get('outcome_status') or {}).get('category','未提供結果')})
    counts=Counter(x['category'] for x in incidents)
    asb=sum(x['category_id']=='anti-social-behaviour' for x in incidents)
    scope=f"{shape['radius_miles']:.2f} miles 半徑" if shape['mode']=='circle' else '地圖框選矩形'
    return section('police',summary=f'{month} · {scope} · 按警方匿名位置計算',shape=shape,month=month,
                   radius_km=shape.get('radius_km'),incidents=incidents,
                   rows=[{'category':k,'count':v} for k,v in counts.most_common()],
                   metrics=[metric('已公開事件（含 ASB）',len(incidents)),metric('罪案（不含 ASB）',len(incidents)-asb),metric('反社會行為 ASB',asb),metric('資料月份',month)],
                   notes=['地圖只顯示警方匿名化的大約位置，不是實際案發地址；同一點可代表多宗事件。','這是單一月份已公開紀錄，並非即時案件或犯罪率；未報案、延遲及警隊缺報均影響數字。',f'缺少可用座標而未納入範圍統計：{unlocated} 宗。'],
                   links=[link('警方位置匿名化及資料限制','https://data.police.uk/about/')],**meta)


async def flood(p):
    from .flood_history import history
    return await history(p,p.get('_flood_years',1),p.get('_flood_radius',5))


async def planning(p):
    if p['country'] != 'England':
        return unavailable('planning','Planning Data API 僅涵蓋 England；請查當地 council 規劃登記冊。','coverage_gap',
                           council_lookup='https://www.gov.uk/find-local-council')
    datasets=['conservation-area','listed-building','green-belt','flood-risk-zone','article-4-direction-area','ancient-woodland','site-of-special-scientific-interest']
    params=[('latitude',p['latitude']),('longitude',p['longitude']),('limit',100)]+[('dataset',x) for x in datasets]
    data,meta=await fetch.get('https://www.planning.data.gov.uk/entity.json', params,ttl=86400)
    rows=[{'name':x.get('name') or x.get('reference'), 'dataset':x.get('dataset'), 'reference':x.get('reference'),
           'url':f'https://www.planning.data.gov.uk/entity/{x["entity"]}'} for x in data.get('entities',[])]
    return section('planning', summary='郵區中心點與公開規劃限制的空間交集', rows=rows,
                   notes=['只測試郵區中心點，不是整個郵區或地塊。無結果不代表無規劃限制；各 council 上載進度不同。','Planning applications 尚非全國完整資料；請同時查地方政府登記冊。最多顯示 100 筆。'],
                   links=[link('官方地圖','https://www.planning.data.gov.uk/map/'),link('查 local council','https://www.gov.uk/find-local-council')]+([link('Wokingham planning','https://www.wokingham.gov.uk/planning')] if p.get('admin_district')=='Wokingham' else []),
                   truncated=bool(data.get('links',{}).get('next')), **meta)


async def applications(p):
    if p['country']!='England':return unavailable('planning','此資料源未涵蓋此國家。','coverage_gap')
    lat,lon=p['latitude'],p['longitude']
    dy,dx=.009,.0145
    poly=f'POLYGON(({lon-dx} {lat-dy},{lon+dx} {lat-dy},{lon+dx} {lat+dy},{lon-dx} {lat+dy},{lon-dx} {lat-dy}))'
    data,meta=await fetch.get('https://www.planning.data.gov.uk/entity.json',{'dataset':'planning-application','geometry':poly,'geometry_relation':'intersects','limit':100},ttl=86400)
    return section('planning', summary='附近規劃申請：中心附近約 2 × 2 km 視窗（東西寬度隨緯度變化）',
                   rows=[{'name':x.get('name') or x.get('reference'),'reference':x.get('reference'),'date':x.get('start-date'),'url':f'https://www.planning.data.gov.uk/entity/{x["entity"]}'} for x in data.get('entities',[])],
                   notes=['全國登記仍不完整；空白不能解讀為沒有申請。最多顯示 100 筆。'], **meta)


async def prices(p):
    if p['country'] not in ('England','Wales'):
        return unavailable('prices','HM Land Registry Price Paid Data 只涵蓋 England / Wales。','coverage_gap')
    query='''PREFIX ppi: <http://landregistry.data.gov.uk/def/ppi/>
    PREFIX lr: <http://landregistry.data.gov.uk/def/common/>
    SELECT ?transaction ?price ?date ?type ?tenure ?paon ?saon ?street ?locality ?town WHERE {
      ?address lr:postcode "%s" .
      ?transaction ppi:propertyAddress ?address; ppi:pricePaid ?price; ppi:transactionDate ?date; ppi:propertyType ?type; ppi:estateType ?tenure .
      OPTIONAL { ?address lr:paon ?paon } OPTIONAL { ?address lr:saon ?saon } OPTIONAL { ?address lr:street ?street } OPTIONAL { ?address lr:locality ?locality } OPTIONAL { ?address lr:town ?town }
    } ORDER BY DESC(?date) LIMIT 501''' % postcode(p['postcode'])
    notes=['面積（平方米）、睡房及浴室數目不是 Land Registry 成交欄位；只顯示已附來源的補充資料。補充資料日期不代表成交當日規格，空白不等於零。Google Maps 連結按完整地址及 postcode 搜尋，位置需自行核對。','成交價不是估值；登記有延遲。歷史樣本並非所有房屋，亦不能由此篩選 4-bed（PPD 沒有睡房數）。','年度中位數受成交組合影響，並非相同物業升幅。']
    try:
        data,meta=await fetch.get('https://landregistry.data.gov.uk/landregistry/query',{'query':query,'output':'json'},ttl=604800)
        rows=[]
        for row in data['results']['bindings']:
            r={k:v['value'] for k,v in row.items()}
            rows.append({'id':r['transaction'],'date':r['date'][:10],'price':int(r['price']), 'type':r['type'].split('/')[-1],
                         'tenure':r['tenure'].split('/')[-1], 'locality':r.get('locality',''),'town':r.get('town',''), 'address':' '.join(r.get(x,'') for x in ['saon','paon','street']).strip()})
    except (UpstreamError,KeyError,ValueError):
        rows=local_records('prices',pc=p['postcode'])
        if not rows:raise UpstreamError('Land Registry 暫時未能連線；可用官方 CSV importer 建立本地後備。')
        meta={'cache':'local_dataset','imported':import_info('prices')}
        notes.append('目前使用本地匯入資料；範圍及年份以匯入記錄為準。')
    truncated=len(rows)>500
    rows=sorted(rows,key=lambda r:r['date'],reverse=True)[:500]
    from .property_details import enrich
    rows=enrich(rows,p['postcode'])
    from .epc_property import enrich_epc
    rows,epc_note=await enrich_epc(rows,p['postcode'])
    notes.append(epc_note)
    notes.append('每平方米成交價 = 歷史成交價 ÷ 最新配對面積；若物業曾擴建，不能視為成交當時的單價。')
    years=defaultdict(list)
    for r in rows:years[r['date'][:4]].append(r['price'])
    trend=[{'year':y,'median':round(statistics.median(v)),'count':len(v)} for y,v in sorted(years.items())]
    return section('prices',summary=f'{p["postcode"]} · 同一完整 postcode 的已登記成交',rows=rows,trend=trend,truncated=truncated,
                   metrics=[metric('樣本成交',len(rows)),metric('歷史樣本中位成交價',round(statistics.median([x['price'] for x in rows])) if rows else None,'GBP')],
                   notes=notes+([f'成交樣本日期：{rows[-1]["date"]} 至 {rows[0]["date"]}。'] if rows else [])+(['最多顯示最近 500 筆，分析僅限此樣本。'] if truncated else []), **meta)


async def census_table(p, topic):
    if p['country'] not in ('England','Wales'):
        return unavailable('census','此 Census 2021 接駁僅涵蓋 England / Wales。Scotland 為 Census 2022，需另用當地資料。','coverage_gap')
    geography=p.get('codes',{}).get('lsoa21')
    if not geography:return unavailable('census','缺少 2021 LSOA 對照；沒有用舊邊界代替。','coverage_gap')
    definitions,_=await fetch.get('https://www.nomisweb.co.uk/api/v01/dataset/def.sdmx.json',{'search':f'*{topic}*'},ttl=2592000)
    families=definitions['structure']['keyfamilies']['keyfamily']
    family=next(x for x in families if x['name']['value'].startswith(topic+' '))
    dims=[x['conceptref'] for x in family['components']['dimension'] if x['conceptref'].startswith('C2021_')]
    params={'geography':geography,'measures':'20100','recordlimit':500}
    data,meta=await fetch.get(f'https://www.nomisweb.co.uk/api/v01/dataset/{family["id"]}.data.csv',params,ttl=2592000,text=True)
    raw=list(csv.DictReader(io.StringIO(data)))
    if not raw or 'OBS_VALUE' not in raw[0]:raise UpstreamError('Nomis 未回傳可用人口資料')
    rows=[{'category':' / '.join(r.get(d+'_NAME','') for d in dims),'count':float(r['OBS_VALUE']), 'status':r.get('OBS_STATUS_NAME'),'year':r['DATE_NAME']} for r in raw if r.get('OBS_VALUE')]
    return section('census',summary=f'{family["name"]["value"]} · {p.get("lsoa21")}', rows=rows,
                   geography=geography, topic=topic, notes=['Census 2021，並非現時人口。統計單位是 LSOA，不是單一 postcode。','不同分類可能包含總計及小計；不可把所有行直接相加。'], **meta)


async def schools(p):
    radius=p.get('_radius_km',10)
    info=import_info('schools')
    allrows=nearby('schools',p['latitude'],p['longitude'],radius,None) if info and p['country']=='England' else []
    rows=allrows[:1000]
    for row in rows:
        row['urn']=row['id']
    favourites=[]
    for urn,name,pc,admissions in [('136449','Reading School','RG1 5LW','https://www.reading-school.co.uk/admissions'),('136891','The Piggott School','RG10 8DS','https://www.piggottschool.org/admissions')]:
        with connect() as db:r=db.execute('SELECT * FROM points WHERE kind=? AND id=?',('schools',urn)).fetchone()
        if r:
            lat,lon=r['lat'],r['lon'];basis='DfE establishment coordinates'
        else:
            try:
                loc=await location(pc);lat,lon=loc['latitude'],loc['longitude'];basis='學校 postcode 中心近似值'
            except UpstreamError:
                favourites.append({'name':name,'urn':urn,'distance_miles':None,'url':admissions,'basis':'暫未取得座標'});continue
        favourites.append({'name':name,'urn':urn,'lat':lat,'lon':lon,'distance_miles':round(haversine(p['latitude'],p['longitude'],lat,lon)/1.609344,2),
                           'basis':basis,'url':admissions,'gias':f'https://www.get-information-schools.service.gov.uk/Establishments/Establishment/Details/{urn}'})
    return section('schools',status='ok' if info and p['country']=='England' else 'partial',summary=f'{radius:g} km 內學校；指定關注學校另列（不受半徑限制）',rows=rows,favourites=favourites,
                   radius_km=radius,metrics=[metric(f'{radius:g} km 內教育機構',len(allrows))],matching_count=len(allrows),truncated=len(allrows)>1000,imported=info,
                   notes=['全部距離是郵區中心到学校位置的直線距離，並非步行路程或 admissions 正式量度。','距離不代表 catchment、優先次序或入學保證；須按入學年度、完整住址及官方政策核對。']+([] if info else ['尚未匯入全國 GIAS CSV；指定學校以 postcode 中心計算。'])+([] if p['country']=='England' else ['GIAS 不涵蓋此國家；附近名單不可視為完整。']),
                   links=[link('DfE 學校搜尋','https://www.get-information-schools.service.gov.uk/'),link('Wokingham admissions','https://www.wokingham.gov.uk/schools-and-education/school-admissions')])


async def transport(p):
    radius=p.get('_radius_km',5)
    info=import_info('transport')
    if not info:return unavailable('transport','先匯入 NaPTAN CSV，即可按任意 GB postcode 搜尋附近公共交通站點。','setup_required')
    if p['country']=='Northern Ireland':return unavailable('transport','NaPTAN starter 資料涵蓋 Great Britain；Northern Ireland 請使用 Translink。','coverage_gap')
    allrows=nearby('transport',p['latitude'],p['longitude'],radius,None)
    rows=allrows[:300]
    rail=[r for r in allrows if r.get('stop_type') in ('RLY','RSE','RPL','MET','TMU')]
    return section('transport',summary=f'{radius:g} km 內 NaPTAN 公共交通站點 · 距離由郵區中心計算',radius_km=radius,rows=rows,rail=rail,imported=info,
                   matching_count=len(allrows),truncated=len(allrows)>300,metrics=[metric(f'{radius:g} km 內站點（表格最多 300）',len(allrows)),metric('最近鐵路站點',rail[0]['distance_miles'] if rail else None,'mi')],
                   notes=['站點可包含多個入口、方向或月台，並非獨立車站數量。','站點距離不能推算通勤時間。全英時刻表、班次及票價需使用旅程規劃服務。'],
                   links=[link('National Rail journey planner','https://www.nationalrail.co.uk/'),link('Traveline','https://www.traveline.info/'),link('TfL journey planner','https://tfl.gov.uk/plan-a-journey/')])


async def journey(p,destination):
    dest=await location(destination)
    km=haversine(p['latitude'],p['longitude'],dest['latitude'],dest['longitude'])
    base=section('tfl',summary=f"{p['postcode']} → {dest['postcode']}",metrics=[metric('直線距離',round(km,2),'km')],notes=['地圖顯示 OSRM / OpenStreetMap 行車路線；時間是路網估算，不含即時交通或停車。起終點為 postcode 中心。','公共交通班次與即時交通請按 Google Maps 選擇出發時間；TfL 旅程只涵蓋其可規劃範圍。'],
        origin=[p['latitude'],p['longitude']],destination=[dest['latitude'],dest['longitude']],links=[link('Google Maps · '+label,'https://www.google.com/maps/dir/?'+urlencode({'api':1,'origin':p['postcode']+', UK','destination':dest['postcode']+', UK','travelmode':mode})) for mode,label in [('transit','公共交通及班次'),('driving','行車及交通時間'),('walking','步行'),('bicycling','單車')]])
    base['sources'].append(source('osrm'))
    async def driving():
        try:
            coordinates=f"{p['longitude']},{p['latitude']};{dest['longitude']},{dest['latitude']}"
            data,meta=await fetch.get('https://router.project-osrm.org/route/v1/driving/'+coordinates,{'overview':'full','geometries':'geojson','steps':'false'},ttl=300,stale=False)
            if data.get('code')!='Ok' or not data.get('routes'):raise UpstreamError('No route')
            route=data['routes'][0]
            base['driving_route']=route['geometry']
            base['metrics'] += [metric('行車路程',round(route['distance']/1000,1),'km'),metric('行車估算（非即時交通）',round(route['duration']/60),'分鐘')]
            base['route_fetched_at']=meta.get('fetched_at')
        except (UpstreamError,KeyError,TypeError,ValueError):
            base['notes'].append('路線地圖暫時不可用；Google Maps 路線連結仍可使用。')
    async def transit():
        params={'mode':'publictransport'}
        if os.getenv('TFL_APP_KEY'):params['app_key']=os.environ['TFL_APP_KEY']
        try:
            data,_=await fetch.get(f'https://api.tfl.gov.uk/Journey/JourneyResults/{quote(p["postcode"])}/to/{quote(dest["postcode"])}',params,ttl=300,stale=False)
            base['rows']=[{'duration_minutes':x.get('duration'),'departure':x.get('startDateTime'),'arrival':x.get('arrivalDateTime'),'route':' → '.join(l.get('instruction',{}).get('summary','') for l in x.get('legs',[]))} for x in data.get('journeys',[])[:5]]
        except UpstreamError:pass
        if not base['rows']:base['notes'].append('TfL 未提供此旅程；請開啟 Google Maps 公共交通查詢。')
    await asyncio.gather(driving(),transit())
    if not base.get('driving_route') or not base['rows']:base['status']='partial'
    return base


async def amenities(p):
    radius=p.get('_radius_km',3.218688)
    data,meta=await fetch.get('https://api.ratings.food.gov.uk/Establishments',{'latitude':p['latitude'],'longitude':p['longitude'],'maxDistanceLimit':radius/1.609344,'pageSize':100,'pageNumber':1,'sortOptionKey':'distance'},headers={'x-api-version':'2'},ttl=604800)
    rows=[{'name':x['BusinessName'],'type':x['BusinessType'],'rating':x.get('RatingValue'),'scheme':x.get('SchemeType'),
           'distance_miles':round(float(x['Distance']),2),'postcode':x.get('PostCode'),'rating_date':x.get('RatingDate','')[:10],
           'url':f'https://ratings.food.gov.uk/business/{x["FHRSID"]}'} for x in data.get('establishments',[]) if x.get('Distance') not in (None,'') and float(x['Distance'])*1.609344<=radius+0.000001]
    return section('amenities',summary=f'{radius:g} km 內食品店、餐廳及有食品登記的設施（最多 100）',rows=rows,radius_km=radius,
                   notes=['FSA 不涵蓋所有商店、GP、醫院或公園。衛生評級不是食物質素評分；Scotland 採不同評核制度。'],
                   links=[link('NHS 尋找醫療服務','https://www.nhs.uk/nhs-services/services-near-you/'),link('OS 公開綠地圖','https://osmaps.com/greenspace')], **meta)


async def green(p):
    radius=p.get('_radius_km',5)
    info=import_info('greenspace')
    local=nearby('greenspace',p['latitude'],p['longitude'],radius,None)
    nearest={}
    for row in local:nearest.setdefault(row.get('site_id') or row['id'],row)
    local=list(nearest.values())[:80]
    if info:return section('greenspace',summary=f'OS Open Greenspace · {radius:g} km 內綠地入口（最多 80 個地點）',rows=local,radius_km=radius,matching_count=len(nearest),truncated=len(nearest)>80,metrics=[metric('範圍內綠地',len(nearest))],imported=info,notes=['距離至 OS 公開入口點，屬直線距離；不代表步行路線或現時通行權。'])
    if os.getenv('ENABLE_OSM','false').lower()!='true':
        return section('osm',status='setup_required',summary='綠地、醫療及一般配套：可匯入 OS Open Greenspace，或啟用 OSM 開放資料。',
                       links=[link('OS Open Greenspace','https://www.ordnancesurvey.co.uk/products/os-open-greenspace'),link('NHS 服務','https://www.nhs.uk/nhs-services/services-near-you/')],notes=['OSM 屬社群開放資料，並非政府；預設未開啟。'])
    query=f'[out:json][timeout:15];(nwr(around:{radius*1000},{p["latitude"]},{p["longitude"]})[leisure~"^(park|nature_reserve|playground)$"];nwr(around:{radius*1000},{p["latitude"]},{p["longitude"]})[amenity~"^(hospital|doctors|pharmacy|library)$"];);out center 80;'
    data,meta=await fetch.get('https://overpass-api.de/api/interpreter',{'data':query},ttl=604800)
    rows=[]
    for x in data.get('elements',[]):
        c=x.get('center',x);tags=x.get('tags',{});lat,lon=c.get('lat'),c.get('lon')
        if lat is None:continue
        rows.append({'name':tags.get('name','未命名設施'),'type':tags.get('leisure') or tags.get('amenity'),
                     'distance_miles':round(haversine(p['latitude'],p['longitude'],lat,lon)/1.609344,2),'lat':lat,'lon':lon})
    return section('osm',summary=f'{radius:g} km 內綠地及生活配套（社群資料，非政府）',radius_km=radius,rows=sorted(rows,key=lambda r:r['distance_miles']),notes=['© OpenStreetMap contributors · ODbL。點距離不保證入口、開放時間或通行權。'], **meta)


async def epc(p):
    if p['country'] not in ('England','Wales'):return unavailable('epc','此能源 API 僅涵蓋 England / Wales；請查當地 EPC register。','coverage_gap')
    from .epc_session import TOKEN
    from .epc_property import records_for_postcode
    rows,meta=await records_for_postcode(p['postcode'])
    if not rows and not TOKEN.get():
        return section('epc',status='key_required',summary='請按「EPC 授權」輸入本次使用的官方 bearer token。',notes=['token 只存於伺服器記憶體，最長一小時；不寫入設定檔或資料庫。','官方 EPC 並不提供可靠的睡房／浴室數目。建築年代通常是區間，並非準確落成日期。'],links=[link('官方 EPC token 入口','https://get-energy-performance-data.communities.gov.uk/guidance/energy-certificate-data-apis')])
    public=[{k:v for k,v in r.items() if k not in ('address_key','schema_type')} for r in rows]
    bands=Counter(r.get('band') or 'Unknown' for r in public)
    return section('epc',summary='此 postcode 的 EPC 證書與歷次能源資料',rows=public,distribution=[{'category':k,'count':v} for k,v in sorted(bands.items())],notes=['證書日期不等於建築日期；建築年代保留官方區間或代碼，不推算準確落成日。','物業類型／built form 如為數字，屬官方 schema 代碼，未核對前不轉成文字。','每次最多 40 份證書詳情；搜尋分頁及部分失敗會另行標示。','可居住房間包括客廳等，不是睡房；此圖按證書數，並非唯一物業數。'],**meta)


async def broadband(p):
    rows=local_records('broadband',pc=p['postcode']);info=import_info('broadband')
    notes=['覆蓋比例為整個 postcode 的住宅及商業物業統計，不是個別地址可購買速度，也不是速度測試。','公開 postcode 檔案沒有 full-fibre 比例；gigabit-capable 不等於全光纖。']
    with connect() as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ofcom_fixed'").fetchone()
        fixed=db.execute('SELECT * FROM ofcom_fixed WHERE postcode=?',(p['postcode'],)).fetchone() if exists else None
    if fixed:
        labels={'sfbb':'≥30 Mbit/s','ufbb100':'≥100 Mbit/s','ufbb300':'≥300 Mbit/s','gigabit':'Gigabit-capable','below_decent':'未達 10 Mbit/s 下載 / 1 Mbit/s 上載（fixed / FWA）'}
        rows=[{'category':label,'coverage_pct':fixed[k],'scope':p['postcode']+' · 全部物業'} for k,label in labels.items()]
    meta={'imported':info};key=os.getenv('OFCOM_API_KEY')
    if key:
        try:
            data,meta=await fetch.get('https://api-proxy.ofcom.org.uk/broadband/coverage/'+quote(p['postcode']),headers={'Ocp-Apim-Subscription-Key':key},ttl=604800,stale=False)
            rows=[{'field':k,'value':v} for k,v in data.items() if not isinstance(v,(dict,list))]
        except UpstreamError:
            notes.append('即時 API 未能使用；以下保留有日期標示的公開下載資料。')
    area=p.get('codes',{}).get('admin_district')
    mobile=local_records('mobile',area=area) if area else []
    result=section('broadband',status='ok' if rows else ('partial' if mobile else 'setup_required'),
                   summary='Ofcom 公開網絡資料 · 寬頻按 postcode；手機按地方政府範圍',rows=rows,notes=notes,
                   links=[link('Ofcom 官方覆蓋查詢（逐地址／網絡商）','https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/ofcom-checker'),link('下載資料及方法','https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/connected-nations-update-spring-2026')],**meta)
    if not rows:result['notes'].append('公開快照未有此 postcode，或尚未匯入 Ofcom 下載檔；不是零覆蓋。')
    result['mobile_status']='area_snapshot' if mobile else 'coverage_gap'
    if mobile:
        result['mobile_rows']=mobile[0]['rows'];result['mobile_meta']={'imported':import_info('mobile')}
        result['notes'].append('手機數字屬 '+mobile[0]['area_name']+' 全區物業比例，不能判定此 postcode、屋內或某一網絡商的訊號。至少一間 = 100% 減零網絡商覆蓋比例；空白不當作零。')
    mobile_url=os.getenv('OFCOM_MOBILE_URL','');mobile_key=os.getenv('OFCOM_MOBILE_KEY','')
    if mobile_url and mobile_key:
        parsed=urlparse(mobile_url)
        if parsed.scheme!='https' or not (parsed.hostname=='api-proxy.ofcom.org.uk' or (parsed.hostname or '').endswith('.azure-api.net')) or '{postcode}' not in mobile_url:
            result['notes'].append('Mobile endpoint 設定不正確；只接受官方 HTTPS gateway 及 {postcode} template。')
        else:
            try:
                data,mm=await fetch.get(mobile_url.replace('{postcode}',quote(p['postcode'],safe='')),headers={'Ocp-Apim-Subscription-Key':mobile_key},ttl=604800,stale=False)
                result['mobile']=data;result['mobile_status']='ok';result['mobile_meta']=mm
            except UpstreamError:result['notes'].append('逐地址 mobile API 暫時未能使用；地方政府快照仍可參考。')
    return result


async def noise(p):
    if p['country']!='England':
        return unavailable('noise','Defra round 4 圖層只涵蓋 England。','coverage_gap')
    info=import_info('noise')
    if info:
        from shapely.geometry import shape, Point
        lon,lat=p['longitude'],p['latitude']
        with connect() as db:
            rows=db.execute('SELECT geometry,meta FROM polygons WHERE kind=? AND minx<=? AND maxx>=? AND miny<=? AND maxy>=?',('noise',lon,lon,lat,lat)).fetchall()
        matches=[json.loads(r['meta']) for r in rows if shape(json.loads(r['geometry'])).covers(Point(lon,lat))]
        return section('noise',summary='郵區中心與已匯入噪音等值區交集',rows=matches,imported=info,notes=['模型年份及指標應分開閱讀。空白可能低於圖層門檻或未覆蓋。'])
    from pyproj import Transformer
    x,y=Transformer.from_crs(4326,27700,always_xy=True).transform(p['longitude'],p['latitude'])
    async def point_value(kind,measure):
        endpoint='road-noise-all-metrics-england-round-4' if kind=='Road' else 'noise-data'
        layer=f'{kind}_Noise_{measure}_England_Round_4_All'
        params={'service':'WMS','version':'1.1.1','request':'GetFeatureInfo','layers':layer,'query_layers':layer,
                'srs':'EPSG:27700','bbox':f'{x-5},{y-5},{x+5},{y+5}','width':101,'height':101,'x':50,'y':50,'info_format':'application/json','feature_count':1}
        data,meta=await fetch.get(f'https://environment.data.gov.uk/spatialdata/{endpoint}/wms',params,ttl=2592000)
        features=data.get('features',[])
        value=features[0].get('properties',{}).get('GRAY_INDEX') if features else None
        value=round(float(value),1) if value is not None and 0<float(value)<150 else None
        return {'source':kind,'metric':measure,'modelled_db':value,'year':'2021 (round 4)','availability':'modelled value' if value is not None else 'NoData / below published threshold',**meta}
    results=await asyncio.gather(*(point_value(k,m) for k in ('Road','Rail') for m in ('Lden','Lnight')),return_exceptions=True)
    rows=[r for r in results if isinstance(r,dict)]
    return section('noise',status='ok' if len(rows)==4 else 'partial' if rows else 'unavailable',summary='Defra 道路／鐵路噪音 · 郵區中心 10 m 模型格網',rows=rows,
                   notes=['模型代表 2021 年全年環境；屬 round 4。並非現時、室內或現場量度。','Lden 包含晚間／夜間懲罰權重；Lnight 為夜間。不同指標不可相加。','NoData 可能低於發布門檻（Lnight 35 dB；其他 40 dB）或未覆蓋，不能當成 0。','© Defra copyright and/or database right 2023. OGL v3.0.'],
                   links=[link('官方模型解說','https://www.gov.uk/government/publications/strategic-noise-mapping-2022')])


async def air(p):
    rows=nearby('air',p['latitude'],p['longitude'],20,10)
    if rows:return section('air',summary='附近已匯入空氣質素資料',rows=rows,imported=import_info('air'))
    # Public UK-AIR station inventory; nearest stations are context, not postcode readings.
    endpoint='https://uk-air.defra.gov.uk/sos-ukair/api/v1/stations'
    fallback=False
    try:
        data,meta=await fetch.get(endpoint,{'expanded':'true','near':json.dumps({'center':{'type':'Point','coordinates':[p['longitude'],p['latitude']]},'radius':30})},ttl=86400)
    except UpstreamError:
        # The official spatial filter can fail independently of the inventory.
        # Retrieve the same official stations and enforce distance locally.
        data,meta=await fetch.get(endpoint,{'expanded':'true'},ttl=86400)
        fallback=True
    rows=[]
    for x in data:
        c=x.get('geometry',{}).get('coordinates',[])
        if len(c)<2:continue
        # UK-AIR returns lat/lon in some deployments despite GeoJSON convention.
        a,b=float(c[0]),float(c[1])
        if 49<=a<=61 and -9<=b<=2:lat,lon=a,b
        elif 49<=b<=61 and -9<=a<=2:lat,lon=b,a
        else:continue
        dist=haversine(p['latitude'],p['longitude'],lat,lon)
        if dist<=30:rows.append({'name':x.get('properties',{}).get('label') or x.get('label'), 'distance_km':round(dist,2), 'station_id':x.get('properties',{}).get('id') or x.get('id')})
    return section('air',summary='30 km 內官方空氣監測站／污染物項目',rows=sorted(rows,key=lambda r:r['distance_km'])[:10],notes=['監測站清單並非污染讀數，也不能當成 postcode 空氣質素評分。']+(['官方附近站點查詢暫不可用；已使用官方完整清單計算 30 km 內站點。'] if fallback else []),links=[link('查看最新官方讀數','https://uk-air.defra.gov.uk/latest/')], **meta)


async def affluence(p):
    rows=local_records('affluence',area=p.get('codes',{}).get('lsoa21'))
    if rows:return section('affluence',summary='已匯入官方社經資料',rows=rows,imported=import_info('affluence'),notes=['地區統計不能推論住戶個人收入。不同國家及年份的 deprivation ranks 不可直接比較。'])
    c=await census_table(p,'TS061')
    c['sources'].append(source('affluence'))
    c['summary']='社經背景：Census 2021 最高學歷分佈'
    c['notes']+=['此為教育背景指標，並非收入或富裕評分。收入／IMD 須另外匯入有年份及官方地理代碼的資料。']
    return c


async def tax(p):
    if p['country']=='Northern Ireland':return section('tax',status='coverage_gap',summary='Northern Ireland 使用 domestic rates，並非 Council Tax。',links=[link('NI domestic rates','https://www.nidirect.gov.uk/information-and-services/owning-home/rates')])
    rows=local_records('tax',area=p.get('codes',{}).get('admin_district'))
    parish=p.get('parish') or ''
    rows=[r for r in rows if (r.get('parish') or '')==parish]
    return section('tax',status='ok' if rows else 'official_lookup',summary=f'{p.get("admin_district")} / {parish} · Council Tax',rows=rows,imported=import_info('tax'),
                   notes=['Postcode 不足以決定個別物業 tax band。請用完整地址查 VOA / SAA；列出的年費未計折扣、豁免或空置附加費。'],
                   links=[link('查 property band','https://www.saa.gov.uk/' if p['country']=='Scotland' else 'https://www.gov.uk/council-tax-bands'),link('查地方政府','https://www.gov.uk/find-local-council')])


from .demography import estimates,ethnicity

from .ground import geology,radon

PROVIDERS={'geology':geology,'radon':radon,'crime':crime,'flood':flood,'planning':planning,'applications':applications,'prices':prices,
           'demographics':lambda p:estimates(p,age=True),'population':estimates,'ethnicity':ethnicity,'population_census':lambda p:census_table(p,'TS001'),
           'housing':lambda p:census_table(p,'TS054'),'affluence':affluence,'schools':schools,'transport':transport,
           'amenities':amenities,'green':green,'epc':epc,'broadband':broadband,'noise':noise,'air':air,'tax':tax}
SOURCE_KEYS={'crime':'police','demographics':'population_estimates','population':'population_estimates','ethnicity':'census','population_census':'census','housing':'census','applications':'planning','green':'osm'}


RADIUS_DEFAULTS={'crime':1.609344,'schools':10,'transport':5,'amenities':3.218688,'green':5}


async def safe_provider(name,p,radius_km=None):
    try:
        # One slow source cannot block the rest of a report indefinitely.
        query={**p,'_radius_km':radius_km} if radius_km is not None and name in RADIUS_DEFAULTS else p
        return await asyncio.wait_for(PROVIDERS[name](query),timeout=48)
    except Exception as e:
        key=SOURCE_KEYS.get(name,name)
        return unavailable(key, ('官方資料來源目前找不到查詢端點（HTTP 404）；不代表此地區沒有紀錄。' if e.status==404 else '官方資料來源暫時未能回應；請稍後再試。') if isinstance(e,UpstreamError) else '來源暫時未能回應，或回傳格式已改變；請稍後再試。')
