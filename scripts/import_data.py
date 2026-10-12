#!/usr/bin/env python3
"""Stream official CSVs into SQLite. Import only files you are entitled to use."""
import argparse
import csv
import io
import json
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect, now, postcode


def rows_from(path,encoding="utf-8-sig"):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            csvs=[n for n in z.namelist() if n.lower().endswith('.csv')]
            if len(csvs)!=1:raise ValueError('ZIP must contain exactly one CSV; extract and choose the relevant file.')
            with z.open(csvs[0]) as raw:
                yield from csv.reader(io.TextIOWrapper(raw,encoding=encoding,errors='strict'))
    else:
        with open(path,encoding=encoding,errors='strict',newline='') as f:yield from csv.reader(f)


def import_file(kind,path,source,vintage,license):
    count=0
    from pyproj import Transformer
    transform=Transformer.from_crs(27700,4326,always_xy=True)
    with connect() as db:
        # One transaction: malformed input leaves the previous import intact.
        if kind=='noise':
            from shapely.geometry import shape
            geo=json.loads(Path(path).read_text())
            if geo.get('crs'):raise ValueError('Convert to RFC 7946 WGS84 GeoJSON and remove crs first.')
            db.execute('DELETE FROM polygons WHERE kind=?',(kind,))
            for i,f in enumerate(geo['features']):
                g=shape(f['geometry']);a,b,c,d=g.bounds
                if not g.is_valid or a < -180 or c>180 or b < -90 or d>90:raise ValueError('Invalid WGS84 geometry')
                db.execute('INSERT INTO polygons VALUES(?,?,?,?,?,?,?,?)',(kind,str(i),a,b,c,d,json.dumps(f['geometry']),json.dumps(f.get('properties',{}))))
                count+=1
        else:
            reader=iter(rows_from(path,encoding="cp1252" if kind=="schools" else "utf-8-sig"))
            first=next(reader)
            if kind=='prices':
                import itertools
                raw=itertools.chain([first],reader)
            else:
                raw=(dict(zip(first,row)) for row in reader)
                db.execute('DELETE FROM points WHERE kind=?',(kind,))
                db.execute('DELETE FROM records WHERE kind=?',(kind,))
            for r in raw:
                if kind=='epc':
                    # Official 2026 CSV names; also accept prior normalized schema.
                    r={k.lower().replace('-','_'):v for k,v in r.items()}
                    r['certificate']=r.get('certificate') or r.get('certificate_number') or r.get('lmk_key') or ''
                    r['band']=r.get('band') or r.get('current_energy_rating') or ''
                    r['date']=r.get('date') or r.get('lodgement_date') or ''
                    r['potential_band']=r.get('potential_band') or r.get('potential_energy_rating') or ''
                    r['id']=r.get('id') or r['certificate']
                    if not r.get('postcode') or not r['certificate'] or not r['band']:
                        raise ValueError('EPC CSV requires postcode, certificate number and current energy rating')
                if kind=='transport':
                    if r.get('Status','active').lower()!='active':continue
                    if not r.get('Latitude') or not r.get('Longitude'):continue
                    lat,lon=float(r['Latitude']),float(r['Longitude'])
                    name=r.get('CommonName') or r['ATCOCode'];id=r['ATCOCode']
                    meta={'stop_type':r.get('StopType'),'indicator':r.get('Indicator'),'locality':r.get('LocalityName'),'modified':r.get('ModificationDateTime')}
                elif kind=='schools':
                    if r.get('EstablishmentStatus (name)')!='Open':continue
                    if not r.get('Easting') or not r.get('Northing'):continue
                    lon,lat=transform.transform(float(r['Easting']),float(r['Northing']))
                    name=r['EstablishmentName'];id=r['URN']
                    meta={'phase':r.get('PhaseOfEducation (name)'),'type':r.get('TypeOfEstablishment (name)'), 'postcode':r.get('Postcode'),
                          'gender':r.get('Gender (name)'), 'age_low':r.get('StatutoryLowAge'),'age_high':r.get('StatutoryHighAge'),
                          'religion':r.get('ReligiousCharacter (name)'), 'pupils':r.get('NumberOfPupils'),'capacity':r.get('SchoolCapacity'),
                          'website':r.get('SchoolWebsite'),'sixth_form':r.get('OfficialSixthForm (name)'),
                          'admissions':r.get('AdmissionsPolicy (name)'), 'url':f'https://www.get-information-schools.service.gov.uk/Establishments/Establishment/Details/{id}'}
                    from scripts.import_school_context import gias_details
                    meta.update(gias_details(r))
                elif kind in ('greenspace','air'):
                    id=r['id'];name=r['name'];lat,lon=float(r['lat']),float(r['lon']);meta=r
                elif kind=='prices':
                    if len(r)!=16:raise ValueError('Price Paid CSV requires the official 16 columns without a header')
                    id=r[0]
                    if r[15]=='D':
                        db.execute('DELETE FROM records WHERE kind=? AND id=?',(kind,id));count+=1;continue
                    pc=postcode(r[3]) if r[3] else None
                    meta={'id':id,'price':int(r[1]),'date':r[2][:10],'type':{'D':'detached','S':'semi-detached','T':'terraced','F':'flat-maisonette','O':'other'}.get(r[4],r[4]),
                          'tenure':{'F':'freehold','L':'leasehold'}.get(r[6],r[6]),'address':' '.join(x for x in [r[8],r[7],r[9]] if x),'postcode':pc}
                    db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)',(kind,id,pc,None,json.dumps(meta)))
                    count+=1;continue
                else:
                    id=r.get('id') or str(count)
                    pc=postcode(r['postcode']) if r.get('postcode') else None
                    if kind=='epc':
                        # Remove all address data at ingestion; store only energy fields plus lookup key.
                        from app.epc_property import normalize
                        meta=normalize(r)
                        meta.pop("address",None)
                        meta['potential_band']=r.get('potential_band','')
                    else:meta=r
                    db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)',(kind,id,pc,r.get('area'),json.dumps(meta)))
                    count+=1;continue
                if not (-90<=lat<=90 and -180<=lon<=180):raise ValueError('Invalid coordinates')
                db.execute('INSERT OR REPLACE INTO points VALUES(?,?,?,?,?,?)',(kind,id,name,lat,lon,json.dumps(meta)))
                count+=1
        if count==0:raise ValueError('No usable records: previous dataset was not replaced')
        db.execute('INSERT OR REPLACE INTO imports VALUES(?,?,?,?,?,?)',(kind,source,vintage,now(),count,license))
    return count


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind',choices=['transport','schools','prices','noise','greenspace','air','epc','broadband','tax','affluence'])
    p.add_argument('path');p.add_argument('--source',required=True);p.add_argument('--vintage',required=True);p.add_argument('--license',required=True)
    a=p.parse_args()
    print(f'Imported {import_file(a.kind,a.path,a.source,a.vintage,a.license):,} records')
