"""On-use source discovery, conditional downloads and transactional imports.
One worker per data directory; never overwrite a valid index with a failed import.
"""
import asyncio,hashlib,html,json,re,time,zipfile,shutil,fcntl
from pathlib import Path
from urllib.parse import urljoin,urlparse
import httpx
from .core import DATA,connect,now,fetch,import_info
STATE=DATA/'update-state.json'
TASK=None
LABELS={'schools':'GIAS 學校','transport':'NaPTAN 交通','greenspace':'OS 綠地','ofsted':'Ofsted 檢查','school_offers':'DfE 收生','school_workforce':'DfE 師資','broadband':'Ofcom 寬頻','mobile':'Ofcom 手機覆蓋'}

def read_state():
    try:return json.loads(STATE.read_text())
    except (OSError,ValueError):return {'sources':{},'running':False}

def save(state):
    temp=STATE.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False));temp.replace(STATE)

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def page(client,url):
    r=client.get(url);r.raise_for_status();return r

def next_data(response):
    m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',response.text,re.S)
    if not m:raise ValueError('官方頁面格式改變，未能確認最新版本')
    return json.loads(m.group(1))['props']['pageProps']

def links(response):
    return [urljoin(str(response.url),html.unescape(x)) for x in re.findall(r'href=["\']([^"\']+)',response.text)]

def allowed(url):
    h=urlparse(url).hostname or ''
    return urlparse(url).scheme=='https' and any(h==x or h.endswith('.'+x) for x in ['gov.uk','education.gov.uk','ofcom.org.uk','os.uk'])

def download(client,url,target,old):
    if not allowed(url):raise ValueError('Download is outside official source domains')
    headers={'Accept':'text/csv'} if urlparse(url).path.lower().endswith('.csv') else {}
    if old.get('status')!='failed' and old.get('download_url')==url and target.exists() and old.get('sha256')==sha(target):
        if old.get('etag'):headers['If-None-Match']=old['etag']
        if old.get('last_modified'):headers['If-Modified-Since']=old['last_modified']
    temp=target.with_suffix(target.suffix+'.part')
    with client.stream('GET',url,headers=headers) as r:
        if r.status_code==304:return target,{k:old[k] for k in ['download_url','etag','last_modified','sha256'] if k in old},False
        r.raise_for_status();size=0
        with temp.open('wb') as f:
            for chunk in r.iter_bytes():
                size+=len(chunk)
                if size>600*1024*1024:raise ValueError('下載超過 600 MB 上限，保留原資料')
                f.write(chunk)
        digest=sha(temp);changed=digest!=old.get('sha256')
        info={'download_url':url,'etag':r.headers.get('etag'),'last_modified':r.headers.get('last-modified'),'sha256':digest}
    temp.replace(target)
    return target,info,changed

def ees(client,slug,kind):
    landing=page(client,'https://explore-education-statistics.service.gov.uk/find-statistics/'+slug)
    summary=next_data(landing);latest=summary['publicationSummary']['latestRelease']['slug']
    r=page(client,'https://explore-education-statistics.service.gov.uk/find-statistics/'+slug+'/'+latest+'/explore');d=next_data(r)
    release=d['releaseVersionSummary'];files=d['dataContent']['supportingFiles']
    if kind=='school_offers':matches=[x for x in files if x['extension']=='csv' and 'school level' in x['title'].lower()]
    else:matches=[x for x in files if x['extension']=='xlsx' and x['title'].lower()=='school level summary']
    if len(matches)!=1:raise ValueError('未能唯一辨認官方逐校資料檔')
    f=matches[0]
    return {'source':str(r.url),'vintage':release['yearTitle']+' · '+(release.get('lastUpdated') or release['published'])[:10],'version':release['id']+':'+f['fileId'],'url':f"https://content.explore-education-statistics.service.gov.uk/api/releases/{release['id']}/files/{f['fileId']}",'suffix':'.'+f['extension'],'year':release['yearTitle']}

