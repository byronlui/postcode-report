"""Official school context: no proprietary ratings, predictions or private pupil data."""
import asyncio
from .core import fetch,local_records,import_info,UpstreamError
from .schooldata import school,normalise_results,DATASETS
EES='https://api.education.gov.uk/statistics/v1/data-sets/'
PUPILS='019e7403-4523-7749-b530-159f451dd83c'
KS2_LA='019afee5-4791-7467-a788-c163fd9b57de'
DESTINATIONS='019d4f41-22d1-71b2-a1a7-f3b91026815b'
async def dataset(id,location,level='SCH'):
    url=EES+id;summary,_=await fetch.get(url,ttl=604800);version=summary['latestVersion']['version']
    meta,_=await fetch.get(url+'/meta',{'dataSetVersion':version,'types':['Filters','Indicators']},ttl=604800)
    params={'dataSetVersion':version,'locations.eq':location,'geographicLevels.eq':level,'pageSize':1000}
    data,provenance=await fetch.get(url+'/query',params,ttl=604800)
    if data.get('paging',{}).get('totalPages',1)>1:raise ValueError('Query incomplete; no partial statistics shown')
    return data,meta,{'url':url,'version':version,'license':'DfE / Crown copyright / OGL v3.0',**provenance}
def decoded_rows(data,meta):
    filters={f['id']:(f['column'],{o['id']:o['label'] for o in f['options']}) for f in meta['filters']}
    indicators={i['id']:i['column'] for i in meta['indicators']}
    for r in data['results']:
        yield {'year':r['timePeriod']['period'],**{filters[k][0]:filters[k][1].get(v,v) for k,v in r['filters'].items() if k in filters},**{indicators[k]:v for k,v in r['values'].items() if k in indicators}}
async def pupils(urn):
    data,meta,source=await dataset(PUPILS,'SCH|urn|'+urn)
    wanted={'Total','FSM eligible','All pupils - performance table metric','FSM eligible - performance table metric','First language English','First language other than English','First language unclassified','Reception (year r)','Key stage 1 (years 1 and 2)','Key stage 2 (years 3 to 6)','Key stage 3 (years 7 to 9)','Key stage 4 (years 10 and 11)','Key stage 5 (years 12 to 14)'}
    rows=[{'year':r['year'],'category':r['breakdown'],'count':r.get('pupil_count'),'percent':r.get('pupil_percent')} for r in decoded_rows(data,meta) if r.get('sex')=='Total' and r.get('attendance_pattern')=='Total' and r.get('breakdown') in wanted]
    return {'status':'ok' if rows else 'no_data','rows':rows,'source':source,'notes':['全校總體統計；各分類會重疊，不能全部相加。c / z / x 等按官方保留，並非 0。']}
async def benchmarks(urn):
    s=school(urn)
    if s.get('phase') not in ['Primary','All-through']:return {'status':'not_applicable','rows':[],'notes':['此比較接駁目前限 KS2；其他階段保留學校歷年成績。']}
    async def get(loc,level,label):
        data,meta,source=await dataset(KS2_LA,loc,level)
        rows=normalise_results(data,meta,{'breakdown':'Total','breakdown_topic':'All pupils','establishment_type_group':'All state funded'},DATASETS['ks2'][1])
        return {'scope':label,'rows':rows,'source':source}
    queries=[get('NAT|code|E92000001','NAT','England')]
    if s.get('la_gss'):queries.append(get('LA|code|'+s['la_gss'],'LA',s.get('local_authority','Local authority')))
    result=await asyncio.gather(*queries,return_exceptions=True);scopes=[r for r in result if isinstance(r,dict)]
    return {'status':'ok' if len(scopes)==len(queries) else 'partial','scopes':scopes,'notes':['僅對照相同學年、科目、指標。區域組別為所有 state-funded schools；不是排名或入學預測。']}
async def destinations(urn):
    s=school(urn)
    if s.get('phase') not in ['Secondary','All-through']:return {'status':'not_available','rows':[],'notes':['未接駁小學逐校 feeder / destination 學校名單；附近學校不可當作實際升學去向。']}
    data,meta,source=await dataset(DESTINATIONS,'SCH|urn|'+urn)
    rows=[]
    for r in decoded_rows(data,meta):
        if any(r.get(k)!='Total' for k in ['sex','breakdown','breakdown_topic','disadvantage_status','ethnicity_major','ethnicity_minor']):continue
        rows.append({'year':r['year'],'category':r['destination_description'],'count':r.get('pupil_count'),'percent':r.get('pupil_percent')})
    return {'status':'ok' if rows else 'no_data','rows':rows,'source':source,'notes':['KS4 後持續教育／就業等類別，並非逐間目的學校名單；資料學年滯後。']}
def offers(urn):
    rows=sorted(local_records('school_offers',area=urn),key=lambda r:(r['year'],r['phase']),reverse=True)
    return {'status':'ok' if rows else 'no_data','rows':rows,'source':import_info('school_offers'),'notes':['National Offer Day 按時申請及取錄資料；不是最終入學人數、學額空缺或成功機率。','同一名申請人可列多個志願。申請總數除以取錄數不能當作超額收生率。','只使用相同 URN；沒有將前身學校或不同入學年級混合。']}
def workforce(urn):
    records=local_records('school_workforce',area=urn)
    return {'status':'ok' if records else 'no_data','rows':records[0]['rows'] if records else [],'source':import_info('school_workforce'),'notes':['Headcount 是人數，FTE 是全職等值，不能混用。缺漏／隱藏符號並非零。','病假欄位是教師病假，不是學生缺席率。']}
async def context(urn,section):
    try:
        if section=='admissions':return offers(urn)
        if section=='workforce':return workforce(urn)
        return await asyncio.wait_for({'pupils':pupils,'benchmarks':benchmarks,'destinations':destinations}[section](urn),timeout=45)
    except (UpstreamError,ValueError,KeyError,TypeError,asyncio.TimeoutError):
        return {'status':'unavailable','rows':[],'notes':['官方來源暫不可用或資料格式改變；沒有以估計數字代替。']}
