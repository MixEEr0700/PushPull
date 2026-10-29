"""Synthetic note write pipeline; immutable before/after releases, native strict clock.
Never opens a user profile. Run serially; results are not Pixel measurements.
"""
import argparse,functools,hashlib,http.server,io,json,math,platform,runpy,shutil,subprocess,tarfile,threading
from pathlib import Path
from statistics import median
from playwright.sync_api import sync_playwright
from measure_incremental_write import ROOT,Server,inject_fixture

PROBE=r"""(()=>{
window.__noteTiming=null;
document.addEventListener('click',e=>{if(e.target.closest('.v2NoteForm [type=submit]'))window.__noteTiming={click:performance.now(),stages:[],tx:[]}},true);
document.addEventListener('submit',e=>{if(e.target.matches('.v2NoteForm')&&!window.__noteTiming)window.__noteTiming={click:performance.now(),stages:[],tx:[]}},true);
const native=IDBDatabase.prototype.transaction;
IDBDatabase.prototype.transaction=function(...a){const tx=native.apply(this,a);if(window.__noteTiming&&tx.mode==='readwrite'&&[...tx.objectStoreNames].includes('journalState')){
 const m={start:performance.now(),durability:tx.durability};__noteTiming.tx.push(m);tx.addEventListener('complete',e=>{m.complete=e.timeStamp});}return tx};
})();"""

FINGERPRINT=r"""async()=>{
 const h=await PushPullDB.open(()=>{throw Error('missing synthetic database')});try{
  if(h.error)throw h.error;const source=h.export(),j=source.data.trainingJournal,m=j.model,p=m.positions.find(p=>p.exerciseId==='PUSH-A-1'&&p.planVersionId===j.activePlanVersionId)??m.positions.find(p=>p.exerciseId==='PUSH-A-1');
  const id='user:'+p.planVersionId+':PUSH-A-1',note=m.userNotes.find(n=>n.id===id);m.userNotes=m.userNotes.filter(n=>n.id!==id);
  const bytes=new TextEncoder().encode(JSON.stringify(source));return {sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join(''),note:note?{text:note.text,revision:note.revision}:null};
 }finally{h.close()}
}"""

def artifact(ref,directory):
 source=directory/'source';source.mkdir(parents=True)
 if ref=='working':
  builder=runpy.run_path(str(ROOT/'scripts/build_release.py'))
  for name in [*builder['ASSETS'],'scripts/service-worker.template.js']:
   target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
 else:
  with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',ref],cwd=ROOT))) as tar:tar.extractall(source,filter='data')
 builder=runpy.run_path(str(ROOT/'scripts/build_release.py'));hashes={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in builder['ASSETS'] if name!='sw.js'}
 app=source/'app.js';text=app.read_text();needle="performance.mark('pushpull-database-ready');"
 if text.count(needle)!=1:raise ValueError('database marker')
 text=text.replace(needle,needle+"\nfor(const name of ['ensureHistory','commit','saveUserNote'])if(typeof database[name]==='function'){const original=database[name];Object.defineProperty(database,name,{value:async(...args)=>{const t=window.__noteTiming,m={name,start:performance.now()};if(t)t.stages.push(m);try{return await original(...args)}finally{m.end=performance.now()}},configurable:true});}" )
 text=text.replace('function render(){',"function render(){const noteRender=window.__noteTiming&&{name:'render',start:performance.now()};",1)
 text=text.replace('paintPwa();paintFullAudit();paintDrive();',"paintPwa();paintFullAudit();paintDrive();if(noteRender){noteRender.end=performance.now();window.__noteTiming.stages.push(noteRender)};",1) if 'paintPwa();paintFullAudit();paintDrive();' in text else text.replace('paintPwa();paintFullAudit();paintDrive()}',"paintPwa();paintFullAudit();paintDrive();if(noteRender){noteRender.end=performance.now();window.__noteTiming.stages.push(noteRender)}}",1)
 app.write_text(text);release=builder['build'](directory/'site',source)
 handler=type('NoteBenchmark',(Server,),{'allowed':set(builder['FILES'])})
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(handler,directory=str(directory/'site')));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 return server,thread,hashes,release

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ref',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--cases',nargs='+',default=['small','history40-raw4']);p.add_argument('--repeats',type=int,default=5);p.add_argument('--cpu',type=float,default=4);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 report={'syntheticOnly':True,'ref':a.ref,'cpuThrottle':a.cpu,'platform':platform.platform(),'cases':{}}
 server,thread,hashes,release=artifact(a.ref,a.output/'runtime');report.update(runtimeSHA256=hashes,release=release)
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);report['chromiumVersion']=browser.version;url=f'http://127.0.0.1:{server.server_port}/'
   for case in a.cases:
    fixture=a.fixtures/(case+'-fixture.json');seed=json.loads(fixture.read_text());rows=report['cases'].setdefault(case,[])
    for n in range(a.repeats):
     c=browser.new_context(service_workers='block',viewport={'width':390,'height':844});c.add_init_script(PROBE);page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d: (errors.append(d.message),d.accept()))
     page.goto(url+'benchmark.html');inject_fixture(page,seed);page.goto(url);page.wait_for_selector('[data-act=start]',timeout=180000)
     oracleBefore=page.evaluate(FINGERPRINT)
     # Conversion/index setup is outside the note clock. Reload restores selective cold view.
     page.reload();page.wait_for_selector('[data-act=start]',timeout=180000)
     page.locator('[data-expand="PUSH-A-1"]').click();page.locator('[data-note-toggle]').click();note=page.locator('[data-personal-note]');note.locator('summary').click();note.locator('textarea').fill('Synthetic note Ł 😀 '+str(n))
     cdp=c.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':a.cpu})
     note.locator('[type=submit]').click();page.wait_for_function("document.querySelector('.toast')?.textContent==='Notatka zapisana'",timeout=180000)
     value=page.evaluate("""async()=>{await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);const t=window.__noteTiming;return {...t,paint:performance.now()}}""")
     if errors or len(value['tx'])!=1 or value['tx'][0]['durability']!='strict' or 'complete' not in value['tx'][0]:raise ValueError({'errors':errors,'timing':value})
     value['clickToStrictMs']=value['tx'][0]['complete']-value['click'];value['nativeTransactionMs']=value['tx'][0]['complete']-value['tx'][0]['start'];value['clickToPaintMs']=value['paint']-value['click'];value['fixtureSHA256']=hashlib.sha256(fixture.read_bytes()).hexdigest()
     cdp.send('Emulation.setCPUThrottlingRate',{'rate':1});oracleAfter=page.evaluate(FINGERPRINT)
     if oracleBefore['sha256']!=oracleAfter['sha256'] or oracleAfter['note']!={'text':'Synthetic note Ł 😀 '+str(n),'revision':(oracleBefore['note']['revision'] if oracleBefore['note'] else 0)+1}:raise ValueError('Note or unchanged full-history/archive oracle failed')
     value['unchangedSourceSHA256']=oracleAfter['sha256'];value['oraclePass']=True;rows.append(value)
     (a.output/'report.json').write_text(json.dumps(report,indent=2));print(case,n,round(value['clickToStrictMs'],1),flush=True);c.close()
   browser.close()
  report['stats']={case:{k:{'median':median(v[k] for v in rows),'p95':sorted(v[k] for v in rows)[math.ceil(.95*len(rows))-1],'n':len(rows)} for k in ['clickToStrictMs','nativeTransactionMs','clickToPaintMs']} for case,rows in report['cases'].items()};(a.output/'report.json').write_text(json.dumps(report,indent=2))
 finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':main()
