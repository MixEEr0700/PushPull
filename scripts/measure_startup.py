"""Synthetic startup stage profiler. Fresh isolated profiles, serial runs only.
No phone/user database; CPU throttling is not Android emulation.
"""
import argparse,functools,hashlib,http.server,io,json,re,runpy,shutil,subprocess,tarfile,threading,platform
from pathlib import Path
from playwright.sync_api import sync_playwright
from measure_incremental_write import ROOT,Server,INJECT,ready,launch,inject_fixture
FUNCTIONS={'indexeddb.js':['open','read','verifyEvidence'], 'model/legacy-model.mjs':['verifyLegacyModel','createLegacyModelFromSource','validateStructuredSource'], 'model/backup.mjs':['createBackup','validateBackup'], 'model/journal-protocol.mjs':['createProtocol','materialize','materializeTraining','validateSource'], 'model/journal-idb.mjs':['readRecords','readTraining','certifyAllocation','replaceLive','legacyEvidence','prepareConversion','activateConversion','openWriter','auditBundle'], 'model/journal-database.mjs':['openDatabase'], 'model/workout-drafts.mjs':['openDrafts'], 'model/drive-sync.mjs':['openDriveBackup'], 'model/journal-runtime.mjs':['reader','selectedSource','readIndexed','installRuntime','openIndexedWriter'], 'model/journal-runtime-index.mjs':['buildRuntime','auditRuntime'], 'app.js':['render','main','statsPanel']}
PROBE=r"""(()=>{const p=globalThis.__startup={spans:[],requests:[],long:[],heap:[],async:async(n,f)=>{const t=performance.now();try{return await f()}finally{p.spans.push({name:n,start:t,ms:performance.now()-t})}},time:(n,f)=>{const t=performance.now();try{return f()}finally{p.spans.push({name:n,start:t,ms:performance.now()-t})}}};try{new PerformanceObserver(l=>p.long.push(...l.getEntries().map(e=>({start:e.startTime,ms:e.duration})))).observe({type:'longtask',buffered:true})}catch{};p.timer=setInterval(()=>p.heap.push(performance.memory?.usedJSHeapSize??0),10);const open=IDBFactory.prototype.open;IDBFactory.prototype.open=function(...args){const t=performance.now(),r=open.apply(this,args);r.addEventListener('success',()=>p.requests.push({name:'open',start:t,ms:performance.now()-t}));return r};for(const op of ['get','getAll']){const old=IDBObjectStore.prototype[op];IDBObjectStore.prototype[op]=function(...args){const t=performance.now(),name=this.name,r=old.apply(this,args);r.addEventListener('success',()=>p.requests.push({name,op,start:t,ms:performance.now()-t,count:op==='getAll'?r.result.length:1}));return r}}})();"""
def instrument(name,text):
 for fn in FUNCTIONS.get(name,[]):
  pattern=re.compile(r'(?P<async>async\s+)?function\s+'+fn+r'\(')
  def repl(m):
   a='async ' if m.group('async') else '';kind='async' if a else 'time'
   return a+f"function {fn}(...args){{return globalThis.__startup?globalThis.__startup.{kind}('{name}:{fn}',()=>__startup_{fn}(...args)):__startup_{fn}(...args)}}\n"+a+f'function __startup_{fn}('
  text=pattern.sub(repl,text,count=1)
 return text

def artifact(ref,directory):
 source=ROOT
 if ref!='working':
  source=directory/'source';source.mkdir(parents=True)
  with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',ref],cwd=ROOT))) as tar:tar.extractall(source,filter='data')
 b=runpy.run_path(str(source/'scripts/build_release.py'));staging=directory/'instrumented';hashes={}
 for name in b['ASSETS']:
  data=(source/name).read_bytes();hashes[name]=hashlib.sha256(data).hexdigest();target=staging/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(instrument(name,data.decode()).encode() if name.endswith(('.js','.mjs')) else data)
 t=staging/'scripts/service-worker.template.js';t.parent.mkdir();shutil.copyfile(source/'scripts/service-worker.template.js',t);release=b['build'](directory/'site',staging)
 handler=type('StartupAllowlist',(Server,),{'allowed':set(b['FILES'])});server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(handler,directory=str(directory/'site')));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();return server,thread,hashes,release

