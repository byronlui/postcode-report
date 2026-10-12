"""Import the official Ofsted latest-inspections CSV, preserving framework and dates."""
import csv,json,sys,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect,now
SOURCE='https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes'
URL='https://assets.publishing.service.gov.uk/media/6aa0175392e72b8ac437ef37/Management_information_-_state-funded_schools_-_latest_inspections_as_at_31_August_2026.csv'
NEW=['Safeguarding standards','Inclusion','Curriculum and teaching','Achievement','Attendance and behaviour','Personal development and wellbeing','Early years (where applicable)','Post-16 provision (where applicable)','Leadership and governance']
OLD=['Latest OEIF overall effectiveness','Latest OEIF quality of education','Latest OEIF behaviour and attitudes','Latest OEIF personal development','Latest OEIF effectiveness of leadership and management','Latest OEIF early years provision (where applicable)','Latest OEIF sixth form provision (where applicable)']

def clean(v):return None if not v or v.strip() in ('NULL','Not applicable','N/A') else v.strip()
def parse(r):
    reports=[]
    for framework,date,urn,fields in [('Renewed EIF','Inspection start date','URN at time of latest full inspection',NEW),('Earlier EIF','Inspection start date of latest OEIF graded inspection','URN at time of latest OEIF graded inspection',OLD),('Ungraded','Date of latest ungraded inspection','URN at time of the ungraded inspection',['Ungraded inspection overall outcome'])]:
        if not clean(r.get(date)):continue
        grades=[]
        for name in fields:
            v=clean(r.get(name))
            if v is not None:
                if framework=='Earlier EIF':v={'1':'Outstanding','2':'Good','3':'Requires improvement','4':'Inadequate','9':'Not judged'}.get(v,v)
                grades.append({'category':name,'value':v,'date':clean(r.get(name+' - date of grade')) or r[date]})
        reports.append({'framework':framework,'date':r[date],'inspection_urn':clean(r.get(urn)),'grades':grades})
    return {'urn':r['URN'],'reports':reports,'report_url':r.get('Web Link (opens in new window)') or 'https://reports.ofsted.gov.uk/provider/23/'+r['URN']}

def import_ofsted(path):
    content=Path(path).read_bytes()
    try:text=content.decode('utf-8-sig')
    except UnicodeDecodeError:text=content.decode('cp1252')
    import io
    reader=csv.DictReader(io.StringIO(text));count=0
    if not {'URN','Inspection start date','Latest OEIF overall effectiveness'}<=set(reader.fieldnames or []):raise ValueError('Unexpected Ofsted schema')
    with connect() as db:
        db.execute("DELETE FROM records WHERE kind='ofsted'")
        for r in reader:
            if not r['URN'].isdigit():continue
            db.execute('INSERT INTO records VALUES(?,?,?,?,?)',('ofsted',r['URN'],None,r['URN'],json.dumps(parse(r))));count+=1
        if not count:raise ValueError('No Ofsted schools')
        db.execute('INSERT OR REPLACE INTO imports VALUES(?,?,?,?,?,?)',('ofsted',SOURCE,'31 August 2026',now(),count,'Ofsted / Crown copyright · OGL v3.0'))
    return count
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('path',nargs='?',default='data/ofsted-202608.csv');p.add_argument('--download',action='store_true');a=p.parse_args()
    if a.download:
        import httpx
        r=httpx.get(URL,timeout=90);r.raise_for_status();Path(a.path).parent.mkdir(exist_ok=True,parents=True);Path(a.path).write_bytes(r.content)
    print('Ofsted schools:',import_ofsted(a.path))
