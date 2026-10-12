"""Import official GIAS details, DfE offers and workforce snapshots; exact URN joins."""
import csv,io,json,sys,zipfile,argparse,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect,now
GIAS_FIELDS={'headteacher':None,'address':None,'phone':'TelephoneNum','local_authority':'LA (name)','la_code':'LA (code)','la_gss':'GSSLACode (name)','boys':'NumberOfBoys','girls':'NumberOfGirls','fsm_pct':'PercentageFSM','census_date':'CensusDate','trust':'Trusts (name)','sponsor':'SchoolSponsors (name)','boarders':'Boarders (name)','nursery':'NurseryProvision (name)','sen_support':'SENNoStat','sen_ehcp':'SENStat'}
def gias_details(r):
    return {**{k:r.get(v,'') for k,v in GIAS_FIELDS.items() if v},
            'headteacher':' '.join(r.get(k,'') for k in ['HeadTitle (name)','HeadFirstName','HeadLastName']).strip(),
            'address':', '.join(r[k] for k in ['Street','Locality','Address3','Town','Postcode'] if r.get(k))}
def enrich_gias(path):
    with zipfile.ZipFile(path) as z:
        raw=z.read(next(n for n in z.namelist() if n.lower().endswith('.csv')))
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:text=raw.decode('cp1252')
    count=0
    with connect() as db:
        for r in csv.DictReader(io.StringIO(text)):
            old=db.execute("SELECT meta FROM points WHERE kind='schools' AND id=?",(r['URN'],)).fetchone()
            if not old:continue
            meta=json.loads(old['meta']);meta.update(gias_details(r))
            db.execute("UPDATE points SET meta=? WHERE kind='schools' AND id=?",(json.dumps(meta),r['URN']));count+=1
    return count
OFFER_FIELDS={'total_applications':'times_put_as_any_preferred_school','first_applications':'times_put_as_1st_preference','second_applications':'times_put_as_2nd_preference','third_applications':'times_put_as_3rd_preference','total_offers':'total_number_places_offered','first_offers':'number_1st_preference_offers','second_offers':'number_2nd_preference_offers','third_offers':'number_3rd_preference_offers','preferred_offers':'number_preferred_offers','outside_la_applications':'all_applications_from_another_LA','outside_la_offers':'offers_to_applicants_from_another_LA'}
OFFERS_SOURCE='https://explore-education-statistics.service.gov.uk/find-statistics/primary-and-secondary-school-applications-and-offers/2026-27/explore'
WORKFORCE_SOURCE='https://explore-education-statistics.service.gov.uk/find-statistics/school-workforce-in-england/2025/explore'
def import_offers(path):
    count=0
    with open(path,encoding='utf-8-sig') as f,connect() as db:
        reader=csv.DictReader(f)
        if not {'school_urn','time_period',*OFFER_FIELDS.values()}<=set(reader.fieldnames):raise ValueError('Offers schema changed')
        db.execute("DELETE FROM records WHERE kind='school_offers'")
        for r in reader:
            urn=r['school_urn'];year=r['time_period']
            if not urn.isdigit() or len(urn)!=6:continue
            meta={'year':year,'phase':r['school_phase'],'entry_year':r['entry_year'],'school_name':r['school_name'],**{k:r[v] for k,v in OFFER_FIELDS.items()}}
            db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)',('school_offers',urn+':'+year+':'+r['school_phase'],None,urn,json.dumps(meta)));count+=1
        if not count:raise ValueError('No school offers')
        db.execute('INSERT OR REPLACE INTO imports VALUES(?,?,?,?,?,?)',('school_offers',OFFERS_SOURCE,'2014/15–2026/27 (29 June 2026 release)',now(),count,'DfE / Crown copyright / OGL v3.0'))
    return count
def xlsx_rows(path):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        with z.open('xl/worksheets/sheet1.xml') as f:
            for _,row in ET.iterparse(f,events=['end']):
                if row.tag.endswith('}row'):
                    values={}
                    for c in row:
                        v=c.find('s:v',ns)
                        if v is not None:values[''.join(x for x in c.attrib['r'] if x.isalpha())]=strings[int(v.text)] if c.get('t')=='s' else v.text
                    yield values;row.clear()
def import_workforce(path,year="2025"):
    iterator=iter(xlsx_rows(path));header=next(iterator);count=0
    if 'URN' not in header.values():raise ValueError('Workforce schema changed')
    with connect() as db:
        db.execute("DELETE FROM records WHERE kind='school_workforce'")
        for vals in iterator:
            r={label:vals.get(col,'') for col,label in header.items()};urn=r['URN']
            if not urn.isdigit():continue
            rows=[{'indicator':k,'value':v,'year':year+' census' if not __import__('re').search(r'20\d{2}/\d{2}',k) else __import__('re').search(r'20\d{2}/\d{2}',k).group()} for k,v in r.items() if k not in list(header.values())[:17]]
            db.execute('INSERT INTO records VALUES(?,?,?,?,?)',('school_workforce',urn,None,urn,json.dumps({'rows':rows})));count+=1
        if not count:raise ValueError('No workforce rows')
        db.execute('INSERT OR REPLACE INTO imports VALUES(?,?,?,?,?,?)',('school_workforce',WORKFORCE_SOURCE,'November 2025 census (published 2026)',now(),count,'DfE / Crown copyright / OGL v3.0'))
    return count
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gias');p.add_argument('--offers');p.add_argument('--workforce');a=p.parse_args()
    for kind,path,fn in [('gias',a.gias,enrich_gias),('offers',a.offers,import_offers),('workforce',a.workforce,import_workforce)]:
        if path:print(kind,fn(path))
