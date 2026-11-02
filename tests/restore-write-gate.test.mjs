import {test} from 'node:test';import assert from 'node:assert/strict';import {transact} from '../model/journal-idb.mjs';
test('pending ownership checked inside strict metadata transaction before any writer work',async()=>{
 const saved=Object.getOwnPropertyDescriptor(globalThis,'localStorage');Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{getItem:()=>null}});
 function database(marker){const seen={};return {seen,objectStoreNames:{contains:()=>true},transaction(stores,mode,options){Object.assign(seen,{stores,mode,options});const tx={abort(){clearTimeout(timer);queueMicrotask(()=>tx.onabort())},objectStore(){return {get(){const req={};queueMicrotask(()=>{req.result=marker;req.onsuccess()});return req;}}}};const timer=setTimeout(()=>tx.oncomplete(),5);return tx;}};}
 try{
  let called=false;const blocked=database({key:'canonical-restore-pending',id:'owner',status:'pending'});await assert.rejects(transact(blocked,['journalResults'],'readwrite',()=>{called=true}),/pending/);assert.equal(called,false);assert.ok(blocked.seen.stores.includes('meta'));assert.equal(blocked.seen.options.durability,'strict');
  assert.equal(await transact(database({id:'owner',status:'pending'}),['meta'],'readwrite',()=>42,{restoreId:'owner'}),42);
  await assert.rejects(transact(database(null),['meta'],'readwrite',()=>0,{restoreId:'owner'}),/markera/);
  globalThis.localStorage.getItem=()=> 'owner';await assert.rejects(async()=>transact(database(null),['meta'],'readwrite',()=>{called=true}),/pending/);assert.equal(called,false);
 }finally{if(saved)Object.defineProperty(globalThis,'localStorage',saved);else delete globalThis.localStorage;}
});
