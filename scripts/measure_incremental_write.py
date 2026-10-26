"""Issue 82: exact shared v1 fixture, serial before/after real Matrix writes.

Synthetic Chromium/Linux only. Never opens an existing user/browser profile.
Run without concurrent local tests. Each case builds its v1 fixture once through
the old validated API, then seeds those exact rows into each isolated profile.
The v2 application performs its actual upgrade. Separate process-cold, warm,
first/new/correction and strict complete measurements; no toast-as-durability.
"""
import argparse
import functools
import hashlib
import http.server
import io
import json
import math
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import tarfile
import tempfile
import threading
from statistics import median
from playwright.sync_api import sync_playwright
from measure_responsiveness import ROOT,SEED
from measure_ui_response import UI_PROBE
from measure_durable_write import instrument as old_instrument,FILL,PROOF

CASES=[('empty',0,0,'ascii'),('small',4,0,'ascii'),('history40',40,0,'ascii'),
       ('history40-raw4',40,4,'ascii'),('history40-unicode4',40,4,'unicode'),
       ('history40-escaped16',40,16,'escaped'),('history400-raw4',400,4,'ascii'),
       ('history400-escaped16',400,16,'escaped')]

def instrument_v2(text):
    target="  tx.oncomplete=()=>{cleanup();if(finished)resolve(result);else reject(Error('Transakcja zakończyła się przed weryfikacją odczytu.'))};"
    if text.count(target)!=1:raise ValueError('v2 native clock marker changed')
    text=text.replace(target,"  tx.oncomplete=event=>{if(window.__saveTx===tx)window.__writeMarks?.push({name:'strict-complete',at:performance.now(),eventTimeStamp:event.timeStamp,durability:tx.durability});cleanup();if(finished)resolve(result);else reject(Error('Transakcja zakończyła się przed weryfikacją odczytu.'))};")
    start=text.index(' async function saveResult(');end=text.index(' return {context,saveResult,',start)
    body=text[start:end]
    markers=[('  portable(command);','detach-validate'),('   guard();const before=state,','context'),
      ('   const object=await objectRecord(e),','entry-hash'),('   const tree=await editIndex(','index-prepare'),
      ("   await transact(db,[...STORES,'meta'],'readwrite',async tx=>{",'transaction-open'),
      ("    guard();check(same(await request(tx.objectStore('journalState')",'cas'),
      ("    await addImmutable(tx,'journalObjects',[object]);",'write-objects'),
      ("    tx.objectStore('journalResults').put(row);",'write-result-root'),
      ("    await readback(tx,'journalResults',[row]);",'readback'),
      ('   maps.journalObjects.set(object.id,object);','publication')]
    for target,label in markers:
        if body.count(target)!=1:raise ValueError('v2 stage marker changed: '+label)
        indent=target[:len(target)-len(target.lstrip())]
        body=body.replace(target,indent+f"window.__writeMarks?.push({{name:'{label}',at:performance.now()}});\n"+target,1)
        if label=='cas':body=body.replace(target,indent+'window.__saveTx=tx;\n'+target,1)
    # Used only by the regression proving that this is the native event clock.
    body=body.replace('   maps.journalObjects.set(object.id,object);',"   if(window.__slowPublish){const until=performance.now()+60;while(performance.now()<until){}}\n   maps.journalObjects.set(object.id,object);",1)
    return text[:start]+body+text[end:]

