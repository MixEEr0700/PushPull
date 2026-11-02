/** Live canonical export: read-only selective journal capture, no rescue reads. */
import {reader} from './journal-runtime.mjs';
import {transact,request,same,LEGACY_STORES} from './journal-idb.mjs';
import {STORES} from './journal-protocol.mjs';
import {createCanonicalBackup,writeCanonicalBackup,readCanonicalBackup} from './canonical-backup.mjs';
const check=(v,m)=>{if(!v)throw Error('Eksport PPC1: '+m);};
async function connect(){return new Promise((resolve,reject)=>{const q=indexedDB.open('pushpull');let absent=false;q.onupgradeneeded=()=>{absent=true;q.transaction.abort()};q.onerror=()=>reject(Error('Brak aktywnej bazy IndexedDB v2.'));q.onblocked=()=>{absent=true;reject(Error('Baza jest zajęta.'));};q.onsuccess=()=>{if(absent){q.result.close();return;}resolve(q.result);};});}
async function auxiliary(db){return transact(db,['meta'],'readonly',async tx=>{
 const store=tx.objectStore('meta'),keys=await request(store.getAllKeys());
 const allowed=['state','training-model-v1','journal-protocol-v2','drive-sync-v1','canonical-preferences-v1'];
 check(keys.every(k=>typeof k==='string'&&(allowed.includes(k)||k.startsWith('workout-draft:'))),'Nieznane trwałe ustawienia — nie utworzono niepełnej kopii.');
 const drafts=await Promise.all(keys.filter(k=>k.startsWith('workout-draft:')).map(async key=>({key,value:await request(store.get(key))})));
 const drive=await request(store.get('drive-sync-v1')),preferences=await request(store.get('canonical-preferences-v1'));
 check(!preferences||(preferences.value&&typeof preferences.value==='object'&&!Array.isArray(preferences.value)),'Nieprawidłowe preferencje — nie pominięto rekordu.');check(!drive||typeof drive.clientId==='string','Nieprawidłowa konfiguracja klienta.');
 return {drafts,preferences:preferences?preferences.value:{},drive:{clientId:drive?drive.clientId:''}};
});}
export async function exportCanonicalLive(buffers,expectedRevision){
 const start=performance.now(),db=await connect();let changed=false;db.onversionchange=()=>{changed=true;db.close();};
 try{
  check(db.version===2,'Wymagana aktywna baza v2.');check(same([...db.objectStoreNames].sort(),[...LEGACY_STORES,...STORES].sort()),'Nieznane magazyny danych — przerwano eksport.');
  const state=await transact(db,['journalState'],'readonly',tx=>request(tx.objectStore('journalState').get('active')));
  check(state&&state.revision===expectedRevision,'Rewizja zmieniła się. Ponów eksport.');
  const aux=await auxiliary(db),r=await reader(db,state),base=await r.metadata('source');
  check(r.maps.journalMetadata.size===state.counts.journalMetadata,'Nieprzypisane metadane.');for(const row of r.maps.journalMetadata.values())check(new Set(row.fields.map(pair=>pair[0])).size===row.fields.length,'Powtórzone pola metadanych.');
  check(Object.keys(base).every(k=>['format','version','data','catalog','archives'].includes(k)),'Nieznane źródła danych.');
  const collections={};
  for(const store of ['journalSessions','journalResults','journalSnapshots']){
   const rows=await transact(db,[store],'readonly',tx=>request(tx.objectStore(store).getAll()));
   for(const row of rows){check(Number.isSafeInteger(row.version)&&row.version>0,'Wersja rekordu.');if(store==='journalSnapshots')check(new Set(row.fields.map(pair=>pair[0])).size===row.fields.length,'Powtórzone pola snapshotu.');}
   check(rows.length===state.counts[store],'Liczba rekordów zmieniła się.');rows.sort((a,b)=>a.position-b.position);
   collections[store]=[];rows.forEach((row,i)=>check(row.position===i,'Niepełna kolejność historii.'));for(let p=0;p<rows.length;p+=32)collections[store].push(...await Promise.all(rows.slice(p,p+32).map(async row=>{const value=await r.collection(store,row.id);check(value.id===row.id,'Identyfikator rekordu różni się od źródła.');return value;})));
  }
  const data={...base.data,sessions:collections.journalSessions,entries:collections.journalResults};
  if(data.trainingJournal)data.trainingJournal={...data.trainingJournal,sessionSnapshots:collections.journalSnapshots};
  else check(collections.journalSnapshots.length===0,'Nieprzypisane snapshoty.');
  const canonical=createCanonicalBackup({source:{format:base.format,version:base.version,data,catalog:base.catalog},...aux,buffers});
  await r.stable();const file=await writeCanonicalBackup(canonical);
  // End-to-end codec equality is enforced before publishing this Blob.
  check(same(await readCanonicalBackup(file),canonical),'Odczyt kopii różni się od danych źródłowych.');
  await r.stable();check(same(await auxiliary(db),aux)&&!changed,'Szkice lub ustawienia zmieniły się podczas eksportu.');
  return {file,metrics:{bytes:file.size,ms:Math.round(performance.now()-start),sessions:data.sessions.length,results:data.entries.length,snapshots:collections.journalSnapshots.length,drafts:aux.drafts.length,buffers:buffers.length}};
 }finally{db.close();}
}
if(typeof DedicatedWorkerGlobalScope!=='undefined'&&globalThis instanceof DedicatedWorkerGlobalScope){globalThis.onmessage=async({data})=>{try{postMessage({result:await exportCanonicalLive(data.buffers,data.revision)})}catch(e){postMessage({error:e.message})}};}
