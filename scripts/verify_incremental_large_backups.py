"""Synthetic v2 growth fixtures: existing v3 reader + v5 isolated trial only.

No production restore, user profile or Drive access. Run after, not concurrently
with, performance measurements. Refuses to overwrite diagnostic output.
"""
import argparse,json,shutil
from pathlib import Path
from measure_incremental_write import artifact,INJECT,ready
from playwright.sync_api import sync_playwright

VERIFY=r"""async()=>{
 const handle=await PushPullDB.open(()=>{throw Error('missing synthetic database')});
 const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)))),b=>b.toString(16).padStart(2,'0')).join('');
 const records=async()=>{const db=await new Promise((ok,no)=>{const r=indexedDB.open('pushpull',2);r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});try{return await new Promise((ok,no)=>{const names=[...db.objectStoreNames],tx=db.transaction(names),out={};for(const n of names){const r=tx.objectStore(n).getAll();r.onsuccess=()=>out[n]=r.result}tx.oncomplete=()=>ok(out);tx.onabort=()=>no(tx.error)})}finally{db.close()}};
 try{
  if(handle.error)throw handle.error;
  const before=await hash(await records()),source=await handle.auditExport(),revision=handle.revision,{sameTrialData,createTrialDatabase}=await import('./model/backup-v5-preview.mjs');
  const result={sessions:source.data.sessions.length,results:source.data.entries.length,snapshots:source.data.trainingJournal.sessionSnapshots.length,archives:source.archives.length};
  try{const text=await handle.exportModelBackup(),stage=await PushPullDB.parseModelBackup(text);if(!sameTrialData(source.data,stage.data)||!sameTrialData(source.catalog,stage.catalog)||!sameTrialData(source.archives,stage.archives))throw Error('v3 differs');window.__v3RestoreText=text;result.expected={data:await hash(source.data),catalog:await hash(source.catalog),archives:await Promise.all(source.archives.map(async a=>({id:a.id,hash:await hash(a)})))};result.v3={equal:true,fileBytes:new TextEncoder().encode(text).length}}catch(error){result.v3={error:error.message}}
  if(!window.__v3Only)try{const codec=await import('./model/backup-v5.mjs'),{text}=await codec.exportBackupV5(source,{createdAt:'2026-10-26T00:00:00.000Z'}),stage=await codec.decodeBackup(text),trial=createTrialDatabase();try{const copy=await trial.restore(stage);if(!sameTrialData(source.data,copy.live.data)||!sameTrialData(source.catalog,copy.live.catalog)||!sameTrialData(source.archives,copy.archives))throw Error('v5 differs');result.v5={equal:true,isolatedTrial:true,fileBytes:new TextEncoder().encode(text).length}}finally{trial.clear()}}catch(error){result.v5={error:error.message}}
  result.readOnly=revision===handle.revision&&before===await hash(await records());if(!result.readOnly)throw Error('Backup verification wrote to source');return result;
 }finally{handle.close()}
}"""
RESTORE=r"""async ({text,expected})=>{
 if(text===undefined){text=window.__incomingV3.join('');window.__incomingV3=null;}
 const handle=await PushPullDB.open(()=>{throw Error('fresh target missing')});
 const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)))),b=>b.toString(16).padStart(2,'0')).join('');
 try{if(handle.error)throw handle.error;await handle.importModelBackup(text);const actual=await handle.auditExport();if(await hash(actual.data)!==expected.data||await hash(actual.catalog)!==expected.catalog)throw Error('Restored data/catalog differ');for(const a of expected.archives){const restored=actual.archives.find(x=>x.id===a.id);if(!restored||await hash(restored)!==a.hash)throw Error('Restored archive differs')}if(!actual.archives.some(a=>a.kind==='before-import'))throw Error('Missing target preimage');return {equal:true,isolatedIndexedDB:true,revision:handle.revision,sessions:actual.data.sessions.length,results:actual.data.entries.length,snapshots:actual.data.trainingJournal.sessionSnapshots.length,archives:actual.archives.length,preimageRetained:true}}finally{handle.close()}
}"""
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixtures',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--ref',default='working');parser.add_argument('--restore-v3-only',action='store_true',help='Do not repeat a completed v5 limit diagnostic');args=parser.parse_args()
 args.output.mkdir(parents=True,exist_ok=False);server,thread,hashes,release=artifact(args.ref,args.output/'runtime');report={'syntheticOnly':True,'purpose':'Functional full-history backup roundtrip; not performance evidence or production restore','runtimeSha256':hashes,'instrumentedRelease':release,'cases':{}}
 try:
  with sync_playwright() as pw:
   for label in ['history400-raw4','history400-escaped16']:
    seed=json.loads((args.fixtures/(label+'-fixture.json')).read_text());browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);context=browser.new_context();page=context.new_page()
    try:
     url='http://127.0.0.1:'+str(server.server_port)+'/';page.goto(url+'benchmark.html');page.evaluate(INJECT,seed);page.goto(url);ready(page);print('VERIFY '+label,flush=True);page.evaluate('flag=>window.__v3Only=flag',args.restore_v3_only);result=page.evaluate(VERIFY)
     if result.get('v3',{}).get('equal'):
      target=browser.new_context()
      try:
       restored=target.new_page();restored.goto(url);ready(restored);restored.evaluate('window.__incomingV3=[]');offset=0;length=page.evaluate('window.__v3RestoreText.length')
       # DevTools has a 100 MiB pending-message cap. Transport chunks only;
       # the app still parses/imports the original complete v3 file unchanged.
       while offset<length:
        part=page.evaluate("offset=>{const s=window.__v3RestoreText;let end=Math.min(offset+1048576,s.length);if(end<s.length&&s.charCodeAt(end-1)>=0xd800&&s.charCodeAt(end-1)<=0xdbff)end--;return {chunk:s.slice(offset,end),next:end}}",offset);restored.evaluate('chunk=>window.__incomingV3.push(chunk)',part['chunk']);offset=part['next']
       result['v3Restore']=restored.evaluate(RESTORE,{'expected':result.pop('expected')})
      finally:target.close()
     report['cases'][label]=result;print(json.dumps(result),flush=True);(args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:context.close();browser.close()
 finally:server.shutdown();server.server_close();thread.join()
 if len(report['cases'])!=2 or any(not result.get('readOnly') or not all(result.get(version,{}).get('equal') for version in (['v3','v3Restore'] if args.restore_v3_only else ['v3','v3Restore','v5'])) for result in report['cases'].values()):
  raise SystemExit('Large backup verification failed; inspect report.json (no source writes).')
if __name__=='__main__':main()