class Server(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?')[0]=='/benchmark.html':
            body=b'<!doctype html><title>Isolated synthetic benchmark bootstrap</title>'
            self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        name=self.path.split('?')[0].lstrip('/') or 'index.html'
        if name not in self.allowed:self.send_error(404);return
        super().do_GET()
    def log_message(self,*args):pass

def artifact(ref,directory):
    source=ROOT
    if ref!='working':
        source=directory/'source';source.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',ref],cwd=ROOT))) as tar:tar.extractall(source,filter='data')
    builder=runpy.run_path(str(source/'scripts/build_release.py'));staging=directory/'instrumented';hashes={}
    for name in builder['ASSETS']:
        data=(source/name).read_bytes();hashes[name]=hashlib.sha256(data).hexdigest()
        if name=='indexeddb.js' and 'model/journal-idb.mjs' not in builder['ASSETS']:data=old_instrument(name,data.decode(),False).encode()
        if name=='model/journal-idb.mjs':data=instrument_v2(data.decode()).encode()
        target=staging/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    template=staging/'scripts/service-worker.template.js';template.parent.mkdir();shutil.copyfile(source/'scripts/service-worker.template.js',template)
    builder['build'](directory/'site',staging)
    handler=type('AllowlistedBenchmark',(Server,),{'allowed':set(builder['FILES'])})
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(handler,directory=str(directory/'site')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    return server,thread,hashes

CAPTURE=r"""async()=>{
 const db=await new Promise((ok,no)=>{const r=indexedDB.open('pushpull',1);r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});
 const stores=[...db.objectStoreNames],rows=await new Promise((ok,no)=>{const tx=db.transaction(stores),out={};for(const s of stores){const r=tx.objectStore(s).getAll();r.onsuccess=()=>out[s]=r.result}tx.oncomplete=()=>ok(out);tx.onabort=()=>no(tx.error)});db.close();
 const handle=await PushPullDB.open(()=>{throw Error('missing fixture')});try{
  const source=JSON.stringify(handle.export()),hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source))),b=>b.toString(16).padStart(2,'0')).join('');
  return {rows,local:Object.fromEntries(Object.entries(localStorage)),sourceHash:hash,sourceBytes:new TextEncoder().encode(source).length};
 }finally{handle.close()}
}"""
INJECT=r"""async fixture=>{
 const request=indexedDB.open('pushpull',1);request.onupgradeneeded=()=>{for(const name of Object.keys(fixture.rows))request.result.createObjectStore(name,{keyPath:name==='meta'?'key':'id'})};
 const db=await new Promise((ok,no)=>{request.onsuccess=()=>ok(request.result);request.onerror=()=>no(request.error)});
 await new Promise((ok,no)=>{const tx=db.transaction(Object.keys(fixture.rows),'readwrite',{durability:'strict'});for(const [name,rows] of Object.entries(fixture.rows))for(const row of rows)tx.objectStore(name).add(row);tx.oncomplete=ok;tx.onabort=()=>no(tx.error)});db.close();
 for(const [k,v] of Object.entries(fixture.local))localStorage.setItem(k,v);
}"""
SOURCE_HASH=r"""async()=>{const db=await PushPullDB.open(()=>{throw Error('missing fixture')});try{if(db.error)throw db.error;return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(db.export())))),b=>b.toString(16).padStart(2,'0')).join('')}finally{db.close()}}"""
def ready(page):page.wait_for_selector('[data-act=start]',timeout=600000)
def fixture(pw,url,count,mib,shape):
    browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);context=browser.new_context();page=context.new_page()
    try:
        page.goto(url);ready(page)
        page.evaluate(r"""({bytes,shape})=>{const part=shape==='escaped'?'Ł😀\\\"\n':shape==='unicode'?'Ł😀':'x',size=new TextEncoder().encode(part).length;window.__archive=part.repeat(Math.floor(bytes/size))+'x'.repeat(bytes%size)}""",{'bytes':mib*1024*1024,'shape':shape})
        sizes=page.evaluate(SEED.replace("raw:'x'.repeat(archiveBytes)",'raw:window.__archive'),{'count':count,'native':True,'archiveBytes':mib*1024*1024})
        return page.evaluate(CAPTURE),sizes
    finally:context.close();browser.close()

def launch(pw,profile):return pw.chromium.launch_persistent_context(str(profile),executable_path=shutil.which('chromium'),args=['--no-sandbox','--enable-precise-memory-info'],viewport={'width':390,'height':844},service_workers='allow')
def prepare_page(context,url,cpu):
    context.add_init_script(UI_PROBE);page=context.new_page();dialogs=[];errors=[];page.on('dialog',lambda d:(dialogs.append(d.message),d.accept()));page.on('pageerror',lambda e:errors.append(str(e)))
    cdp=context.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':cpu});page.goto(url,timeout=600000);ready(page)
    return page,cdp,dialogs,errors
def one_profile(pw,url,profile,seed,cpu,writes):
    # Exact v1 database bytes and localStorage, including raw archives, are shared
    # between paired variants. Initial conversion is recorded, outside save clock.
    context=launch(pw,profile);page=context.new_page();page.goto(url+'benchmark.html');page.evaluate(INJECT,seed);page.close()
    page,cdp,dialogs,errors=prepare_page(context,url,cpu)
    initial=page.evaluate('performance.now()');page.evaluate('navigator.serviceWorker.ready');page.wait_for_function('navigator.serviceWorker.controller!==null',timeout=60000)
    if page.evaluate(SOURCE_HASH)!=seed['sourceHash']:raise ValueError('Exact fixture source differs after load/conversion')
    context.close() # Stop browser process, retain this synthetic profile only.
    context=launch(pw,profile);context.set_offline(True)
    try:
        page,cdp,dialogs,errors=prepare_page(context,url,cpu);cold=page.evaluate('performance.now()')
        page.reload(timeout=600000);ready(page);warm=page.evaluate('performance.now()')
        page.evaluate("document.querySelector('[data-act=start]').click()")
        page.wait_for_function("document.querySelector('[data-act=finish]')&&!document.querySelector('#app').inert",timeout=600000)
        proof=page.evaluate(PROOF);exercises=page.locator('[data-expand]').evaluate_all('bs=>bs.map(b=>b.dataset.expand)').__getitem__(slice(0,4))
        cdp.send('HeapProfiler.collectGarbage');retained_before=cdp.send('Runtime.getHeapUsage');samples=[]
        for n in range(writes):
            ex=exercises[n%len(exercises)]
            page.evaluate("id=>{const b=document.querySelector('[data-expand=\"'+id+'\"]');if(b.getAttribute('aria-expanded')!=='true')b.click()}",ex)
            page.wait_for_selector('[data-panel=result]');page.evaluate("document.querySelector('[data-panel=result]').click()");page.wait_for_selector('.performanceForm')
            page.evaluate(FILL,{'native':True,'weight':str(31+n)})
            page.wait_for_function("document.querySelector('[data-draft-status]')?.textContent.includes('Szkic zapisany lokalnie')",timeout=600000)
            dialogs.clear()
            page.evaluate("window.__saveTx=null;window.__writeMarks=[];window.__heapSamples=[];window.__heapTimer=setInterval(()=>__heapSamples.push(performance.memory.usedJSHeapSize),10);__ui.begin();document.querySelector('.performanceForm [type=submit]').click()")
            page.wait_for_function("!document.querySelector('#app').inert",timeout=600000,polling='raf')
            if page.locator('.performanceForm').count():raise ValueError('Save refused: '+repr(dialogs))
            sample=page.evaluate('__ui.end()');extra=page.evaluate("()=>{clearInterval(__heapTimer);return {marks:__writeMarks,start:__ui.sample.start,heap:Math.max(0,...__heapSamples,performance.memory.usedJSHeapSize)}}")
            marks=extra['marks'];native=[m for m in marks if m['name']=='strict-complete']
            if len(native)!=1 or native[0]['durability']!='strict':raise ValueError('Missing native strict complete')
            sample.update({'kind':'new' if n<len(exercises) else 'correction','first':n==0,'clickToStrictCompleteMs':native[0]['at']-extra['start'],'nativeEventMs':native[0]['eventTimeStamp']-extra['start'],'sampledHeapHighWaterBytes':extra['heap'],'marks':marks})
            sample['completionCallbackMs']=sample.pop('durableMs');sample['stageMs']={}
            for a,b in zip(marks,marks[1:]):
                if a['name']=='strict-complete':continue
                sample['stageMs'][a['name']]=b['at']-a['at']
            samples.append(sample);print(f'  write {n+1}/{writes} {sample["kind"]} native={sample["clickToStrictCompleteMs"]:.1f}ms UI={sample["fullMs"]:.1f}ms',flush=True)
        if page.evaluate(PROOF)!=proof:raise ValueError('Original history/snapshots/archive changed')
        if errors:raise ValueError(errors)
        cdp.send('HeapProfiler.collectGarbage');retained_after=cdp.send('Runtime.getHeapUsage')
        return {'initialReadyMs':initial,'processColdReadyMs':cold,'warmReadyMs':warm,'preserved':True,'proof':proof,'retainedBefore':retained_before,'retainedAfter':retained_after,'samples':samples}
    finally:context.close()

def statistics(profiles):
    rows=[r for p in profiles for r in p['samples']];out={}
    for group,selected in [('all',rows),('new',[r for r in rows if r['kind']=='new']),('correction',[r for r in rows if r['kind']=='correction']),('first',[r for r in rows if r['first']])]:
        out[group]={}
        for key in ['clickToStrictCompleteMs','firstMs','fullMs','maxTaskMs','blockingMs','sampledHeapHighWaterBytes']:
            values=sorted(r[key] for r in selected if r.get(key) is not None)
            if values:out[group][key]={'n':len(values),'median':median(values),'p95':values[math.ceil(.95*len(values))-1],'max':values[-1]}
    return out
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',default='4647511');p.add_argument('--after',default='working');p.add_argument('--profiles',type=int,default=3);p.add_argument('--writes',type=int,default=8);p.add_argument('--cpu',type=float,default=4);p.add_argument('--cases',nargs='+',choices=[c[0] for c in CASES]);p.add_argument('--output',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True);args=p.parse_args()
    if args.output.exists():p.error('Refusing to overwrite measurements; use a new output')
    args.artifacts.mkdir(parents=True,exist_ok=True)
    report={'syntheticOnly':True,'method':'Exact shared v1 fixture per case; initial actual conversion, process-cold and warm offline starts; actual Matrix submit -> native strict oncomplete before Promise publication. Three independent paired profiles; first four new results, next four corrections. CPU throttle is not Android emulation. Memory is sampled JS heap high-water plus post-GC retained, not an absolute process peak.','before':args.before,'after':args.after,'cpuThrottle':args.cpu,'profiles':args.profiles,'writes':args.writes,'platform':platform.platform(),'cases':{}}
    servers=[]
    try:
        for side,ref in [('before',args.before),('after',args.after)]:
            directory=args.artifacts/side;directory.mkdir();server,thread,hashes=artifact(ref,directory);servers.append((server,thread));report[side+'RuntimeSha256']=hashes;report[side+'URL']='http://127.0.0.1:'+str(server.server_port)+'/'
        with sync_playwright() as pw:
            for label,count,mib,shape in CASES:
                if args.cases and label not in args.cases:continue
                print('FIXTURE '+label,flush=True);seed,sizes=fixture(pw,report['beforeURL'],count,mib,shape)
                (args.artifacts/(label+'-fixture.json')).write_text(json.dumps(seed,ensure_ascii=True));case=report['cases'][label]={'sizes':sizes,'fixtureSourceHash':seed['sourceHash'],'fixtureSourceBytes':seed['sourceBytes'],'before':[],'after':[]}
                for i in range(args.profiles):
                    for side in (['before','after'] if i%2==0 else ['after','before']):
                        print(f'BEGIN {label} {side} {i+1}/{args.profiles}',flush=True)
                        try:case[side].append(one_profile(pw,report[side+'URL'],args.artifacts/f'{label}-{side}-{i}',seed,args.cpu,args.writes))
                        except Exception as error:case.setdefault('errors',[]).append({'side':side,'profile':i,'error':str(error)});raise
                        finally:
                            case['statistics']={side:statistics(case[side]) for side in ['before','after'] if case[side]};args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
                print('COMPLETE '+label+' '+json.dumps({side:case['statistics'][side]['all']['clickToStrictCompleteMs'] for side in ['before','after']}),flush=True)
    finally:
        for server,thread in servers:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':main()
