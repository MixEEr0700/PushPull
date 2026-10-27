"""Issue 75: isolated synthetic UI timings, never a real user profile.

First visible feedback/full view are two-rAF DOM proxies, NOT physical touch-to-
photon measurements. Durable = strict history transaction's complete event.
A process-cold run reopens a seeded persistent profile; OS caches remain warm.
Run serially, without tests/other benchmarks: --ref REF --runs 5 --output PATH.
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

from playwright.sync_api import sync_playwright
from measure_responsiveness import ROOT, Server, PROBE, SEED, instrument

UI_PROBE = PROBE + r"""(() => {
 const u=window.__ui={commits:[],handlers:[]};
 const put=IDBObjectStore.prototype.put;
 IDBObjectStore.prototype.put=function(value,...args){
  const result=put.call(this,value,...args);
  if(this.name==='meta'&&value?.key==='state'||this.name==='journalState'&&value?.id==='active'){
   const tx=this.transaction;
   tx.addEventListener('complete',()=>u.commits.push({at:performance.now(),durability:tx.durability}));
  }
  return result;
 };
 u.frames=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(performance.now()))));
 u.begin=()=>{
  const s=u.sample={start:performance.now(),first:null};
  const observer=new MutationObserver(records=>{
   if(s.first!==null||!records.some(r=>!r.target.parentElement?.closest('[data-pwa-notice],[data-pwa-version]')&&!r.target.closest?.('[data-pwa-notice],[data-pwa-version]')))return;
   if(s.scheduled)return;s.scheduled=true;
   u.frames().then(t=>{s.first=t-s.start});
  });
  observer.observe(document.getElementById('app'),{childList:true,subtree:true,characterData:true});
  s.observer=observer;return s;
 };
 u.end=async()=>{
  const s=u.sample,end=await u.frames();s.observer.disconnect();
  const p=__probe,long=p.long.filter(x=>x.start>=s.start&&x.start<=end);
  return {firstMs:s.first,fullMs:end-s.start,
   durableMs:u.commits.filter(x=>x.at>=s.start&&x.at<=end).map(x=>({ms:x.at-s.start,durability:x.durability})),
   handlerQueueMs:u.handlers.filter(x=>x.at>=s.start&&x.at<=end).map(x=>x.at-x.event),
   spans:p.spans.filter(x=>x.start>=s.start&&x.start<=end),
   maxTaskMs:Math.max(0,...long.map(x=>x.ms)),blockingMs:long.reduce((a,x)=>a+Math.max(0,x.ms-50),0),
   transactions:p.transactions.filter(x=>x.start>=s.start&&x.start<=end)};
 };
})();"""
LEGACY_SEED = r"""async ({count,archiveBytes})=>{
 const db=await PushPullDB.open(()=>{throw Error('missing fixture')}),d=db.value;
 for(let n=0;n<count;n++){
  const type=['PUSH A','PULL A','PUSH B','PULL B'][n%4],id='synthetic-'+n;
  d.sessions.push({id,seq:n+1,type,date:new Date(Date.UTC(2025,0,n+1)).toISOString().slice(0,10),status:'done'});
  for(const ex of d.exercises[type])d.entries.push({id:id+'-'+ex.id,sessionId:id,exerciseId:ex.id,kg:'20',reps:'8',series:Array.from({length:ex.sets},()=>({kg:'20',reps:'8'}))});
 }
 await db.commit(d,{importedArchives:archiveBytes?[{id:'synthetic-archive',kind:'recovery',createdAt:'2026-01-01T00:00:00.000Z',raw:'x'.repeat(archiveBytes)}]:[]});
 const sizes={sessions:d.sessions.length,entries:d.entries.length,liveBytes:new TextEncoder().encode(JSON.stringify(d)).length,archiveBytes};db.close();return sizes;
}"""


def phase(page, action, ready):
    page.evaluate('__ui.begin()')
    page.evaluate(action)
    page.wait_for_function(ready, timeout=180000, polling='raf')
    return page.evaluate('__ui.end()')


def navigate(page, url):
    page.goto(url, wait_until='domcontentloaded', timeout=180000)
    page.wait_for_function("document.querySelector('[data-act=start]')", timeout=180000)
    result=page.evaluate(r"""async()=>{
      const end=await __ui.frames(),p=__probe;
      return {firstMs:performance.getEntriesByName('first-contentful-paint')[0]?.startTime??null,
       fullMs:end,maxTaskMs:Math.max(0,...p.long.map(x=>x.ms)),blockingMs:p.long.reduce((a,x)=>a+Math.max(0,x.ms-50),0),spans:p.spans,transactions:p.transactions};
    }""")
    return result


def sample(pw, url, profile, count, native, cpu, archive_bytes):
    options=dict(executable_path=shutil.which('chromium'),args=['--no-sandbox'],viewport={'width':390,'height':844},service_workers='allow')
    def open_context():
        context=pw.chromium.launch_persistent_context(str(profile),**options)
        context.add_init_script(UI_PROBE)
        page=context.pages[0]
        for other in context.pages[1:]:other.close()
        page.bring_to_front()
        page.on('dialog',lambda dialog:dialog.accept())
        return context,page
    context,page=open_context()
    try:
        navigate(page,url)
        sizes=page.evaluate(SEED if native else LEGACY_SEED,{'count':count,'native':native,'archiveBytes':archive_bytes})
        page.evaluate('navigator.serviceWorker.ready')
    finally:context.close()
    # Reopen an entire browser process with only synthetic persisted records.
    context,page=open_context()
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        cdp=context.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':cpu})
        phases={'processCold':navigate(page,url),'warm':navigate(page,url)}
        page.wait_for_function('navigator.serviceWorker.controller!==null')
        context.set_offline(True)
        phases['offline']=navigate(page,url)
        phases['calendar']=phase(page,"document.querySelector('[data-tab=calendar]').click()","document.querySelector('[data-act=prevMonth]')")
        phases['data']=phase(page,"document.querySelector('[data-tab=settings]').click()","document.querySelector('[data-tab=settings].active')")
        phases['training']=phase(page,"document.querySelector('[data-tab=training]').click()","document.querySelector('[data-act=start]')")
        phases['start']=phase(page,"document.querySelector('[data-act=start]').click()","document.querySelector('[data-act=finish]')&&!document.querySelector('#app').inert")
        phases['expand']=phase(page,"document.querySelector('[data-expand=\"PUSH-A-1\"]').click()","document.querySelector('[data-panel=result]')")
        form='.performanceForm' if native else '.seriesResultForm'
        phases['editor']=phase(page,"document.querySelector('[data-panel=result]').click()",f"document.querySelector('{form}')")
        for field,value in [('kg','21'),('reps','9')]:
            selector=f'[data-quick={field}]' if native else f'[data-main={field}]'
            phases[field]=phase(page,f"()=>{{const el=document.querySelector('{selector}');el.value='{value}';el.dispatchEvent(new Event('input',{{bubbles:true}}))}}",f"document.querySelector('{selector}').value==='{value}'")
        phases['save']=phase(page,f"document.querySelector('{form}').requestSubmit()",f"!document.querySelector('{form}')&&!document.querySelector('#app').inert")
        phases['finish']=phase(page,"document.querySelector('[data-act=finish]').click()","document.querySelector('[data-act=start]')&&!document.querySelector('#app').inert")
        if errors:raise RuntimeError(errors)
        return {'sizes':sizes,'phases':phases}
    finally:context.close()


def summarize(rows):
    result={}
    def stats(values):
        values=sorted(values)
        return {'median':values[len(values)//2],'p95':values[math.ceil(len(values)*.95)-1]}
    for phase_name in rows[0]['phases']:
        samples=[r['phases'][phase_name] for r in rows]
        item={key:stats([s[key] for s in samples if s.get(key) is not None]) for key in ['firstMs','fullMs','blockingMs','maxTaskMs'] if any(s.get(key) is not None for s in samples)}
        durable=[s['durableMs'][-1]['ms'] for s in samples if s.get('durableMs')]
        if durable:item['durableMs']=stats(durable)
        spans={}
        for s in samples:
            for span in s['spans']:spans[span['name']]=spans.get(span['name'],0)+span['ms']/len(samples)
        item['meanInclusiveSpansMs']=spans
        result[phase_name]=item
    return result


def compact_report(report):
    """Retain every sample/summary without thousands of overlapping raw spans."""
    out={**report,'scenarios':{}}
    for name,scenario in report['scenarios'].items():
        rows=[]
        for row in scenario['samples']:
            phases={}
            for name_,phase in row['phases'].items():
                item={k:v for k,v in phase.items() if k not in ['spans','transactions','handlerQueueMs']}
                spans={}
                for span in phase['spans']:spans[span['name']]=spans.get(span['name'],0)+span['ms']
                item['inclusiveSpansMs']=spans
                item['transactions']=[{'ms':t['ms'],'mode':t['mode']} for t in phase['transactions']]
                queue=phase.get('handlerQueueMs',[])
                if queue:item['handlerQueueMs']={'first':queue[0],'last':queue[-1],'callbacks':len(queue)}
                phases[name_]=item
            rows.append({**row,'phases':phases})
        out['scenarios'][name]={'summary':scenario['summary'],'samples':rows}
    def rounded(value):
        if isinstance(value,float):return round(value,3)
        if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
        if isinstance(value,list):return [rounded(v) for v in value]
        return value
    return rounded(out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref',default='working');parser.add_argument('--runs',type=int,default=5)
    parser.add_argument('--cpu',type=float,default=4);parser.add_argument('--counts',type=int,nargs='+',default=[4,400])
    parser.add_argument('--kind',choices=['legacy','v2'],default='legacy');parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--archive-mib',type=int,default=4)
    parser.add_argument('--compact',action='store_true',help='Group inclusive spans per phase; retain every sample')
    args=parser.parse_args()
    if args.runs<1 or args.cpu<1 or args.archive_mib<0 or any(n<0 or n%4 for n in args.counts):parser.error('runs>=1, cpu>=1, archive-mib>=0, counts nonnegative multiples of four')
    with tempfile.TemporaryDirectory(prefix='pushpull-ui-') as temp:
        directory=Path(temp);source=ROOT
        if args.ref!='working':
            source=directory/'source';source.mkdir()
            with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',args.ref],cwd=ROOT))) as archive:archive.extractall(source,filter='data')
        builder=runpy.run_path(str(source/'scripts/build_release.py'));staging=directory/'instrumented'
        for name in builder['ASSETS']:
            target=staging/name;target.parent.mkdir(parents=True,exist_ok=True);body=(source/name).read_bytes()
            if name in ['app.js','indexeddb.js']:
                text=instrument(name,body.decode())
                if name=='app.js':text=text.replace('handlers.get(event).push(handler);',"handlers.get(event).push(e=>{__ui.handlers.push({at:performance.now(),event:e.timeStamp});return handler(e)});")
                body=text.encode()
            target.write_bytes(body)
        (staging/'scripts').mkdir();shutil.copyfile(source/'scripts/service-worker.template.js',staging/'scripts/service-worker.template.js')
        builder['build'](directory/'site',staging)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Server,directory=str(directory/'site')))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        report={'ref':args.ref,'runs':args.runs,'cpuThrottle':args.cpu,'archiveMiB':args.archive_mib,'viewport':[390,844],'platform':platform.platform(),'scenarios':{},'sourceRuntimeSha256':{n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in builder['ASSETS']}}
        try:
            with sync_playwright() as pw:
                for count in args.counts:
                    rows=[];key=f'{args.kind}-{count}'
                    for n in range(args.runs):
                        rows.append(sample(pw,f'http://127.0.0.1:{server.server_port}/',directory/f'profile-{count}-{n}',count,args.kind=='v2',args.cpu,args.archive_mib*1024*1024))
                        report['scenarios'][key]={'samples':rows,'summary':summarize(rows)}
                        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(compact_report(report) if args.compact else report,indent=2)+'\n')
                        print(f'{args.ref} {key} {n+1}/{args.runs}',flush=True)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()