CAPTURE=r"""async()=>{const db=await new Promise((ok,no)=>{const r=indexedDB.open('pushpull');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});try{const names=[...db.objectStoreNames],rows=await new Promise((ok,no)=>{const tx=db.transaction(names),out={};for(const n of names){const r=tx.objectStore(n).getAll();r.onsuccess=()=>out[n]=r.result}tx.oncomplete=()=>ok(out);tx.onabort=()=>no(tx.error)});window.__seedJSON=JSON.stringify({databaseVersion:db.version,rows,local:Object.fromEntries(Object.entries(localStorage))});return __seedJSON.length}finally{db.close()}}"""
def capture(page,path):
 length=page.evaluate(CAPTURE);parts=[];offset=0
 while offset<length:
  part=page.evaluate("i=>{let end=Math.min(i+1048576,__seedJSON.length);if(end<__seedJSON.length&&__seedJSON.charCodeAt(end-1)>=0xd800&&__seedJSON.charCodeAt(end-1)<=0xdbff)end--;return {text:__seedJSON.slice(i,end),next:end}}",offset);parts.append(part['text']);offset=part['next']
 path.write_text(''.join(parts));page.evaluate('window.__seedJSON=null')
def inject(page,seed):
 page.goto(page.url.rsplit('/',1)[0]+'/benchmark.html');inject_fixture(page,seed)
def measure(context,url,cpu):
 context.add_init_script(PROBE);page=context.new_page();session=context.new_cdp_session(page);session.send('Emulation.setCPUThrottlingRate',{'rate':cpu});page.goto(url,timeout=600000);ready(page)
 result=page.evaluate("()=>{clearInterval(__startup.timer);return {readyMs:performance.now(),uiReadyMarkMs:performance.getEntriesByName('pushpull-training-ready')[0]?.startTime??null,paint:performance.getEntriesByType('paint').map(p=>p.toJSON()),marks:performance.getEntriesByType('mark').map(p=>p.toJSON()),navigation:performance.getEntriesByType('navigation')[0].toJSON(),...__startup,heapHighWaterBytes:Math.max(0,...__startup.heap,performance.memory.usedJSHeapSize)}}");result.pop('timer',None);result.pop('heap',None);return page,result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--fixtures',type=Path,default=Path('/workspace/issue82-performance-final'));p.add_argument('--cases',nargs='+',default=['small','history40-raw4','history40-escaped16']);p.add_argument('--cpu',type=float,default=4);p.add_argument('--after');p.add_argument('--repeats',type=int,default=1);p.add_argument('--skip-capture',action='store_true');p.add_argument('--seed-suffix',default='-fixture.json');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
 refs=[('v1','4647511'),('C','5b735e4')] if not args.after else [('after',args.after)];report={'syntheticOnly':True,'cpuThrottle':args.cpu,'cases':{},'artifacts':{},'platform':platform.platform(),'chromium':subprocess.check_output(['chromium','--version'],text=True).strip(),'cpuModel':next(x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),'repeats':args.repeats};servers=[]
 try:
  with sync_playwright() as pw:
   for side,ref in refs:
    server,thread,hashes,release=artifact(ref,args.output/side);servers.append((server,thread));url='http://127.0.0.1:'+str(server.server_port)+'/';report['artifacts'][side]={'ref':ref,'hashes':hashes,'release':release}
    for label in args.cases:
     print('BEGIN',label,side,flush=True);seed=json.loads((args.fixtures/(label+args.seed_suffix)).read_text());profile=args.output/(label+'-'+side);context=launch(pw,profile);page=context.new_page();page.goto(url+'benchmark.html');inject_fixture(page,seed);page.close()
     page,initial=measure(context,url,args.cpu);page.evaluate('navigator.serviceWorker.ready');page.wait_for_function('navigator.serviceWorker.controller!==null');
     if not args.skip_capture:capture(page,args.output/(label+'-'+side+'-captured.json'))
     context.close()
     runs={'initial':initial};report['cases'].setdefault(label,{})[side]=runs
     report['cases'][label]['fixture']={'sha256':hashlib.sha256((args.fixtures/(label+args.seed_suffix)).read_bytes()).hexdigest(),'databaseVersion':seed.get('databaseVersion',1),'counts':{k:len(v) for k,v in seed['rows'].items()}}
     for n in range(args.repeats):
      context=launch(pw,profile);context.set_offline(True);page,cold=measure(context,url,args.cpu);page.close();page,warm=measure(context,url,args.cpu);context.close()
      runs['cold'+str(n)]=cold;runs['warm'+str(n)]=warm;(args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
     print('COMPLETE',label,side,{k:round(v['readyMs'],1) for k,v in runs.items()},flush=True)
 finally:
  for s,t in servers:s.shutdown();s.server_close();t.join()
if __name__=='__main__':main()
