/** Issue #82 A: isolated lossless protocol. No database opening or UI imports. */
import {freeze,portable,immutableJSON,parseJson,requireThat as check} from './backup-json.mjs';
import * as legacyModel from './legacy-model.mjs';
import {hashJSON,sha,shaBytes,encodedJSON,buildIndex,auditIndex,indexKey,checkAbort} from './journal-index.mjs';
/** Ordered JSON equality without allocating two multi-megabyte JSON strings.
 * Callers validate portable JSON at their trust boundary. */
export function equalJSON(a,b,{ordered=true}={}){
 const visited=new WeakMap();
 function equal(x,y){
  if(x===y)return true;
  if(x===null||y===null||typeof x!=='object'||typeof y!=='object'||Array.isArray(x)!==Array.isArray(y))return false;
  if(visited.get(x)?.has(y))return true;
  const left=Object.keys(x),right=Object.keys(y);
  if(left.length!==right.length)return false;
  if(ordered||Array.isArray(x)){if(left.some((k,i)=>k!==right[i]))return false;}
  else if(left.some(k=>!Object.hasOwn(y,k)))return false;
  if(!visited.has(x))visited.set(x,new WeakSet());visited.get(x).add(y);
  return left.every(k=>equal(x[k],y[k]));
 }
 return equal(a,b);
}
export const PROTOCOL=2;
export const ROW_STORES=['journalMetadata','journalSessions','journalResults','journalSnapshots','journalArchives'];
export const STORES=['journalObjects',...ROW_STORES,'journalIndex','journalState','journalCheckpoints'];
// Allocation guards, not promises of device capacity. Conversion can fail safely
// below these limits; neither the old checkpoint nor archives are discarded.
export const LIMITS=Object.freeze({objectBytes:128*1024*1024,totalBytes:512*1024*1024,records:1000000});
const verifiedBundles=new WeakMap();
const trainingBundles=new WeakMap();
const checkpointDigests=new WeakMap();
const verifiedObjects=new WeakMap();
async function checkpointDigest(checkpoint,maxBytes=LIMITS.totalBytes){
 checkpoint=protocolInput(checkpoint);
 if(!checkpointDigests.has(checkpoint)){
  // Only a deeply immutable, portable checkpoint gets a reusable byte proof.
  check(immutableJSON(checkpoint),'immutable checkpoint required');
  const bytes=encodedJSON(JSON.stringify(checkpoint),maxBytes);
  checkpointDigests.set(checkpoint,{bytes:bytes.length,sha256:await shaBytes(bytes)});
 }
 const proof=checkpointDigests.get(checkpoint);check(proof.bytes<=maxBytes,'protocol total size');return proof;
}
export function protocolInput(value){portable(value);return immutableJSON(value)?value:freeze(structuredClone(value));}
export function protocolBudget(bundle){check(verifiedBundles.has(bundle),'verified immutable bundle required');return verifiedBundles.get(bundle).budget;}
export function trainingProof(bundle){return trainingBundles.get(bundle);}
export function limitsFor(options={}){const limits={...LIMITS,...options};for(const [key,n] of Object.entries(limits))check(Object.hasOwn(LIMITS,key)&&Number.isSafeInteger(n)&&n>0&&n<=LIMITS[key],'protocol limit');return limits;}
export async function objectRecord(value,limits=LIMITS){
 portable(value);const json=JSON.stringify(value),bytes=encodedJSON(json,limits.objectBytes);
 return freeze({id:await shaBytes(bytes),json,bytes:bytes.length});
}
export async function readObject(row,limits=LIMITS){
 portable(row);
 const proven=verifiedObjects.get(row);
 if(verifiedObjects.has(row)){check(row.bytes<=limits.objectBytes,'object size');return proven;}
 row=Object.isFrozen(row)?row:freeze({...row}); // Detach mutable rows before SHA awaits.
 check(row&&Object.keys(row).join(',')==='id,json,bytes'&&typeof row.json==='string','object shape');
 check(Number.isSafeInteger(row.bytes)&&row.bytes<=limits.objectBytes,'object size');const bytes=encodedJSON(row.json,limits.objectBytes);check(row.bytes===bytes.length,'object size');
 check(row.id===await shaBytes(bytes),'object SHA-256');const value=parseJson(row.json);portable(value);const owned=freeze(value);verifiedObjects.set(row,owned);return owned;
}
export function validateState(state){
 if(state&&Object.hasOwn(state,'runtime'))check(state.runtime&&Object.keys(state.runtime).join(',')==='version,indexRoot,sourceRoot'&&state.runtime.version===1&&state.runtime.sourceRoot===state.indexRoot&&/^[a-f0-9]{64}$/.test(state.runtime.indexRoot),'runtime index version/root');
 check(state&&['id,protocol,epoch,revision,indexRoot,counts,ownerId,modelEnabled,legacyRef,checkpointRefs,root','id,protocol,epoch,revision,indexRoot,counts,ownerId,modelEnabled,legacyRef,checkpointRefs,allocation,root','id,protocol,epoch,revision,indexRoot,counts,ownerId,modelEnabled,legacyRef,checkpointRefs,allocation,runtime,root'].includes(Object.keys(state).join(',')),'state shape');
 check(state.id==='active'&&state.protocol===PROTOCOL&&typeof state.epoch==='string'&&state.epoch.length>0&&Number.isSafeInteger(state.revision)&&state.revision>=0&&[state.root,state.indexRoot].every(v=>/^[a-f0-9]{64}$/.test(v))&&typeof state.ownerId==='string'&&state.ownerId.length>0,'protocol state');
 check(Object.keys(state.counts).join(',')===ROW_STORES.join(',')&&Object.values(state.counts).every(n=>Number.isSafeInteger(n)&&n>=0)&&typeof state.modelEnabled==='boolean'&&/^[a-f0-9]{64}$/.test(state.legacyRef),'state counts/capability');
 check(Array.isArray(state.checkpointRefs)&&state.checkpointRefs.every(r=>r&&Object.keys(r).join(',')==='id,sha256'&&typeof r.id==='string'&&r.id.length>0&&/^[a-f0-9]{64}$/.test(r.sha256))&&new Set(state.checkpointRefs.map(r=>r.id)).size===state.checkpointRefs.length,'checkpoint references');return state;
}
export function validateAllocation(budget,limits=LIMITS){
 check(budget&&Object.keys(budget).join(',')==='bytes,records,maxObjectBytes'&&Object.values(budget).every(n=>Number.isSafeInteger(n)&&n>=0),'allocation shape');
 check(budget.bytes<=limits.totalBytes&&budget.maxObjectBytes<=limits.objectBytes&&budget.records<=limits.records,'protocol retained size/count limit');return budget;
}
export async function allocationFor(records){
 let bytes=0,maxObjectBytes=0;
 for(const row of records.journalObjects){bytes+=row.bytes;maxObjectBytes=Math.max(maxObjectBytes,row.bytes);}
 for(const cp of records.journalCheckpoints)bytes+=(await checkpointDigest(cp,LIMITS.totalBytes-bytes)).bytes;
 return {bytes,records:Object.values(records).reduce((n,rows)=>n+rows.length,0),maxObjectBytes};
}
export async function sealState(value){const {root,...body}=value;return freeze(validateState({...body,root:await hashJSON(body)}));}
export async function validateSource(source,ownerId,createdAt='2026-10-25T00:00:00.000Z'){
 check(source?.format==='pushpull-backup'&&source.version===2,'protocol source version');
 // Existing validators include the complete native snapshot/performance graph.
 // The isolated protocol can also be exercised with the retained v1 reader.
 return legacyModel.validateStructuredSource?legacyModel.validateStructuredSource(source,ownerId):legacyModel.createLegacyModelFromSource(source,{ownerId,createdAt});
}
export async function createProtocol(input,{epoch=crypto.randomUUID(),revision=0,ownerId=input?.data?.trainingJournal?.model?.ownerId??'local-journal',modelEnabled=!!input?.data?.trainingJournal,legacyRaw=null,checkpoints=[],signal,limits:requestedLimits}={}){
 checkAbort(signal);portable(input);
 const source=immutableJSON(input)?input:freeze(structuredClone(input)),limits=limitsFor(requestedLimits),ownedCheckpoints=protocolInput(checkpoints);
 check(Array.isArray(ownedCheckpoints),'checkpoint collection');
 await validateSource(source,ownerId);checkAbort(signal);
 const records=Object.fromEntries(STORES.map(s=>[s,[]])),objects=new Map(),objectProofs=new WeakMap(),checkpointRefs=[];let total=0;
 records.journalCheckpoints=ownedCheckpoints;
 for(const checkpoint of ownedCheckpoints){const digest=await checkpointDigest(checkpoint,limits.totalBytes-total);total+=digest.bytes;check(total<=limits.totalBytes,'protocol total size');checkpointRefs.push({id:checkpoint.id,sha256:digest.sha256});}
 async function ref(value){
  if(value&&typeof value==='object'&&objectProofs.has(value))return objectProofs.get(value);
  checkAbort(signal);const row=await objectRecord(value,limits),old=objects.get(row.id);
  check(!old||old.json===row.json,'object collision');if(!old){total+=row.bytes;check(total<=limits.totalBytes,'protocol total size');objects.set(row.id,row);}
  if(value&&typeof value==='object')objectProofs.set(value,row.id);return row.id;
 }
 async function collection(store,values){
  for(let position=0;position<values.length;position++){
   checkAbort(signal);const value=values[position];
   const row={id:value.id,version:1,position};
   if(store==='journalSnapshots'){
    row.fields=[];for(const [key,item] of Object.entries(value))row.fields.push([key,await ref(item)]);
   }else row.ref=await ref(value);
   records[store].push(freeze(row));
  }
  return {kind:'collection',store};
 }
 async function metadata(id,value){
  const fields=[];
  for(const [key,item] of Object.entries(value)){
   let slot;
   if(id==='source'&&key==='data')slot=await metadata('data',item);
   else if(id==='source'&&key==='archives')slot=await collection('journalArchives',item);
   else if(id==='data'&&key==='sessions')slot=await collection('journalSessions',item);
   else if(id==='data'&&key==='entries')slot=await collection('journalResults',item);
   else if(id==='data'&&key==='trainingJournal'&&item)slot=await metadata('journal',item);
   else if(id==='journal'&&key==='sessionSnapshots')slot=await collection('journalSnapshots',item);
   else slot={kind:'object',ref:await ref(item)};
   fields.push([key,slot]);
  }
  records.journalMetadata.push(freeze({id,version:1,fields}));return {kind:'metadata',id};
 }
 check(legacyRaw===null||typeof legacyRaw==='string','legacy anchor');
 await metadata('source',source);const legacyRef=await ref(legacyRaw);records.journalObjects=[...objects.values()];
 const leaves=[];for(const store of ROW_STORES)for(const row of records[store])leaves.push([indexKey(store,row.id),await hashJSON(row)]);
 check(leaves.length<=limits.records,'protocol record count');
 const tree=await buildIndex(leaves,{signal});records.journalIndex=[...tree.nodes.values()];
 check(typeof modelEnabled==='boolean'&&(!source.data.trainingJournal||modelEnabled),'model capability');
 // Bound allocation accounting to the authenticated root. It permits a normal
 // start to avoid reading retained revision objects and recovery checkpoints.
 records.journalState=[{}];const allocation=await allocationFor(records);validateAllocation(allocation,limits);
 const state=await sealState({id:'active',protocol:PROTOCOL,epoch,revision,indexRoot:tree.root,counts:Object.fromEntries(ROW_STORES.map(s=>[s,records[s].length])),ownerId,modelEnabled,legacyRef,checkpointRefs,allocation});
 records.journalState=[state];check(Object.values(records).reduce((n,rows)=>n+rows.length,0)<=limits.records,'protocol record count');return freeze({state,records});
}
export async function materialize(input,options={}){return decodeBundle(input,options,false);}
/** Training view: all live graph/IDs/relations are validated. Raw archives,
 * checkpoints and unused old revisions remain explicitly unaudited until a
 * full read/export. This view must never be used as a complete backup. */
