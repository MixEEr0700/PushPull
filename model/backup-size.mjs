/** Local, read-only protocol-v2 inventory. No exporter, Drive, localStorage,
 * writer, migration, raw archive parser or full history materialization. */
import {textProfile,valueProfile,combineProfiles,escapedProfile} from './backup-size-json.mjs';
const STORES=['journalObjects','journalMetadata','journalSessions','journalResults','journalSnapshots','journalArchives','journalIndex','journalState','journalCheckpoints'];
export const LIMITS=Object.freeze({records:250000,objectBytes:64*1024*1024,checkpointBytes:64*1024*1024,semanticBytes:8*1024*1024,timeoutMs:120000});
const failure=code=>Object.assign(Error('Backup size measurement: '+code),{code});
const check=(condition,code='unavailable')=>{if(!condition)throw failure(code)};
const stamp=s=>JSON.stringify(s);
const emptyParts=()=>({history:0,snapshots:0,archives:0,model:0,catalog:0,other:0,structure:0});
const shape={counts:['sessions','results','snapshots','plans','catalogPlans','catalogVersions','archives','objects','repeatedReferences'],sourceBytes:['history','snapshots','archives','model','catalog','other','structure','total'],representationBytes:['uniqueReferencedObjects','repeatedReferencedObjects','referenceEnvelope','sourceAsJsonString','sourceEscapingOverhead','sourceAsJsonStringAgain','sourceReescapingOverhead','sourcePretty','sourceFormattingOverhead'],storedBytes:['activeObjects','retainedObjects','checkpoints','protocolRows','total'],timingsMs:['read','count','total']};
export function anonymousReport(value){
 check(value&&Object.keys(value).join(',')===Object.keys(shape).join(','));
 for(const [group,keys] of Object.entries(shape)){
  check(value[group]&&Object.keys(value[group]).join(',')===keys.join(','));
  check(keys.every(k=>Number.isSafeInteger(value[group][k])&&value[group][k]>=0));
 }
 check(value.sourceBytes.total===Object.values(value.sourceBytes).slice(0,-1).reduce((a,b)=>a+b,0));
 check(value.storedBytes.total===Object.values(value.storedBytes).slice(0,-1).reduce((a,b)=>a+b,0));
 check(JSON.stringify(value).length<8192);return value;
}
/** Reader permits independent fixtures/oracles without fake production storage. */
export async function inventory(reader,{signal,limits:given={},expectedRevision,now=()=>performance.now()}={}){
 const limits={...LIMITS,...given};for(const k of Object.keys(limits))check(Number.isSafeInteger(limits[k])&&limits[k]>0&&limits[k]<=LIMITS[k],'limit');
 const started=now();let readMs=0,countMs=0;
 const guard=()=>{if(signal?.aborted)throw failure('cancelled');check(now()-started<limits.timeoutMs,'limit')};
 const read=async(...a)=>{guard();const t=now(),v=await reader.get(...a);readMs+=now()-t;guard();return v};
 const count=fn=>{guard();const t=now(),v=fn();countMs+=now()-t;guard();return v};
 const initial=await read('journalState','active');
 check(initial?.id==='active'&&initial.protocol===2&&Number.isSafeInteger(initial.revision)&&initial.epoch&&initial.root&&initial.allocation,'unsupported');
 if(expectedRevision!==undefined)check(initial.revision===expectedRevision,'changed');
 check(initial.allocation.maxObjectBytes<=limits.objectBytes&&initial.allocation.records<=limits.records,'limit');
 const indexes={},profiles=new Map(),uses=new Map(),modelRefs=new Set(),parts=emptyParts(),stored={activeObjects:0,retainedObjects:0,checkpoints:0,protocolRows:0,total:0};
 let nRecords=0,objectBytes=0,repeatedReferences=0,uniqueReferencedObjects=0,repeatedReferencedObjects=0;
 for(const store of STORES){
  const t=now(),keys=await reader.keys(store,limits.records+1);readMs+=now()-t;guard();nRecords+=keys.length;check(nRecords<=limits.records,'limit');indexes[store]=keys;
 }
 check(nRecords===initial.allocation.records,'changed');
 const rows={};
 for(const store of ['journalMetadata','journalSessions','journalResults','journalSnapshots','journalArchives']){
  rows[store]=[];
  for(const id of indexes[store]){const row=await read(store,id);check(row&&row.id===id);rows[store].push(row);stored.protocolRows+=count(()=>valueProfile(row).bytes);}
  check(rows[store].length===initial.counts?.[store],'changed');
 }
 const metadata=new Map(rows.journalMetadata.map(r=>[r.id,r]));
 const use=ref=>{check(typeof ref==='string');uses.set(ref,(uses.get(ref)??0)+1)};
 for(const row of rows.journalMetadata){check(Array.isArray(row.fields));for(const [key,slot] of row.fields){check(typeof key==='string'&&slot);if(slot.kind==='object'){use(slot.ref);if(row.id==='journal'&&key==='model')modelRefs.add(slot.ref);}}}
 for(const store of ['journalSessions','journalResults','journalArchives'])for(const row of rows[store])use(row.ref);
 for(const row of rows.journalSnapshots){check(Array.isArray(row.fields));for(const [key,ref] of row.fields){use(ref);if(key==='model')modelRefs.add(ref);}}
 for(const id of indexes.journalObjects){
  const row=await read('journalObjects',id);check(row&&row.id===id&&typeof row.json==='string'&&row.bytes<=limits.objectBytes,'limit');
  const p=count(()=>textProfile(row.json));check(p.bytes===row.bytes);objectBytes+=p.bytes;
  const bytes=count(()=>valueProfile(row).bytes);
  if(uses.has(id)){
   profiles.set(id,p);stored.activeObjects+=bytes;uniqueReferencedObjects+=p.bytes;
   repeatedReferences+=uses.get(id)-1;repeatedReferencedObjects+=(uses.get(id)-1)*p.bytes;
  }else stored.retainedObjects+=bytes;
 }
 check([...uses.keys()].every(id=>profiles.has(id)));
 const checkpointUpperBound=initial.allocation.bytes-objectBytes;
 check(checkpointUpperBound>=0&&checkpointUpperBound<=limits.checkpointBytes,'limit');
 let checkpointPayload=0;
 for(const id of indexes.journalCheckpoints){const row=await read('journalCheckpoints',id);const bytes=count(()=>valueProfile(row).bytes);check(bytes<=limits.checkpointBytes,'limit');stored.checkpoints+=bytes;checkpointPayload+=bytes;}
 check(checkpointPayload===checkpointUpperBound);
 for(const store of ['journalIndex','journalState'])for(const id of indexes[store]){const row=await read(store,id);stored.protocolRows+=count(()=>valueProfile(row).bytes);}
 const seen=new Set(),collections=new Set();
 const bucket=path=>path[1]==='catalog'?'catalog':path[1]==='archives'?'archives':path[1]==='data'?(path[2]==='sessions'||path[2]==='entries'||path[2]==='changes'?'history':path[2]==='trainingJournal'&&path[3]==='sessionSnapshots'?'snapshots':'model'):'other';
 const leaf=(ref,path)=>{const p=profiles.get(ref);check(p);parts[bucket(path)]+=p.bytes;return p};
 const assemble=(children,keys=null,category='structure')=>{const p=combineProfiles(children,keys);parts[category]+=p.bytes-children.reduce((n,v)=>n+v.bytes,0);return p};
 function collection(store,path){
  check(Object.hasOwn(rows,store)&&store!=='journalMetadata'&&!collections.has(store));collections.add(store);
  const ordered=rows[store].slice().sort((a,b)=>a.position-b.position);
  return assemble(ordered.map((row,i)=>{
   check(row.position===i);
   if(store!=='journalSnapshots')return leaf(row.ref,path);
   return assemble(row.fields.map(([key,ref])=>leaf(ref,[...path,key])),row.fields.map(([key])=>key),bucket(path));
  }),null,bucket(path));
 }
 function materialSize(id,path){
  check(!seen.has(id));seen.add(id);const row=metadata.get(id);check(row&&Array.isArray(row.fields));
  const keys=row.fields.map(([key])=>key);check(new Set(keys).size===keys.length);
  return assemble(row.fields.map(([key,slot])=>{
   const next=[...path,key];
   if(slot.kind==='object')return leaf(slot.ref,next);
   if(slot.kind==='collection')return collection(slot.store,next);
   check(slot.kind==='metadata');return materialSize(slot.id,next);
  }),keys);
 }
 const source=materialSize('source',['source']);check(seen.size===metadata.size);
 for(const store of ['journalSessions','journalResults','journalSnapshots','journalArchives'])check(collections.has(store)||!rows[store].length);
 const semantic=async ref=>{
  check(profiles.get(ref)?.bytes<=limits.semanticBytes,'limit');const row=await read('journalObjects',ref);
  return count(()=>JSON.parse(row.json));
 };
 const catalogSlot=metadata.get('source')?.fields.find(([k])=>k==='catalog')?.[1];check(catalogSlot?.kind==='object');
 const catalog=await semantic(catalogSlot.ref);check(Array.isArray(catalog.plans)&&Array.isArray(catalog.planVersions));
 const planIds=new Set();
 for(const ref of modelRefs){const model=await semantic(ref);check(Array.isArray(model.planVersions));for(const p of model.planVersions){check(typeof p.id==='string');planIds.add(p.id);}}
 const importedSlot=metadata.get('journal')?.fields.find(([k])=>k==='importedPlans')?.[1];
 if(importedSlot){check(importedSlot.kind==='object');const packets=await semantic(importedSlot.ref);check(Array.isArray(packets));for(const p of packets){check(typeof p.planVersion?.id==='string');planIds.add(p.planVersion.id);}}
 guard();check(stamp(await read('journalState','active'))===stamp(initial),'changed');
 stored.total=stored.activeObjects+stored.retainedObjects+stored.checkpoints+stored.protocolRows;
 return anonymousReport({
  counts:{sessions:rows.journalSessions.length,results:rows.journalResults.length,snapshots:rows.journalSnapshots.length,plans:planIds.size,catalogPlans:catalog.plans.length,catalogVersions:catalog.planVersions.length,archives:rows.journalArchives.length,objects:indexes.journalObjects.length,repeatedReferences},
  sourceBytes:{...parts,total:source.bytes},
  representationBytes:{uniqueReferencedObjects,repeatedReferencedObjects,referenceEnvelope:source.bytes-uniqueReferencedObjects-repeatedReferencedObjects,sourceAsJsonString:escapedProfile(source).bytes,sourceEscapingOverhead:escapedProfile(source).bytes-source.bytes,sourceAsJsonStringAgain:escapedProfile(escapedProfile(source)).bytes,sourceReescapingOverhead:escapedProfile(escapedProfile(source)).bytes-escapedProfile(source).bytes,sourcePretty:source.pretty,sourceFormattingOverhead:source.pretty-source.bytes},
  storedBytes:stored,timingsMs:{read:Math.round(readMs),count:Math.round(countMs),total:Math.round(now()-started)}
 });
}
async function openReader(name){
 if(indexedDB.databases)check((await indexedDB.databases()).some(d=>d.name===name),'unavailable');
 const db=await new Promise((resolve,reject)=>{
  const r=indexedDB.open(name);let unavailable=false;
  r.onupgradeneeded=()=>{unavailable=true;r.transaction.abort()};
  r.onerror=()=>reject(failure('unavailable'));r.onblocked=()=>{unavailable=true;reject(failure('unavailable'))};
  r.onsuccess=()=>{if(unavailable){r.result.close();reject(failure('unavailable'))}else resolve(r.result)};
 });
 if(db.version!==2||STORES.some(s=>!db.objectStoreNames.contains(s))){db.close();throw failure('unsupported')}
 let changed=false;db.onversionchange=()=>{changed=true;db.close()};
 const read=(store,make)=>new Promise((resolve,reject)=>{
  if(changed){reject(failure('changed'));return;}
  let result;const tx=db.transaction(store,'readonly'),r=make(tx.objectStore(store));
  r.onsuccess=()=>result=r.result;tx.oncomplete=()=>resolve(result);
  tx.onabort=tx.onerror=()=>reject(failure('unavailable'));
 });
 return {get:(s,id)=>read(s,t=>t.get(id)),keys:(s,max)=>read(s,t=>t.getAllKeys(null,max)),close:()=>db.close()};
}
/** Only numeric allowlisted aggregates cross the worker boundary. */
if(typeof DedicatedWorkerGlobalScope!=='undefined'&&globalThis instanceof DedicatedWorkerGlobalScope){
 globalThis.onmessage=async({data})=>{
  let reader;
  try{reader=await openReader('pushpull');const report=await inventory(reader,{expectedRevision:data.revision});globalThis.postMessage({report});}
  catch(error){globalThis.postMessage({error:['limit','changed','unsupported'].includes(error.code)?error.code:'unavailable'});}
  finally{reader?.close();}
 };
}
export function measureBackupSize({signal,revision}={}){
 return new Promise((resolve,reject)=>{
  if(signal?.aborted){reject(failure('cancelled'));return;}
  let worker,timer,done=false;
  const finish=(error,report)=>{if(done)return;done=true;clearTimeout(timer);signal?.removeEventListener('abort',abort);worker?.terminate();error?reject(error):resolve(report)};
  const abort=()=>finish(failure('cancelled'));
  try{
   worker=new Worker(new URL('./backup-size.mjs',import.meta.url),{type:'module'});
   worker.onmessage=({data})=>{try{if(data.error)throw failure(['limit','changed','unsupported'].includes(data.error)?data.error:'unavailable');finish(null,anonymousReport(data.report));}catch{finish(failure(data.error??'unavailable'));}};
   worker.onerror=e=>{e.preventDefault();finish(failure('unavailable'))};
   signal?.addEventListener('abort',abort,{once:true});timer=setTimeout(()=>finish(failure('limit')),LIMITS.timeoutMs);worker.postMessage({revision});
  }catch{finish(failure('unavailable'))}
 });
}
