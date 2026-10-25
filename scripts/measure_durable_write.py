"""Synthetic click -> strict IDB complete measurements. Never opens a user profile.

Serial execution only; no parallel benchmarks/tests. CPU throttle is not Android.
Default: three independent profiles, eight new exercise results per profile.
--detail adds inclusive function spans; --cpu-profile is a separate diagnostic
single write, whose wall time must not be mixed into ordinary timing statistics.
"""
import argparse
from collections import Counter,defaultdict
import functools
import hashlib
import http.server
import io
import json
import math
from pathlib import Path
import platform
import re
import runpy
import shutil
import subprocess
import tarfile
import tempfile
import threading
from statistics import median
from playwright.sync_api import sync_playwright
from measure_responsiveness import ROOT,Server,SEED
from measure_ui_response import UI_PROBE,LEGACY_SEED

FUNCTIONS={
 'app.js':['persist','render','bindingFor'],
 'indexeddb.js':['save','encode','decode','verifyRows','verifyPreparedRows','validateCatalog','catalogFor'],
 'storage.js':['validate'],
 'model/legacy-model.mjs':['payload','createLegacyModel','createLegacyModelFromSource'],
 'model/backup-json.mjs':['parseJson'],
 'model/legacy-backup.mjs':['readLegacyBackup','validateV1','validateV2'],
 'model/backup.mjs':['createBackup','validatePayload','digest'],
 'model/journal.mjs':['project'],
 'model/training-model.mjs':['validateModel','validateSessionSnapshot','createModel'],
 'model/performance.mjs':['validatePerformance']}
MARKERS=[
 ('      PushPullStorage.validate(data);validateCatalog(data,nextCatalog);','validation'),
 ('      const encoded=encode(data,nextCatalog), checksum=await digest({data,catalog:nextCatalog});','source-encode-hash'),
 ('      const backups=[];','archives'),
 ('      const api=expectedModel || modelOwnerId!==null?await modelAPI():null;','legacy-projection'),
 ("      await transaction(db,'readwrite',async tx=>{",'transaction-open'),
 ("        const stored=await request(tx.objectStore('meta').get('state'));",'cas-read'),
 ('        if(canonical(storedModel || null)!==canonical(expectedModel))','cas-compare'),
 ('        for(const table of TABLES) {','source-write'),
 ('        const actual=await read(tx);','source-readback'),
 ('        const decoded=verifyRows(actual.root,actual.rows,encoded.rows);','source-verify'),
 ('        if(nextModel){','model-write-readback-compare'),
 ('        next.verified=true;','root-verified-complete'),
 ('      if(importing){','post-complete'),
 ('      modelState=nextModel;','memory-publication')]

# Diagnostic-only native costs; no input text/bytes are retained. Keep separate
# from the unprofiled series: interception itself adds overhead.
DETAIL_PROBE=r"""(() => {
 const p=__probe,sha=crypto.subtle.digest.bind(crypto.subtle),encode=TextEncoder.prototype.encode,stringify=JSON.stringify,parse=JSON.parse;
 crypto.subtle.digest=async(...args)=>{const start=performance.now();try{return await sha(...args)}finally{p.spans.push({name:'native.SHA256',start,ms:performance.now()-start,bytes:args[1].byteLength})}};
 TextEncoder.prototype.encode=function(...args){const start=performance.now();try{return encode.apply(this,args)}finally{p.spans.push({name:'native.TextEncoder',start,ms:performance.now()-start})}};
 JSON.stringify=function(...args){if((args[0]&&typeof args[0]==='object')||typeof args[0]==='string'&&args[0].length>65536)return p.time('native.JSON.stringify.bulk',()=>stringify.apply(this,args));return stringify.apply(this,args)};
 JSON.parse=function(...args){if(typeof args[0]==='string'&&args[0].length>65536)return p.time('native.JSON.parse.bulk',()=>parse.apply(this,args));return parse.apply(this,args)};
})();"""


