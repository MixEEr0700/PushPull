/** Issue #82 B. Explicit v2 connection, conversion and isolated strict writer. */
import {freeze,portable,canonical,requireThat as check} from './backup-json.mjs';
import {STORES,createProtocol,materialize,sealState,objectRecord,protocolInput,protocolBudget,limitsFor} from './journal-protocol.mjs';
import {hashJSON,sha,indexKey,editIndex,checkAbort} from './journal-index.mjs';
import {prepareLegacyBackup} from './legacy-backup.mjs';
import {validateSessionSnapshot} from './training-model.mjs';
import {projectEntry} from './journal.mjs';
export const VERSION=2,MARKER='journal-protocol-v2';
export const LEGACY_STORES=['meta','plans','planVersions','exercises','sessions','entries','sets','notes','changes','backups'];
const conversions=new WeakMap();
const auditedBundles=new WeakSet();
export const request=req=>new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
export const same=(a,b)=>{portable(a);portable(b);return JSON.stringify(a)===JSON.stringify(b);};
export function transact(db,stores,mode,work,{signal}={}){
 checkAbort(signal);
 return new Promise((resolve,reject)=>{
  const tx=db.transaction(stores,mode,mode==='readwrite'?{durability:'strict'}:undefined);let result,failure,finished=false;
  const abort=()=>{failure=signal.reason??new DOMException('Aborted','AbortError');try{tx.abort()}catch{}};
  const cleanup=()=>signal?.removeEventListener('abort',abort);
  tx.oncomplete=()=>{cleanup();if(finished)resolve(result);else reject(Error('Transakcja zakończyła się przed weryfikacją odczytu.'))};
  tx.onabort=()=>{cleanup();reject(failure??tx.error??new DOMException('Aborted','AbortError'))};tx.onerror=()=>{};
  signal?.addEventListener('abort',abort,{once:true});
  Promise.resolve().then(()=>work(tx)).then(value=>{result=value;finished=true},error=>{failure=error;try{tx.abort()}catch{cleanup();reject(error)}});
 });
}
export async function connectV2(name,{onVersionChange=()=>{}}={}){
 return new Promise((resolve,reject)=>{
  const req=indexedDB.open(name,VERSION);let abandoned=false,failure;
  req.onupgradeneeded=()=>{
   // No hashing, source conversion, network or user work in versionchange.
   try{
    for(const name of STORES)if(!req.result.objectStoreNames.contains(name))req.result.createObjectStore(name,{keyPath:'id'});
    if(req.result.objectStoreNames.contains('meta'))req.transaction.objectStore('meta').put({key:MARKER,protocol:2,status:'pending'});
   }catch(error){failure=error;req.transaction.abort();}
  };
  req.onblocked=()=>{abandoned=true;reject(Error('Zamknij inne karty PushPull. Aktualizacja bazy oczekuje; danych nie usunięto.'))};
  req.onerror=()=>reject(failure??req.error);
  req.onsuccess=()=>{if(abandoned){req.result.close();return}req.result.onversionchange=()=>{onVersionChange();req.result.close()};resolve(req.result)};
 });
}
export async function readRecords(db,{signal}={}){
 const bundle=await transact(db,STORES,'readonly',async tx=>{
  const records=Object.fromEntries(await Promise.all(STORES.map(async s=>[s,await request(tx.objectStore(s).getAll())])));
  return {state:records.journalState.find(s=>s.id==='active')??null,records};
 },{signal});
 // Freeze an owned native read without cloning its large checkpoint again.
 // Non-JSON corruption stays available as raw evidence; validators reject it.
 try{portable(bundle);freeze(bundle)}catch{}
 return bundle;
}
export async function legacyEvidence(db){
 return transact(db,LEGACY_STORES,'readonly',async tx=>Object.fromEntries(await Promise.all(LEGACY_STORES.map(async s=>[s,await request(tx.objectStore(s).getAll())]))));
}
async function equalRows(tx,expected){
 for(const [store,rows] of Object.entries(expected)){
  const actual=await request(tx.objectStore(store).getAll()),key=store==='meta'?'key':'id';
  const comparable=list=>list.filter(row=>store!=='meta'||row.key!==MARKER).slice().sort((a,b)=>String(a[key])<String(b[key])?-1:1);
  check(same(comparable(actual),comparable(rows)),'conversion CAS '+store);
 }
}
async function addImmutable(tx,store,rows){
 for(const row of rows){
  const existing=await request(tx.objectStore(store).get(row.id));
  if(existing)check(same(existing,row),'immutable collision '+store);else tx.objectStore(store).add(row);
 }
}
async function readback(tx,store,rows){for(const row of rows)check(same(await request(tx.objectStore(store).get(row.id)),row),'readback '+store);}
/** Caller supplies the exact, fully verified v1 evidence captured with source.
 * It is checked again inside the conversion tx, including unknown meta/drafts.
 * A stale preparation never restores the checkpoint over a later v1 write. */