export async function materializeTraining(input,{objectIds,...options}={}){
 const bundle=protocolInput(input),ids=protocolInput(objectIds);
 check(Array.isArray(ids)&&ids.every(id=>typeof id==='string'&&/^[a-f0-9]{64}$/.test(id))&&new Set(ids).size===ids.length,'object key collection');
 const known=new Set(ids);check(bundle.records.journalObjects.every(r=>known.has(r?.id))&&bundle.records.journalArchives.every(r=>known.has(r.ref)),'missing retained object');
 check(Object.values(bundle.records).reduce((n,rows)=>n+rows.length,0)-bundle.records.journalObjects.length+ids.length===bundle.state.allocation?.records,'allocation record count');
 const source=await decodeBundle(bundle,options,true);
 trainingBundles.set(bundle,{source,budget:bundle.state.allocation,objectIds:ids});return source;
}
async function decodeBundle(input,{signal,limits:requestedLimits}={},training=false){
 checkAbort(signal);const bundle=protocolInput(input),limits=limitsFor(requestedLimits),proven=verifiedBundles.get(bundle);
 if(proven&&!training){check(proven.budget.bytes<=limits.totalBytes&&proven.budget.maxObjectBytes<=limits.objectBytes&&proven.budget.records<=limits.records,'protocol retained size/count limit');return proven.source;}
 const state=validateState(bundle.state),records=bundle.records;
 const {root,...stateBody}=state;check(root===await hashJSON(stateBody),'state SHA-256');
 const maps={},leaves=[];let total=0,count=0,maxObjectBytes=0;
 for(const store of STORES){
  check(Array.isArray(records[store]),'missing store '+store);count+=records[store].length;check(count<=limits.records,'protocol record count');
  maps[store]=new Map();for(const row of records[store]){check(typeof row?.id==='string'&&!maps[store].has(row.id),'duplicate record');maps[store].set(row.id,row);}
 }
 check(JSON.stringify(records.journalState)==='['+JSON.stringify(state)+']','active state mismatch');
 check(Array.isArray(state.checkpointRefs)&&state.checkpointRefs.length===records.journalCheckpoints.length&&new Set(state.checkpointRefs.map(r=>r.id)).size===state.checkpointRefs.length,'checkpoint completeness');
 if(training)validateAllocation(state.allocation,limits);
 for(const ref of state.checkpointRefs){
  check(maps.journalCheckpoints.has(ref.id),'missing checkpoint');
  if(!training){const proof=await checkpointDigest(maps.journalCheckpoints.get(ref.id),limits.totalBytes-total);total+=proof.bytes;check(ref.sha256===proof.sha256,'checkpoint root binding');}
 }
 for(const checkpoint of training?[]:records.journalCheckpoints){
  if(checkpoint.protocol===1){
   check(Number.isSafeInteger(checkpoint.revision)&&checkpoint.evidence?.meta?.find(r=>r.key==='state')?.revision===checkpoint.revision,'checkpoint version');
   check(checkpoint.evidenceHash===await hashJSON(checkpoint.evidence),'checkpoint SHA-256');
  }else{
   check(checkpoint.protocol===2&&typeof checkpoint.raw==='string'&&checkpoint.sha256===await sha(checkpoint.raw),'recovery checkpoint SHA-256');
  }
 }
 const objects=new Map();
 for(const row of records.journalObjects){checkAbort(signal);total+=row.bytes;maxObjectBytes=Math.max(maxObjectBytes,row.bytes);check(total<=limits.totalBytes,'protocol total size');objects.set(row.id,await readObject(row,limits));}
 check(objects.has(state.legacyRef)&&(objects.get(state.legacyRef)===null||typeof objects.get(state.legacyRef)==='string'),'legacy anchor reference');
 for(const store of ROW_STORES){
  check(records[store].length===state.counts[store],'record count '+store);
  for(const row of records[store]){portable(row);check(Number.isSafeInteger(row.version)&&row.version>0,'record version');leaves.push([indexKey(store,row.id),await hashJSON(row)]);}
 }
 await auditIndex(state.indexRoot,id=>maps.journalIndex.get(id),leaves,{signal});
 // Old immutable nodes/objects are retained as revision evidence; verify their
 // bytes too, rather than treating a hash-looking ID as a validation proof.
 const {verifyNode}=await import('./journal-index.mjs');for(const row of records.journalIndex)await verifyNode(row);
 const seenMeta=new Set(),seenCollections=new Set(),object=id=>{check(objects.has(id),'missing object');return objects.get(id);};
 const fields=(pairs,resolve)=>{
  check(Array.isArray(pairs),'metadata fields');const keys=new Set();
  return freeze(Object.fromEntries(pairs.map(pair=>{check(Array.isArray(pair)&&pair.length===2&&typeof pair[0]==='string'&&!keys.has(pair[0]),'duplicate field');keys.add(pair[0]);return [pair[0],resolve(pair[1])];})));
 };
 function collection(store){
  check(ROW_STORES.includes(store)&&store!=='journalMetadata'&&!seenCollections.has(store),'collection source');seenCollections.add(store);
  const rows=[...records[store]].sort((a,b)=>a.position-b.position);
  const values=rows.map((row,i)=>{
   check(row.position===i,'collection order');const snapshot=store==='journalSnapshots';
   check(Object.keys(row).join(',')==='id,version,position,'+(snapshot?'fields':'ref'),'collection row shape');
   if(training&&store==='journalArchives')return null;
   const value=snapshot?fields(row.fields,object):object(row.ref);check(value?.id===row.id,'collection identity');return value;
  });return freeze(training&&store==='journalArchives'?[]:values);
 }
 function metadata(id){
  check(!seenMeta.has(id),'metadata cycle');seenMeta.add(id);const row=maps.journalMetadata.get(id);
  check(row&&Object.keys(row).join(',')==='id,version,fields','metadata row shape');
  return fields(row.fields,slot=>{
   check(slot&&typeof slot==='object','slot');
   if(slot.kind==='object'){check(Object.keys(slot).join(',')==='kind,ref','object slot');return object(slot.ref);}
   if(slot.kind==='collection'){check(Object.keys(slot).join(',')==='kind,store','collection slot');return collection(slot.store);}
   check(slot.kind==='metadata'&&Object.keys(slot).join(',')==='kind,id','metadata slot');return metadata(slot.id);
  });
 }
 const source=metadata('source');check(seenMeta.size===maps.journalMetadata.size,'unused metadata');
 for(const store of ROW_STORES.filter(s=>s!=='journalMetadata'))check(seenCollections.has(store)||records[store].length===0,'unused collection');
 await validateSource(source,state.ownerId);checkAbort(signal);
 if(!training&&state.runtime)await (await import('./journal-runtime-index.mjs')).auditRuntime(state,maps,source,{signal});
 if(!training){
  const budget=freeze({bytes:total,records:count,maxObjectBytes});
  if(state.allocation){validateAllocation(state.allocation,limits);check(JSON.stringify(state.allocation)===JSON.stringify(budget),'allocation mismatch');}
  verifiedBundles.set(bundle,{source,budget});
 }else check(total<=state.allocation.bytes&&maxObjectBytes<=state.allocation.maxObjectBytes,'live allocation mismatch');
 return source;
}
