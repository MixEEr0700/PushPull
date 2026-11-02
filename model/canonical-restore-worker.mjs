import {readCanonicalBackup} from './canonical-backup.mjs';
import {exportCanonicalLive} from './canonical-export-worker.mjs';
import {transact,request,same,replaceSource,readRecords} from './journal-idb.mjs';
import '../storage.js';
import {hashJSON} from './journal-index.mjs';
import {RESTORE_KEY} from './canonical-restore-gate.mjs';

const check=(v,m)=>{if(!v)throw Error('Restore PPC1: '+m);};
let continueLocal,reserveLocal;
const open=()=>new Promise((r,j)=>{const q=indexedDB.open('pushpull');q.onupgradeneeded=()=>q.transaction.abort();q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error)});
async function restore(file,baseline){
 const started=performance.now(),canonical=await readCanonicalBackup(file),db=await open();
 const id=crypto.randomUUID();let closed=false;db.onversionchange=()=>{closed=true;db.close()};
 try{
  const state=await transact(db,['journalState'],'readonly',tx=>request(tx.objectStore('journalState').get('active'))),revision=state?.revision;
  check(state&&revision===1&&state.counts.journalSessions===0&&state.counts.journalResults===0&&state.counts.journalSnapshots===0&&state.counts.journalArchives===0&&state.legacyRef===await hashJSON(null),'Cel nie jest nowym, czystym profilem.');
  const current=await readCanonicalBackup((await exportCanonicalLive([],revision)).file);
  check(same(current.source.data,baseline.data)&&same(current.source.catalog,baseline.catalog)&&current.drafts.length===0&&Object.keys(current.preferences).length===0&&current.drive.clientId==='','Cel nie jest czystą instalacją. Nie nadpisano danych.');
  const meta=await transact(db,['meta'],'readonly',tx=>request(tx.objectStore('meta').getAll()));
  check(meta.every(r=>['state','training-model-v1','journal-protocol-v2','drive-sync-v1','canonical-preferences-v1'].includes(r.key)),'Cel ma dodatkowe trwałe dane.');const preferenceBefore=meta.find(r=>r.key==='canonical-preferences-v1');check(!preferenceBefore||same(preferenceBefore.value,{}),'Cel ma preferencje.');
  check(same(meta.find(r=>r.key==='journal-protocol-v2'),{key:'journal-protocol-v2',protocol:2,status:'active',epoch:state.epoch}),'Marker celu zmienił się.');
  const driveBefore=meta.find(r=>r.key==='drive-sync-v1'),legacyState=meta.find(r=>r.key==='state');check((driveBefore?.clientId??'')===''&&legacyState?.migration?.source==='new'&&!driveBefore?.selected&&Object.keys(driveBefore?.accounts??{}).length===0,'Profil był już używany.');
  const before=await readRecords(db);check(same(before.state,state),'Zmieniono profil podczas sprawdzania.');
  check(!meta.some(r=>r.key===RESTORE_KEY),'Inne przywracanie jest w toku.');
  const reserved=await new Promise(resolve=>{reserveLocal=resolve;postMessage({reserve:id});});check(reserved===true,'Nie zarezerwowano pustego localStorage.');
  await transact(db,[...Object.keys(before.records),'meta'],'readwrite',async tx=>{
   check(!closed,'Połączenie zamknięte.');
   for(const [store,rows] of Object.entries(before.records))check(same(await request(tx.objectStore(store).getAll()),rows),'Zmieniono cel przed zapisem.');
   check(same(await request(tx.objectStore('meta').getAll()),meta),'Zmieniono metadane celu.');
   tx.objectStore('meta').add({key:RESTORE_KEY,id,status:'pending'});check((await request(tx.objectStore('meta').get(RESTORE_KEY))).id===id,'Marker readback');
  });
  postMessage({claimed:true});
  const guard=()=>check(!closed,'Połączenie zamknięte.');
  const writer=await replaceSource(db,{...canonical.source,archives:[]},{expectedState:before.state,ownerId:canonical.source.data.trainingJournal?.model.ownerId??'local-journal',modelEnabled:!!canonical.source.data.trainingJournal,recovery:true,indexed:true,legacyRaw:null,guard,restoreId:id});
  await transact(db,['meta'],'readwrite',async tx=>{
   const store=tx.objectStore('meta');
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
  return {buffers:canonical.buffers,metrics:{sessions:canonical.source.data.sessions.length,results:canonical.source.data.entries.length,drafts:canonical.drafts.length,buffers:canonical.buffers.length,ms:Math.round(performance.now()-started),bytes:file.size}};
 }finally{db.close();}
}
if(typeof DedicatedWorkerGlobalScope!=='undefined'&&globalThis instanceof DedicatedWorkerGlobalScope){onmessage=async({data})=>{if(Object.hasOwn(data,'reserveOK')){reserveLocal?.(data.reserveOK);return;}if(Object.hasOwn(data,'localOK')){continueLocal?.(data.localOK);return;}try{postMessage({result:await restore(data.file,data.baseline)})}catch(e){postMessage({error:e.message})}};}
