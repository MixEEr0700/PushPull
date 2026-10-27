/* Optional DevTools snippet, NOT an application asset. Local timings only.
 * No DB reads/writes, storage, network, record contents, IDs or form values.
 * Observe one normal UI operation at a time. samples() copies aggregates;
 * stop() restores wrappers. Reload also removes this volatile probe.
 */
(() => {
 'use strict';
 if(window.PushPullWriteProbe)throw Error('Write probe already installed; call stop() first.');
 const database=IDBDatabase.prototype,store=IDBObjectStore.prototype;
 const digestDescriptor=Object.getOwnPropertyDescriptor(crypto.subtle,'digest');
 const original={transaction:database.transaction,put:store.put,add:store.add,get:store.get,digest:crypto.subtle.digest};
 const contexts=new WeakMap(),buffer=[];let current=null,stopped=false;
 const now=()=>performance.now();
 function publish(row){if(!row.published){row.published=true;buffer.push(row);if(buffer.length>20)buffer.shift();}}
 function begin(event){
  const root=document.getElementById('app');if(!root||root.inert)return;
  const button=event.target.closest?.('button');
  const form=event.type==='submit'?event.target:button?.closest('form');
  let kind;
  if(form?.matches('.performanceForm,.seriesResultForm,#resultForm,.historicalResultForm,.editForm'))kind='result';
  else if(button?.matches('[data-act=start]'))kind='start';
  else if(button?.matches('[data-act=finish]'))kind='finish';
  if(!kind)return;
  if(event.type==='submit'&&current&&!current.finished)return;
  current={kind,trigger:event.type,t0:now(),status:'pending',statePuts:0,modelGetMs:[],nativeSha:[],seenBusy:false};
 }
 function wrappedTransaction(...args){
  const tx=Reflect.apply(original.transaction,this,args);
  if(tx.mode==='readwrite'&&current){
   const context={row:current,at:now(),history:false};contexts.set(tx,context);
   const finish=complete=>{
    if(stopped||!context.history)return;
    const row=context.row,t=now();row.status=complete?'complete':'aborted';row.durability=tx.durability;
    row.preTransactionMs=context.at-row.t0;row.transactionMs=t-context.at;
    if(complete)row.clickToStrictCompleteMs=t-row.t0;
    publish(row);
   };
   tx.addEventListener('complete',()=>finish(true),{once:true});
   tx.addEventListener('abort',()=>finish(false),{once:true});
  }
  return tx;
 }
 function wrappedPut(...args){
  const context=contexts.get(this.transaction);
  if(context&&this.name==='meta'){
   if(args[0]?.key==='state'){context.history=true;context.row.statePuts++;}
   if(args[0]?.key==='training-model-v1')context.row.modelWriteMs=now()-context.row.t0;
  }
  if(context&&this.name==='journalState'&&args[0]?.id==='active'){context.history=true;context.row.statePuts++;}
  return Reflect.apply(original.put,this,args);
 }
 function wrappedAdd(...args){
  const context=contexts.get(this.transaction);
  if(context&&['sessions','journalSessions'].includes(this.name))context.history=true;
  return Reflect.apply(original.add,this,args);
 }
 function wrappedGet(...args){
  const request=Reflect.apply(original.get,this,args),context=contexts.get(this.transaction);
  if(context&&this.name==='meta'&&args[0]==='training-model-v1'){
   const at=now();request.addEventListener('success',()=>{if(!stopped)context.row.modelGetMs.push(now()-at);},{once:true});
  }
  return request;
 }
 function wrappedDigest(...args){
  const row=current,at=now(),result=Reflect.apply(original.digest,this,args);
  if(!row)return result;
  const measured=()=>{if(!stopped)row.nativeSha.push({ms:now()-at,inputBytes:args[1].byteLength});};
  return result.then(value=>{measured();return value;},error=>{measured();throw error;});
 }
 const observer=new MutationObserver(()=>{
  if(!current||stopped)return;
  if(document.getElementById('app')?.inert){current.seenBusy=true;return;}
  if(current.seenBusy){
   current.uiReadyMs=now()-current.t0;current.finished=true;
   if(current.status==='pending')current.status='no-history-complete';
   publish(current);current=null;
  }
 });
 database.transaction=wrappedTransaction;store.put=wrappedPut;store.add=wrappedAdd;store.get=wrappedGet;crypto.subtle.digest=wrappedDigest;
 document.addEventListener('click',begin,true);document.addEventListener('submit',begin,true);
 observer.observe(document.getElementById('app'),{subtree:true,childList:true,attributes:true,attributeFilter:['inert']});
 const samples=()=>buffer.map(row=>Object.fromEntries(['kind','trigger','status','durability','preTransactionMs','transactionMs','clickToStrictCompleteMs','uiReadyMs','statePuts','modelGetMs','modelWriteMs','nativeSha'].filter(k=>row[k]!==undefined).map(k=>[k,structuredClone(row[k])])));
 const api=Object.freeze({samples,stop(){
  stopped=true;observer.disconnect();document.removeEventListener('click',begin,true);document.removeEventListener('submit',begin,true);
  if(database.transaction===wrappedTransaction)database.transaction=original.transaction;
  if(store.put===wrappedPut)store.put=original.put;if(store.add===wrappedAdd)store.add=original.add;if(store.get===wrappedGet)store.get=original.get;
  if(crypto.subtle.digest===wrappedDigest){if(digestDescriptor)Object.defineProperty(crypto.subtle,'digest',digestDescriptor);else delete crypto.subtle.digest;}
  if(window.PushPullWriteProbe===api)delete window.PushPullWriteProbe;
  return samples();
 }});
 window.PushPullWriteProbe=api;
})();
