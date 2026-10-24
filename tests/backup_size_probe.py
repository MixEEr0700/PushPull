"""Opt-in Issue #54 measurements, not an application backup format or migration.

Uses only fresh temporary profiles, existing fixture/module APIs and local HTTP.
Artifacts stay in the required --output directory; never accepts a user backup.
"""
import argparse
import functools
import gzip
import hashlib
import http.server
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright, expect
from test_browser import QuietServer, ROOT
from drive_backup_probe import renderer_rss


class Sink(QuietServer):
    output = None

    def do_POST(self):
        # Only this process's generated exports, named by a fixed integer counter.
        if self.path != '/probe-export':
            self.send_error(404); return
        target = type(self).output / f'{len(list(type(self).output.glob("*.json"))):02d}.json'
        remaining = int(self.headers['Content-Length'])
        with target.open('wb') as stream:
            while remaining:
                part = self.rfile.read(min(remaining, 1024*1024))
                if not part: raise EOFError('incomplete synthetic export')
                stream.write(part); remaining -= len(part)
        body = json.dumps({'file': target.name}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)


MEASURE = """async ({label,restore})=>{
 const db=await PushPullDB.open(()=>{}), {canonical}=await import('/model/backup-json.mjs');
 try {
  const start=performance.now(), text=await db.exportModelBackup();
  const exportedMs=performance.now()-start, heap=performance.memory.usedJSHeapSize;
  const document=JSON.parse(text), source=JSON.parse(document.payload.legacySources[0].raw);
  const hash=async v=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(v)))),b=>b.toString(16).padStart(2,'0')).join('');
  const before=await hash({data:db.value,drafts:await db.readDrafts()}), prior=source.archives;
  const saved=await (await fetch('/probe-export',{method:'POST',body:text})).json();
  let restoreMs=null;
  if(restore){const t=performance.now();await db.importModelBackup(text);restoreMs=performance.now()-t;
   if(before!==await hash({data:db.value,drafts:await db.readDrafts()}))throw Error('history/draft changed');
   const after=db.export().archives;
   for(const a of prior)if(!after.some(b=>canonical(a)===canonical(b)))throw Error('archive lost');
  }
  return {label,...saved,exportedMs:Math.round(exportedMs),restoreMs:restoreMs===null?null:Math.round(restoreMs),heap,
   sessions:source.data.sessions.length,results:source.data.entries.length,
   snapshots:source.data.trainingJournal?.sessionSnapshots.length??0,
   activations:source.data.trainingJournal?.activations?.length??0,archives:prior.length,
   sourceBytes:new TextEncoder().encode(JSON.stringify(source)).length,
   dataBytes:new TextEncoder().encode(JSON.stringify(source.data)).length,
   catalogBytes:new TextEncoder().encode(JSON.stringify(source.catalog)).length,
   unchanged:true};
 }finally{db.close()}
}"""


HISTORY = """async ({count,packet})=>{
 const db=await PushPullDB.open(()=>{});
 const j=await import('/model/journal.mjs'), p=await import('/model/plan-import.mjs'), perf=await import('/model/performance.mjs');
 try{let data=db.value;
  if(!data.trainingJournal.importedPlans?.length)data=p.stagePlan(data,packet,data.trainingJournal.model.ownerId);
  for(let i=data.sessions.length;i<count;i++){
   const at=new Date(Date.UTC(2026,0,1)+i*2.5*86400000).toISOString();
   if(i===60)data=p.stageActivation(data,packet.planVersion.id,at);
   const s={id:'synthetic-session-'+i,seq:i+1,date:at.slice(0,10),status:'active',type:j.nextType(data)};
   data.sessions.push(s);data.activeId=s.id;await j.startSession(data,s,at);
   for(const ex of j.exercisesFor(data,s)){
    const performance=perf.newPerformance(ex);
    for(const r of performance.rows)for(const seg of r.segments){seg.kg=String(10+i%20);seg.reps=String(8+i%3)}
    const series=perf.flatten(performance),e={id:s.id+'-'+ex.id,sessionId:s.id,exerciseId:ex.id,kg:series[0].kg,reps:series[0].reps,series,performance,createdAt:at};
    j.recordEntry(data,e);data.entries.push(e);
   }
   s.status='done';data.activeId=null;j.advance(data,s);
  }
  await db.commit(data);
 }finally{db.close()}
}"""


