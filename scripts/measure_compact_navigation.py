"""Stages F/G: synthetic, offline navigation only (no repeated full exports).
Uses retained Stage E captures, isolated browser profiles and real IndexedDB.
CPU throttling is not a physical Android measurement. Run serially.
"""
import argparse,hashlib,json,math,platform
from pathlib import Path
from statistics import median
from playwright.sync_api import sync_playwright
from measure_startup import artifact,PROBE
from measure_incremental_write import launch,inject_fixture,ready

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ref',required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--cases',nargs='+',default=['small','history40-raw4','history400-raw4']);p.add_argument('--repeats',type=int,default=5);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 report={'syntheticOnly':True,'ref':a.ref,'cpuThrottle':4,'platform':platform.platform(),'cases':{}}
 server,thread,hashes,release=artifact(a.ref,a.output/'artifact');report['runtimeSha256']=hashes;report['instrumentedRelease']=release
 try:
  with sync_playwright() as pw:
   for case in a.cases:
    path=a.fixtures/(case+'-after-captured.json');seed=json.loads(path.read_text());context=launch(pw,a.output/(case+'-profile'));context.add_init_script(PROBE);page=context.new_page();url=f'http://127.0.0.1:{server.server_port}/';page.goto(url+'benchmark.html');inject_fixture(page,seed);page.close();page=context.new_page();cdp=context.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':4});page.goto(url,timeout=600000);ready(page);page.evaluate('navigator.serviceWorker.ready');page.wait_for_function('navigator.serviceWorker.controller!==null');context.set_offline(True)
    page.evaluate("""()=>{
     window.__click=0;window.__navNative=null;
     document.addEventListener('click',e=>{if(e.target.closest('[data-tab=settings]')){__click=performance.now();__navNative={click:__click}}},true);
     new MutationObserver(()=>{const n=__navNative;if(!n||n.domAt!==undefined||document.querySelector('h1')?.textContent!=='Dane i kopia zapasowa')return;
      n.domAt=performance.now();requestAnimationFrame(()=>requestAnimationFrame(()=>n.twoFramesAt=performance.now()));
     }).observe(document.getElementById('app'),{childList:true,subtree:true});
    }""")
    runs=[]
    for n in range(a.repeats):
     if n:page.locator('[data-tab=training]').click()
     page.locator('[data-tab=settings]').click();page.wait_for_function("document.querySelector('h1')?.textContent==='Dane i kopia zapasowa'")
     sample=page.evaluate("""()=>({ms:performance.now()-__click,requests:__startup.requests.filter(s=>s.start>=__click).length,spans:__startup.spans.filter(s=>s.start>=__click),heapBytes:performance.memory.usedJSHeapSize})""")
     # Preserve old RPC-inclusive ms; separately record in-page DOM/two-frame clocks.
     page.wait_for_function('__navNative?.twoFramesAt!==undefined')
     sample.update(page.evaluate('()=>({nativeDomMs:__navNative.domAt-__navNative.click,nativeTwoFramesMs:__navNative.twoFramesAt-__navNative.click})'))
     runs.append(sample)
    for width in [360,390,412]:
     page.set_viewport_size({'width':width,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(a.output/(case+'-'+str(width)+'.png')),full_page=True)
    values=sorted(r['ms'] for r in runs);report['cases'][case]={'fixtureSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'runs':runs,'medianMs':median(values),'p95Ms':values[math.ceil(len(values)*.95)-1]}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(case,report['cases'][case]['medianMs'],report['cases'][case]['p95Ms'],flush=True);context.close()
 finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':main()