export async function prepareConversion(source,evidence,{ownerId,signal}={}){
 portable(evidence);portable(source);const captured=freeze(structuredClone(evidence)),original=freeze(structuredClone(source));
 const verified=await PushPullDB.verifyEvidence(captured);
 check(canonical(verified)===canonical(original),'conversion v1 source binding');
 const previousOwner=captured.meta.find(r=>r.key==='training-model-v1')?.document.payload.model.ownerId;
 check(ownerId===undefined||previousOwner===undefined||ownerId===previousOwner,'conversion owner');ownerId??=previousOwner;
 const revision=captured.meta.find(r=>r.key==='state')?.revision;check(Number.isSafeInteger(revision),'v1 revision');
 const epoch=crypto.randomUUID(),checkpoint={id:'v1:'+epoch,protocol:1,revision,sourceHash:await sha(canonical(original)),evidenceHash:await hashJSON(captured),evidence:captured};
 const bundle=await createProtocol(original,{epoch,revision,ownerId,modelEnabled:!!original.data.trainingJournal||captured.meta.some(r=>r.key==='training-model-v1'),legacyRaw:captured.meta.find(r=>r.key==='state').legacyRaw,checkpoints:[checkpoint],signal}),roundtrip=await materialize(bundle,{signal});
 check(same(roundtrip,original),'conversion full source oracle');
 const token=freeze({protocol:2,epoch:bundle.state.epoch,revision});conversions.set(token,{original,captured,bundle,checkpoint});return token;
}
export async function activateConversion(db,token,{signal,guard=()=>{}}={}){
 check(conversions.has(token),'prepared conversion token');const {original,captured,bundle,checkpoint}=conversions.get(token);
 await transact(db,[...LEGACY_STORES,...STORES],'readwrite',async tx=>{
  guard();check(!await request(tx.objectStore('journalState').get('active')),'conversion already active');
  check(same(await request(tx.objectStore('meta').get(MARKER)),{key:MARKER,protocol:2,status:'pending'}),'conversion pending marker');
  for(const store of STORES)check(await request(tx.objectStore(store).count())===0,'conversion stores not empty');
  await equalRows(tx,captured);
  for(const store of STORES.filter(s=>!['journalState','journalCheckpoints'].includes(s)))for(const row of bundle.records[store])tx.objectStore(store).add(row);
  tx.objectStore('journalCheckpoints').add(checkpoint);
  for(const store of STORES.filter(s=>!['journalState','journalCheckpoints'].includes(s)))await readback(tx,store,bundle.records[store]);
  await readback(tx,'journalCheckpoints',[checkpoint]);guard();
  tx.objectStore('journalState').add(bundle.state);await readback(tx,'journalState',[bundle.state]);
  const marker={key:MARKER,protocol:2,status:'active',epoch:bundle.state.epoch};tx.objectStore('meta').put(marker);
  check(same(await request(tx.objectStore('meta').get(MARKER)),marker),'conversion marker readback');
 },{signal});
 // A complete readonly restart audit is independent of the pre-commit objects.
 const stored=await readRecords(db,{signal});check(same(stored.state,bundle.state),'conversion restart revision');
 check(same(await materialize(stored,{signal}),original),'conversion restart oracle');return openWriter(db,{bundle:stored,signal,guard});
}
export async function convertV1(db,source,evidence,options={}){return activateConversion(db,await prepareConversion(source,evidence,options),options);}
async function auditBundle(input,options={}){
 const bundle=protocolInput(input);
 for(const checkpoint of auditedBundles.has(bundle)?[]:bundle.records.journalCheckpoints){
  if(checkpoint.protocol!==1)continue;
  const original=await PushPullDB.verifyEvidence(checkpoint.evidence);
  check(checkpoint.sourceHash===await sha(canonical(original)),'checkpoint source SHA-256');
 }
 const source=await materialize(bundle,options);auditedBundles.add(bundle);return source;
}
export async function openWriter(db,{bundle,signal,guard=()=>{},limits:requestedLimits}={}){
 const limits=limitsFor(requestedLimits);
 let saved=protocolInput(bundle??await readRecords(db,{signal})),source=await auditBundle(saved,{signal,limits}),state=saved.state,busy=false;
 let allocation=protocolBudget(saved);
 const maps=Object.fromEntries(STORES.map(s=>[s,new Map(saved.records[s].map(r=>[r.id,r]))]));saved=null;
 let pairs,globalIds;
 function ids(entry){if(!source.data.trainingJournal)return [entry.id];const snapshot=source.data.trainingJournal.sessionSnapshots.find(s=>s.sessionId===entry.sessionId);return projectEntry({id:entry.id,sessionId:entry.sessionId,binding:'uninterpreted',payloadVersion:1,data:entry},snapshot).resultRecords.map(r=>r.id)}
 function indexResults(){pairs=new Map();globalIds=new Map();for(const e of source.data.entries){pairs.set(JSON.stringify([e.sessionId,e.exerciseId]),e.id);for(const id of ids(e))globalIds.set(id,e.id)}}
 indexResults();
 function context(sessionId,exerciseId){
  const id=pairs.get(JSON.stringify([sessionId,exerciseId])),row=id?maps.journalResults.get(id):null,snapshot=source.data.trainingJournal?.sessionSnapshots?.find(s=>s.sessionId===sessionId);
  return {expectedEpoch:state.epoch,expectedRevision:state.revision,expectedEntryHash:row?.ref??null,snapshotHash:snapshot?maps.journalSnapshots.get(snapshot.id).fields.find(([key])=>key==='model')[1]:null};
 }
 async function saveResult(command,{signal}={}){
  // This detachment and portable validation happen before the first await.
  portable(command);const cmd=freeze(structuredClone(command));checkAbort(signal);check(!busy,'writer busy');busy=true;
  try{
   guard();const before=state,e=cmd.entry,pair=JSON.stringify([cmd.sessionId,cmd.exerciseId]),oldId=pairs.get(pair),old=oldId?maps.journalResults.get(oldId):null;
   check(cmd.expectedEpoch===before.epoch&&cmd.expectedRevision===before.revision&&cmd.expectedEntryHash===(old?.ref??null),'result CAS');
   check(e?.sessionId===cmd.sessionId&&e.exerciseId===cmd.exerciseId&&(!old||e.id===old.id)&&(!maps.journalResults.has(e.id)||old?.id===e.id),'result identity');
   const d=source.data,session=d.sessions.find(s=>s.id===e.sessionId),snapshot=d.trainingJournal?.sessionSnapshots?.find(s=>s.sessionId===e.sessionId);
   check(session,'result session');
   check(cmd.snapshotHash===context(e.sessionId,e.exerciseId).snapshotHash,'result snapshot CAS');
   if(snapshot){validateSessionSnapshot(snapshot);check(session.journalSnapshotId===snapshot.id&&snapshot.unitId===session.type,'result snapshot relation');}
   // The immutable source was fully validated at load. Validate the complete
   // changed entry and every result binding, not the unrelated history again.
   const probe=freeze({version:1,exercises:d.exercises,sessions:[session],entries:[e],nextType:d.nextType,activeId:session.status==='active'?session.id:null,
    ...(d.trainingJournal?{trainingJournal:{model:{planVersions:d.trainingJournal.model.planVersions},sessionSnapshots:snapshot?[snapshot]:[]}}:{})});
   PushPullStorage.validate(probe);prepareLegacyBackup(probe);
   const newIds=d.trainingJournal?projectEntry({id:e.id,sessionId:e.sessionId,binding:'uninterpreted',payloadVersion:1,data:e},snapshot).resultRecords.map(r=>r.id):[e.id];
   for(const id of newIds)check(!globalIds.has(id)||globalIds.get(id)===oldId,'duplicate global result ID');
   const object=await objectRecord(e,limits),row=freeze({id:e.id,version:(old?.version??0)+1,position:old?.position??before.counts.journalResults,ref:object.id});
   check(Number.isSafeInteger(row.version),'result version limit');
   const required=new Map(),neededObjects=new Map();
   const requireRow=(store,id)=>{const value=maps[store].get(id);check(value,'required record');required.set(indexKey(store,id),{store,row:value});return value;};
   const requireObject=id=>{const value=maps.journalObjects.get(id);check(value,'required object');neededObjects.set(id,value);};
   for(const id of ['source','data',...(d.trainingJournal?['journal']:[])])requireRow('journalMetadata',id);
   const dataMeta=maps.journalMetadata.get('data');
   for(const field of ['exercises','nextType'])requireObject(dataMeta.fields.find(([key])=>key===field)[1].ref);
   if(d.trainingJournal)requireObject(maps.journalMetadata.get('journal').fields.find(([key])=>key==='model')[1].ref);
   requireObject(requireRow('journalSessions',session.id).ref);
   if(old)requireObject(requireRow('journalResults',old.id).ref);
   if(snapshot)for(const [,ref] of requireRow('journalSnapshots',snapshot.id).fields)requireObject(ref);
   const tree=await editIndex(before.indexRoot,id=>maps.journalIndex.get(id),[[indexKey('journalResults',row.id),await hashJSON(row)]],{signal});
   // Authenticate required records' paths as well as the changed result path.
   for(const [key,{row:record}] of required){
    let id=before.indexRoot,found=false;
    while(id){const n=maps.journalIndex.get(id);check(n,'required index');tree.observed.set(id,n);if(n.key===key){check(n.value===await hashJSON(record),'required index record');found=true;break}id=key<n.key?n.left:n.right;}
    check(found,'required index missing');
   }
   const next=await sealState({...before,revision:before.revision+1,indexRoot:tree.root,counts:{...before.counts,journalResults:before.counts.journalResults+(old?0:1)}});
   const newObject=maps.journalObjects.has(object.id)?0:1,newNodes=[...tree.added.keys()].filter(id=>!maps.journalIndex.has(id)).length;
   const nextAllocation={bytes:allocation.bytes+(newObject?object.bytes:0),records:allocation.records+newObject+newNodes+(old?0:1)};
   check(nextAllocation.bytes<=limits.totalBytes,'protocol total size');check(nextAllocation.records<=limits.records,'protocol record count');
   await transact(db,[...STORES,'meta'],'readwrite',async tx=>{
    guard();check(same(await request(tx.objectStore('journalState').get('active')),before),'root CAS');
    const marker={key:MARKER,protocol:2,status:'active',epoch:before.epoch};check(same(await request(tx.objectStore('meta').get(MARKER)),marker),'protocol marker');
    for(const {store,row} of required.values())check(same(await request(tx.objectStore(store).get(row.id)),row),'required CAS '+store);
    for(const node of tree.observed.values())check(same(await request(tx.objectStore('journalIndex').get(node.id)),node),'index CAS');
    for(const obj of neededObjects.values())check(same(await request(tx.objectStore('journalObjects').get(obj.id)),obj),'object CAS');
    if(!old)check(!await request(tx.objectStore('journalResults').get(row.id)),'new result CAS');
    await addImmutable(tx,'journalObjects',[object]);await addImmutable(tx,'journalIndex',[...tree.added.values()]);
    tx.objectStore('journalResults').put(row);tx.objectStore('journalState').put(next);
    await readback(tx,'journalResults',[row]);await readback(tx,'journalObjects',[...neededObjects.values(),object]);
    await readback(tx,'journalIndex',[...tree.observed.values(),...tree.added.values()]);await readback(tx,'journalState',[next]);
    check(same(await request(tx.objectStore('meta').get(MARKER)),marker),'protocol marker readback');guard();
   },{signal});
   // Native strict complete has happened. Publish only this result; neither a
   // full materializer nor a clone/serialization of all history is used here.
   maps.journalObjects.set(object.id,object);maps.journalResults.set(row.id,row);maps.journalState.set('active',next);for(const [id,n] of tree.added)maps.journalIndex.set(id,n);
   const entries=source.data.entries.slice(),position=old?.position??entries.length;if(old)for(const id of ids(entries[position]))globalIds.delete(id);
   entries[position]=e;source=freeze({...source,data:{...source.data,entries}});state=next;allocation=nextAllocation;
   pairs.set(pair,e.id);for(const id of newIds)globalIds.set(id,e.id);
   return freeze({entry:e,revision:next.revision,epoch:next.epoch,entryHash:object.id});
  }finally{busy=false}
 }
 return {context,saveResult,get source(){return source},get state(){return state},get legacyRaw(){return JSON.parse(maps.journalObjects.get(state.legacyRef).json)},async audit(){return auditBundle(await readRecords(db))}};
}
