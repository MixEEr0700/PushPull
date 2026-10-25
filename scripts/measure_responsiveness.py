"""Synthetic, isolated browser measurements; never opens an existing user profile.

Example: python scripts/measure_responsiveness.py --ref 4230ca3 --runs 5 --output /tmp/before.json
Use --ref working for the working checkout. Timings include two animation frames
after the expected DOM state. CDP CPU throttling is NOT a physical Android test.
"""
import argparse
from collections import defaultdict
import functools
import http.server
import io
import json
import math
import platform
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_release import ASSETS

# Instrument only the served test artifact, equally for all compared revisions.
# Inclusive spans may overlap. No production instrumentation or stored records.
FUNCTIONS = {
    'app.js': ['render', 'main', 'entriesFor', 'bindingFor', 'persist', 'captureDraft'],
    'indexeddb.js': ['open', 'load', 'save', 'decode', 'verifyRows', 'validateCatalog', 'readDrafts'],
}
PROBE = r"""(() => {
 const p=window.__probe={spans:[],long:[],transactions:[],requests:[]};
 p.time=(name,fn)=>{const start=performance.now();try{return fn()}finally{p.spans.push({name,start,ms:performance.now()-start})}};
 p.async=async(name,fn)=>{const start=performance.now();try{return await fn()}finally{p.spans.push({name,start,ms:performance.now()-start})}};
 new PerformanceObserver(list=>p.long.push(...list.getEntries().map(e=>({start:e.startTime,ms:e.duration})))).observe({type:'longtask',buffered:true});
 const desc=Object.getOwnPropertyDescriptor(Element.prototype,'innerHTML');
 Object.defineProperty(Element.prototype,'innerHTML',{...desc,set(value){return p.time('innerHTML',()=>desc.set.call(this,value))}});
 const transaction=IDBDatabase.prototype.transaction;
 IDBDatabase.prototype.transaction=function(...args){const start=performance.now(),tx=transaction.apply(this,args);tx.addEventListener('complete',()=>p.transactions.push({start,ms:performance.now()-start,mode:args[1]||'readonly'}));return tx};
 const getAll=IDBObjectStore.prototype.getAll;
 IDBObjectStore.prototype.getAll=function(...args){const start=performance.now(),name=this.name,r=getAll.apply(this,args);r.addEventListener('success',()=>p.requests.push({name,start,ms:performance.now()-start,count:r.result.length}));return r};
 window.__twoFrames=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
})();"""

SEED = r"""async ({count,native,archiveBytes})=>{
 const db=await PushPullDB.open(()=>{throw Error('fixture must already exist')}),d=db.value;
 const journal=await import('./model/journal.mjs'),v2=await import('./model/v2-plan.mjs'),perf=await import('./model/performance.mjs');
 if(native){await db.prepareModel({backupText:JSON.stringify(db.export()),ownerId:'synthetic-perf'});d.trainingJournal=journal.initialize('synthetic-perf');v2.activate(d,'2026-01-01T00:00:00.000Z')}
 for(let n=0;n<count;n++){
  const type=['PUSH A','PULL A','PUSH B','PULL B'][n%4],sid='synthetic-'+n;
  const session={id:sid,seq:n+1,type,date:new Date(Date.UTC(2025,0,n+1)).toISOString().slice(0,10),status:'done'};d.sessions.push(session);
  if(native)await journal.startSession(d,session,'2026-01-01T00:00:00.000Z');
  for(const ex of journal.exercisesFor(d,session)){
   const e={id:sid+'-'+ex.id,sessionId:sid,exerciseId:ex.id,kg:'20',reps:'8'};
   if(native){e.performance=perf.newPerformance(ex);if(e.performance.loadConvention.basis===null)e.performance.loadConvention.basis='machine-indication';for(const r of e.performance.rows)for(const s of r.segments){s.kg='20';s.reps='8'}e.series=perf.flatten(e.performance);journal.recordEntry(d,e)}
   else e.series=Array.from({length:ex.sets},()=>({kg:'20',reps:'8'}));
   d.entries.push(e);
  }
 }
 // A synthetic raw archive; no deletion, import or migration of real data.
 const archives=archiveBytes?[{id:'synthetic-archive',kind:'recovery',createdAt:'2026-01-01T00:00:00.000Z',raw:'x'.repeat(archiveBytes)}]:[];
 await db.commit(d,{importedArchives:archives});
 const sizes={sessions:d.sessions.length,entries:d.entries.length,snapshots:d.trainingJournal?.sessionSnapshots.length||0,liveBytes:new TextEncoder().encode(JSON.stringify(d)).length,archiveBytes};db.close();return sizes;
}"""