def instrument(name,text,detail):
    if name=='indexeddb.js':
        start=text.index('    async function save(');end=text.index('    try {\n      raw=legacy();',start)
        body=text[start:end]
        for target,label in MARKERS:
            if label=='cas-compare' and 'sameStoredModel(storedModel' in body:target='        if(!sameStoredModel(storedModel || null,expectedModel))'
            if label=='source-readback' and 'read(tx,!preparedSource)' in body:target='        const actual=await read(tx,!preparedSource);'
            if label=='source-verify' and 'const decoded=preparedSource?' in body:target='        const decoded=preparedSource?'
            if label=='root-verified-complete' and 'next={...next,verified:true' in body:target='        next={...next,verified:true'
            if body.count(target)!=1:raise ValueError('Measurement marker mismatch: '+label)
            indent=target[:len(target)-len(target.lstrip())]
            body=body.replace(target,indent+f"window.__writeMarks?.push({{name:'{label}',at:performance.now()}});\n"+target,1)
        if '      const preparedSource=!!api' in body:
            body=body.replace('      const preparedSource=!!api',"      window.__writeMarks?.push({name:'source-preparation',at:performance.now()});\n      const preparedSource=!!api",1)
        text=text[:start]+body+text[end:]
    for fn in FUNCTIONS.get(name,[]) if detail else (['persist','render'] if name=='app.js' else []):
        pattern=re.compile(r'(?P<async>async\s+)?function\s+'+fn+r'\(')
        def replace(match):
            prefix='async ' if match.group('async') else '';method='async' if prefix else 'time'
            return prefix+f"function {fn}(...args){{return window.__probe.{method}('{name}:{fn}',()=>__timed_{fn}(...args))}}\n"+prefix+f'function __timed_{fn}('
        text=pattern.sub(replace,text,count=1)
    return text


FILL=r"""({native,weight})=>{
 const form=document.querySelector(native?'.performanceForm':'.seriesResultForm');
 if(native){
  const basis=form.querySelector('[data-load-basis]');if(basis&&!basis.value){basis.value='machine-indication';basis.dispatchEvent(new Event('change',{bubbles:true}))}
  for(const field of ['kg','reps'])for(const el of form.querySelectorAll('[data-field='+field+']')){el.value=field==='kg'?weight:'9';el.dispatchEvent(new Event('input',{bubbles:true}))}
 }else for(const field of ['kg','reps']){const el=form.querySelector('[data-main='+field+']');el.value=field==='kg'?weight:'9';el.dispatchEvent(new Event('input',{bubbles:true}))}
}"""
PROOF=r"""async()=>{
 const db=await PushPullDB.open(()=>{throw Error('missing fixture')});
 try{
  if(db.error)throw db.error;
  const d=db.value,old={sessions:d.sessions.filter(s=>s.id.startsWith('synthetic-')),entries:d.entries.filter(e=>e.id.startsWith('synthetic-')),snapshots:d.trainingJournal?.sessionSnapshots.filter(s=>s.sessionId.startsWith('synthetic-'))??[]};
  const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)))),x=>x.toString(16).padStart(2,'0')).join('');
  return {history:await hash(old),archives:await hash(db.export().archives),sessions:old.sessions.length,results:old.entries.length,snapshots:old.snapshots.length};
 }finally{db.close()}
}"""


