"""Create portable source and public-data bundles, excluding credentials/runtime files."""
from pathlib import Path
import hashlib,json,sqlite3,zipfile,tempfile,shutil
ROOT=Path(__file__).resolve().parents[1]
DATA_FILES=['geosure.gpkg','geosure-meta.json','gias-current.csv','gias-current.json','auto-transport.csv','auto-greenspace.csv','auto-greenspace.gpkg','auto-greenspace.zip','auto-ofsted.csv','auto-school_offers.csv','auto-school_workforce.xlsx','auto-broadband.zip','auto-mobile.zip','charvil-tax.csv','update-state.json']

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def source_files():
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(ROOT)
        if any(p in {'.venv','__pycache__','.pytest_cache','.git','delivery'} for p in rel.parts):continue
        if path.name in {'.DS_Store','.env'} or (path.name.startswith('.env.') and path.name!='.env.example'):continue
        if rel.parts[0]=='data' and path.name not in {'README.md','.gitkeep'}:continue
        yield str(rel),path

def bundle(name,files):
    target=ROOT/'delivery'/name;temp=target.with_suffix('.tmp')
    manifest=[]
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=2) as z:
        for rel,path in files:
            z.write(path,'postcode-report/'+rel)
            manifest.append({'path':rel,'bytes':path.stat().st_size,'sha256':digest(path)})
        z.writestr('postcode-report/FILE-MANIFEST.json',json.dumps({'version':'2026-10-11','files':manifest,'notes':'No credentials or virtualenv. Public data are dated snapshots; refresh after startup.'},indent=2))
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        assert not any('/.env' in n and not n.endswith('/.env.example') for n in z.namelist())
    temp.replace(target)
    print(name,target.stat().st_size,'bytes',len(manifest),'files',flush=True)

def main():
    (ROOT/'delivery').mkdir(exist_ok=True)
    files=list(source_files())
    bundle('Open-Neighbourhood-source.zip',files)
    with tempfile.TemporaryDirectory() as temp:
        backup=Path(temp)/'report.sqlite3'
        with sqlite3.connect(ROOT/'data/report.sqlite3') as src,sqlite3.connect(backup) as dst:
            src.backup(dst)
            # Transfer imported public datasets, not arbitrary cached responses.
            dst.execute('DELETE FROM cache');dst.commit();dst.execute('VACUUM')
            assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        data=[('data/'+name,ROOT/'data'/name) for name in DATA_FILES if (ROOT/'data'/name).is_file()]
        bundle('Open-Neighbourhood-with-data.zip',files+data+[('data/report.sqlite3',backup)])
if __name__=='__main__':main()
