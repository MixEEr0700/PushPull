/** Issue #82 B. Explicit v2 connection, conversion and isolated strict writer. */
import {freeze,portable,canonical,requireThat as check} from './backup-json.mjs';
import {equalJSON,STORES,ROW_STORES,createProtocol,materialize,materializeTraining,trainingProof,validateState,validateAllocation,allocationFor,sealState,objectRecord,protocolInput,protocolBudget,limitsFor} from './journal-protocol.mjs';
import {hashJSON,sha,indexKey,editIndex,buildIndex,checkAbort} from './journal-index.mjs';
import {prepareLegacyBackup} from './legacy-backup.mjs';
import {validateSessionSnapshot} from './training-model.mjs';
import {projectEntry} from './journal.mjs';
export const VERSION=2,MARKER='journal-protocol-v2';
export const LEGACY_STORES=['meta','plans','planVersions','exercises','sessions','entries','sets','notes','changes','backups'];
const conversions=new WeakMap();
const auditedBundles=new WeakSet();
const verifiedEvidence=new WeakMap();
export async function verifyConversionEvidence(evidence){
 const captured=protocolInput(evidence);
 if(!verifiedEvidence.has(captured))verifiedEvidence.set(captured,protocolInput(await PushPullDB.verifyEvidence(captured)));
 return verifiedEvidence.get(captured);
}
export const request=req=>new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
export const same=(a,b)=>{portable(a);portable(b);return equalJSON(a,b);};
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
/** Single native read snapshot; never getAll large objects/checkpoints. */
export async function readTraining(db,{signal}={}){
 const captured=await transact(db,[...STORES,'meta'],'readonly',async tx=>{
  const records=Object.fromEntries(await Promise.all(STORES.filter(s=>!['journalObjects','journalCheckpoints'].includes(s)).map(async s=>[s,await request(tx.objectStore(s).getAll())])));
  const state=records.journalState.find(s=>s.id==='active');
  if(!state?.allocation)return null; // Older C roots need one full certification.
  validateState(state);validateAllocation(state.allocation);
  check(same(await request(tx.objectStore('meta').get(MARKER)),{key:MARKER,protocol:2,status:'active',epoch:state.epoch}),'protocol marker');
  const [objectIds,checkpointIds]=await Promise.all(['journalObjects','journalCheckpoints'].map(s=>request(tx.objectStore(s).getAllKeys())));
  check(objectIds.length+checkpointIds.length+Object.values(records).reduce((n,rows)=>n+rows.length,0)===state.allocation.records,'allocation record count');
  const refs=new Set([state.legacyRef]);
  for(const row of records.journalMetadata)for(const [,slot] of row.fields)if(slot.kind==='object')refs.add(slot.ref);
  for(const store of ['journalSessions','journalResults'])for(const row of records[store])refs.add(row.ref);
  for(const row of records.journalSnapshots)for(const [,id] of row.fields)refs.add(id);
  const known=new Set(objectIds);
  for(const row of records.journalArchives)check(known.has(row.ref),'missing archive object');
  records.journalObjects=await Promise.all([...refs].map(id=>request(tx.objectStore('journalObjects').get(id))));
  records.journalCheckpoints=checkpointIds.map(id=>({id}));return {bundle:{state,records},objectIds};
 },{signal});
 if(!captured)return null;
 const bundle=protocolInput(captured.bundle);await materializeTraining(bundle,{objectIds:freeze(captured.objectIds),signal});return bundle;
}
/** One-time upgrade for roots written by C: full independent audit first,
 * then only a strict CAS root update. No schema reset or data deletion. */
