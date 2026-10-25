/** Issue #82 A: isolated lossless protocol. No database opening or UI imports. */
import {freeze,portable,immutableJSON,parseJson,requireThat as check} from './backup-json.mjs';
import {createLegacyModelFromSource} from './legacy-model.mjs';
import {hashJSON,sha,buildIndex,auditIndex,indexKey,checkAbort} from './journal-index.mjs';
export const PROTOCOL=2;
export const ROW_STORES=['journalMetadata','journalSessions','journalResults','journalSnapshots','journalArchives'];
export const STORES=['journalObjects',...ROW_STORES,'journalIndex','journalState','journalCheckpoints'];
// Allocation guards, not promises of device capacity. Conversion can fail safely
// below these limits; neither the old checkpoint nor archives are discarded.
export const LIMITS=Object.freeze({objectBytes:128*1024*1024,totalBytes:512*1024*1024,records:1000000});
export function limitsFor(options={}){const limits={...LIMITS,...options};for(const [key,n] of Object.entries(limits))check(Object.hasOwn(LIMITS,key)&&Number.isSafeInteger(n)&&n>0&&n<=LIMITS[key],'protocol limit');return limits;}
export async function objectRecord(value,limits=LIMITS){
 portable(value);const json=JSON.stringify(value),bytes=new TextEncoder().encode(json);
 check(bytes.length<=limits.objectBytes,'protocol object size');return freeze({id:await sha(json),json,bytes:bytes.length});
}
export async function readObject(row,limits=LIMITS){
 check(row&&Object.keys(row).join(',')==='id,json,bytes'&&typeof row.json==='string','object shape');
 check(Number.isSafeInteger(row.bytes)&&row.bytes<=limits.objectBytes&&row.bytes===new TextEncoder().encode(row.json).length,'object size');
 check(row.id===await sha(row.json),'object SHA-256');const value=parseJson(row.json);portable(value);return freeze(value);
}
export function validateState(state){
 check(state&&Object.keys(state).join(',')==='id,protocol,epoch,revision,root,counts,ownerId','state shape');
 check(state.id==='active'&&state.protocol===PROTOCOL&&typeof state.epoch==='string'&&state.epoch.length>0&&Number.isSafeInteger(state.revision)&&state.revision>=0&&/^[a-f0-9]{64}$/.test(state.root)&&typeof state.ownerId==='string'&&state.ownerId.length>0,'protocol state');
 check(Object.keys(state.counts).join(',')===ROW_STORES.join(',')&&Object.values(state.counts).every(n=>Number.isSafeInteger(n)&&n>=0),'state counts');return state;
}
export async function validateSource(source,ownerId,createdAt='2026-10-25T00:00:00.000Z'){
 check(source?.format==='pushpull-backup'&&source.version===2,'protocol source version');
 // Existing validators include the complete native snapshot/performance graph.
 return createLegacyModelFromSource(source,{ownerId,createdAt});
}
export async function createProtocol(input,{epoch=crypto.randomUUID(),revision=0,ownerId=input?.data?.trainingJournal?.model?.ownerId??'local-journal',signal,limits:requestedLimits}={}){
 checkAbort(signal);portable(input);
 const source=immutableJSON(input)?input:freeze(structuredClone(input)),limits=limitsFor(requestedLimits);
 await validateSource(source,ownerId);checkAbort(signal);
 const records=Object.fromEntries(STORES.map(s=>[s,[]])),objects=new Map(),objectProofs=new WeakMap();let total=0;
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
   else if(id==='data'&&key==='trainingJournal')slot=await metadata('journal',item);
   else if(id==='journal'&&key==='sessionSnapshots')slot=await collection('journalSnapshots',item);
   else slot={kind:'object',ref:await ref(item)};
   fields.push([key,slot]);
  }
  records.journalMetadata.push(freeze({id,version:1,fields}));return {kind:'metadata',id};
 }
 await metadata('source',source);records.journalObjects=[...objects.values()];
 const leaves=[];for(const store of ROW_STORES)for(const row of records[store])leaves.push([indexKey(store,row.id),await hashJSON(row)]);
 check(leaves.length<=limits.records,'protocol record count');
 const tree=await buildIndex(leaves,{signal});records.journalIndex=[...tree.nodes.values()];
 const state=freeze(validateState({id:'active',protocol:PROTOCOL,epoch,revision,root:tree.root,counts:Object.fromEntries(ROW_STORES.map(s=>[s,records[s].length])),ownerId}));
 records.journalState=[state];check(Object.values(records).reduce((n,rows)=>n+rows.length,0)<=limits.records,'protocol record count');return freeze({state,records});
}
export async function materialize(bundle,{signal,limits:requestedLimits}={}){
 checkAbort(signal);const limits=limitsFor(requestedLimits),state=validateState(bundle.state),records=bundle.records;
 const maps={},leaves=[];let total=0,count=0;
 for(const store of STORES){
  check(Array.isArray(records[store]),'missing store '+store);count+=records[store].length;check(count<=limits.records,'protocol record count');
  maps[store]=new Map();for(const row of records[store]){check(typeof row?.id==='string'&&!maps[store].has(row.id),'duplicate record');maps[store].set(row.id,row);}
 }
 check(JSON.stringify(records.journalState)==='['+JSON.stringify(state)+']','active state mismatch');
 const objects=new Map();
 for(const row of records.journalObjects){checkAbort(signal);total+=row.bytes;check(total<=limits.totalBytes,'protocol total size');objects.set(row.id,await readObject(row,limits));}
 for(const store of ROW_STORES){
  check(records[store].length===state.counts[store],'record count '+store);
  for(const row of records[store]){portable(row);check(Number.isSafeInteger(row.version)&&row.version>0,'record version');leaves.push([indexKey(store,row.id),await hashJSON(row)]);}
 }
 await auditIndex(state.root,id=>maps.journalIndex.get(id),leaves,{signal});
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
  return freeze(rows.map((row,i)=>{
   check(row.position===i,'collection order');const snapshot=store==='journalSnapshots';
   check(Object.keys(row).join(',')==='id,version,position,'+(snapshot?'fields':'ref'),'collection row shape');
   const value=snapshot?fields(row.fields,object):object(row.ref);check(value?.id===row.id,'collection identity');return value;
  }));
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
 await validateSource(source,state.ownerId);checkAbort(signal);return source;
}
