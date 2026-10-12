#!/usr/bin/env python3
"""Convert official OS Open Greenspace GeoPackage access points to local index."""
import csv,sqlite3,sys,tempfile,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pyproj import Transformer
from shapely import from_wkb
from scripts.import_data import import_file

def convert(path,output):
    transform=Transformer.from_crs(27700,4326,always_xy=True)
    with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True) as db,open(output,'w',newline='') as f:
        srs=db.execute("SELECT srs_id FROM gpkg_geometry_columns WHERE table_name='access_point'").fetchone()[0]
        if srs!=27700:raise ValueError('Expected British National Grid EPSG:27700')
        w=csv.DictWriter(f,fieldnames=['id','name','lat','lon','type','access_type','site_id']);w.writeheader()
        # Multiple entrances remain explicit; the report deduplicates sites by nearest entrance.
        query='SELECT a.id,a.geometry,a.access_type,a.ref_to_greenspace_site,s.function,s.distinctive_name_1 FROM access_point a JOIN greenspace_site s ON a.ref_to_greenspace_site=s.id'
        for id,blob,access,site,function,name in db.execute(query):
            if blob[:2]!=b'GP':raise ValueError('Invalid GeoPackage geometry')
            envelope=(blob[3]>>1)&7
            offset=8+{0:0,1:32,2:48,3:48,4:64}[envelope]
            point=from_wkb(blob[offset:]);lon,lat=transform.transform(point.x,point.y)
            w.writerow({'id':id,'name':name or function,'lat':lat,'lon':lon,'type':function,'access_type':access,'site_id':site})

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('gpkg');p.add_argument('--vintage',required=True);a=p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        out=Path(d)/'greens.csv';convert(a.gpkg,out)
        n=import_file('greenspace',out,'https://api.os.uk/downloads/v1/products/OpenGreenspace',a.vintage,'OGL v3.0; contains OS data © Crown copyright and database right 2026')
        print(f'Imported {n:,} OS access points')
