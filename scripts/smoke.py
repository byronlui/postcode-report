"""Live smoke test. Records outcomes, never asserts an unavailable service is working."""
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import fetch,now
from app.providers import location,safe_provider,PROVIDERS
async def main():
 await fetch.start()
 try:
  p=await location('RG10 9RZ');print('LOCATION',p['postcode'],p['latitude'],p['longitude'],flush=True)
  names=list(PROVIDERS)
  async def run(n):
   d=await safe_provider(n,p);print(n,d['status'],len(d.get('rows',[])),d['summary'][:130],flush=True);return d
  parts=await asyncio.gather(*(run(n) for n in names))
  Path('docs/rg109rz-live-report.json').write_text(json.dumps({'tested_at':now(),'location':p,'sections':dict(zip(names,parts))},ensure_ascii=False,indent=2))
 finally:await fetch.close()
asyncio.run(main())
