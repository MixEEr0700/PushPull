/** Matrix-compatible facade. All official writes after activation use v2. */
import {freeze,portable,canonical} from './backup-json.mjs';
import {openWriter,connectV2,readRecords,readTraining,certifyAllocation,legacyEvidence,prepareConversion,activateConversion,replaceSource,replaceLive,transact,request,same,MARKER} from './journal-idb.mjs';
import {readIndexed,installRuntime,openIndexedWriter} from './journal-runtime.mjs';
import {protocolInput} from './journal-protocol.mjs';
import {verifyConversionEvidence} from './journal-idb.mjs';
import {createLegacyModelFromSource,legacyPayload,exportBackup,readLegacyBackup,parseModelBackup} from './legacy-model.mjs';
const OWNER='pushpull_indexeddb_owner';
const clone=value=>structuredClone(value);
async function probe(name){
 return new Promise((resolve,reject)=>{
  const req=indexedDB.open(name);let absent=false;
  req.onupgradeneeded=()=>{absent=true;req.transaction.abort()};
  req.onerror=()=>absent?resolve(null):reject(req.error);
  req.onsuccess=()=>{req.result.onversionchange=()=>req.result.close();resolve(req.result)};
 });
}
/** Snapshot models stay frozen and can be shared. The editable current plan,
 * entries/forms and metadata are detached. No mutable model is shared by sessions. */
