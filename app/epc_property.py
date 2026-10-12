"""Exact EPC linkage: no postcode-only or fuzzy property matching."""
import asyncio,hashlib,re
from .epc_session import TOKEN,get as private_get
from .core import fetch,local_records,UpstreamError
from .property_details import value

def key(address,postcode):
    # Preserve token boundaries, flat numbers and ranges to avoid false joins.
    address=re.sub(r'[\s,]+',' ',str(address).upper()).strip()
    return hashlib.sha256((address+'|'+re.sub(r'\s+','',postcode.upper())).encode()).hexdigest()

def sale_keys(row,pc):
    # Only add locality/town explicitly supplied by Land Registry. Never drop a
    # flat/unit or use fuzzy house-number matching.
    address=row['address']
    variants={address}
    locality=row.get('locality') or '';town=row.get('town') or ''
    for suffix in [locality,town,' '.join(x for x in [locality,town] if x)]:
        if suffix:variants.add(address+' '+suffix)
    return {key(v,pc) for v in variants}

def detail_priority(records):
    # A postcode with many historic certificates must not exhaust the detail
    # budget before the latest certificate for each property has been loaded.
    latest=[];history=[];seen=set()
    for r in sorted(records,key=lambda r:str(r.get('date') or ''),reverse=True):
        identity=r.get('uprn') or r.get('address_key') or r.get('certificate')
        (history if identity in seen else latest).append(r);seen.add(identity)
    return latest+history

def display_value(raw):
    # Some EPC schemas wrap translated display text in a value/language object.
    if isinstance(raw,dict):return display_value(raw.get('value'))
    return raw

def normalize(raw):
    r={re.sub('[^a-z0-9]','',k.lower()):v for k,v in raw.items()}
    def pick(*names):return next((display_value(r[n]) for n in names if r.get(n) not in (None,'')),None)
    address=pick('address') or ' '.join(str(pick('addressline'+str(i),'address'+str(i)) or '') for i in range(1,5)).strip()
    town=pick('posttown')
    if town and str(town).upper() not in address.upper():address=(address+' '+str(town)).strip()
    pc=str(pick('postcode') or '')
    return {'address':address or None,'postcode':pc or None,'certificate':pick('certificate','certificatenumber','lmkkey'),'uprn':str(pick('uprn') or ''),'band':pick('band','currentenergyrating','currentenergyefficiencyband'),'date':pick('date','lodgementdate','registrationdate'),'address_key':key(address,pc) if address and pc else None,'property_type':pick('dwellingtype','propertytype'),'built_form':pick('builtform'),'construction_age_band':pick('constructionageband','constructionage'),'potential_band':pick('potentialenergyrating','potentialenergyefficiencyband'),'floor_area_m2':value(pick('totalfloorarea','flooraream2')),'habitable_rooms':value(pick('numberhabitablerooms','numberofhabitablerooms','habitablerooms','habitableroomcount'),True)}

def measurements(document):
    # Modern certificate fields are at the root. Never confuse roof/extension
    # areas or age bands with those of the main dwelling.
    root=document.get('data',document)
    fields=normalize(root)
    parts=root.get('sap_building_parts',[])
    main=[p for p in parts if str(p.get('building_part_number'))=='1']
    if len(main)==1 and main[0].get('construction_age_band') is not None:
        fields['construction_age_band']=main[0]['construction_age_band']
    from .epc_fields import facts
    fields['detail_groups']=facts(root)
    fields['schema_type']=root.get('schema_type')
    return fields

async def decode_codes(records):
    async def code_table(code):
        try:
            data,_=await private_get('https://api.get-energy-performance-data.communities.gov.uk/api/codes/info',{'code':code})
            return code,data.get('data',[])
        except UpstreamError:return code,[]
    tables=dict(await asyncio.gather(*(code_table(c) for c in ['built_form','construction_age_band','property_type'])))
    for r in records:
        for code,entries in tables.items():
            raw=r.get(code)
            if raw is None:continue
            matches={v['value'] for e in entries if str(e.get('key'))==str(raw) for v in e.get('values',[]) if v.get('schemaVersion')==r.get('schema_type') and v.get('value')}
            if len(matches)==1:r[code]=next(iter(matches))
            elif str(raw).isdigit() or (code=='construction_age_band' and len(str(raw))<3):r[code]='官方代碼 '+str(raw)+'（未能解讀）'


