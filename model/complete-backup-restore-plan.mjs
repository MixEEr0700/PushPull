/** #129 safety prerequisite. Read-only planner; deliberately no commit API. */
import {readCompleteContract,COMPLETE_STORES} from './complete-backup-contract.mjs';
import {localSource} from './complete-backup-capture.mjs';
import {STORES,createProtocol,materialize,equalJSON} from './journal-protocol.mjs';
import {transact,request} from './journal-idb.mjs';
import {freeze} from './backup-json.mjs';
const check=(v,m)=>{if(!v)throw Error('PPC1 restore plan: '+m);};
export const RESTORE_BLOCKERS=Object.freeze(['cross-storage-crash-recovery','startup-recovery-gate','auxiliary-store-CAS-preimage-readback','all-writer-exclusion']);
export function storePolicy(name){
 check(COMPLETE_STORES.includes(name),'unclassified store');
 if(name==='meta')return 'classify-each-record';
 if(name==='journalCheckpoints')return 'retain-in-inert-evidence';
 if(STORES.includes(name))return 'regenerate-active-protocol';
 return 'retain-in-inert-evidence';
}
export function metaPolicy(key){
 if(key==='drive-sync-v1')return 'retain-drive-evidence-reconnect-manually';
 if(key==='journal-protocol-v2'||key==='state'||key==='training-model-v1')return 'regenerate-never-replay';
 if(key.startsWith('workout-draft:'))return 'preserve-draft-rebind-CAS-before-activation';
 return 'retain-unclassified-evidence-no-activation';
}
export function localPolicy(key){
 check(localSource(key),'unclassified local key');
 if(key==='pushpull_indexeddb_owner')return 'regenerate-target-routing';
 if(key==='pushpull_skeleton_v1')return 'retain-anchor-evidence-bind-new-protocol';
 if(key.startsWith('pushpull_skeleton_v1_backup_'))return 'retain-rescue-evidence-no-auto-restore';
 return 'preserve-buffer-and-conflicts-verify-context-before-activation';
}
/** Observation only, not a reservation/CAS authorization. Does not open/create
 * an absent database. Recheck under the future commit barrier is mandatory. */
export async function inspectEmptyRestoreTarget({signal}={}){
 signal?.throwIfAborted();check(typeof indexedDB.databases==='function','database inventory unavailable');
 let changed=false,db;const event=e=>{if(e.storageArea===localStorage&&(e.key===null||e.key.startsWith('pushpull')))changed=true;};
 const guard=()=>{signal?.throwIfAborted();check(!changed,'target changed');};
 const local=()=>{const keys=[];for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);check(typeof key==='string','local inventory');if(key.startsWith('pushpull'))keys.push(key);}check(keys.length===0,'target localStorage is not empty');};
 addEventListener('storage',event);
 try{
  local();const databases=await indexedDB.databases();guard();const present=databases.find(d=>d.name==='pushpull');
  const counts=Object.fromEntries(COMPLETE_STORES.map(k=>[k,0]));
  if(present){
   check(present.version===2,'target database version');
   db=await new Promise((resolve,reject)=>{const q=indexedDB.open('pushpull');let failed=false;const stop=e=>{failed=true;reject(e);};q.onupgradeneeded=()=>{q.transaction.abort();stop(Error('PPC1 restore plan: target disappeared'));};q.onblocked=()=>stop(Error('PPC1 restore plan: target blocked'));q.onerror=()=>stop(q.error);q.onsuccess=()=>{if(failed)q.result.close();else resolve(q.result);};});
   db.onversionchange=()=>{changed=true;db.close();};
   check(equalJSON([...db.objectStoreNames].sort(),[...COMPLETE_STORES].sort()),'target store inventory');
   await transact(db,COMPLETE_STORES,'readonly',async tx=>{await Promise.all(COMPLETE_STORES.map(async name=>{const store=tx.objectStore(name);check(store.keyPath===(name==='meta'?'key':'id')&&!store.autoIncrement,'target store schema');counts[name]=await request(store.count());}));guard();local();},{signal});
   check(Object.values(counts).every(n=>n===0),'target database is not empty');
  }
  local();guard();
  return freeze({kind:'empty-target-observation',database:present?'empty-schema-v2':'absent',counts,localKeys:[],reserved:false});
 }finally{removeEventListener('storage',event);db?.close();}
}
/** Reading a file and preparing a replacement graph confers no write authority.
 * The entire input remains intact as evidence; dispositions are explicit. */
export async function planCompleteRestore(file,{signal,limits}={}){
 const evidence=await readCompleteContract(file,{signal,limits});signal?.throwIfAborted();
 const prior=evidence.indexedDB.stores.journalState.find(r=>r.id==='active');
 // ownerId inside the training model is logical provenance, not a Drive device ID.
 const graph=await createProtocol(evidence.source,{epoch:crypto.randomUUID(),revision:0,ownerId:prior.ownerId,modelEnabled:prior.modelEnabled,legacyRaw:null,checkpoints:[],signal});
 check(graph.state.epoch!==prior.epoch,'fresh epoch required');
 check(equalJSON(await materialize(graph,{signal}),evidence.source),'candidate source equality');
 signal?.throwIfAborted();
 return freeze({format:'pushpull-restore-plan',version:1,canCommit:false,productionComplete:false,blockers:[...RESTORE_BLOCKERS],evidence,
  candidate:{source:evidence.source,graph,drive:{mode:'manual',enabled:false,selected:null,accounts:{},clientId:''}},
  stores:COMPLETE_STORES.map(store=>({store,policy:storePolicy(store),count:evidence.indexedDB.stores[store].length})),
  meta:evidence.indexedDB.stores.meta.map(r=>({key:r.key,policy:metaPolicy(r.key)})),
  local:evidence.localStorage.map(r=>({key:r.key,policy:localPolicy(r.key)}))});
}