function editable(data){
 if(!data.trainingJournal)return clone(data);
 const {trainingJournal}=data,journal=clone({...trainingJournal,sessionSnapshots:[]}),result=clone({...data,trainingJournal:null});
 journal.sessionSnapshots=trainingJournal.sessionSnapshots.slice();result.trainingJournal=journal;return result;
}
export async function openDatabase(v1,fresh,{training=false}={}){
 let db,writer,source=null,unverified=null,error=null,stale=false,closed=false,notify=()=>{},anchor=null,pendingRevision=0,recoveryCopies=[],deferred=false,historyDeferred=false;
 const channel=typeof BroadcastChannel==='undefined'?null:new BroadcastChannel('pushpull-indexeddb');
 const raw=()=>localStorage.getItem(PushPullStorage.KEY);
 const block=message=>{stale=true;error=Error(message);notify(error)};
 const guard=()=>{
  if(closed||stale)throw error??Error('Połączenie bazy zamknięte. Zachowaj szkic i uruchom ponownie.');
  if(raw()!==anchor)throw Error('Starsza wersja zmieniła dane. Zachowaj obie kopie przed odzyskaniem.');
 };
 const versionChanged=()=>{closed=true;block('Zmieniono wersję bazy. Zachowaj szkice i zamknij inne karty. Nie wyzerowano danych.')};
 const announce=()=>channel?.postMessage({revision:writer.state.revision,epoch:writer.state.epoch});
 function publish(next,{live=false}={}){
  const knownArchives=live&&!deferred?source?.archives:null;
  writer=next;source=knownArchives?Object.freeze({...writer.source,archives:knownArchives}):writer.source;
  if(live)deferred=!knownArchives;
  anchor=writer.legacyRaw;error=null;stale=false;localStorage.setItem(OWNER,v1.NAME+':2');
 }
 async function activateLatest(prepared){
  for(let attempt=0;attempt<3;attempt++){
   try{return await activateConversion(db,prepared,{guard})}
   catch(failure){
    if(!/conversion already active|conversion CAS/.test(failure.message))throw failure;
    const bundle=await readRecords(db);if(bundle.state)return openWriter(db,{bundle,guard});
    const evidence=await legacyEvidence(db),latest=await v1.verifyEvidence(evidence);
    anchor=evidence.meta.find(r=>r.key==='state').legacyRaw;guard();prepared=await prepareConversion(latest,evidence);
   }
  }
  throw Error('Inna karta aktualizuje bazę. Zachowaj szkice i uruchom ponownie.');
 }
 try{
  db=await probe(v1.NAME);
  if(!db||db.version===1){
   // Existing v1 needs one native capture and one full oracle, not openV1's
   // load/model build followed by a second independent capture of the same DB.
   const present=db&&await transact(db,['meta'],'readonly',tx=>request(tx.objectStore('meta').get('state')));
   if(present){
    const evidence=protocolInput(await legacyEvidence(db));unverified={format:'pushpull-idb-recovery',version:1,evidence};
    source=await verifyConversionEvidence(evidence);anchor=raw();pendingRevision=present.revision;
    if(anchor!==evidence.meta.find(r=>r.key==='state').legacyRaw)throw Error('Starsza wersja zmieniła dane. Zachowaj obie kopie przed odzyskaniem.');
    const prepared=await prepareConversion(source,evidence);guard();db.close();db=await connectV2(v1.NAME,{onVersionChange:versionChanged});publish(await activateLatest(prepared));
   }else{
   const legacy=await v1.openV1(fresh);
   if(legacy.error){
    // Another new tab can finish upgrade while this v1 handle is loading or
    // preparing its initial save. Reopen the actual v2 state, never its old copy.
    const latest=await probe(v1.NAME),upgraded=latest?.version===2;latest?.close();
    db?.close();channel?.close();if(upgraded){legacy.close();return openDatabase(v1,fresh,{training})}return legacy;
   }
   try{
    source=freeze(legacy.export());anchor=raw();pendingRevision=legacy.revision;
    if(!db)db=await probe(v1.NAME);
    const evidence=await legacyEvidence(db);unverified={format:'pushpull-idb-recovery',version:1,evidence};
    const prepared=await prepareConversion(source,evidence,{ownerId:evidence.meta.find(r=>r.key==='training-model-v1')?.document.payload.model.ownerId});
    guard();legacy.close();db.close();db=await connectV2(v1.NAME,{onVersionChange:versionChanged});
    publish(await activateLatest(prepared));
   }finally{legacy.close();}
   }
  }else{
   db.onversionchange=()=>{versionChanged();db.close()};
   const indexed=training?await readIndexed(db):null;
   if(indexed){publish(await openIndexedWriter(db,{token:indexed,guard}));deferred=true;historyDeferred=true;}else{
   let bundle=training?await readTraining(db):null;deferred=!!bundle;
   if(!bundle)bundle=await readRecords(db);
   unverified=deferred?null:{format:'pushpull-idb-recovery',version:2,...bundle};
   if(bundle.state){
    if(training&&!bundle.state.allocation){anchor=JSON.parse(bundle.records.journalObjects.find(r=>r.id===bundle.state.legacyRef).json);bundle=await certifyAllocation(db,bundle,{guard});}
    publish(await openWriter(db,{bundle,guard}));guard();
   }else{
    // Pending conversion reads current v1 stores, never replays an earlier
    // checkpoint or enables the v1 writer against database version 2.
    const marker=await transact(db,['meta'],'readonly',tx=>request(tx.objectStore('meta').get(MARKER)));
    if(!same(marker,{key:MARKER,protocol:2,status:'pending'})||Object.values(bundle.records).some(rows=>rows.length))throw Error('Niekompletna baza v2. Zachowaj kopię do odzyskania; nie odtworzono starszej historii v1.');
    const evidence=await legacyEvidence(db);source=freeze(await v1.verifyEvidence(evidence));anchor=evidence.meta.find(r=>r.key==='state').legacyRaw;pendingRevision=evidence.meta.find(r=>r.key==='state').revision;
    guard();const prepared=await prepareConversion(source,evidence);publish(await activateLatest(prepared));
   }
  }
  }
  if(training&&writer&&!writer.state.runtime){
   const bundle=await readTraining(db);try{await installRuntime(db,bundle,{guard})}catch(failure){if(!/install root CAS/.test(failure.message)||!await readIndexed(db))throw failure}
   publish(await openIndexedWriter(db,{guard}));deferred=true;historyDeferred=true;
  }
  unverified=null;guard();
 }catch(failure){error=failure;if(db?.version===2&&!unverified)try{unverified={format:'pushpull-idb-recovery',version:2,...await readRecords(db)}}catch{}}
 const storageListener=event=>{if(event.key===PushPullStorage.KEY||event.key===null)block('Starsza wersja zmieniła dane. Zapis wstrzymany.')};
 window.addEventListener('storage',storageListener);
 if(channel)channel.onmessage=({data})=>{if(data?.modelChanged||data?.revision>(writer?.state.revision??pendingRevision)||data?.epoch&&writer&&data.epoch!==writer.state.epoch)block('Dane zapisano w innej karcie. Zachowaj szkice i odśwież stronę.')};
 const requireDB=()=>{if(!db||closed)throw Error('IndexedDB niedostępne. Zachowaj szkice i uruchom ponownie.');};
 const revision=()=>{const n=writer?.state.revision??unverified?.state?.revision??pendingRevision;return Number.isSafeInteger(n)?n:pendingRevision;};
 const snapshot=()=>{if(!source)throw Error('Brak zweryfikowanej bazy do eksportu.');if(deferred)throw Error('Pełna kopia wymaga odczytu i audytu archiwów.');return {...clone({...source,data:null}),data:editable(source.data)};};
 async function ensureFull(){
  if(error)throw error;guard();if(!deferred)return;
  const expected=writer.state,bundle=await readRecords(db);
  if(!same(bundle.state,expected))throw Error('Pełny odczyt: root CAS. Otwórz aplikację ponownie.');
  const complete=await openWriter(db,{bundle,guard});
  const actual=await transact(db,['journalState'],'readonly',tx=>request(tx.objectStore('journalState').get('active')));
  guard();if(!same(actual,expected)||!same(writer.state,expected))throw Error('Pełny odczyt: root CAS. Otwórz aplikację ponownie.');
  publish(complete);deferred=false;historyDeferred=false;
 }
 async function ensureHistory(){
  if(!historyDeferred)return;if(error)throw error;guard();
  const expected=writer.state,bundle=await readTraining(db);
  if(!bundle||!same(bundle.state,expected))throw Error('Historia: root CAS. Otwórz ponownie.');
  const complete=await openWriter(db,{bundle,guard});guard();
  const actual=await transact(db,['journalState'],'readonly',tx=>request(tx.objectStore('journalState').get('active')));
  if(!same(actual,expected))throw Error('Historia: root CAS. Otwórz ponownie.');
  publish(complete,{live:true});historyDeferred=false;
 }
 async function sessionCommand(name,command){
  if(error)throw error;guard();const archives=!deferred&&source.archives;
  try{const ack=await writer[name]({...command,...writer.sessionContext()});source=archives?freeze({...writer.source,archives}):writer.source;announce();return ack}
  catch(failure){if(/CAS|marker|index|object/.test(failure.message))block(failure.message);throw failure}
 }
 async function auditExport(){
  if(error)throw error;guard();const expected=writer.state,actual=await writer.audit();
  const current=await transact(db,['journalState'],'readonly',tx=>request(tx.objectStore('journalState').get('active')));
  if(!same(current,expected))throw Error('Baza zmieniła się podczas eksportu. Otwórz ponownie.');
  return actual;
 }
 function additions(archives,incoming){
  for(const item of incoming){const existing=archives.find(a=>a.id===item.id);if(existing&&canonical(existing)===canonical(item))continue;archives.push(existing?{...item,sourceId:item.id,id:'imported:'+crypto.randomUUID()}:item)}return archives;
 }
 async function commit(data,{importing=false,importedCatalog=null,importedArchives=[],backupBefore=false,expectedRevision=null,expectedLegacyRaw=undefined,modelOwnerId=null,modelEnabled=undefined}={}){
  // Own the candidate before awaiting anything; callers may keep editing theirs.
  portable(data);portable(importedArchives);const own=clone(data),givenCatalog=importedCatalog&&clone(importedCatalog),incoming=clone(importedArchives);
  requireDB();if(error&&!importing)throw error;
  if(historyDeferred&&!importing)throw Error('Zmiana pełnego modelu wymaga wczytania historii przed edycją.');
  const liveOnly=!importing&&!backupBefore&&!incoming.length&&writer?.state.allocation;
  if(deferred&&!liveOnly)await ensureFull();
  const expected=writer?.state??unverified?.state??null,currentRevision=revision(),legacy=raw();
  if(expectedRevision!==null&&expectedRevision!==currentRevision)throw Error('Dane zmieniły się od podglądu kopii. Otwórz podgląd ponownie.');
  if(expectedLegacyRaw!==undefined&&expectedLegacyRaw!==legacy)throw Error('Starsza wersja zmieniła dane od podglądu.');
  if(!importing)guard();
  PushPullStorage.validate(own);const catalog=givenCatalog??v1.catalogFor(own,source?.catalog);v1.validateCatalog(own,catalog);v1.validateArchives(incoming);
  let archives=liveOnly?[]:source?clone(source.archives):[];
  if(importing||backupBefore){
   const preimage=source?(writer?.state.modelEnabled?JSON.stringify(await createLegacyModelFromSource(source,{ownerId:writer.state.ownerId,createdAt:new Date().toISOString()})):JSON.stringify(source)):JSON.stringify(unverified);
   archives.push({id:'idb:'+crypto.randomUUID(),kind:'before-import',createdAt:new Date().toISOString(),raw:preimage});
  }
  if(importing&&legacy!==anchor)archives.push({id:'legacy-conflict:'+crypto.randomUUID(),kind:'legacy-conflict',createdAt:new Date().toISOString(),raw:legacy});
  additions(archives,incoming);
  const candidate={format:'pushpull-backup',version:2,data:own,catalog,archives},ownerId=modelOwnerId??own.trainingJournal?.model.ownerId??writer?.state.ownerId??'local-journal';
  const operationGuard=()=>{if(closed)throw Error('Połączenie zamknięte.');if(raw()!==legacy)throw Error('Starsza wersja zmieniła dane w trakcie operacji.');if(!importing&&stale)throw error;};
  try{
   const next=await (liveOnly?replaceLive:replaceSource)(db,candidate,{expectedState:expected,ownerId,modelEnabled:modelEnabled??(!!own.trainingJournal||writer?.state.modelEnabled||modelOwnerId!==null),legacyRaw:legacy,recovery:importing&&!writer,revision:pendingRevision,indexed:training,guard:operationGuard});
   publish(next,{live:liveOnly});if(!liveOnly)deferred=false;historyDeferred=false;unverified=null;recoveryCopies=[];announce();
  }catch(failure){
   if(failure.code==='post-complete-readback'){recoveryCopies=archives;block(failure.message);}
   else if(/CAS/.test(failure.message)){block('Dane zmieniły się w innej karcie. Otwórz podgląd ponownie.');throw error;}
   throw failure;
  }
 }
 return {
  get error(){return error},get value(){return source&&editable(source.data)},get catalog(){return source&&clone(source.catalog)},
  get archivesDeferred(){return deferred},get historyDeferred(){return historyDeferred},ensureFull,ensureHistory,
  get startSession(){return writer?.startSession?command=>sessionCommand('startSession',command):undefined},
  get finishSession(){return writer?.finishSession?command=>sessionCommand('finishSession',command):undefined},
  get saveUserNote(){return writer?.saveUserNote?command=>sessionCommand('saveUserNote',command):undefined},
  changeAge(entry){return writer?.changeAge?.(entry)??null},
  get raw(){try{return raw()}catch{return anchor}},get revision(){return revision()},
  get model(){if(deferred)throw Error('Pełny model wymaga odczytu i audytu archiwów.');return writer?.state.modelEnabled&&source?clone(legacyPayload(source,writer.state.ownerId)):null},
  set onchange(fn){notify=fn},
  export:snapshot,auditExport,recovery(){return unverified?clone(unverified):source?snapshot():null},
  async recoveryEvidence(){
   requireDB();const stores=[...db.objectStoreNames];
   // A pending v2 conversion still owns the original v1 tables. A diagnostic
   // download must retain both representations, drafts and unknown metadata,
   // in one native snapshot, even if the v2 stores are empty or corrupt.
   const records=await transact(db,stores,'readonly',async tx=>Object.fromEntries(await Promise.all(stores.map(async store=>[store,await request(tx.objectStore(store).getAll())]))));
   return db.version===1?{format:'pushpull-idb-recovery',version:1,evidence:records}:{format:'pushpull-idb-recovery',version:2,state:records.journalState?.find(r=>r.id==='active')??null,records};
  },
  async saveResult(command){
   if(error)throw error;guard();
   try{const archives=!deferred&&source.archives,ack=await writer.saveResult(command);source=archives?Object.freeze({...writer.source,archives}):writer.source;announce();return ack}
   catch(failure){if(/CAS|marker|index|object|closed|Starsza/.test(failure.message))block(failure.message);throw failure}
  },
  resultContext(sessionId,exerciseId){if(error)throw error;guard();return writer.context(sessionId,exerciseId)},
  commit,
  async prepareModel({backupText,ownerId}={}){
   await ensureFull();
   if(error)throw error;guard();
   if(writer.state.modelEnabled){if(ownerId!==writer.state.ownerId)throw Error('Inny właściciel modelu.');return createLegacyModelFromSource(source,{ownerId,createdAt:new Date().toISOString()})}
   if(canonical(readLegacyBackup(backupText).original)!==canonical(source))throw Error('Kopia nie odpowiada pełnej bieżącej bazie.');
   const archive={id:'model-migration:'+writer.state.revision,kind:'before-model-migration',createdAt:new Date().toISOString(),raw:backupText};
   await commit(source.data,{importedArchives:[archive],modelOwnerId:ownerId,modelEnabled:true});
   return createLegacyModelFromSource(source,{ownerId,createdAt:new Date().toISOString()});
  },
  async exportModelBackup(){const value=await auditExport();if(!writer.state.modelEnabled)throw Error('Model nie został przygotowany.');return exportBackup(await createLegacyModelFromSource(value,{ownerId:writer.state.ownerId,createdAt:new Date().toISOString()}));},
  async importModelBackup(text,options={}){const parsed=await parseModelBackup(text);return commit(parsed.data,{...options,importing:true,importedCatalog:parsed.catalog,importedArchives:parsed.archives??[],modelOwnerId:parsed.document.payload.model.ownerId});},
  backups(){return [...new Set([...(source?.archives??[]),...recoveryCopies].map(a=>a.id))]},
  backupLabel(id){const item=[...(source?.archives??[]),...recoveryCopies].find(a=>a.id===id);return ({migration:'Przed migracją','before-import':'Przed przywróceniem / importem','legacy-conflict':'Zapis starszej wersji','legacy-backup':'Wcześniejsza kopia'}[item?.kind]??'Kopia')+' · '+new Date(item?.createdAt).toLocaleString('pl-PL')},
  async readBackup(id){await ensureFull();const item=[...(source?.archives??[]),...recoveryCopies].find(a=>a.id===id);if(!item)throw Error('Brak kopii');return item.raw},
  async readDriveState(){requireDB();return transact(db,['meta'],'readonly',tx=>request(tx.objectStore('meta').get('drive-sync-v1')))},
  async writeDriveState(value,expectedToken){
   requireDB();const next={...clone(value),key:'drive-sync-v1',token:crypto.randomUUID()};
   return transact(db,['meta'],'readwrite',async tx=>{const store=tx.objectStore('meta'),old=await request(store.get(next.key));if((old?.token??null)!==expectedToken)throw Error('Ustawienia Google zmieniły się w innej karcie. Odśwież aplikację.');if(old?.mode==='manual'){next.mode='manual';next.enabled=false;}store.put(next);if(!same(await request(store.get(next.key)),next))throw Error('Nie zweryfikowano stanu Drive.');return next});
  },
  async readDraftObservation(){
   requireDB();return transact(db,['meta','journalState'],'readonly',async tx=>{
    const [state,rows]=await Promise.all([request(tx.objectStore('journalState').get('active')),request(tx.objectStore('meta').getAll(IDBKeyRange.bound('workout-draft:','workout-draft;',false,true),1025))]);
    if(rows.length>1024)throw Object.assign(Error('Limit odczytu szkiców'),{code:'draft-read-limit'});
    if(!Number.isSafeInteger(state?.revision??pendingRevision))throw Error('Nie odczytano rewizji historii.');
    return {historyRevision:state?.revision??pendingRevision,sources:rows.filter(r=>r.key.startsWith('workout-draft:')).map(value=>({source:'idb-meta',storageKey:value.key,value}))};
   });
  },
  async readDrafts(){requireDB();return transact(db,['meta'],'readonly',async tx=>(await request(tx.objectStore('meta').getAll(IDBKeyRange.bound('workout-draft:','workout-draft;',false,true)))).filter(r=>r.key.startsWith('workout-draft:')))},
  async writeDraft(record,expectedToken){
   requireDB();const safe=clone(record);if(safe.key!=='workout-draft:'+safe.id)throw Error('Nieprawidłowy klucz szkicu.');
   return transact(db,['meta'],'readwrite',async tx=>{const store=tx.objectStore('meta'),old=await request(store.get(safe.key));if((old?.token??null)!==expectedToken)throw Error('Szkic zmienił się w innej karcie. Zachowano obie wersje.');store.put(safe);if(!same(await request(store.get(safe.key)),safe))throw Error('Nie udało się zweryfikować szkicu.');});
  },
  async removeDraft(record){
   requireDB();if(typeof record.id!=='string'||record.key!=='workout-draft:'+record.id)throw Error('Nieprawidłowy klucz szkicu.');
   return transact(db,['meta'],'readwrite',async tx=>{const store=tx.objectStore('meta'),old=await request(store.get(record.key));if(old&&old.token!==record.token&&!(old.id===record.id&&old.sequence<record.sequence))return false;store.delete(record.key);return true;});
  },
  close(){closed=true;channel?.close();db?.close();window.removeEventListener('storage',storageListener)}
 };
}