export async function certifyAllocation(db,bundle,{guard=()=>{}}={}){
 if(bundle.state.allocation)return bundle;
 await auditBundle(bundle);const next=await sealState({...bundle.state,revision:bundle.state.revision+1,allocation:protocolBudget(bundle)});
 await transact(db,[...STORES,'meta'],'readwrite',async tx=>{
  guard();await equalRows(tx,bundle.records);
  check(same(await request(tx.objectStore('meta').get(MARKER)),{key:MARKER,protocol:2,status:'active',epoch:next.epoch}),'certification marker CAS');
  tx.objectStore('journalState').put(next);await readback(tx,'journalState',[next]);guard();
 });
 // Every existing row was independently read and compared in the strict tx;
 // retain those proven immutable objects instead of cloning the checkpoint yet
 // again solely to publish the new small root.
 return freeze({state:next,records:{...bundle.records,journalState:[next]}});
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
 const captured=protocolInput(evidence),original=protocolInput(source);
 const verified=await verifyConversionEvidence(captured);
 check(equalJSON(verified,original,{ordered:false}),'conversion v1 source binding');
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
 check(same(await materialize(stored,{signal}),original),'conversion restart oracle');
 // Native readback, root-bound checkpoint hash and exact detached equality
 // establish the same v1 validation proof; never infer it from a revision/ID.
 const readCheckpoint=stored.records.journalCheckpoints.find(r=>r.id===checkpoint.id);
 check(same(readCheckpoint,checkpoint),'conversion checkpoint restart oracle');
 verifiedEvidence.set(readCheckpoint.evidence,await verifyConversionEvidence(captured));
 return openWriter(db,{bundle:stored,signal,guard});
}
export async function convertV1(db,source,evidence,options={}){return activateConversion(db,await prepareConversion(source,evidence,options),options);}
async function auditBundle(input,options={}){
 const bundle=protocolInput(input);
 for(const checkpoint of auditedBundles.has(bundle)?[]:bundle.records.journalCheckpoints){
  if(checkpoint.protocol!==1)continue;
 const original=await verifyConversionEvidence(checkpoint.evidence);
  check(checkpoint.sourceHash===await sha(canonical(original)),'checkpoint source SHA-256');
 }
 const source=await materialize(bundle,options);auditedBundles.add(bundle);return source;
}
/** Live graph operation (session start/finish, notes/date/plan edits). Archive
 * rows, checkpoint references and every retained immutable object stay intact.
 * Import, preimage creation and explicit backup operations use replaceSource. */
