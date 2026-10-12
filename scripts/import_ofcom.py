"""Import official January 2026 Ofcom OGL releases; no API key required."""
import argparse,csv,io,json,sys,zipfile,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect,now,postcode,DATA
SOURCE='https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/connected-nations-update-spring-2026'
BASE='https://www.ofcom.org.uk/siteassets/resources/documents/research-and-data/multi-sector/infrastructure-research/connected-nations-spring-2026/'
DOWNLOADS={'fixed':'202601_fixed_broadband_coverage_and_full_fibre_take-up-r1.zip?v=422620','mobile':'202601_mobile_coverage_r1.zip?v=417690'}
FIELDS=['SFBB availability (% premises)','UFBB (100Mbit/s) availability (% premises)','UFBB availability (% premises)','Gigabit availability (% premises)','% of premises unable to receive decent broadband from fixed or FWA']

def percent(value):
    if value is None or value.strip() in ('','NA','N/A','-'):return None
    n=float(value)
    if not 0<=n<=100:raise ValueError('Invalid coverage percentage')
    return n

def import_fixed(path):
    count=0
    with zipfile.ZipFile(path) as z,connect() as db:
        files=[n for n in z.namelist() if re.search(r'/postcode_files(?:_r\d+)?/',n) and n.endswith('.csv')]
        if not files:raise ValueError('Expected corrected January 2026 postcode_files_r2 release')
        db.execute('CREATE TABLE IF NOT EXISTS ofcom_fixed(postcode TEXT PRIMARY KEY,sfbb REAL,ufbb100 REAL,ufbb300 REAL,gigabit REAL,below_decent REAL)')
        db.execute('DELETE FROM ofcom_fixed')
        for name in files:
            with z.open(name) as raw:
                reader=csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8-sig'))
                if not set(['postcode']+FIELDS)<=set(reader.fieldnames or []):raise ValueError('Unexpected Ofcom schema')
                batch=[]
                for row in reader:
                    batch.append((postcode(row['postcode']),*(percent(row[k]) for k in FIELDS)))
                    count+=1
                    if len(batch)>=5000:
                        db.executemany('INSERT INTO ofcom_fixed VALUES(?,?,?,?,?,?)',batch);batch=[]
                db.executemany('INSERT INTO ofcom_fixed VALUES(?,?,?,?,?,?)',batch)
        if not count:raise ValueError('Empty dataset')
        db.execute('INSERT OR REPLACE INTO imports VALUES(?,?,?,?,?,?)',('broadband',SOURCE,'January 2026 · postcode r2 (July correction)',now(),count,'Ofcom · Open Government Licence v3.0'))
    return count

def import_mobile(path):
    count=0
    with zipfile.ZipFile(path) as z,connect() as db:
        files=[n for n in z.namelist() if re.search(r'20\d{4}_mobile_coverage_laua_r\d+\.csv$',n)]
        if len(files)!=1:raise ValueError('Expected January 2026 mobile local authority CSV')
        db.execute("DELETE FROM records WHERE kind='mobile'")
        with z.open(files[0]) as raw:
            reader=csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8-sig'))
            required={'laua','laua_name','4G_prem_in_0','4G_prem_out_0','5G_high_confidence_prem_out_0'}
            if not required<=set(reader.fieldnames or []):raise ValueError('Unexpected mobile schema')
            for r in reader:
                rows=[]
                for field,label in [('4G_prem_in','4G · 室內'),('4G_prem_out','4G · 室外'),('5G_high_confidence_prem_out','5G · 室外 / High confidence'),('5G_very_high_confidence_prem_out','5G · 室外 / Very high confidence')]:
                    none=percent(r.get(field+'_0'))
                    rows.append({'category':label,'scope':r['laua_name']+' · 全區物業','at_least_one_pct':round(100-none,2) if none is not None else None,'all_four_pct':percent(r.get(field+'_4'))})
                meta={'area_name':r['laua_name'],'rows':rows}
                db.execute('INSERT INTO records VALUES(?,?,?,?,?)',('mobile',r['laua'],None,r['laua'],json.dumps(meta)))
                count+=1
        if not count:raise ValueError('Empty mobile dataset')
        db.execute('INSERT OR REPLACE INTO imports VALUES(?,?,?,?,?,?)',('mobile',SOURCE,'January 2026',now(),count,'Ofcom · Open Government Licence v3.0'))
    return count

def download(kind):
    import httpx
    path=DATA/f'ofcom-{kind}-202601.zip';temp=path.with_suffix('.part')
    with httpx.stream('GET',BASE+DOWNLOADS[kind],timeout=90,follow_redirects=True) as response:
        response.raise_for_status()
        with temp.open('wb') as f:
            for chunk in response.iter_bytes():f.write(chunk)
    if not zipfile.is_zipfile(temp):raise ValueError('Download is not a ZIP')
    temp.replace(path)
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--download',action='store_true');p.add_argument('--fixed');p.add_argument('--mobile')
    a=p.parse_args()
    fixed=download('fixed') if a.download else a.fixed
    mobile=download('mobile') if a.download else a.mobile
    if not fixed and not mobile:p.error('Use --download or --fixed PATH / --mobile PATH')
    if fixed:print('Fixed postcodes:',import_fixed(fixed),flush=True)
    if mobile:print('Mobile local authorities:',import_mobile(mobile),flush=True)
