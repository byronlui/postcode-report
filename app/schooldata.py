"""School profiles from GIAS, Ofsted and the public DfE EES API."""
import asyncio,json
from .core import connect,fetch,local_records,import_info,UpstreamError
DATASETS={
 'ks2':('019afee4-e5d0-72f9-9a8f-d7a1a56eac1d',['expected_standard_pupil_percent','higher_standard_pupil_percent','average_scaled_score'],{'breakdown':'Total','breakdown_topic':'All pupils'}),
 'ks4':('19e39901-a96c-be76-b9c2-6af54ae076d2',['attainment8_average','progress8_average','ebacc_aps_average'],{'disadvantage_status':'Total','first_language':'Total','mobility':'Total','prior_attainment':'Total','sex':'Total'}),
 'ks5':('019c2960-81e3-70c2-8d65-72c3718ae4fd',['aps_per_entry','aps_per_entry_grade','best_three_alevels_aps','aab_percent','aps_per_entry_student_count'],{'disadvantage_status':'Total','exam_cohort':'A level'})}

def school(urn):
    with connect() as db:r=db.execute("SELECT * FROM points WHERE kind='schools' AND id=?",(urn,)).fetchone()
    if not r:return None
    return {**json.loads(r['meta']),'urn':urn,'name':r['name'],'lat':r['lat'],'lon':r['lon']}

def normalise_results(data,meta,required,columns):
    filters={f['column']:f for f in meta['filters']};expected={}
    for column,label in required.items():
        f=filters.get(column)
        if not f:raise ValueError('DfE filter schema changed')
        option=next((o for o in f['options'] if o['label']==label),None)
        if not option:raise ValueError('DfE cohort missing')
        expected[f['id']]=option['id']
    indicators={x['id']:x for x in meta['indicators'] if x['column'] in columns}
    subjects=next((f for f in meta['filters'] if f['column']=='subject'),None)
    rows=[]
    for r in data['results']:
        if any(r['filters'].get(k)!=v for k,v in expected.items()):continue
        subject=next((o['label'] for o in subjects['options'] if o['id']==r['filters'].get(subjects['id'])),'') if subjects else ''
        for id,indicator in indicators.items():
            value=r['values'].get(id)
            if value is None:continue
            # Preserve suppressed/not-applicable codes; never coerce to zero.
            rows.append({'year':r['timePeriod']['period'],'subject':subject,'indicator':indicator['label'],'column':indicator['column'],'value':value,'unit':indicator.get('unit','')})
    return sorted(rows,key=lambda r:(r['year'],r['subject'],r['indicator']),reverse=True)

async def performance(urn,stage):
    id,columns,required=DATASETS[stage];url='https://api.education.gov.uk/statistics/v1/data-sets/'+id
    try:
        summary,sm=await fetch.get(url,ttl=604800)
        version=summary['latestVersion']['version']
        meta,mm=await fetch.get(url+'/meta',{'dataSetVersion':version,'types':['Filters','Indicators']},ttl=604800)
        indicators=[x['id'] for x in meta['indicators'] if x['column'] in columns]
        if not indicators:raise ValueError('No matching indicators')
        params={'dataSetVersion':version,'locations.eq':'SCH|urn|'+urn,'pageSize':1000,'indicators':indicators}
        data,dm=await fetch.get(url+'/query',params,ttl=604800)
        if data.get('paging',{}).get('totalPages',1)>1:raise ValueError('School query exceeds page limit')
        rows=normalise_results(data,meta,required,columns)
        return {'stage':stage,'status':'ok' if rows else 'no_data','rows':rows,'dataset_id':id,'version':summary['latestVersion']['version'],'url':url,'provenance':dm,'metadata_provenance':mm,'summary_provenance':sm,
                'notes':['All-pupil / total cohort only; A-level cohort for KS5.','Suppression and non-applicability codes remain as published (for example c, z, x).','Compare like-for-like years and phases. Progress 8 is not available for every year; no value is imputed.']}
    except (UpstreamError,ValueError,KeyError,TypeError):
        return {'stage':stage,'status':'unavailable','rows':[],'url':url,'notes':['DfE source unavailable or schema changed; no substitute performance figure.']}

async def profile(urn):
    s=school(urn)
    if not s:return None
    phase=s.get('phase','');high=int(s.get('age_high') or 0)
    stages=[]
    if phase in ('Primary','All-through') or (int(s.get('age_low') or 99)<=10 and high>=11):stages.append('ks2')
    if phase in ('Secondary','All-through'):stages.append('ks4')
    if high>=16:stages.append('ks5')
    async def bounded(stage):
        try:return await asyncio.wait_for(performance(urn,stage),timeout=45)
        except asyncio.TimeoutError:return {'stage':stage,'status':'unavailable','rows':[],'notes':['DfE request timed out.']}
    s['performance']=await asyncio.gather(*(bounded(stage) for stage in stages))
    inspection=local_records('ofsted',area=urn)
    s['ofsted']=inspection[0] if inspection else None
    s['sources']={'gias':import_info('schools'),'ofsted':import_info('ofsted')}
    website=s.get('website') or ''
    if website and not website.startswith(('https://','http://')):s['website']='https://'+website
    s['links']={'gias':f'https://www.get-information-schools.service.gov.uk/Establishments/Establishment/Details/{urn}',
                'ofsted':f'https://reports.ofsted.gov.uk/provider/23/{urn}',
                'performance':f'https://www.compare-school-performance.service.gov.uk/school/{urn}',
                'admissions':{'136449':'https://www.reading-school.co.uk/admissions','136891':'https://www.piggottschool.org/admissions'}.get(urn,s.get('website') or 'https://www.gov.uk/schools-admissions')}
    s['links']['parentview']='https://parentview.ofsted.gov.uk/'
    s['links']['financials']='https://financial-benchmarking-and-insights-tool.education.gov.uk/'
    s['links']['council_admissions']='https://www.wokingham.gov.uk/schools-and-education/school-admissions' if s.get('local_authority')=='Wokingham' else 'https://www.gov.uk/schools-admissions'
    return s