def analyze(path):
    """Read-only size estimates; gzip inverse must equal every original byte.

    The archive-free projection and unique raw-byte totals are NOT full backups.
    Unknown archive contents are opaque, not silently interpreted or discarded.
    """
    raw=path.read_bytes(); started=time.monotonic(); packed=gzip.compress(raw, mtime=0)
    compress_ms=round((time.monotonic()-started)*1000)
    started=time.monotonic(); unpacked=gzip.decompress(packed)
    assert unpacked==raw
    decompress_ms=round((time.monotonic()-started)*1000)
    doc=json.loads(raw); source=json.loads(doc['payload']['legacySources'][0]['raw'])
    archives=source['archives']; seen={}; occurrences=0; opaque=0
    def visit(items, depth=0):
        nonlocal occurrences, opaque
        assert depth<20, 'synthetic depth bound'
        for a in items:
            value=a['raw']
            if value is None:continue
            # Size/inventory encoding only, not a proposed archive serialization.
            # Preserve JS lone surrogate code units instead of replacing them.
            value=value.encode('utf-8','surrogatepass'); occurrences+=1; digest=hashlib.sha256(value).hexdigest()
            if digest in seen:
                assert seen[digest]==value  # Do not assume hash equality proves byte equality.
                continue
            seen[digest]=value
            try:
                nested=json.loads(value)
                if nested.get('format')=='pushpull-backup' and nested.get('version')==3:
                    visit(json.loads(nested['payload']['legacySources'][0]['raw']).get('archives',[]),depth+1)
                elif nested.get('format')=='pushpull-backup' and nested.get('version')==2:
                    visit(nested.get('archives',[]),depth+1)
                else:opaque+=1
            except (ValueError,KeyError,TypeError,AttributeError):opaque+=1
    visit(archives)
    # Analytical lower bounds only: excludes manifests, metadata, model and indices.
    unique_bytes=sum(map(len,seen.values()))
    compressed_unique=sum(len(gzip.compress(v,mtime=0)) for v in seen.values())
    direct=[a['raw'] for a in archives if a['raw'] is not None]
    # Re-encode only to measure escaping; this is not used for lossless restoration.
    json_size=lambda v:len(json.dumps(v,ensure_ascii=False,separators=(',',':')).encode())
    return {'v3Bytes':len(raw),'driveNodeBytes':json_size({'format':'pushpull-drive-backup','version':1,'id':'0'*36,'parents':[],'createdAt':'2026-01-01T00:00:00.000Z','backup':raw.decode(),'digest':'0'*64}),
            'gzipBytes':len(packed),'gzipMs':compress_ms,'gunzipMs':decompress_ms,'gzipByteExact':True,
            'directRawBytes':sum(len(v.encode('utf-8','surrogatepass')) for v in direct),'directUniqueRawBytes':sum(len(v.encode('utf-8','surrogatepass')) for v in set(direct)),
            'uniqueNestedRawBytes':unique_bytes,'uniqueNestedGzipBytes':compressed_unique,
            'archiveOccurrencesVisited':occurrences,'uniqueRawBlobs':len(seen),'opaqueBlobs':opaque}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scenario',choices=['minimal','opaque','v2','history'],required=True)
    parser.add_argument('--restores',type=int,choices=range(6),default=0)
    args=parser.parse_args()
    if args.scenario=='history' and args.restores:
        parser.error('History is the no-restore control; use a separate restore scenario')
    args.output.mkdir(parents=True,exist_ok=False);Sink.output=args.output
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Sink,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/'
    rows=[]
    try:
        with tempfile.TemporaryDirectory(prefix='pushpull-size-') as profile,sync_playwright() as pw:
            context=pw.chromium.launch_persistent_context(profile,executable_path=shutil.which('chromium'),args=['--no-sandbox','--enable-precise-memory-info'],service_workers='block',viewport={'width':390,'height':844})
            page=context.new_page();page.on('dialog',lambda d:d.accept());page.goto(url)
            expect(page.locator('[data-act=start]')).to_be_visible()
            if args.scenario in ['v2','history']:
                page.locator('[data-tab=settings]').click();page.locator('[data-view=plans]').click()
                page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
                with page.expect_download():page.locator('[data-plan-activate]').click()
                expect(page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
            else:
                page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{await d.prepareModel({ownerId:'synthetic-size',backupText:JSON.stringify(d.export())});await d.commit(d.value)}finally{d.close()}}""")
            if args.scenario=='opaque':
                page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{
                 await d.commit(d.value,{importing:true,importedArchives:[
                  {id:'opaque-null',raw:null},{id:'opaque-broken',raw:'{broken'},
                  {id:'opaque-future',raw:'  {"version":99,"unknown":"Ł😀"}\\n'},
                  {id:'opaque-text',raw:'not JSON: \\" / Ł😀'},
                  {id:'opaque-surrogate',raw:String.fromCharCode(0xd800)}
                 ].map(a=>({...a,kind:'synthetic-unknown',createdAt:'2026-01-01T00:00:00.000Z',sourceId:'same-source',extension:{unknown:['Ł😀',null,1]}}))});
                }finally{d.close()}}""")
            # A storage sentinel verifies restore does not clear local-only drafts.
            page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{await d.writeDraft({id:'synthetic-size',key:'workout-draft:synthetic-size',token:'synthetic',sequence:1,value:{kg:'7',reps:''}},null)}finally{d.close()}}""")
            def measure(label,restore=False):
                row=page.evaluate(MEASURE,{'label':label,'restore':restore});row['rendererRssCheckpoint']=renderer_rss()
                row.update(analyze(args.output/row['file']));rows.append(row)
                print(json.dumps(row),flush=True)
            if args.scenario=='history':
                packet=json.loads((ROOT/'tests/fixtures/plan-v3.json').read_text())
                measure('0-sessions')
                for count in [60,120]:
                    page.evaluate(HISTORY,{'count':count,'packet':packet});measure(f'{count}-sessions')
            else:
                for i in range(args.restores+1):measure(f'{i}-restores',i<args.restores)
            context.close()
    finally:
        server.shutdown();server.server_close();thread.join()
        (args.output/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n')


if __name__=='__main__':main()
