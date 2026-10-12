#!/usr/bin/env python3
"""Download public national datasets and populate the local database.
No login, paywall, API key or commercial data source is used.
"""
import argparse,hashlib,html,re,sys,time,zipfile,shutil
from datetime import date
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import DATA
from scripts.import_data import import_file
from scripts.import_greenspace import convert


def download(client,url,path,md5=None):
    tmp=path.with_suffix(path.suffix+'.part')
    with client.stream('GET',url) as r:
        r.raise_for_status()
        with tmp.open('wb') as f:
            for chunk in r.iter_bytes():f.write(chunk)
    if md5 and hashlib.md5(tmp.read_bytes()).hexdigest()!=md5:raise ValueError('Download checksum mismatch')
    tmp.replace(path)


def hidden_fields(form):
    from html.parser import HTMLParser
    class Inputs(HTMLParser):
        def __init__(self):super().__init__();self.values={}
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if tag=='input' and a.get('type')=='hidden' and a.get('name'):self.values[a['name']]=a.get('value','')
    parser=Inputs();parser.feed(form);return parser.values


def gias(client):
    # Socket resets can escape httpx as native OSError on macOS. Retry those
    # transient network failures without treating disk/schema errors as transient.
    import time
    for attempt in range(3):
        try:return _gias_once(client)
        except (httpx.TransportError,OSError) as error:
            transient=isinstance(error,httpx.TransportError) or getattr(error,'errno',None) in {32,54,60,104,110}
            if not transient or attempt==2:raise
            time.sleep(attempt+1)

def _gias_once(client):
    """DfE daily public CSV; avoid the unreliable generated File.xhtml ZIP redirect."""
    import csv,json
    from datetime import timedelta
    path=DATA/'gias-current.csv';manifest=DATA/'gias-current.json'
    try:old=json.loads(manifest.read_text())
    except (OSError,ValueError):old={}
    # Daily files may not have been published yet just after midnight.
    for offset in range(3):
        day=date.today()-timedelta(days=offset)
        url='https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/edubasealldata'+day.strftime('%Y%m%d')+'.csv'
        headers={}
        if old.get('url')==url and path.exists():
            if old.get('etag'):headers['If-None-Match']=old['etag']
            if old.get('last_modified'):headers['If-Modified-Since']=old['last_modified']
        with client.stream('GET',url,headers=headers) as r:
            if r.status_code==404:continue
            if r.status_code==304:
                if old.get('sha256')==hashlib.sha256(path.read_bytes()).hexdigest():return path
                raise ValueError('Local GIAS checksum changed; remove the manifest and retry')
            r.raise_for_status();temp=path.with_suffix('.part');size=0
            with temp.open('wb') as f:
                for chunk in r.iter_bytes():
                    size+=len(chunk)
                    if size>200*1024*1024:raise ValueError('GIAS download exceeds 200 MB')
                    f.write(chunk)
            with temp.open(encoding='cp1252',newline='') as f:
                reader=csv.DictReader(f)
                if not {'URN','EstablishmentName','Easting','Northing','EstablishmentStatus (name)'}<=set(reader.fieldnames or []):raise ValueError('GIAS CSV schema not recognised; existing download retained')
                if not next(reader,None):raise ValueError('Empty GIAS download')
            info={'url':url,'vintage':day.isoformat(),'etag':r.headers.get('etag'),'last_modified':r.headers.get('last-modified'),'sha256':hashlib.sha256(temp.read_bytes()).hexdigest()}
            temp.replace(path);manifest.write_text(json.dumps(info));return path
    raise RuntimeError('No daily GIAS CSV published in the last three days; retained previous index')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--only',choices=['transport','schools','greenspace']);p.add_argument('--reuse',action='store_true',help='Reuse already downloaded files; caller is responsible for vintage');a=p.parse_args()
    today=date.today().isoformat()
    with httpx.Client(timeout=120,follow_redirects=True,headers={'User-Agent':'OpenNeighbourhood/1.0 public dataset downloader'}) as c:
        if not a.only or a.only=='transport':
            path=DATA/'naptan.csv'
            if not(a.reuse and path.exists()):download(c,'https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv',path)
            n=import_file('transport',path,'https://naptan.api.dft.gov.uk/v1/access-nodes',today+' download (check file modified fields)','OGL v3.0')
            print('NaPTAN:',n,flush=True)
        if not a.only or a.only=='schools':
            path=DATA/'gias-current.csv'
            if not path.exists():path=DATA/'gias.zip'
            if not(a.reuse and path.exists()):path=gias(c)
            n=import_file('schools',path,'https://www.get-information-schools.service.gov.uk/Downloads',__import__('json').loads((DATA/'gias-current.json').read_text())['vintage'] if path.name=='gias-current.csv' else 'reused legacy download; verify vintage','OGL v3.0')
            print('GIAS:',n,flush=True)
        if not a.only or a.only=='greenspace':
            base='https://api.os.uk/downloads/v1/products/OpenGreenspace'
            r=c.get(base);r.raise_for_status();product=r.json()
            r=c.get(product['downloadsUrl']);r.raise_for_status()
            item=next(x for x in r.json() if x['format']=='GeoPackage' and x['area']=='GB')
            path=DATA/'greenspace.zip'
            if not(a.reuse and path.exists()):download(c,item['url'],path,item.get('md5'))
            # Exact internal file copied without extracting arbitrary paths.
            with zipfile.ZipFile(path) as z:
                member=next(n for n in z.namelist() if n.endswith('.gpkg'))
                gpkg=DATA/'greenspace.gpkg'
                with z.open(member) as src,gpkg.open('wb') as dst:shutil.copyfileobj(src,dst)
            output=DATA/'greenspace.csv';convert(gpkg,output)
            n=import_file('greenspace',output,base,product['version'],'OGL v3.0; contains OS data © Crown copyright and database right '+str(date.today().year))
            print('OS Open Greenspace access points:',n,flush=True)

if __name__=='__main__':main()
