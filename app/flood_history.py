"""Recorded flooding, not a count of warnings or flooded properties."""
import math
from datetime import date
from pyproj import Transformer
from shapely.geometry import shape,Point,mapping
from shapely.ops import transform
from .core import fetch,UpstreamError
URL='https://environment.data.gov.uk/spatialdata/recorded-flood-outlines/ogc/features/v1/collections/Recorded_Flood_Outlines/items'
SOURCE='https://www.data.gov.uk/dataset/16e32c53-35a6-4d54-a111-ca09031eaaaf/recorded-flood-outlines'
WARNINGS='https://environment.data.gov.uk/dataset/88bed270-d465-11e4-8669-f0def148f590'

def cutoff_date(years,today=None):
    today=today or date.today()
    if not years:return None
    try:return today.replace(year=today.year-years)
    except ValueError:return today.replace(year=today.year-years,day=28)

def select_features(features,lat,lon,radius,years,today=None):
    today=today or date.today();cutoff=cutoff_date(years,today)
    project=Transformer.from_crs('EPSG:4326','EPSG:27700',always_xy=True).transform
    point=transform(project,Point(lon,lat));rows=[];geometries=[];undated=0
    for f in features:
        g=shape(f['geometry']);projected=transform(project,g);distance=projected.distance(point)/1000
        if distance>radius:continue
        p=f['properties'];start=(p.get('start_date') or '')[:10];end=(p.get('end_date') or start)[:10]
        if not start or start.startswith('0001'):
            undated+=1
            if years:continue
        elif cutoff and (end<cutoff.isoformat() or start>today.isoformat()):continue
        row={'id':str(p.get('rec_out_id',f.get('id'))),'event_group':p.get('rec_grp_id'),'name':p.get('name'),'start_date':start or '未提供','end_date':end or '未提供','flood_source':p.get('flood_src'),'cause':p.get('flood_caus'),'quality':p.get('data_qual') or '未提供','point_within':bool(g.covers(Point(lon,lat))),'distance_km':round(distance,3)}
        rows.append(row)
        geometries.append({'type':'Feature','geometry':mapping(g.simplify(.00003,preserve_topology=True)),'properties':row})
    order=sorted(range(len(rows)),key=lambda i:rows[i]['start_date'],reverse=True)
    return [rows[i] for i in order],{'type':'FeatureCollection','features':[geometries[i] for i in order]},undated

async def history(p,years=1,radius=5):
    from .providers import section,metric,link
    if p['country']!='England':return section('flood',status='coverage_gap',summary='歷史水浸圖層目前涵蓋 England。',links=[link('官方長期風險查詢','https://www.gov.uk/check-long-term-flood-risk')])
    lat,lon=p['latitude'],p['longitude'];dy=radius/110.5;dx=radius/(111.32*math.cos(math.radians(lat)))
    params={'bbox':f'{lon-dx},{lat-dy},{lon+dx},{lat+dy}','limit':500};features=[];truncated=False;meta={}
    # All dates fetched so changing period uses the same coherent spatial response.
    for page in range(10):
        data,meta=await fetch.get(URL,{**params,'startIndex':page*500},ttl=86400)
        batch=data.get('features',[]);features.extend(batch)
        has_next=any(x.get('rel')=='next' for x in data.get('links',[]))
        if not has_next:break
        if not batch:raise UpstreamError('Incomplete flood pagination')
    else:truncated=True
    rows,geojson,undated=select_features(features,lat,lon,radius,years)
    all_local,_,_=select_features(features,lat,lon,radius,0)
    latest=max((r['end_date'] for r in all_local if r['end_date']!='未提供'),default='未提供')
    period=f'過去 {years} 年' if years else '全部可取得年份'
    return section('flood',status='partial' if truncated or meta.get('cache')=='stale' else 'ok',summary=f'{period} · {radius:g} km 內已記錄水浸範圍',rows=rows,
      metrics=[metric('水浸範圍紀錄（非事件數）',len(rows)),metric('覆蓋郵區中心的範圍紀錄',sum(r['point_within'] for r in rows))],
      notes=[f'此範圍官方紀錄中最新事件結束日期：{latest}；不是表示此後一定沒有水浸。','這是 EA 已記錄水浸範圍，不是現行警報、警報次數或物業內部受浸證明；同一事件可有多個範圍紀錄。','官方通常按季發布，收集及核實可能延遲數月。最近一年沒有紀錄，不代表從未水浸或沒有風險。','距離量度至水浸範圍邊界；位置為郵區中心，不是物業地址。',f'附近缺日期紀錄 {undated} 筆；指定年份時不納入。']+(['資料過多，只取得前 5,000 個範圍，數量不完整。'] if truncated else []),
      links=[link('EA Recorded Flood Outlines',SOURCE),link('歷史警報目錄（目前未接駁下載）',WARNINGS),link('物業長期水浸風險','https://www.gov.uk/check-long-term-flood-risk'),link('現行警報另查','https://check-for-flooding.service.gov.uk/')],
      years=years,radius_km=radius,period_start=cutoff_date(years).isoformat() if years else None,period_end=date.today().isoformat(),geojson=geojson,truncated=truncated,**meta)
