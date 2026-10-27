"""Issue90 synthetic offline navigation and explicit JSON export; no user data."""
import argparse,json,sys,hashlib,platform,math
from pathlib import Path
from statistics import median
from playwright.sync_api import sync_playwright
from measure_startup import artifact,PROBE
from measure_incremental_write import launch,inject_fixture,ready

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--before',default='cbbf2d1');p.add_argument('--after',default='working');p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--repeats',type=int,default=3);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 report={'syntheticOnly':True,'cpuThrottle':4,'platform':platform.platform(),'repeats':a.repeats,'cases':{},'artifacts':{}}
 try:
  with sync_playwright() as pw:
   for side,ref in [('before',a.before),('after',a.after)]:
    server,thread,hashes,release=artifact(ref,a.output/side);report['artifacts'][side]={'ref':ref,'hashes':hashes,'release':release}
    try:
     url=f'http://127.0.0.1:{server.server_port}/'
     for case in ['empty','history40-raw4','history40-escaped16','history400-raw4','history400-escaped16']:
      path=a.fixtures/(case+'-after-captured.json');seed=json.loads(path.read_text());context=launch(pw,a.output/(side+'-'+case));context.add_init_script(PROBE);page=context.new_page();page.goto(url+'benchmark.html');inject_fixture(page,seed);page.close()
      runs=[];report['cases'].setdefault(case,{'fixtureSHA256':hashlib.sha256(path.read_bytes()).hexdigest()})[side]=runs
      for trial in range(a.repeats):
       page=context.new_page();cdp=context.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':4});page.goto(url,timeout=600000);ready(page);page.evaluate('navigator.serviceWorker.ready');page.wait_for_function('navigator.serviceWorker.controller!==null');context.set_offline(True)
       page.evaluate("""()=>{window.__click=0;document.addEventListener('click',e=>{if(e.target.closest('[data-tab=settings]'))__click=performance.now()},true)}""")
       page.locator('[data-tab=settings]').click();page.wait_for_function("document.querySelector('h1')?.textContent==='Dane i kopia zapasowa'",timeout=600000)
       nav=page.evaluate("""()=>({ms:performance.now()-__click,spans:__startup.spans.filter(s=>s.start>=__click),requests:__startup.requests.filter(s=>s.start>=__click).length,heap:performance.memory.usedJSHeapSize})""")
       # Real file generation and download, including full audit on the lazy path.
       page.evaluate("""()=>{window.__exportClick=0;document.addEventListener('click',e=>{if(e.target.closest('[data-act=export]'))__exportClick=performance.now()},true)}""")
       with page.expect_download(timeout=600000) as download:page.locator('[data-act=export]').click()
       export=page.evaluate("""()=>({ms:performance.now()-__exportClick,spans:__startup.spans.filter(s=>s.start>=__exportClick)})""");file=Path(download.value.path());export['fileBytes']=file.stat().st_size;export['sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
       runs.append({'trial':trial,'navigation':nav,'export':export});(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(side,case,trial,round(nav['ms']),round(export['ms']),flush=True);page.close()
      context.close()
    finally:server.shutdown();server.server_close();thread.join()
 finally:(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