def run_profile(browser,url,args,index,report):
    context=browser.new_context(viewport={'width':390,'height':844},service_workers='allow')
    context.add_init_script(UI_PROBE)
    if args.detail:context.add_init_script(DETAIL_PROBE)
    dialogs=[];errors=[]
    def attach(page):
        page.on('dialog',lambda d:(dialogs.append(d.message),d.accept()))
        page.on('pageerror',lambda e:errors.append(str(e)))
    page=context.new_page();attach(page)
    try:
        page.goto(url);page.wait_for_selector('[data-act=start]',timeout=180000)
        page.evaluate(r"""({bytes,shape})=>{const chunk=shape==='escaped'?'Ł😀\\\"\n':'x',n=new TextEncoder().encode(chunk).length;window.__benchArchive=chunk.repeat(Math.floor(bytes/n))+'x'.repeat(bytes%n)}""",{'bytes':args.archive_mib*1024*1024,'shape':args.archive_shape})
        seed=(SEED if args.kind=='v2' else LEGACY_SEED).replace("raw:'x'.repeat(archiveBytes)",'raw:window.__benchArchive')
        sizes=page.evaluate(seed,{'count':args.count,'native':args.kind=='v2','archiveBytes':args.archive_mib*1024*1024})
        page.evaluate('navigator.serviceWorker.ready');page.close()
        page=context.new_page();attach(page);page.bring_to_front();page.goto(url)
        page.wait_for_selector('[data-act=start]',timeout=180000)
        page.wait_for_function('navigator.serviceWorker.controller!==null')
        context.set_offline(True)
        cdp=context.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':args.cpu})
        page.evaluate("document.querySelector('[data-act=start]').click()")
        page.wait_for_function("document.querySelector('[data-act=finish]')&&!document.querySelector('#app').inert",timeout=180000)
        before=page.evaluate(PROOF)
        exercises=page.locator('[data-expand]').evaluate_all('(buttons)=>buttons.map(b=>b.dataset.expand)')
        if not exercises:raise RuntimeError('Missing current plan exercises')
        samples=[]
        for n in range(args.writes):
            exercise=exercises[n%len(exercises)]
            page.evaluate("id=>{const b=document.querySelector('[data-expand=\"'+id+'\"]');if(b.getAttribute('aria-expanded')!=='true')b.click()}",exercise)
            page.wait_for_selector('[data-panel=result]')
            page.evaluate("document.querySelector('[data-panel=result]').click()")
            form='.performanceForm' if args.kind=='v2' else '.seriesResultForm'
            page.wait_for_selector(form)
            page.evaluate(FILL,{'native':args.kind=='v2','weight':str(21+n)})
            page.wait_for_function("document.querySelector('[data-draft-status]')?.textContent.includes('Szkic zapisany lokalnie')",timeout=180000)
            dialogs.clear()
            if args.cpu_profile:
                cdp.send('Profiler.enable');cdp.send('Profiler.setSamplingInterval',{'interval':1000});cdp.send('Profiler.start')
            page.evaluate(f"window.__writeMarks=[];__ui.begin();document.querySelector('{form} [type=submit]').click()")
            page.wait_for_function("!document.querySelector('#app').inert",timeout=180000,polling='raf')
            if page.locator(form).count():raise RuntimeError('Result not committed: '+repr(dialogs))
            sample=page.evaluate('__ui.end()')
            if not sample['durableMs'] or any(x['durability']!='strict' for x in sample['durableMs']):raise RuntimeError('Missing strict history completion')
            sample['clickToStrictCompleteMs']=sample['durableMs'][-1]['ms']
            marks=page.evaluate('window.__writeMarks');sample['stageMs']={a['name']:b['at']-a['at'] for a,b in zip(marks,marks[1:])}
            spans=defaultdict(float)
            for span in sample.pop('spans'):spans[span['name']]+=span['ms']
            sample['inclusiveSpansMs']=dict(spans)
            sample['transactions']=[{k:v for k,v in tx.items() if k!='start'} for tx in sample['transactions']]
            sample.pop('handlerQueueMs',None);sample.pop('durableMs',None)
            if args.cpu_profile:
                profile=cdp.send('Profiler.stop')['profile'];nodes={x['id']:x['callFrame'] for x in profile['nodes']};times=Counter()
                for node,delta in zip(profile.get('samples',[]),profile.get('timeDeltas',[])):
                    frame=nodes[node];times[(frame['functionName'],frame['url'].split('/')[-1])]+=delta/1000
                sample['cpuSelfMs']=[{'function':key[0],'file':key[1],'ms':value} for key,value in times.most_common(30)]
            samples.append(sample)
            report['profiles']=report.get('profiles',[])
            report['inProgress']={'profile':index+1,'writes':len(samples)}
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2)+'\n')
            print(f'{args.ref} {args.kind}-{args.count} archive={args.archive_mib}MiB profile={index+1}/{args.profiles} write={n+1}/{args.writes} strict={sample["clickToStrictCompleteMs"]:.1f}ms',flush=True)
        after=page.evaluate(PROOF)
        if before!=after:raise RuntimeError('Synthetic history/archive preservation failed')
        if errors:raise RuntimeError(errors)
        return {'sizes':sizes,'preserved':True,'proof':before,'samples':samples}
    finally:context.close()


