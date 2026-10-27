/** Native selective reader and strict delta writer. No history array rebuilding. */
import {freeze,portable,requireThat as check} from './backup-json.mjs';
import {STORES,ROW_STORES,protocolInput,trainingProof,protocolBudget,materialize,objectRecord,readObject,sealState,validateState,validateAllocation,limitsFor} from './journal-protocol.mjs';
import {hashJSON,indexKey,editIndex,checkAbort,committedNodes} from './journal-index.mjs';
import {runtimeKey,lookupIndex,buildRuntime,descriptor,contextSummary,resultIds,runtimeInfo,sessionHeader} from './journal-runtime-index.mjs';
import {transact,request,same,MARKER,readRecords} from './journal-idb.mjs';
import * as journal from './journal.mjs';
import {validateSessionSnapshot} from './training-model.mjs';
import {prepareLegacyBackup} from './legacy-backup.mjs';
import {comparison} from './performance.mjs';
const proofs=new WeakMap();
function sessionData(source,{starting=false}={}){
 const d=source.data,j=d.trainingJournal;
 return {...d,exercises:starting?structuredClone(d.exercises):d.exercises,sessions:d.sessions.slice(),entries:d.entries,
 ...(j?{trainingJournal:{...j,...(starting?{model:structuredClone(j.model)}:{}),sessionSnapshots:j.sessionSnapshots.slice()}}:{})};
}
async function checkRows(tx,store,rows,message){
 const actual=await Promise.all(rows.map(row=>request(tx.objectStore(store).get(row.id))));
 rows.forEach((row,i)=>check(same(actual[i],row),message+' '+store));
}
async function addRows(tx,store,rows){
 const actual=await Promise.all(rows.map(row=>request(tx.objectStore(store).get(row.id))));
 rows.forEach((row,i)=>{if(actual[i])check(same(actual[i],row),'immutable collision '+store);else tx.objectStore(store).add(row)});
}
const marker=state=>({key:MARKER,protocol:2,status:'active',epoch:state.epoch});
/** Capture per-key reads with a root CAS on completion. Hashing never holds a tx. */
export async function reader(db,state,{signal}={}){
 validateState(state);validateAllocation(state.allocation);check(state.runtime?.version===1,'runtime index required');
 const {root,...body}=state;check(root===await hashJSON(body),'state SHA-256');
 const maps=Object.fromEntries(STORES.map(s=>[s,new Map()])),values=new Map(),pending=new Map();
 async function get(store,id){
  checkAbort(signal);if(maps[store].has(id))return maps[store].get(id);
  const key=indexKey(store,id);
  // Concurrent paths often share the same node/model. One owned native read,
  // one immutable proof; every use still participates in the strict tx CAS.
  if(!pending.has(key))pending.set(key,transact(db,[store],'readonly',tx=>request(tx.objectStore(store).get(id)),{signal}).then(value=>{const row=value?freeze(value):null;maps[store].set(id,row);return row}));
  return pending.get(key);
 }
 const node=id=>get('journalIndex',id);
 async function object(id){if(!values.has(id))values.set(id,(async()=>readObject(await get('journalObjects',id)))());return values.get(id)}
 async function row(store,id){const value=await get(store,id);check(value&&await lookupIndex(state.indexRoot,indexKey(store,id),node,{signal})===await hashJSON(value),'required index record');return value;}
 async function collection(store,id){const r=await row(store,id);return r.fields?freeze(Object.fromEntries(await Promise.all(r.fields.map(async([key,ref])=>[key,await object(ref)])))):object(r.ref)}
 async function runtime(...parts){const id=await lookupIndex(state.runtime.indexRoot,runtimeKey(...parts),node,{signal});return id?object(id):null}
 async function metadata(id){const r=await row('journalMetadata',id),entries=await Promise.all(r.fields.map(async([key,slot])=>[key,slot.kind==='object'?await object(slot.ref):slot.kind==='metadata'?await metadata(slot.id):[]]));return freeze(Object.fromEntries(entries))}
 async function stable(){const actual=await transact(db,[...STORES,'meta'],'readonly',async tx=>({state:await request(tx.objectStore('journalState').get('active')),marker:await request(tx.objectStore('meta').get(MARKER)),counts:Object.fromEntries(await Promise.all(STORES.map(async store=>[store,await request(tx.objectStore(store).count())])))}),{signal});check(same(actual.state,state),'selective root CAS');check(same(actual.marker,marker(state)),'protocol marker');
  for(const store of ROW_STORES)check(actual.counts[store]===state.counts[store],'selective collection count');
  check(actual.counts.journalState===1&&Object.values(actual.counts).reduce((n,v)=>n+v,0)===state.allocation.records,'selective allocation count');}

 return {state,maps,object,row,collection,runtime,metadata,stable,node};
}
async function selectedSource(r){
 const base=await r.metadata('source'),d=base.data,info=await r.runtime('info');check(info&&Number.isSafeInteger(info.maxSeq),'runtime info');
 const sessionIds=new Set([d.activeId,info.lastDone].filter(Boolean)),snapshotIds=new Set(info.previews),entryIds=new Set(),ages=new Map();
 const initialSessions=await Promise.all([...sessionIds].map(id=>r.collection('journalSessions',id)));
 const active=initialSessions.find(s=>s.id===d.activeId);if(active?.journalSnapshotId)snapshotIds.add(active.journalSnapshotId);
 const initialSnapshots=await Promise.all([...snapshotIds].map(id=>r.collection('journalSnapshots',id)));
 const previewData={...d,sessions:initialSessions,...(d.trainingJournal?{trainingJournal:{...d.trainingJournal,sessionSnapshots:initialSnapshots}}:{})};
 const displayed=journal.units(previewData).flatMap(u=>journal.previewExercises(previewData,u.id));
 if(active)displayed.push(...journal.exercisesFor(previewData,active));
 const contexts=new Map();for(const view of displayed)for(const ex of view.members??[view]){if(!contexts.has(ex.id))contexts.set(ex.id,[]);contexts.get(ex.id).push(ex)}
 for(const [id,views] of contexts){
  const c=await r.runtime('context',id);if(!c)continue;
  for(const h of c.heads){
   const [variant,plan,unit,basis]=h.selector;
   if(!views.some(ex=>(ex.journalVariantId?variant===ex.journalVariantId:variant===null)&&(!ex.planVersionId||plan===ex.planVersionId)&&(!ex.imported||(ex.loadConvention.basis===null||basis===ex.loadConvention.basis)&&unit===ex.loadConvention.unit)))continue;
   entryIds.add(h.id);sessionIds.add(h.sessionId);if(h.snapshotId)snapshotIds.add(h.snapshotId);
  }
  for(const [key,age] of c.ages)ages.set(key,age);
 }
 if(d.activeId){const entries=await r.runtime('session',d.activeId);check(Array.isArray(entries),'runtime active session');for(const id of entries)entryIds.add(id);}
 const sessions=await Promise.all([...sessionIds].map(id=>r.collection('journalSessions',id)));
 for(const s of sessions)if(s.journalSnapshotId)snapshotIds.add(s.journalSnapshotId);
 const entries=await Promise.all([...entryIds].map(id=>r.collection('journalResults',id))),snapshots=await Promise.all([...snapshotIds].map(id=>r.collection('journalSnapshots',id)));
 for(const snap of snapshots){validateSessionSnapshot(snap);const s=sessions.find(s=>s.id===snap.sessionId);if(!s){sessions.push(await r.collection('journalSessions',snap.sessionId))}check((sessions.find(s=>s.id===snap.sessionId)).journalSnapshotId===snap.id,'snapshot session relation');}
 const source=freeze({...base,data:{...d,sessions,entries,...(d.trainingJournal?{trainingJournal:{...d.trainingJournal,sessionSnapshots:snapshots}}:{})}});
 // Required live fragments have the exact same full entry validators as writes.
 for(const e of entries){const session=sessions.find(s=>s.id===e.sessionId);check(session,'indexed result session');validateEntry(source.data,e,session);}
 await r.stable();return {source,info,ages};
}
function validateEntry(d,e,session){
 const snap=d.trainingJournal?.sessionSnapshots.find(s=>s.sessionId===e.sessionId);
 if(snap){validateSessionSnapshot(snap);check(session.journalSnapshotId===snap.id&&snap.unitId===session.type,'result snapshot relation')}
 const probe=freeze({version:1,exercises:d.exercises,sessions:[session],entries:[e],nextType:d.nextType,activeId:session.status==='active'?session.id:null,
 ...(d.trainingJournal?{trainingJournal:{model:{planVersions:d.trainingJournal.model.planVersions},sessionSnapshots:snap?[snap]:[]}}:{})});
 PushPullStorage.validate(probe);prepareLegacyBackup(probe);resultIds(d,e);
}
export async function readIndexed(db,{signal}={}){
 const state=await transact(db,['journalState'],'readonly',tx=>request(tx.objectStore('journalState').get('active')),{signal});if(!state?.runtime)return null;
 const r=await reader(db,state,{signal}),view=await selectedSource(r),token=freeze({state});proofs.set(token,{r,...view});return token;
}
/** One-time full live verification before installing the index. Retains every
 * original object, row, checkpoint and archive. No schema/versionchange. */
