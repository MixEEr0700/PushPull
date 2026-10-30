/** Read-only live capture for the existing complete PPC1 contract; no UI/restore. */
import {COMPLETE_STORES,LOCAL_SOURCES,validateCompleteContract,writeCompleteContract} from './complete-backup-contract.mjs';
import {STORES,materialize,equalJSON} from './journal-protocol.mjs';
import {freeze,portable} from './backup-json.mjs';
export const CAPTURE_LIMITS=Object.freeze({records:10000,bytes:64*1024*1024,nodes:100000,depth:32,ms:30000});
const check=(v,m)=>{if(!v)throw Error('PPC1 capture: '+m);};
export const localSource=key=>LOCAL_SOURCES.some(k=>k.endsWith(':')||k.endsWith('_')?key.startsWith(k):key===k);
function budget(limits,guard){
 let bytes=0,nodes=0,records=0;
 return value=>{
  check(++records<=limits.records,'record limit');
  function visit(v,depth){
   guard();check(depth<=limits.depth,'depth limit');check(++nodes<=limits.nodes,'node limit');
   bytes+=typeof v==='string'?2*v.length:16;check(bytes<=limits.bytes,'memory budget');
   if(v&&typeof v==='object')for(const k of Object.keys(v)){bytes+=2*k.length;check(bytes<=limits.bytes,'memory budget');visit(v[k],depth+1);}
  }
  visit(value,0);
  portable(value);
 };
}
function locals(storage,charge,guard){
 const keys=[];for(let i=0;i<storage.length;i++){guard();const k=storage.key(i);check(typeof k==='string','localStorage enumeration');if(localSource(k))keys.push(k);else check(!k.startsWith('pushpull'),'unclassified PushPull localStorage key');}
 keys.sort();check(new Set(keys).size===keys.length,'localStorage inventory changed');
 return keys.map(key=>{guard();const raw=storage.getItem(key);check(typeof raw==='string','localStorage value disappeared');const row={key,raw};charge?.(row);return row;});
}
function connect(factory,guard,signal,ms){return new Promise((resolve,reject)=>{
 guard();const req=factory.open('pushpull');let abandoned=false;
 const cleanup=()=>{clearTimeout(timer);signal?.removeEventListener('abort',cancel);};
 const stop=e=>{abandoned=true;cleanup();reject(e);};
 const cancel=()=>stop(new DOMException('Cancelled','AbortError'));
 const timer=setTimeout(()=>stop(Error('PPC1 capture: time limit')),ms);
 signal?.addEventListener('abort',cancel,{once:true});
 req.onupgradeneeded=()=>{abandoned=true;req.transaction.abort();};
 req.onblocked=()=>stop(Error('PPC1 capture: database blocked'));
 req.onerror=()=>{cleanup();reject(Error('PPC1 capture: database unavailable (no creation or upgrade)'));};
 req.onsuccess=()=>{cleanup();if(abandoned){req.result.close();return;}try{guard();resolve(req.result);}catch(e){req.result.close();reject(e);}};
});}
/** All stores share one readonly transaction. Final verification streams rows
 * against the first snapshot, retaining no second full ledger. localStorage is
 * sampled synchronously inside the last cursor event, while IDB locks still hold. */
function scan(db,{guard,signal,storage,charge,expected,expectedLocal}){return new Promise((resolve,reject)=>{
 let tx,error,local,completed=0;const rows=expected??Object.fromEntries(COMPLETE_STORES.map(k=>[k,[]]));
 const fail=e=>{error??=e;try{tx?.abort();}catch{};};
 try{guard();tx=db.transaction(COMPLETE_STORES,'readonly');}catch(e){reject(e);return;}
 const cancel=()=>fail(new DOMException('Cancelled','AbortError'));
 signal?.addEventListener('abort',cancel,{once:true});
 tx.onabort=()=>{signal?.removeEventListener('abort',cancel);reject(error??tx.error??Error('PPC1 capture: transaction aborted'));};
 tx.onerror=()=>{error??=tx.error;};
 tx.oncomplete=()=>{signal?.removeEventListener('abort',cancel);try{guard();check(equalJSON(local,locals(storage,null,guard)),'localStorage changed');resolve({rows,local});}catch(e){reject(e);}};
 try{for(const name of COMPLETE_STORES){
  const store=tx.objectStore(name);check(store.keyPath===(name==='meta'?'key':'id')&&!store.autoIncrement,'store schema');let i=0;
  const req=store.openCursor();
  req.onerror=()=>fail(req.error);
  req.onsuccess=()=>{try{
   guard();const cursor=req.result;
   if(cursor){
    if(expected)check(i<rows[name].length&&equalJSON(cursor.value,rows[name][i]),'persistent records changed');
    else{charge(cursor.value);rows[name].push(cursor.value);}
    i++;cursor.continue();
   }else{
    if(expected)check(i===rows[name].length,'persistent inventory changed');
    if(++completed===COMPLETE_STORES.length){local=locals(storage,expected?null:charge,guard);if(expected)check(equalJSON(local,expectedLocal),'localStorage changed');}
   }
  }catch(e){fail(e);}};
 }}catch(e){fail(e);}
});}
export async function captureCompleteContract({indexedDB=globalThis.indexedDB,storage=globalThis.localStorage,events=globalThis,signal,limits:overrides={}}={}){
 const limits={...CAPTURE_LIMITS};for(const [k,v] of Object.entries(overrides)){check(Object.hasOwn(limits,k)&&Number.isSafeInteger(v)&&v>0&&v<=limits[k],'limits may only be lowered');limits[k]=v;}
 const started=performance.now();let dirty=false,closed=false,db;
 const guard=()=>{if(signal?.aborted)throw new DOMException('Cancelled','AbortError');check(!dirty,'localStorage changed in another context');check(!closed,'database version changed');check(performance.now()-started<=limits.ms,'time limit');};
 const changed=e=>{if(e.storageArea===storage&&(e.key===null||localSource(e.key)||e.key.startsWith('pushpull')))dirty=true;};
 check(events?.addEventListener&&events?.removeEventListener&&storage&&indexedDB,'persistent sources unavailable');
 events.addEventListener('storage',changed);
 try{
  db=await connect(indexedDB,guard,signal,limits.ms);db.onversionchange=()=>{closed=true;db.close();};
  check(db.version===2&&equalJSON(Array.from(db.objectStoreNames).sort(),[...COMPLETE_STORES].sort()),'database schema/inventory');
  const charge=budget(limits,guard);
  const {rows,local}=await scan(db,{guard,signal,storage,charge});
  freeze(rows);const state=rows.journalState.find(r=>r.id==='active');check(state,'active journal missing');
  const source=await materialize(freeze({state,records:Object.fromEntries(STORES.map(k=>[k,rows[k]]))}),{signal});guard();
  const result=freeze({format:'pushpull-complete-contract',version:1,capture:{before:state.root,after:state.root,scope:'supplied-persistent-snapshot',otherTabs:'unknown',counts:Object.fromEntries(COMPLETE_STORES.map(k=>[k,rows[k].length])),localKeys:local.map(r=>r.key)},source,indexedDB:{name:'pushpull',version:2,stores:rows},localStorage:local});
  await validateCompleteContract(result,{signal});guard();
  await scan(db,{guard,signal,storage,expected:rows,expectedLocal:local});guard();
  return result;
 }finally{events.removeEventListener('storage',changed);db?.close();}
}
export async function writeCapturedCompleteContract(options={}){const snapshot=await captureCompleteContract(options);return writeCompleteContract(snapshot,{signal:options.signal});}