export async function replaceLive(db,input,{expectedState,ownerId,modelEnabled,legacyRaw,guard=()=>{},signal}={}){
 const source=protocolInput(input);check(source.archives?.length===0,'live operation cannot replace archives');
 const before=await readTraining(db,{signal});check(before&&same(before.state,expectedState),'live root CAS');
 const limits=limitsFor(),old=before.state,original=before.records;
 const created=await createProtocol(source,{epoch:old.epoch,revision:old.revision+1,ownerId,modelEnabled,legacyRaw,signal});
 const records={...created.records,journalArchives:original.journalArchives};
 const runtime=old.runtime?await (await import('./journal-runtime-index.mjs')).buildRuntime(source,{signal,sourceRoot:before.state.indexRoot}):null;
 if(runtime)records.journalObjects=[...new Map([...records.journalObjects,...runtime.objects].map(r=>[r.id,r])).values()];
 const leaves=[];for(const store of ROW_STORES)for(const row of records[store])leaves.push([indexKey(store,row.id),await hashJSON(row)]);
 const tree=await buildIndex(leaves,{signal});records.journalIndex=[...new Map([...tree.nodes.values(),...(runtime?.nodes??[])].map(r=>[r.id,r])).values()];
 const knownObjects=new Set(trainingProof(before).objectIds),knownNodes=new Set(original.journalIndex.map(r=>r.id));
 const addedObjects=records.journalObjects.filter(r=>!knownObjects.has(r.id)),addedNodes=records.journalIndex.filter(r=>!knownNodes.has(r.id));
 const allocation={bytes:old.allocation.bytes+addedObjects.reduce((n,r)=>n+r.bytes,0),records:old.allocation.records+addedObjects.length+addedNodes.length+ROW_STORES.reduce((n,s)=>n+records[s].length-original[s].length,0),maxObjectBytes:records.journalObjects.reduce((n,r)=>Math.max(n,r.bytes),old.allocation.maxObjectBytes)};
 validateAllocation(allocation,limits);
 const state=await sealState({...created.state,indexRoot:tree.root,counts:Object.fromEntries(ROW_STORES.map(s=>[s,records[s].length])),checkpointRefs:old.checkpointRefs,allocation,...(runtime?{runtime:{...runtime.runtime,sourceRoot:tree.root}}:{})});
 await transact(db,[...STORES,'meta'],'readwrite',async tx=>{
  guard();check(same(await request(tx.objectStore('journalState').get('active')),old),'live root CAS');
  const marker={key:MARKER,protocol:2,status:'active',epoch:old.epoch};check(same(await request(tx.objectStore('meta').get(MARKER)),marker),'live marker CAS');
  for(const store of ROW_STORES)check(await request(tx.objectStore(store).count())===original[store].length,'live collection count CAS');
  // Required live contents are checked again inside the transaction. This does
  // not read opaque archives/checkpoints under the pretext of a small edit.
  for(const store of ROW_STORES)await readback(tx,store,original[store]);
  await readback(tx,'journalObjects',original.journalObjects);await readback(tx,'journalIndex',original.journalIndex);
  for(const store of ROW_STORES.filter(s=>s!=='journalArchives')){tx.objectStore(store).clear();for(const row of records[store])tx.objectStore(store).add(row);}
  await addImmutable(tx,'journalObjects',records.journalObjects);await addImmutable(tx,'journalIndex',records.journalIndex);
  for(const store of ROW_STORES)await readback(tx,store,records[store]);
  await readback(tx,'journalObjects',records.journalObjects);await readback(tx,'journalIndex',records.journalIndex);
  tx.objectStore('journalState').put(state);await readback(tx,'journalState',[state]);
  check(same(await request(tx.objectStore('meta').get(MARKER)),marker),'live marker readback');guard();
 },{signal});
 try{
  const stored=await readTraining(db,{signal});check(stored&&same(stored.state,state),'live restart root');
  check(same(trainingProof(stored).source,source),'live restart source oracle');return await openWriter(db,{bundle:stored,guard,signal});
 }catch(failure){throw Object.assign(Error('Nie potwierdzono odczytu po zapisie. Nie usunięto danych. '+failure.message,{cause:failure}),{code:'post-complete-readback'});}
}
/** Full operation for archive additions, preimages and explicit import/restore. A confirmed restore can quarantine a corrupt representation
 * as exact opaque evidence; normal operations never purge immutable records. */