def summary(profiles):
    rows=[r for p in profiles for r in p['samples']]
    result={}
    for key in ['clickToStrictCompleteMs','firstMs','fullMs','blockingMs','maxTaskMs']:
        values=sorted(r[key] for r in rows if r.get(key) is not None)
        if values:result[key]={'median':median(values),'p95':values[math.ceil(.95*len(values))-1],'max':values[-1]}
    result['meanStageMs']={key:sum(r['stageMs'].get(key,0) for r in rows)/len(rows) for key in rows[0]['stageMs']}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref',default='working');parser.add_argument('--kind',choices=['v2','legacy'],default='v2')
    parser.add_argument('--count',type=int,default=4);parser.add_argument('--archive-mib',type=int,default=4)
    parser.add_argument('--archive-shape',choices=['ascii','escaped'],default='ascii')
    parser.add_argument('--cpu',type=float,default=4);parser.add_argument('--profiles',type=int,default=3);parser.add_argument('--writes',type=int,default=8)
    parser.add_argument('--detail',action='store_true');parser.add_argument('--cpu-profile',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.count<0 or args.count%4 or args.archive_mib<0 or args.cpu<1 or args.profiles<1 or args.writes<1:parser.error('Nonnegative counts divisible by 4; cpu/profiles/writes >=1')
    if args.cpu_profile and (args.profiles!=1 or args.writes!=1):parser.error('CPU profiling requires --profiles 1 --writes 1; use a separate report')
    with tempfile.TemporaryDirectory(prefix='pushpull-durable-') as temp:
        directory=Path(temp);source=ROOT
        if args.ref!='working':
            source=directory/'source';source.mkdir()
            with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',args.ref],cwd=ROOT))) as archive:archive.extractall(source,filter='data')
        builder=runpy.run_path(str(source/'scripts/build_release.py'));staging=directory/'instrumented'
        for name in builder['ASSETS']:
            target=staging/name;target.parent.mkdir(parents=True,exist_ok=True);body=(source/name).read_bytes()
            if name in FUNCTIONS:body=instrument(name,body.decode(),args.detail).encode()
            target.write_bytes(body)
        (staging/'scripts').mkdir();shutil.copyfile(source/'scripts/service-worker.template.js',staging/'scripts/service-worker.template.js')
        builder['build'](directory/'site',staging)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Server,directory=str(directory/'site')))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        report={'ref':args.ref,'baseCommit':subprocess.check_output(['git','rev-parse','HEAD' if args.ref=='working' else args.ref],cwd=ROOT,text=True).strip(),'kind':args.kind,'count':args.count,'archiveMiB':args.archive_mib,'archiveShape':args.archive_shape,'cpuThrottle':args.cpu,'viewport':[390,844],'platform':platform.platform(),'detail':args.detail,'cpuProfiled':args.cpu_profile,'profiles':[],'sourceRuntimeSha256':{n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in builder['ASSETS']}}
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);report['browser']=browser.version
                try:
                    for i in range(args.profiles):
                        report['profiles'].append(run_profile(browser,f'http://127.0.0.1:{server.server_port}/',args,i,report))
                        report.pop('inProgress',None);report['summary']=summary(report['profiles']);args.output.write_text(json.dumps(report,indent=2)+'\n')
                finally:browser.close()
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()