def ofsted(client):
    from scripts.import_ofsted import SOURCE
    r=page(client,SOURCE);candidates=[u for u in links(r) if urlparse(u).hostname=='assets.publishing.service.gov.uk' and 'latest_inspections' in u.lower() and urlparse(u).path.lower().endswith('.csv') and 'state-funded' in u.lower()]
    def stamp(u):
        from datetime import datetime
        m=re.search(r'(\d{1,2})_([A-Za-z]+)_(20\d{2})',u)
        if not m:return datetime.min
        for fmt in ['%d %B %Y','%d %b %Y']:
            try:return datetime.strptime(' '.join(m.groups()),fmt)
            except ValueError:pass
        return datetime.min
    if not candidates:raise ValueError('官方最新 Ofsted CSV 未找到')
    u=max(set(candidates),key=stamp)
    # GOV.UK may serve a preview for the bare asset URL.
    u=u.split('?')[0]+'?download=1'
    if stamp(u).year<2000:raise ValueError('Ofsted 日期未能確認')
    return {'source':SOURCE,'url':u,'version':u,'vintage':stamp(u).date().isoformat(),'suffix':'.csv'}

def ofcom(client,kind):
    index=page(client,'https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/infrastructure-research')
    candidates=list(dict.fromkeys(u for u in links(index) if '/coverage-and-speeds/connected-nations' in u and not any(x in u for x in ['planned','deployment']) and re.search(r'20\d{2}',u)))
    def rank(u):
        y=max(map(int,re.findall(r'20\d{2}',u)));month=1 if 'spring' in u else 6 if 'summer' in u else 9
        return y,month
    if not candidates:raise ValueError('Ofcom 最新報告目錄未找到')
    source=max(candidates,key=rank);r=page(client,source)
    candidates=[u for u in links(r) if '.zip' in u.lower() and ('fixed' in u.lower() and 'broadband' in u.lower() if kind=='broadband' else 'mobile' in u.lower() and 'coverage' in u.lower())]
    if len(set(candidates))!=1:raise ValueError('Ofcom 下載版本有多個或未找到，需檢查格式')
    u=candidates[0];m=re.search(r'(20\d{4})',u)
    return {'source':source,'url':u,'version':u,'vintage':m.group(1) if m else source.rsplit('/',1)[-1],'suffix':'.zip'}