export async function replaceSource(db,input,{expectedState,ownerId,modelEnabled,legacyRaw,signal,guard=()=>{},recovery=false,revision=0}={}){
 portable(input);const source=freeze(structuredClone(input)),before=await readRecords(db,{signal});
 check(same(before.state??null,expectedState??null),'bulk root CAS');
 if(!recovery)await auditBundle(before,{signal});
 if(recovery)portable(before.records); // Never lose non-JSON corruption in an opaque JSON preimage.
 const previousRevision=Number.isSafeInteger(before.state?.revision)?before.state.revision:revision;
 const checkpoint=recovery?{id:'recovery:'+crypto.randomUUID(),protocol:2,raw:JSON.stringify(before.records)}:null;
 if(checkpoint)checkpoint.sha256=await sha(checkpoint.raw);
 let bundle=await createProtocol(source,{epoch:recovery?crypto.randomUUID():before.state.epoch,revision:previousRevision+1,ownerId,modelEnabled,legacyRaw,checkpoints:recovery?[checkpoint]:before.records.journalCheckpoints,signal});
 if(before.state?.runtime){
  const runtime=await (await import('./journal-runtime-index.mjs')).buildRuntime(source,{signal,sourceRoot:before.state.indexRoot});
  const records={...bundle.records,journalObjects:[...new Map([...bundle.records.journalObjects,...runtime.objects].map(r=>[r.id,r])).values()],journalIndex:[...new Map([...bundle.records.journalIndex,...runtime.nodes].map(r=>[r.id,r])).values()]};
  const state=await sealState({...bundle.state,runtime:{...runtime.runtime,sourceRoot:bundle.state.indexRoot}});records.journalState=[state];bundle=freeze({state,records});
 }
 const anticipated={...bundle.records};
 for(const store of ['journalObjects','journalIndex'])anticipated[store]=[...new Map([...(recovery?[]:before.records[store]),...bundle.records[store]].map(r=>[r.id,r])).values()];
 anticipated.journalCheckpoints=recovery?[checkpoint]:before.records.journalCheckpoints;
 const allocated=await sealState({...bundle.state,allocation:await allocationFor(anticipated)});
 anticipated.journalState=[allocated];bundle=freeze({state:allocated,records:{...bundle.records,journalState:[allocated]}});
 check(same(await materialize({state:bundle.state,records:anticipated},{signal}),source),'bulk retained capacity/source oracle');
 await transact(db,[...STORES,'meta'],'readwrite',async tx=>{
  guard();await equalRows(tx,before.records);
  if(recovery){
   // Explicit restore only, with the complete raw preimage kept in this same
   // transaction. Corrupt hash-addressed records cannot stay in the active set.
   for(const store of STORES)tx.objectStore(store).clear();
   tx.objectStore('journalCheckpoints').add(checkpoint);await readback(tx,'journalCheckpoints',[checkpoint]);
  }else for(const store of ROW_STORES)tx.objectStore(store).clear();
  await addImmutable(tx,'journalObjects',bundle.records.journalObjects);await addImmutable(tx,'journalIndex',bundle.records.journalIndex);
  for(const store of ROW_STORES)for(const row of bundle.records[store])tx.objectStore(store).add(row);
  for(const store of ROW_STORES){
   const actual=await request(tx.objectStore(store).getAll()),expected=bundle.records[store];
   check(actual.length===expected.length,'bulk row count');await readback(tx,store,expected);
  }
  await readback(tx,'journalObjects',bundle.records.journalObjects);await readback(tx,'journalIndex',bundle.records.journalIndex);
  tx.objectStore('journalState').put(bundle.state);await readback(tx,'journalState',[bundle.state]);
  const marker={key:MARKER,protocol:2,status:'active',epoch:bundle.state.epoch};tx.objectStore('meta').put(marker);check(same(await request(tx.objectStore('meta').get(MARKER)),marker),'bulk marker readback');guard();
 },{signal});
 try{
  const stored=await readRecords(db,{signal});check(same(stored.state,bundle.state),'bulk restart revision');
  check(same(await auditBundle(stored,{signal}),source),'bulk restart source');return await openWriter(db,{bundle:stored,signal,guard});
 }catch(failure){throw Object.assign(Error('Nie potwierdzono odczytu po zapisie. Kopia sprzed operacji została zachowana. Odśwież aplikację. '+failure.message),{code:'post-complete-readback'});}
}
export async function openWriter(db,{bundle,signal,guard=()=>{},limits:requestedLimits}={}){
 const limits=limitsFor(requestedLimits);
 let saved=protocolInput(bundle??await readRecords(db,{signal})),training=trainingProof(saved),source=training?.source??await auditBundle(saved,{signal,limits}),state=saved.state,busy=false;
 let allocation=training?.budget??protocolBudget(saved);validateAllocation(allocation,limits);
 if(state.runtime){const {openIndexedWriter}=await import('./journal-runtime.mjs');return openIndexedWriter(db,{guard,signal,completeSource:source,bundle:saved,limits});}
 const maps=Object.fromEntries(STORES.map(s=>[s,new Map(saved.records[s].map(r=>[r.id,r]))]));saved=null;
 if(training)for(const id of training.objectIds)if(!maps.journalObjects.has(id))maps.journalObjects.set(id,null);
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
   const newObject=maps.journalObjects.has(object.id)?0:1,newNodes=[...tree.added.keys()].filter(id=>!maps.journalIndex.has(id)).length;
   const nextAllocation={bytes:allocation.bytes+(newObject?object.bytes:0),records:allocation.records+newObject+newNodes+(old?0:1),maxObjectBytes:Math.max(allocation.maxObjectBytes,object.bytes)};
   check(nextAllocation.bytes<=limits.totalBytes,'protocol total size');check(nextAllocation.records<=limits.records,'protocol record count');
   const next=await sealState({...before,revision:before.revision+1,indexRoot:tree.root,counts:{...before.counts,journalResults:before.counts.journalResults+(old?0:1)},...(before.allocation?{allocation:nextAllocation}:{})});
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
