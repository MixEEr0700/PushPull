"""Synthetic finish clocks; isolated exact protocol-v2 fixtures, no Android claims.
Run serially without concurrent tests. Source archives stay in the database.
Native strict complete uses the existing benchmark-only transaction probe.
"""
import argparse,hashlib,json,math,platform,shutil
from pathlib import Path
from statistics import median
from playwright.sync_api import sync_playwright
from measure_incremental_write import artifact,inject_fixture

PROBE='''(()=>{
 window.__writeMarks=[];window.__click=0;window.__panel=0;window.__finalDOM=0;
 document.addEventListener('click',e=>{if(e.target.closest('[data-act=finish],[data-finish-save]')){window.__click=performance.now();window.__writeMarks=[];performance.clearMarks();}},true);
 const seen=new WeakSet(),del=IDBObjectStore.prototype.delete;IDBObjectStore.prototype.delete=function(key){if(this.name==='meta'&&String(key).startsWith('workout-draft:')&&!seen.has(this.transaction)){const tx=this.transaction;seen.add(tx);tx.addEventListener('complete',event=>__writeMarks.push({name:'draft-cleanup-complete',at:performance.now(),eventTimeStamp:event.timeStamp,durability:tx.durability}))}return del.call(this,key)};
 new MutationObserver(()=>{if(document.querySelector('[data-finish-panel]')&&!window.__panel)window.__panel=performance.now();if(!window.__finalDOM&&window.__click&&document.querySelector('[data-act=start]')&&!document.querySelector('[data-draft-discard]'))window.__finalDOM=performance.now()}).observe(document,{childList:true,subtree:true});
})();'''
ORACLE='''async()=>{const d=await PushPullDB.open(()=>{});try{const before=window.__before,after=d.value;return {history:before.entries.every(e=>JSON.stringify(e)===JSON.stringify(after.entries.find(x=>x.id===e.id))),snapshots:before.trainingJournal.sessionSnapshots.every(s=>JSON.stringify(s)===JSON.stringify(after.trainingJournal.sessionSnapshots.find(x=>x.id===s.id))),model:JSON.stringify(before.trainingJournal.model)===JSON.stringify(after.trainingJournal.model),archives:JSON.stringify(window.__beforeArchives)===JSON.stringify(d.export().archives),active:after.activeId,sessions:after.sessions.length,entries:after.entries.length,drafts:(await d.readDrafts()).length}}finally{d.close()}}'''

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--repeats',type=int,default=3);p.add_argument('--cpu',type=float,default=4);p.add_argument('--after-only',type=Path,help='reuse completed unchanged baseline report; remeasure changed runtime only');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
 report={'syntheticOnly':True,'platform':platform.platform(),'cpuThrottle':args.cpu,'repeats':args.repeats,'cases':{}}
 if args.after_only:
  previous=json.loads(args.after_only.read_text());report['before']=previous['before'];report['reusedBeforeReport']=str(args.after_only);report['cases']={k:{'before':v['before']} for k,v in previous['cases'].items() if 'before' in v}
 with sync_playwright() as pw:
  for ref in (['working'] if args.after_only else ['de84e6361ad18baeb17a1b51c7fae88b92fd7390','working']):
   label='before' if ref!='working' else 'after';server,thread,hashes,release=artifact(ref,args.output/label);url=f'http://127.0.0.1:{server.server_port}/'
   try:
    report[label]={'ref':ref,'runtimeSHA256':hashes,'instrumentedRelease':release}
    browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--enable-precise-memory-info'])
    for case in ['small','history40-raw4']:
     path=args.fixtures/(case+'-fixture.json');seed=json.loads(path.read_text())
     for batch in ([False,True] if label=='after' else [False]):
      key=case+('-drafts3' if batch else '-saved3');rows=report['cases'].setdefault(key,{}).setdefault(label,[])
      for n in range(args.repeats):
       context=browser.new_context(service_workers='block',viewport={'width':390,'height':844});context.add_init_script(PROBE);page=context.new_page();page.on('dialog',lambda d:d.accept());errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
       page.goto(url+'benchmark.html');inject_fixture(page,seed);page.goto(url);page.wait_for_selector('[data-act=start]',timeout=120000)
       cdp=context.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':args.cpu})
       page.evaluate('''async()=>{const h=await PushPullDB.open(()=>{});try{window.__before=structuredClone(h.value);window.__beforeArchives=h.export().archives;if(!Array.isArray(__beforeArchives))throw Error('Missing archive oracle')}finally{h.close()}}''')
       page.locator('[data-type="PUSH A"]').click();page.locator('[data-act=start]').click();page.wait_for_selector('[data-act=finish]')
       for eid in ['PUSH-A-1','PUSH-A-2','PUSH-A-3']:
        page.locator('[data-expand="'+eid+'"]').click();f=page.locator('.performanceForm');f.locator('[data-quick=kg]').fill('40');f.locator('[data-quick=reps]').fill('10');page.wait_for_function("document.querySelector('[data-draft-status]')?.textContent.includes('Szkic zapisany lokalnie')")
        if not batch:f.locator('[type=submit]').click();page.wait_for_function("!document.querySelector('.performanceForm')")
       page.locator('[data-act=finish]').click()
       panel=None
       if batch:
        page.wait_for_selector('[data-finish-save]');panel=page.evaluate('__panel-__click');page.locator('[data-finish-save]').click()
       page.wait_for_selector('[data-act=start]',timeout=120000)
       # Wait for post-commit draft cleanup too; never time the success toast as durability.
       page.wait_for_function("!document.querySelector('[data-draft-resume],[data-draft-discard]')")
       values=page.evaluate('''()=>{const marks=__writeMarks,strict=marks.filter(m=>m.name==='strict-complete'),last=strict.at(-1);if(!last||strict.some(m=>m.durability!=='strict'))throw Error('Missing strict native event');return {clickToStrictCompleteMs:last.at-__click,nativeStrict:strict,writeMarks:marks,appMarks:performance.getEntriesByType('mark').map(m=>({name:m.name,at:m.startTime})),panelOpenMs:null,finalDOMReadyAt:window.__finalDOM,heapBytes:performance.memory.usedJSHeapSize}}''')
       if len(values['nativeStrict'])!=(4 if batch else 1):raise ValueError('Unexpected native command count')
       values['panelOpenMs']=panel;values['oracle']=page.evaluate(ORACLE);values['fixtureSHA256']=hashlib.sha256(path.read_bytes()).hexdigest()
       if errors or not all(values['oracle'][k] for k in ['history','snapshots','model','archives']) or values['oracle']['active'] is not None or values['oracle']['drafts']:raise ValueError({'errors':errors,'oracle':values['oracle']})
       rows.append(values);(args.output/'report.json').write_text(json.dumps(report,indent=2));print(label,key,n,round(values['clickToStrictCompleteMs'],2),flush=True);context.close()
    browser.close()
   finally:server.shutdown();server.server_close();thread.join()
 for case,variants in report['cases'].items():
  for label,rows in list(variants.items()):
   numbers=sorted(r['clickToStrictCompleteMs'] for r in rows);variants[label+'Stats']={'medianMs':median(numbers),'p95Ms':numbers[math.ceil(.95*len(numbers))-1],'n':len(numbers)}
 (args.output/'report.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
