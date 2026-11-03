import {canonical as canonicalJSON} from './backup-json.mjs';
import {readCanonicalBackup,assertCanonicalRestoreKeys} from './canonical-backup.mjs';
import {exportCanonicalLive} from './canonical-export-worker.mjs';
import {transact,request,same,replaceSource,readRecords} from './journal-idb.mjs';
import '../storage.js';
import {hashJSON} from './journal-index.mjs';
import {saveRescue,readRescue} from './canonical-rescue.mjs';
import {RESTORE_KEY} from './canonical-restore-gate.mjs';

const check=(v,m)=>{if(!v)throw Error('Restore PPC1: '+m);};
let continueLocal,reserveLocal;
const open=()=>new Promise((r,j)=>{const q=indexedDB.open('pushpull');q.onupgradeneeded=()=>q.transaction.abort();q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error)});
async function restore(file,baseline){
 const started=performance.now(),canonical=assertCanonicalRestoreKeys(await readCanonicalBackup(file)),db=await open();
 const id=baseline.recovery??crypto.randomUUID();let closed=false;db.onversionchange=()=>{closed=true;db.close()};
 try{
  const state=await transact(db,['journalState'],'readonly',tx=>request(tx.objectStore('journalState').get('active'))),revision=state?.revision;
  const recovery=baseline.recovery?await readRescue(id):null;
  if(recovery)check(same(await readCanonicalBackup(recovery.file),canonical),'Plik nie odpowiada punktowi cofnięcia.');
  const before=await readRecords(db),meta=await transact(db,['meta'],'readonly',tx=>request(tx.objectStore('meta').getAll()));
  check(same(before.state,state),'Zmieniono profil podczas sprawdzania.');
  const pending=meta.find(r=>r.key===RESTORE_KEY);check(!pending||recovery&&pending.id===id,'Inne przywracanie jest w toku.');
  let protectedPoint=recovery;
  if(recovery){if(pending)check(same(pending.state,state),'Zmieniono root podczas przerwanej operacji. Nie nadpisano obcych danych.');else{const current=await readCanonicalBackup((await exportCanonicalLive(baseline.buffers,revision)).file);check(await hashJSON(canonicalJSON(current))===recovery.evidence.incoming,'Zmieniono dane po aktywacji. Nie nadpisano obcych danych.');}}
  if(!recovery){
   check(revision===baseline.revision||!baseline.replace&&revision===1,'Rewizja zmieniła się od podglądu.');
   const currentFile=(await exportCanonicalLive(baseline.buffers,revision)).file;
   const current=await readCanonicalBackup(currentFile);
   if(baseline.expected)check(same(current,await readCanonicalBackup(baseline.expected)),'Dane lub szkice zmieniły się od podglądu.');
   check(same(current.drafts,meta.filter(r=>r.key.startsWith('workout-draft:')).map(value=>({key:value.key,value})))&&same(current.preferences,meta.find(r=>r.key==='canonical-preferences-v1')?.value??{})&&current.drive.clientId===(meta.find(r=>r.key==='drive-sync-v1')?.clientId??''),'Snapshot ustawień nie odpowiada punktowi ratunkowemu.');

   if(!baseline.replace)check(same(current.source.data,baseline.data)&&same(current.source.catalog,baseline.catalog)&&!current.drafts.length&&!Object.keys(current.preferences).length,'Cel nie jest czystą instalacją.');
   protectedPoint=await saveRescue(id,currentFile,{records:before.records,meta,buffers:baseline.buffers,state,incoming:await hashJSON(canonicalJSON(canonical))});
  }
  const reserved=await new Promise(resolve=>{reserveLocal=resolve;postMessage({reserve:id});});check(reserved===true,'Nie zarezerwowano localStorage.');
  await transact(db,[...Object.keys(before.records),'meta'],'readwrite',async tx=>{
   check(!closed,'Połączenie zamknięte.');
   for(const [store,rows] of Object.entries(before.records))check(same(await request(tx.objectStore(store).getAll()),rows),'Zmieniono cel przed zapisem.');
   check(same(await request(tx.objectStore('meta').getAll()),meta),'Zmieniono metadane celu.');
   tx.objectStore('meta').put({key:RESTORE_KEY,id,status:'pending',state});check((await request(tx.objectStore('meta').get(RESTORE_KEY))).id===id,'Marker readback');
  },pending?{restoreId:id}:{});
  postMessage({claimed:true});
  const guard=()=>check(!closed,'Połączenie zamknięte.');
  const writer=await replaceSource(db,{...canonical.source,archives:[]},{expectedState:before.state,ownerId:canonical.source.data.trainingJournal?.model.ownerId??'local-journal',modelEnabled:!!canonical.source.data.trainingJournal,recovery:true,indexed:true,legacyRaw:null,guard,restoreId:id,expectedRecords:before.records,rescueReference:{id,sha:protectedPoint.sha,evidenceSHA:protectedPoint.evidenceSHA}});
  await transact(db,['meta'],'readwrite',async tx=>{
   const store=tx.objectStore('meta');
   const expected=[...meta.filter(r=>![RESTORE_KEY,'journal-protocol-v2'].includes(r.key)),{key:RESTORE_KEY,id,status:'pending',state:writer.state},{key:'journal-protocol-v2',protocol:2,status:'active',epoch:writer.state.epoch}];const sort=rows=>rows.sort((a,b)=>a.key<b.key?-1:a.key>b.key?1:0);check(same(sort(await request(store.getAll())),sort(expected)),'Konflikt metadanych po claim.');
   for(const row of await request(store.getAll()))if(row.key.startsWith('workout-draft:'))store.delete(row.key);
   for(const draft of canonical.drafts){check(draft.value.key===draft.key,'Klucz szkicu');check(!await request(store.get(draft.key)),'Konflikt szkicu');store.add(draft.value);check(same(await request(store.get(draft.key)),draft.value),'Odczyt szkicu');}
   const preferences={key:'canonical-preferences-v1',value:canonical.preferences};store.put(preferences);check(same(await request(store.get(preferences.key)),preferences),'Odczyt preferencji');
   const drive={key:'drive-sync-v1',mode:'manual',enabled:false,clientId:canonical.drive.clientId,selected:null,accounts:{},deviceId:crypto.randomUUID(),token:crypto.randomUUID()};store.put(drive);check(same(await request(store.get(drive.key)),drive),'Odczyt konfiguracji');
  },{restoreId:id});
  const expectedMeta=await transact(db,['meta'],'readonly',tx=>request(tx.objectStore('meta').getAll()));
  const local=await new Promise((resolve,reject)=>{continueLocal=resolve;postMessage({local:canonical.buffers});});
  check(local===true,'Nie potwierdzono localStorage. Profil pozostaje pending.');
  const actual=await readCanonicalBackup((await exportCanonicalLive(canonical.buffers,writer.state.revision,id)).file);
  check(same(actual,canonical),'Pełny readback różni się od kopii.');
  await transact(db,['meta','journalState'],'readwrite',async tx=>{
   check(same(await request(tx.objectStore('journalState').get('active')),writer.state),'Aktywacja CAS');check(same(await request(tx.objectStore('meta').getAll()),expectedMeta),'Aktywacja meta CAS');
   tx.objectStore('meta').delete(RESTORE_KEY);check(!await request(tx.objectStore('meta').get(RESTORE_KEY)),'Aktywacja readback');
  },{restoreId:id});
  return {buffers:canonical.buffers,metrics:{sessions:canonical.source.data.sessions.length,results:canonical.source.data.entries.length,drafts:canonical.drafts.length,buffers:canonical.buffers.length,ms:Math.round(performance.now()-started),bytes:file.size,rescueId:id}};
 }finally{db.close();}
}
if(typeof DedicatedWorkerGlobalScope!=='undefined'&&globalThis instanceof DedicatedWorkerGlobalScope){onmessage=async({data})=>{if(Object.hasOwn(data,'reserveOK')){reserveLocal?.(data.reserveOK);return;}if(Object.hasOwn(data,'localOK')){continueLocal?.(data.localOK);return;}try{if(data.action==='read-rescue'){const p=await readRescue(data.id);postMessage({result:{file:p.file,id:p.id,createdAt:p.createdAt}});return;}postMessage({result:await restore(data.file,data.baseline)})}catch(e){postMessage({error:e.message})}};}
