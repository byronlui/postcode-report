"""Small live coverage and validation check against the running local app."""
import asyncio,json
from pathlib import Path
import httpx
async def main():
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8765',timeout=60) as c:
  results={}
  for pc in ['SW1A 1AA','CF10 1EP','EH1 1YZ','BT1 5GS']:
   r=await c.get('/api/location/'+pc);r.raise_for_status();p=r.json()
   assert p.get('country')
   results[pc]={'country':p['country'],'postcode':p['postcode']}
  for pc,section in [('EH1 1YZ','crime'),('BT1 5GS','prices')]:
   r=await c.get('/api/report/'+pc+'/'+section);r.raise_for_status();d=r.json()
   assert d['status']=='coverage_gap',d
   results[pc][section]=d['status']
  r=await c.get('/api/location/invalid');assert r.status_code==422
  r=await c.get('/api/journey',params={'origin':'RG10 9RZ','destination':'EC2M 7PY'});r.raise_for_status()
  results['journey']=r.json()
  Path('docs/coverage-live-check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
  print(json.dumps(results,ensure_ascii=False,indent=2))
asyncio.run(main())