def instrument(name, text):
    for fn in FUNCTIONS.get(name, []):
        pattern = re.compile(r'(?P<async>async\s+)?function\s+' + fn + r'\(')
        def replace(match):
            asynchronous = bool(match.group('async'))
            method = 'async' if asynchronous else 'time'
            wrapper = ('async ' if asynchronous else '') + f"function {fn}(...args){{return window.__probe.{method}('{fn}',()=>__measured_{fn}(...args))}}\n"
            return wrapper + ('async ' if asynchronous else '') + f'function __measured_{fn}('
        text = pattern.sub(replace, text, count=1)
    return text


class Server(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        name = self.path.split('?')[0].lstrip('/') or 'index.html'
        # Serve the built runtime allowlist, never the repository or reports.
        if name not in {*ASSETS, 'sw.js', 'release.json'}:
            self.send_error(404)
            return
        body = (Path(self.directory) / name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', self.guess_type(name))
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'max-age=3600' if name not in ['index.html','sw.js'] else 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def phase(page, expression, ready):
    start = page.evaluate('performance.now()')
    page.evaluate(expression)
    page.wait_for_function(ready, timeout=180000)
    page.evaluate('window.__twoFrames()')
    end = page.evaluate('performance.now()')
    return page.evaluate(r"""({start,end})=>{
     const p=window.__probe,spans=p.spans.filter(x=>x.start>=start&&x.start<=end),long=p.long.filter(x=>x.start>=start&&x.start<=end);
     return {ms:end-start,spans,longTasks:long.length,maxTaskMs:Math.max(0,...long.map(x=>x.ms)),blockingMs:long.reduce((a,x)=>a+Math.max(0,x.ms-50),0),transactions:p.transactions.filter(x=>x.start>=start&&x.start<=end),requests:p.requests.filter(x=>x.start>=start&&x.start<=end)};
    }""", {'start': start, 'end': end})


def navigate(page, url):
    page.goto(url, wait_until='domcontentloaded')
    page.wait_for_function("document.querySelector('[data-act=start]')", timeout=180000)
    page.evaluate('window.__twoFrames()')
    end = page.evaluate('performance.now()')
    # Navigation resets the performance time origin.
    return page.evaluate(r"""end=>({ms:end,spans:__probe.spans,longTasks:__probe.long.length,maxTaskMs:Math.max(0,...__probe.long.map(x=>x.ms)),blockingMs:__probe.long.reduce((a,x)=>a+Math.max(0,x.ms-50),0),transactions:__probe.transactions,requests:__probe.requests})""", end)


def measure(browser, url, count, native, archive_bytes, cpu, offline):
    # Each repetition starts a new browser context. Only synthetic DB is touched.
    context = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='allow' if offline else 'block')
    context.add_init_script(PROBE)
    page = context.new_page()
    page.on('dialog', lambda dialog: dialog.accept())
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        navigate(page, url)
        sizes = page.evaluate(SEED, {'count': count, 'native': native, 'archiveBytes': archive_bytes})
        # Finish fixture setup outside the measurements. A closed tab cannot leak
        # its history-change BroadcastChannel into the measured application.
        page.close()
        page = context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        page.on('pageerror', lambda error: errors.append(str(error)))
        cdp = context.new_cdp_session(page)
        cdp.send('Emulation.setCPUThrottlingRate', {'rate': cpu})
        cdp.send('Network.clearBrowserCache')
        phases = {'cold': navigate(page, url), 'warm': navigate(page, url)}
        if offline:
            page.evaluate('navigator.serviceWorker.ready')
            page.wait_for_function('navigator.serviceWorker.controller!==null')
            context.set_offline(True)
            phases['offline'] = navigate(page, url)
        # JS click avoids Playwright actionability/scroll overhead in the latency.
        phases['start'] = phase(page, "document.querySelector('[data-act=start]').click()", "document.querySelector('[data-act=finish]')")
        phases['exercise'] = phase(page, "document.querySelector('[data-expand=\"PUSH-A-1\"]').click()", "document.querySelector('[data-panel=result]')")
        form = '.performanceForm' if native else '.seriesResultForm'
        phases['editor'] = phase(page, "document.querySelector('[data-panel=result]').click()", f"document.querySelector('{form}')")
        kg = '[data-quick=kg]' if native else '[data-main=kg]'
        reps = '[data-quick=reps]' if native else '[data-main=reps]'
        phases['input'] = phase(page, f"""()=>{{for(const [selector,value] of [[{json.dumps(kg)},'21'],[{json.dumps(reps)},'9']]){{const el=document.querySelector(selector);if(!el)throw Error('missing input '+selector);el.value=value;el.dispatchEvent(new Event('input',{{bubbles:true}}))}}}}""", "document.querySelector('[data-draft-status]')?.textContent.includes('Szkic zapisany lokalnie')")
        phases['save'] = phase(page, f"document.querySelector('{form}').requestSubmit()", f"!document.querySelector('{form}')")
        phases['navigation'] = phase(page, "document.querySelector('[data-tab=calendar]').click()", "document.querySelector('[data-act=prevMonth]')")
        if errors:
            raise RuntimeError(errors)
        return {'sizes': sizes, 'phases': phases}
    finally:
        context.close()


def summarize(rows):
    out = {}
    for name in rows[0]['phases']:
        samples = [r['phases'][name] for r in rows]
        times = sorted(s['ms'] for s in samples)
        spans = defaultdict(list)
        for sample in samples:
            totals = defaultdict(float)
            for span in sample['spans']:
                totals[span['name']] += span['ms']
            for key, value in totals.items():
                spans[key].append(value)
        out[name] = {'medianMs': times[len(times)//2], 'p95Ms': times[math.ceil(len(times)*.95)-1],
                     'maxTaskMs': max(s['maxTaskMs'] for s in samples),
                     'medianBlockingMs': sorted(s['blockingMs'] for s in samples)[len(times)//2],
                     'meanInclusiveSpansMs': {key: sum(values)/len(samples) for key,values in spans.items()}}
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='working')
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--cpu', type=float, default=4)
    parser.add_argument('--counts', type=int, nargs='+', default=[4, 400])
    parser.add_argument('--v2-counts', type=int, nargs='+', default=[4, 40])
    parser.add_argument('--kinds', nargs='+', choices=['legacy','v2'], default=['legacy','v2'])
    parser.add_argument('--archive-mib', type=int, default=4)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    if args.runs<1:parser.error('--runs must be positive')
    if args.cpu<1 or args.archive_mib<0 or any(n<0 for n in [*args.counts,*args.v2_counts]):
        parser.error('CPU rate must be >=1; archive size and counts must be nonnegative')
    with tempfile.TemporaryDirectory(prefix='pushpull-perf-') as temporary:
        directory=Path(temporary)
        if args.ref=='working':
            source=ROOT
        else:
            source=directory/'source';source.mkdir()
            raw=subprocess.check_output(['git','archive',args.ref],cwd=ROOT)
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                archive.extractall(source,filter='data')
        # Rehash the instrumented copy so the actual SW integrity checks work.
        builder=runpy.run_path(str(source/'scripts/build_release.py'))
        staging=directory/'instrumented'
        for name in builder['ASSETS']:
            target=staging/name;target.parent.mkdir(parents=True,exist_ok=True)
            body=(source/name).read_bytes()
            target.write_bytes(instrument(name,body.decode()).encode() if name in FUNCTIONS else body)
        (staging/'scripts').mkdir()
        shutil.copyfile(source/'scripts/service-worker.template.js',staging/'scripts/service-worker.template.js')
        builder['build'](directory/'site',staging)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Server,directory=str(directory/'site')))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        report={'ref':args.ref,'runs':args.runs,'cpuThrottle':args.cpu,'offline':args.offline,'viewport':[390,844],'platform':platform.platform(),'processor':platform.processor(),'scenarios':{}}
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
                report['browser']=browser.version
                for kind in args.kinds:
                    for count in args.v2_counts if kind=='v2' else args.counts:
                        name=f'{kind}-{count}'
                        rows=[]
                        for run in range(args.runs):
                            rows.append(measure(browser,f'http://127.0.0.1:{server.server_port}/',count,kind=='v2',args.archive_mib*1024*1024,args.cpu,args.offline))
                            print(f'{name} {run+1}/{args.runs}',flush=True)
                        report['scenarios'][name]={'summary':summarize(rows),'samples':rows}
                        args.output.write_text(json.dumps(report,indent=2)+'\n')
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    main()
