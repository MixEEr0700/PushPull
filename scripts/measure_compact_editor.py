"""Issue99 before/after compact editor, isolated synthetic v2 databases.
Serial only; native strict complete is instrumented in immutable test artifacts.
Not an Android result. Never uses an existing browser profile or user database.
"""
import argparse,hashlib,json,math,platform,shutil
from pathlib import Path
from statistics import median
from playwright.sync_api import sync_playwright
from measure_incremental_write import artifact,inject_fixture
from measure_finish import ORACLE

PROBE='''(()=>{
window.__writeMarks=[];
document.addEventListener('click',e=>{
 if(e.target.closest('[data-rich-action=toggle]'))window.__editorClick=performance.now();
 if(e.target.closest('.performanceForm [type=submit]')){window.__saveClick=performance.now();window.__writeMarks=[];}
},true);
new MutationObserver(()=>{if(window.__editorClick&&!window.__editorDOM&&document.querySelector('[data-rich-details]:not([hidden])'))window.__editorDOM=performance.now()}).observe(document,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
})();'''

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--fixtures',required=True,type=Path);p.add_argument('--repeats',type=int,default=3);p.add_argument('--cpu',type=float,default=4);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
 report={'syntheticOnly':True,'platform':platform.platform(),'cpuThrottle':args.cpu,'repeats':args.repeats,'width':390,'cases':{}}
 with sync_playwright() as pw:
  for ref in ['42fc1010092c7adea0ad3520a493f7600d9b1bdc','working']:
   label='before' if ref!='working' else 'after';server,thread,hashes,release=artifact(ref,args.output/label);url=f'http://127.0.0.1:{server.server_port}/';report[label]={'ref':ref,'runtimeSHA256':hashes,'instrumentedRelease':release}
   try:
    browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--enable-precise-memory-info'])
    report[label]['chromiumVersion']=browser.version
    for case in ['small','history40-raw4']:
     fixture=args.fixtures/(case+'-fixture.json');seed=json.loads(fixture.read_text())
     for kind,unit,eid in [('plain','PUSH A','PUSH-A-1'),('drop','PUSH A','PUSH-A-5'),('lp','PULL A','PULL-A-1')]:
      rows=report['cases'].setdefault(case+'-'+kind,{}).setdefault(label,[])
      for n in range(args.repeats):
       context=browser.new_context(service_workers='block',viewport={'width':390,'height':844});context.add_init_script(PROBE);page=context.new_page();page.on('dialog',lambda d:d.accept());errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
       page.goto(url+'benchmark.html');inject_fixture(page,seed);page.goto(url);page.wait_for_selector('[data-act=start]',timeout=120000)
       cdp=context.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':args.cpu})
       page.evaluate('''async()=>{const h=await PushPullDB.open(()=>{});try{window.__before=structuredClone(h.value);window.__beforeArchives=h.export().archives;if(!Array.isArray(__beforeArchives))throw Error('Missing archive oracle')}finally{h.close()}}''')
       page.locator('[data-type="'+unit+'"]').click();page.locator('[data-act=start]').click();page.wait_for_selector('[data-act=finish]');page.locator('[data-expand="'+eid+'"]').click()
       f=page.locator('.performanceForm');f.locator('[data-quick=kg]').fill('24');f.locator('[data-quick=reps]').fill('10')
       f.locator('[data-rich-action=toggle]').click()
       # Drop fields are separate real segments in both releases.
       for el in f.locator('[data-field=kg]').all():el.fill('24')
       for el in f.locator('[data-field=reps]').all():el.fill('10')
       page.wait_for_function("document.querySelector('[data-draft-status]')?.textContent.includes('Szkic zapisany lokalnie')")
       values=page.evaluate('''()=>{const f=document.querySelector('.performanceForm'),d=f.querySelector('[data-rich-details]');return {editorDOMMs:__editorDOM-__editorClick,detailsHeightPx:d.getBoundingClientRect().height,detailsElements:d.querySelectorAll('*').length,detailsInputs:d.querySelectorAll('input').length,heapWithFixtureAndOracleBytes:performance.memory.usedJSHeapSize}}''')
       f.locator('[type=submit]').click();page.wait_for_function("!document.querySelector('.performanceForm')")
       values.update(page.evaluate('''()=>{const strict=__writeMarks.filter(m=>m.name==='strict-complete');if(strict.length!==1||strict[0].durability!=='strict')throw Error('Native durability missing');return {clickToStrictCompleteMs:strict[0].eventTimeStamp-__saveClick,nativeStrict:strict,writeMarks:__writeMarks}}'''))
       values['oracle']=page.evaluate(ORACLE);values['fixtureSHA256']=hashlib.sha256(fixture.read_bytes()).hexdigest()
       values['resultOracle']=page.evaluate('''async eid=>{const d=await PushPullDB.open(()=>{});try{const e=d.value.entries.find(e=>e.exerciseId===eid&&e.sessionId===d.value.activeId),rows=e.performance.rows;return {rows:rows.length,segments:e.series.length,tonnage:e.series.reduce((n,s)=>n+Number(s.kg)*Number(s.reps),0),sides:rows.map(r=>r.side),all24x10:e.series.every(s=>s.kg==='24'&&s.reps==='10')}}finally{d.close()}}''',eid)
       expected=1440 if kind in ['lp','drop'] else 720
       if errors or not all(values['oracle'][k] for k in ['history','snapshots','model','archives']) or values['oracle']['drafts'] or not values['resultOracle']['all24x10'] or values['resultOracle']['tonnage']!=expected:raise ValueError({'errors':errors,'values':values})
       rows.append(values);(args.output/'report.json').write_text(json.dumps(report,indent=2));print(label,case,kind,n,round(values['clickToStrictCompleteMs'],1),flush=True);context.close()
    browser.close()
   finally:server.shutdown();server.server_close();thread.join()
 for case,variants in report['cases'].items():
  for label,rows in list(variants.items()):
   variants[label+'Stats']={}
   for key in ['clickToStrictCompleteMs','editorDOMMs','detailsHeightPx','detailsElements','detailsInputs','heapWithFixtureAndOracleBytes']:
    numbers=sorted(r[key] for r in rows);variants[label+'Stats'][key]={'median':median(numbers),'p95':numbers[math.ceil(.95*len(numbers))-1],'n':len(numbers)}
 (args.output/'report.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