export async function installRuntime(db,bundle,{guard=()=>{},signal}={}){
 if(bundle.state.runtime)return;
 const source=trainingProof(bundle)?.source??await materialize(bundle),budget=trainingProof(bundle)?.budget??protocolBudget(bundle),built=await buildRuntime(source,{signal,sourceRoot:bundle.state.indexRoot});
 const objects=new Map(bundle.records.journalObjects.map(r=>[r.id,r])),nodes=new Map(bundle.records.journalIndex.map(r=>[r.id,r]));
 // Training proof includes all retained IDs, even objects not read at startup.
 const ids=new Set(trainingProof(bundle)?.objectIds??objects.keys());const addedObjects=built.objects.filter(r=>!ids.has(r.id)),addedNodes=built.nodes.filter(r=>!nodes.has(r.id));
 const allocation={bytes:budget.bytes+addedObjects.reduce((n,r)=>n+r.bytes,0),records:budget.records+addedObjects.length+addedNodes.length,maxObjectBytes:Math.max(budget.maxObjectBytes,...addedObjects.map(r=>r.bytes))};validateAllocation(allocation);
 // This installs derived representation only; the journal has not changed.
 // Preserve its revision/draft observations. The changed SHA-bound full root
 // still makes every older prepared writer fail its exact root CAS.
 const state=await sealState({...bundle.state,runtime:built.runtime,allocation});
 await transact(db,[...STORES,'meta'],'readwrite',async tx=>{
  guard();check(same(await request(tx.objectStore('journalState').get('active')),bundle.state),'install root CAS');check(same(await request(tx.objectStore('meta').get(MARKER)),marker(state)),'install marker');
  for(const store of ROW_STORES){check(await request(tx.objectStore(store).count())===bundle.records[store].length,'install count CAS');for(const row of bundle.records[store])check(same(await request(tx.objectStore(store).get(row.id)),row),'install row CAS')}
  for(const [store,rows] of [['journalObjects',bundle.records.journalObjects],['journalIndex',bundle.records.journalIndex]])for(const row of rows)check(same(await request(tx.objectStore(store).get(row.id)),row),'install content CAS');
  for(const [store,rows] of [['journalObjects',built.objects],['journalIndex',built.nodes]])for(const row of rows){const old=await request(tx.objectStore(store).get(row.id));if(old)check(same(old,row),'install immutable collision');else tx.objectStore(store).add(row);check(same(await request(tx.objectStore(store).get(row.id)),row),'install readback')}
  tx.objectStore('journalState').put(state);check(same(await request(tx.objectStore('journalState').get('active')),state),'install root readback');guard();
 },{signal});
}
export async function openIndexedWriter(db,{token,guard=()=>{},signal,completeSource=null,bundle=null,limits:requestedLimits}={}){
 const limits=limitsFor(requestedLimits);token??=await readIndexed(db,{signal});check(proofs.has(token),'selective proof required');
 let {r,source,info,ages}=proofs.get(token),state=r.state,busy=false;
 if(completeSource)source=completeSource;
 const knownRows=Object.fromEntries(ROW_STORES.map(store=>[store,new Map(r.maps[store])]));
 if(bundle)for(const store of ROW_STORES)for(const row of bundle.records[store])knownRows[store].set(row.id,row);
 const legacy=await r.object(state.legacyRef);check(legacy===null||typeof legacy==='string','legacy anchor');
 const context=(sessionId,exerciseId)=>{
  const e=source.data.entries.find(e=>e.sessionId===sessionId&&e.exerciseId===exerciseId),snap=source.data.trainingJournal?.sessionSnapshots.find(s=>s.sessionId===sessionId);
  return {expectedEpoch:state.epoch,expectedRevision:state.revision,expectedEntryHash:e?knownRows.journalResults.get(e.id)?.ref??null:null,snapshotHash:snap?knownRows.journalSnapshots.get(snap.id)?.fields.find(([k])=>k==='model')[1]:null};
 };
 async function change(prepare,{signal}={}){
  checkAbort(signal);check(!busy,'writer busy');busy=true;
  try{
   guard();await r.metadata('source');const before=state,changed=[],objects=new Map(),runtimeChanges=new Map();
   async function ref(v){const row=await objectRecord(v,limits);objects.set(row.id,row);return row.id}
   async function collection(store,value){const old=await r.row(store,value.id);
    const row={id:value.id,version:(old?.version??0)+1,position:old?.position??before.counts[store],...(store==='journalSnapshots'?{fields:await Promise.all(Object.entries(value).map(async([k,v])=>[k,await ref(v)]))}:{ref:await ref(value)})};check(Number.isSafeInteger(row.version),'record version limit');changed.push({store,row});return row;
   }
   async function putNew(store,value){
    const id=value.id;check(await lookupIndex(before.indexRoot,indexKey(store,id),r.node,{signal})===null,'new identity collision');
    check(!await transact(db,[store],'readonly',tx=>request(tx.objectStore(store).get(id)),{signal}),'new record collision');
    const row={id,version:1,position:before.counts[store],...(store==='journalSnapshots'?{fields:await Promise.all(Object.entries(value).map(async([k,v])=>[k,await ref(v)]))}:{ref:await ref(value)})};check(Number.isSafeInteger(row.version),'record version limit');changed.push({store,row});return row;
   }
   async function metadata(id,value){const old=await r.row('journalMetadata',id),fields=[],slots=new Map(old.fields);
    for(const [key,item] of Object.entries(value)){const slot=slots.get(key);fields.push([key,!slot||slot.kind==='object'&&item!==await r.object(slot.ref)?{kind:'object',ref:await ref(item)}:slot]);}
    const row=freeze({...old,version:old.version+1,fields});check(Number.isSafeInteger(row.version),'metadata version limit');changed.push({store:'journalMetadata',row});
   }
   async function index(parts,value){runtimeChanges.set(runtimeKey(...parts),value===undefined?null:await ref(value));}
   const result=await prepare({ref,collection,putNew,metadata,index,before});checkAbort(signal);
   const primary=await editIndex(before.indexRoot,r.node,await Promise.all(changed.map(async({store,row})=>[indexKey(store,row.id),await hashJSON(row)])),{signal});
   const secondary=await editIndex(before.runtime.indexRoot,r.node,runtimeChanges,{signal});
   const nodes=committedNodes([primary.root,secondary.root],new Map([...primary.added,...secondary.added]));
   let addBytes=0,addRecords=0,maxObjectBytes=before.allocation.maxObjectBytes;
   await transact(db,['journalObjects','journalIndex'],'readonly',async tx=>{
    await Promise.all([['journalObjects',objects],['journalIndex',nodes]].map(async([store,rows])=>{
     const pairs=[...rows],actual=await Promise.all(pairs.map(([id])=>request(tx.objectStore(store).get(id))));
     pairs.forEach(([,row],i)=>{if(actual[i])check(same(actual[i],row),'immutable collision');else{addRecords++;if(store==='journalObjects'){addBytes+=row.bytes;maxObjectBytes=Math.max(maxObjectBytes,row.bytes)}}});
    }));
   },{signal});
   const counts={...before.counts};for(const {store,row} of changed)if(row.version===1){counts[store]++;addRecords++}
   const allocation={bytes:before.allocation.bytes+addBytes,records:before.allocation.records+addRecords,maxObjectBytes};validateAllocation(allocation,limits);
   const next=await sealState({...before,revision:before.revision+1,indexRoot:primary.root,counts,allocation,runtime:{version:1,indexRoot:secondary.root,sourceRoot:primary.root}});
   // Capture every authenticated dependency, including absence paths, in CAS.
   await transact(db,[...STORES,'meta'],'readwrite',async tx=>{
    guard();check(same(await request(tx.objectStore('journalState').get('active')),before),'root CAS');check(same(await request(tx.objectStore('meta').get(MARKER)),marker(before)),'protocol marker');
    const counts=await Promise.all(STORES.map(store=>request(tx.objectStore(store).count())));
    for(const store of ROW_STORES)check(counts[STORES.indexOf(store)]===before.counts[store],'collection count CAS');
    check(counts.reduce((n,v)=>n+v,0)===before.allocation.records,'allocation count CAS');
    await Promise.all([...ROW_STORES,'journalObjects','journalIndex'].map(store=>checkRows(tx,store,[...r.maps[store].values()].filter(Boolean),'required CAS')));
    await checkRows(tx,'journalIndex',[...primary.observed.values(),...secondary.observed.values()],'index CAS');
    const newRows=changed.filter(v=>v.row.version===1),existing=await Promise.all(newRows.map(({store,row})=>request(tx.objectStore(store).get(row.id))));
    check(existing.every(v=>!v),'new record CAS');
    for(const [store,rows] of [['journalObjects',objects],['journalIndex',nodes]])await addRows(tx,store,[...rows.values()]);
    for(const {store,row} of changed){if(row.version===1)tx.objectStore(store).add(row);else tx.objectStore(store).put(row);}tx.objectStore('journalState').put(next);
    await Promise.all([['journalObjects',objects],['journalIndex',nodes]].map(([store,rows])=>checkRows(tx,store,[...rows.values()],'delta readback')));
    await Promise.all(changed.map(({store,row})=>checkRows(tx,store,[row],'delta readback')));
    check(same(await request(tx.objectStore('journalState').get('active')),next),'root readback');check(same(await request(tx.objectStore('meta').get(MARKER)),marker(next)),'marker readback');guard();
   },{signal});
   // Publish only after the native strict transaction's complete event.
   state=next;source=result.source;info=result.info??info;ages=result.ages??ages;
   r=await reader(db,state);
   for(const {store,row} of changed)knownRows[store].set(row.id,row);
   // Seed only proven committed rows/objects/nodes, plus previous verified input.
   for(const {store,row} of changed)r.maps[store].set(row.id,row);
   for(const [id,row] of objects)r.maps.journalObjects.set(id,row);for(const [id,row] of nodes)r.maps.journalIndex.set(id,row);
   return freeze({...result.ack,epoch:state.epoch,revision:state.revision});
  }finally{busy=false}
 }
 async function saveResult(command,options={}){
  portable(command);const cmd=protocolInput(command);
  return change(async({collection,putNew,index,before})=>{
   const e=cmd.entry,d=source.data,oldId=await r.runtime('pair',cmd.sessionId,cmd.exerciseId),old=oldId?await r.collection('journalResults',oldId):null;
   const session=await r.collection('journalSessions',e.sessionId);let snapshots=d.trainingJournal?.sessionSnapshots??[];
   if(session.journalSnapshotId){const verified=await r.collection('journalSnapshots',session.journalSnapshotId);snapshots=snapshots.some(s=>s.id===verified.id)?snapshots.map(s=>s.id===verified.id?verified:s):[...snapshots,verified];}
   const data={...d,sessions:d.sessions.some(s=>s.id===session.id)?d.sessions.map(s=>s.id===session.id?session:s):[...d.sessions,session],...(d.trainingJournal?{trainingJournal:{...d.trainingJournal,sessionSnapshots:snapshots}}:{})};
   check(cmd.expectedEpoch===before.epoch&&cmd.expectedRevision===before.revision&&cmd.expectedEntryHash===(oldId?r.maps.journalResults.get(oldId).ref:null),'result CAS');
   const snap=snapshots.find(s=>s.sessionId===session.id),snapHash=snap?r.maps.journalSnapshots.get(snap.id)?.fields.find(([k])=>k==='model')[1]:null;
   check(cmd.snapshotHash===snapHash,'result snapshot CAS');check(e.sessionId===cmd.sessionId&&e.exerciseId===cmd.exerciseId&&(!old||e.id===old.id),'result identity');validateEntry(data,e,session);
   const newIds=resultIds(data,e);check(new Set(newIds).size===newIds.length,'duplicate global result ID');
   for(const id of newIds){const owner=await r.runtime('global',id);check(owner===null||owner===oldId,'duplicate global result ID');await index(['global',id],e.id)}
   if(old)for(const id of resultIds(data,old))if(!newIds.includes(id))await index(['global',id],undefined);
   const row=old?await collection('journalResults',e):await putNew('journalResults',e);
   await index(['pair',e.sessionId,e.exerciseId],e.id);const sessionEntries=await r.runtime('session',session.id);check(Array.isArray(sessionEntries),'runtime session');if(!old)await index(['session',session.id],[...sessionEntries,e.id]);
   const history=[...(await r.runtime('history',e.exerciseId)??[])],at=history.findIndex(ds=>ds.id===e.id);if(at<0)history.push(descriptor(data,e));else history[at]=descriptor(data,e);const summary=contextSummary(history);
   await index(['history',e.exerciseId],history);await index(['context',e.exerciseId],summary);
   const nextAges=new Map(ages);for(const [k,v] of summary.ages)nextAges.set(k,v);
   return {source:freeze({...source,data:{...data,entries:d.entries.some(v=>v.id===e.id)?d.entries.map(v=>v.id===e.id?e:v):[...d.entries,e]}}),ages:nextAges,ack:{entry:e,entryHash:row.ref}};
  },options);
 }
 async function startSession(command,options={}){
  portable(command);const cmd=protocolInput(command);
  return change(async({putNew,metadata,index,before})=>{
   check(cmd.expectedEpoch===before.epoch&&cmd.expectedRevision===before.revision,'session CAS');check(!source.data.activeId,'session already active');
   const d=sessionData(source,{starting:true}),s={id:cmd.id,seq:info.maxSeq+1,type:cmd.type,date:cmd.date,status:'active'};
   d.sessions.push(s);d.activeId=s.id;journal.prepareSourceSession(d,s);if(d.trainingJournal)await journal.startSession(d,s,cmd.startedAt);
   PushPullStorage.validate({...d,sessions:[s],entries:[]});
   const snapshot=d.trainingJournal?.sessionSnapshots.find(snap=>snap.sessionId===s.id);if(snapshot)validateSessionSnapshot(snapshot);
   await putNew('journalSessions',s);if(snapshot)await putNew('journalSnapshots',snapshot);
   const catalog=PushPullDB.catalogFor({...d,sessions:[s]},source.catalog);await metadata('source',{...source,catalog});await metadata('data',d);if(d.trainingJournal)await metadata('journal',d.trainingJournal);
   await index(['session',s.id],[]);const nextInfo={...info,maxSeq:s.seq};
   if(snapshot&&!d.trainingJournal.activePlanVersionId){nextInfo.previews=info.previews.filter(id=>source.data.trainingJournal.sessionSnapshots.find(sn=>sn.id===id)?.unitId!==s.type);nextInfo.previews.push(snapshot.id);nextInfo.previews.sort((a,b)=>Object.keys(d.exercises).indexOf(d.trainingJournal.sessionSnapshots.find(sn=>sn.id===a)?.unitId)-Object.keys(d.exercises).indexOf(d.trainingJournal.sessionSnapshots.find(sn=>sn.id===b)?.unitId))}
   await index(['info'],nextInfo);return {source:freeze({...source,data:d,catalog}),info:nextInfo,ack:{session:s}};
  },options);
 }
 async function finishSession(command,options={}){
  portable(command);const cmd=protocolInput(command);
  return change(async({collection,metadata,index,before})=>{
   check(cmd.expectedEpoch===before.epoch&&cmd.expectedRevision===before.revision,'session CAS');check(source.data.activeId===cmd.id,'active session CAS');
   await r.collection('journalSessions',cmd.id);const active=source.data.sessions.find(s=>s.id===cmd.id);if(active?.journalSnapshotId)await r.collection('journalSnapshots',active.journalSnapshotId);
   const d=sessionData(source),oldSession=d.sessions.find(s=>s.id===cmd.id);check(oldSession?.status==='active','active session');const s={...oldSession,status:'done'};d.sessions=d.sessions.map(v=>v.id===s.id?s:v);d.activeId=null;journal.advance(d,s);
   await collection('journalSessions',s);await metadata('data',d);if(d.trainingJournal)await metadata('journal',d.trainingJournal);
   const sessionEntries=await r.runtime('session',s.id),exerciseIds=new Set();for(const id of sessionEntries){const entry=await r.collection('journalResults',id);exerciseIds.add(entry.exerciseId)}
   const nextAges=new Map(ages);
   for(const id of exerciseIds){const history=await r.runtime('history',id);check(history,'runtime history');const next=history.map(ds=>ds.session.id===s.id?{...ds,session:sessionHeader(s)}:ds),summary=contextSummary(next);await index(['history',id],next);await index(['context',id],summary);for(const [k,v] of summary.ages)nextAges.set(k,v)}
   const nextInfo={...info,lastDone:info.lastDone&&d.sessions.find(v=>v.id===info.lastDone)?.seq>s.seq?info.lastDone:s.id};await index(['info'],nextInfo);
   return {source:freeze({...source,data:d}),info:nextInfo,ages:nextAges,ack:{session:s}};
  },options);
 }
 return {context,saveResult,startSession,finishSession,get source(){return source},get state(){return state},get legacyRaw(){return legacy},
  sessionContext(){return {expectedEpoch:state.epoch,expectedRevision:state.revision}},changeAge(entry){const c=comparison(source.data,entry);return c?(ages.get(c.context)??null):null},
  async audit(){return materialize(await readRecords(db))}};
}
