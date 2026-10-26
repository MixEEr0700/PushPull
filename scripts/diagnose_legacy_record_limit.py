import argparse,json,shutil
from pathlib import Path
from measure_incremental_write import artifact,ready,SEED
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description='Isolated synthetic legacy single-record limit diagnostic; never opens user profiles.')
parser.add_argument('--output',type=Path,required=True);parser.add_argument('--before',default='4647511');args=parser.parse_args()
base=args.output;base.mkdir(parents=True,exist_ok=False)
server,thread,hashes,release=artifact(args.before,base/'before')
url='http://127.0.0.1:'+str(server.server_port)+'/'
probe=r"""(()=>{
 window.__idbDiagnostic=[];
 const log=x=>__idbDiagnostic.push(x),transaction=IDBDatabase.prototype.transaction;
 IDBDatabase.prototype.transaction=function(...args){const tx=transaction.apply(this,args);tx.addEventListener('error',event=>log({event:'transaction-error',stores:[...tx.objectStoreNames],error:event.target.error?.name,message:event.target.error?.message,source:event.target.source?.name}));tx.addEventListener('abort',()=>log({event:'transaction-abort',error:tx.error?.name,message:tx.error?.message}));return tx};
 for(const method of ['add','put']){const original=IDBObjectStore.prototype[method];IDBObjectStore.prototype[method]=function(value,...args){const context={store:this.name,method,key:value?.key??null},large=this.name==='meta'&&['state','training-model-v1'].includes(value?.key);if(large)log({...context,event:'write-start'});let r;try{r=original.call(this,value,...args)}catch(error){log({...context,event:'sync-error',error:error.name,message:error.message});throw error}r.addEventListener('error',()=>log({...context,event:'request-error',error:r.error?.name,message:r.error?.message}));if(large)r.addEventListener('success',()=>log({...context,event:'write-success'}));return r}}
})();"""
report={'syntheticOnly':True,'purpose':'diagnose setup abort, not performance evidence','source':args.before,'cases':{}}
try:
 with sync_playwright() as pw:
  for label,mib,shape in [('raw4',4,'ascii'),('escaped16',16,'escaped')]:
   browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--enable-precise-memory-info']);context=browser.new_context();context.add_init_script(probe);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   try:
    page.goto(url);ready(page)
    before=page.evaluate('async()=>({storage:await navigator.storage.estimate(),heap:performance.memory.usedJSHeapSize})')
    page.evaluate(r"""({bytes,shape})=>{const part=shape==='escaped'?'Ł😀\\\"\n':'x',size=new TextEncoder().encode(part).length;window.__archive=part.repeat(Math.floor(bytes/size))+'x'.repeat(bytes%size)}""",{'bytes':mib*1048576,'shape':shape})
    print('SETUP '+label,flush=True)
    try:out={'sizes':page.evaluate(SEED.replace("raw:'x'.repeat(archiveBytes)",'raw:window.__archive'),{'count':400,'native':True,'archiveBytes':mib*1048576})}
    except Exception as error:out={'error':str(error)}
    out.update({'before':before,'after':page.evaluate('async()=>({storage:await navigator.storage.estimate(),heap:performance.memory.usedJSHeapSize,events:__idbDiagnostic})'),'pageErrors':errors})
    # The failed all-source transaction must not expose a partial history.
    out['restart']=page.evaluate("async()=>{const h=await PushPullDB.open(()=>{throw Error('missing')});try{return {error:h.error?.message??null,sessions:h.value?.sessions.length,entries:h.value?.entries.length}}finally{h.close()}}")
    report['cases'][label]=out;(base/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({label:out}),flush=True)
   finally:context.close();browser.close()
finally:server.shutdown();server.server_close();thread.join()