def update_one(client,kind,old,progress):
    from scripts.import_data import import_file
    from scripts.bootstrap_data import gias
    from scripts.import_school_context import import_offers,import_workforce
    from scripts.import_ofsted import import_ofsted
    from scripts.import_ofcom import import_fixed,import_mobile
    info={};spec=None;count=None
    if kind=='schools':
        progress('正在檢查 GIAS 公開匯出')
        
        path=gias(client)
        digest=sha(path);info={'sha256':digest,'source':'https://www.get-information-schools.service.gov.uk/Downloads','vintage':json.loads((DATA/'gias-current.json').read_text())['vintage']}
        changed=digest!=old.get('sha256') or not import_info(kind)
        if changed:count=import_file('schools',path,info['source'],info['vintage'],'OGL v3.0')
    else:
        if kind=='transport':spec={'source':'https://naptan.api.dft.gov.uk/v1/access-nodes','url':'https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv','vintage':now()[:10]+' download; per-row modification dates','suffix':'.csv'}
        elif kind=='greenspace':
            base='https://api.os.uk/downloads/v1/products/OpenGreenspace';p=page(client,base).json();items=page(client,p['downloadsUrl']).json();item=next(x for x in items if x['format']=='GeoPackage' and x['area']=='GB')
            spec={'source':base,'url':item['url'],'version':p['version']+':'+str(item.get('md5')),'vintage':p['version'],'suffix':'.zip','md5':item.get('md5')}
        elif kind=='ofsted':spec=ofsted(client)
        elif kind=='school_offers':spec=ees(client,'primary-and-secondary-school-applications-and-offers',kind)
        elif kind=='school_workforce':spec=ees(client,'school-workforce-in-england',kind)
        elif kind in ['broadband','mobile']:spec=ofcom(client,kind)
        info={**spec};target=DATA/('auto-'+kind+spec['suffix'])
        # Immutable version/file IDs and OS checksums avoid unnecessary transfers.
        if kind in ['greenspace','school_offers','school_workforce'] and old.get('version')==spec.get('version') and import_info(kind):return {**old,**info,'status':'current','message':'官方版本未變','checked_at':now()}
        progress('已確認來源，正在檢查／下載檔案')
        path,headers,changed=download(client,spec['url'],target,old);info.update(headers)
        changed=changed or not import_info(kind)
        if changed:
            progress('正在驗證並匯入新版本；原資料仍可查閱')
            if kind=='greenspace':
                if spec.get('md5') and hashlib.md5(path.read_bytes()).hexdigest()!=spec['md5']:raise ValueError('OS checksum mismatch')
                from scripts.import_greenspace import convert
                with zipfile.ZipFile(path) as z:
                    member=next(n for n in z.namelist() if n.endswith('.gpkg'));gpkg=DATA/'auto-greenspace.gpkg'
                    with z.open(member) as src,gpkg.open('wb') as dst:shutil.copyfileobj(src,dst)
                output=DATA/'auto-greenspace.csv';convert(gpkg,output);count=import_file(kind,output,spec['source'],spec['vintage'],'OGL v3.0; contains OS data © Crown copyright and database right')
            elif kind=='transport':count=import_file(kind,path,spec['source'],spec['vintage'],'OGL v3.0')
            elif kind=='ofsted':count=import_ofsted(path)
            elif kind=='school_offers':count=import_offers(path)
            elif kind=='school_workforce':count=import_workforce(path,year=spec['year'])
            elif kind=='broadband':count=import_fixed(path)
            elif kind=='mobile':count=import_mobile(path)
            with connect() as db:db.execute('UPDATE imports SET source=?,vintage=? WHERE kind=?',(spec['source'],spec['vintage'],kind))
    return {**old,**info,'status':'updated' if changed else 'current','message':f'已更新 {count:,} 筆' if changed else '官方檔案內容未變','checked_at':now(),'imported':import_info(kind)}

def run():
    with (DATA/'update.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        state=read_state();state.update(running=True,started_at=now(),finished_at=None)
        for kind,label in LABELS.items():state['sources'][kind]={**state['sources'].get(kind,{}),'name':label,'status':'queued','message':'等待本次版本檢查'}
        save(state)
        with httpx.Client(timeout=120,follow_redirects=True,headers={'User-Agent':'OpenNeighbourhood/1.0 public data version checker'}) as client:
            for kind in LABELS:
                old=state['sources'].get(kind,{})
                def progress(message):
                    state['sources'][kind]={**old,'name':LABELS[kind],'status':'checking','message':message};save(state)
                progress('正在檢查官方最新發布')
                try:result=update_one(client,kind,old,progress)
                except Exception as e:
                    # Never report failed discovery as "latest". Preserve last successful index.
                    result={**old,'status':'failed','checked_at':now(),'message':'未能確認／匯入最新版本，保留已匯入資料。'+str(e)[:160],'imported':import_info(kind)}
                state['sources'][kind]={**result,'name':LABELS[kind]};save(state)
        with connect() as db:
            for r in db.execute('SELECT * FROM imports'):
                if r['kind'] not in LABELS:state['sources'][r['kind']]={'name':r['kind'],'status':'manual','message':'此本地匯入未有自動更新接駁；不能保證最新。','imported':dict(r)}
        state.update(running=False,finished_at=now());save(state)

async def start():
    global TASK
    # Each use invalidates previous-use API freshness, but shares overlapping bulk jobs.
    fetch.revalidate_since=time.time()
    if TASK is None or TASK.done():TASK=asyncio.create_task(asyncio.to_thread(run))
    return status()

def status():
    s=read_state()
    s['running']=TASK is not None and not TASK.done()
    s['api_policy']='每次開啟／搜尋報告，API 於本次首次查詢重新取得資料；同次使用按來源更新頻率快取。資料年份以官方發布為準。'
    s['limitations']='未接駁資料、需要登入的 EPC、地方 council tax 及未有全國接口的項目不會被標成最新。'
    return s
