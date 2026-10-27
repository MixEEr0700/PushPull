"""Read-only 400-session startup under a renderer old-space cap; synthetic only.
Seed with an unrestricted process, then restart the isolated profile at the cap.
No fixture generation, migration, production profile or full-export memory claim.
"""
import argparse,json,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
from measure_startup import artifact,measure
from measure_incremental_write import inject_fixture

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ref',required=True);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--old-space',type=int,default=128);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
 seed=json.loads(args.fixture.read_text());server,thread,hashes,release=artifact(args.ref,args.output/'runtime');url='http://127.0.0.1:'+str(server.server_port)+'/'
 try:
  with sync_playwright() as pw:
   profile=args.output/'profile';common={'executable_path':shutil.which('chromium'),'viewport':{'width':390,'height':844},'service_workers':'block'}
   context=pw.chromium.launch_persistent_context(str(profile),args=['--no-sandbox'],**common);page=context.new_page();page.goto(url+'benchmark.html');inject_fixture(page,seed);context.close()
   context=pw.chromium.launch_persistent_context(str(profile),args=['--no-sandbox','--enable-precise-memory-info','--js-flags=--max-old-space-size='+str(args.old_space)],**common)
   try:
    context.add_init_script("window.__memoryWrites=0;const nativeTx=IDBDatabase.prototype.transaction;IDBDatabase.prototype.transaction=function(...args){if(args[1]==='readwrite')__memoryWrites++;return nativeTx.apply(this,args)}")
    page,startup=measure(context,url,4)
    actual=page.evaluate("""async()=>{const db=await new Promise((ok,no)=>{const r=indexedDB.open('pushpull');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});try{
     const state=await new Promise((ok,no)=>{const tx=db.transaction(['journalState']),r=tx.objectStore('journalState').get('active');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});
     return {root:state.root,writes:__memoryWrites,age:document.querySelector('[data-result-change]')?.textContent};
    }finally{db.close()}}""")
    if actual['root']!=seed['rows']['journalState'][0]['root'] or actual['writes']!=0:raise ValueError('Read-only startup changed the native database')
    if '100' not in actual['age']:raise ValueError('Unloaded history age does not match the 400-session oracle')
    result={'syntheticOnly':True,'ref':args.ref,'oldSpaceMiB':args.old_space,'cpuThrottle':4,'sessions':len(seed['rows']['journalSessions']),'results':len(seed['rows']['journalResults']),'rootUnchanged':True,'writes':0,'age':actual['age'],'heapHighWaterBytes':startup['heapHighWaterBytes'],'uiReadyMarkMs':startup['uiReadyMarkMs'],'runtimeSha256':hashes,'instrumentedRelease':release}
    (args.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['runtimeSha256','instrumentedRelease']}),flush=True)
   finally:context.close()
 finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':main()