def apply(rows,records,pc):
    for row in rows:
        matched=[r for r in records if r.get('address_key') in sale_keys(row,pc)]
        uprns={r.get('uprn') for r in matched if r.get('uprn')}
        ambiguous=len(uprns)>1
        if ambiguous:matched=[]
        matched=sorted(matched,key=lambda r:r.get('date') or '',reverse=True)
        row['epc_match_status']='多個 UPRN，未能確認物業' if ambiguous else 'EPC 地址未配對'
        row.update(epc_band=None,epc_date=None,habitable_rooms=None,epc_type=None,construction_age_band=None,epc_history=[])
        if matched:
            latest=matched[0]
            # Same-date conflicting certificates are ambiguous, not a latest winner.
            peers=[r for r in matched if r.get('date')==latest.get('date')]
            if len({(r.get('floor_area_m2'),r.get('band'),r.get('habitable_rooms')) for r in peers})>1:
                row['epc_match_status']='同日證書衝突，未能確認'
                continue
            row['epc_match_status']='已配對 EPC' if latest.get('floor_area_m2') is not None else '已配對地址，證書詳情未取得'
            row.update(epc_type=' / '.join(str(latest.get(k)) for k in ['property_type','built_form'] if latest.get(k)) or None,construction_age_band=latest.get('construction_age_band'),epc_band=latest.get('band'),epc_date=latest.get('date'),habitable_rooms=latest.get('habitable_rooms'))
            row['epc_history']=[{k:r.get(k) for k in ['certificate','date','band','floor_area_m2','habitable_rooms','property_type','built_form','construction_age_band','potential_band']} for r in matched]
            if latest.get('floor_area_m2') is not None:
                row['supplementary_details_source']=row.get('details_source')
                row['supplementary_details_date']=row.get('details_date')
                row['floor_area_m2']=latest['floor_area_m2']
                row['details_date']=latest.get('date');row['details_source']='MHCLG EPC · exact address match'
                row['details_note']='最新 EPC 面積，不一定代表成交當日；可居住房間數並非睡房數'
        area=row.get('floor_area_m2')
        row['floor_area_sqft']=round(area*10.7639104,1) if area else None
        row['price_per_m2']=round(row['price']/area) if area else None
    return rows

async def enrich_epc(rows,pc):
    records=local_records('epc',pc=pc)
    message='使用本地 EPC 匯入；資料版本見能源頁。' if records else '請按「EPC 授權」輸入本次 token，讀取面積、類型及建築年代。'
    if TOKEN.get():
        try:
            records,meta=await records_for_postcode(pc,set().union(*(sale_keys(r,pc) for r in rows)))
            message='官方 EPC：完整地址配對。'+meta.get('summary_detail','')
        except (UpstreamError,KeyError,ValueError,TypeError):message='EPC 授權或即時查詢失敗；僅使用本地 EPC（如有），不影響成交資料。'
    result=apply(rows,records,pc)
    if not records:
        for row in result:row['epc_match_status']='請輸入 EPC token' if not TOKEN.get() else 'EPC 查詢失敗或沒有證書'
    return result,message

async def records_for_postcode(pc,wanted=None):
    """Session-only live documents; local imports remain a marked fallback."""
    from .core import import_info
    if not TOKEN.get():return local_records('epc',pc=pc),{'cache':'local_dataset','imported':import_info('epc')}
    data,meta=await private_get('https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search',{'postcode':pc,'page_size':5000,'current_page':1})
    raw=data.get('data',[])
    if not isinstance(raw,list):raise UpstreamError('EPC 官方回應格式已變更')
    records=[normalize(r) for r in raw if str(r.get('postcode','')).replace(' ','').upper()==pc.replace(' ','').upper()]
    records.sort(key=lambda r:str(r.get('date') or ''),reverse=True)
    matches=detail_priority([r for r in records if wanted is None or r['address_key'] in wanted])
    sem=asyncio.Semaphore(4)
    async def detail(r):
        async with sem:
            doc,_=await private_get('https://api.get-energy-performance-data.communities.gov.uk/api/certificate',{'certificate_number':r['certificate']})
            fields=measurements(doc)
            r.update({k:v for k,v in fields.items() if v is not None and k not in ('certificate','uprn','address_key','date','band')})
    results=await asyncio.gather(*(detail(r) for r in matches[:40]),return_exceptions=True)
    await decode_codes(matches[:40])
    meta['truncated']=bool(data.get('pagination',{}).get('nextPage')) or len(matches)>40
    failures=sum(isinstance(x,Exception) for x in results)
    meta['status']='partial' if failures or meta['truncated'] else 'ok'
    meta['summary_detail']=f'已讀取 {min(40,len(matches))-failures} 份詳情；{failures} 份失敗。'+('只顯示部分詳情。' if meta['truncated'] else '')
    return records,meta

async def certificate_details(number):
    document,meta=await private_get('https://api.get-energy-performance-data.communities.gov.uk/api/certificate',{'certificate_number':number})
    row=measurements(document)
    await decode_codes([row])
    return {k:v for k,v in row.items() if k not in ('address_key','uprn','certificate','schema_type','date','band')},meta
