import test from 'node:test';
import assert from 'node:assert/strict';
import {collectDrafts,openDraftObserver} from '../model/draft-collector.mjs';
const at='2026-10-24T00:00:00.000Z';
const row=token=>({key:'workout-draft:d',id:'d',version:1,token,sequence:1,sessionId:'s',exerciseId:'e',context:{sessionId:'s',exerciseId:'e',sessionType:'PUSH A',status:'active',snapshotId:null,planVersionId:null,positionId:null,variantId:null,legacyDefinition:null},baseline:null,kind:'legacy',value:{kg:'1,',reps:'',series:[{kg:'',reps:''}]},updatedAt:at});
const a=row('a'),b=row('b');
const local={length:1,key:()=> 'pushpull_workout_draft_v1:d:b',getItem:()=> ' '+JSON.stringify(b)+'\n'};
const base={database:{readDraftObservation:async()=>({historyRevision:1,sources:[{source:'idb-meta',storageKey:a.key,value:a}]})},getMemory:()=>[{source:'editor-memory',record:b,binding:{context:b.context,baseline:null},durableToken:null,parent:null}],storage:()=>local};
test('all real-source observations stay separate; no flush/reload/write calls and no completeness claim',async()=>{
 const out=await collectDrafts(base);assert.equal(out.evidence.sources.length,3);assert.ok(out.classification.every(x=>x.status==='conflict'));assert.equal(out.coverage.otherTabs,'unknown');assert.equal(out.capture.scope,'observed-origin');assert.equal(out.evidence.sources[1].raw,local.getItem());
});
test('history and draft changes cause bounded retry or refusal independently of history revision',async()=>{
 let n=0;
 const changing={...base,database:{readDraftObservation:async()=>({historyRevision:1,sources:[{source:'idb-meta',storageKey:a.key,value:{...a,token:String(n++)}}]})}};
 await assert.rejects(collectDrafts(changing),e=>e.code==='unstable');assert.equal(n,4);
 n=0;const stabilizing={...base,database:{readDraftObservation:async()=>({historyRevision:n++<1?1:2,sources:[]})}};
 assert.equal((await collectDrafts(stabilizing)).diagnostics.attempts,2);
});
test('each unavailable source fails explicitly, not as an empty successful collection',async()=>{
 for(const [code,patch] of [['idb-unavailable',{database:{readDraftObservation:async()=>{throw Error('private')}}}],['local-unavailable',{storage:()=>{throw Error('private')}}],['memory-unavailable',{getMemory:()=>{throw Error('private')}}]])await assert.rejects(collectDrafts({...base,...patch}),e=>e.code===code&&!e.message.includes('private'));
});
test('responding peers preserved; a known peer missing next round refuses collection',async()=>{
 const peer={id:'synthetic-tab',sources:base.getMemory()};let n=0;
 await assert.rejects(collectDrafts({...base,peers:{observe:async()=>n++===0?[peer]:[]}}),e=>e.code==='peer-unavailable');
 const out=await collectDrafts({...base,peers:{observe:async()=>[peer]}});assert.equal(out.coverage.respondingTabs,1);assert.equal(out.evidence.sources.length,4);assert.equal(out.coverage.otherTabs,'unknown');
});
test('abort and limits return no partial evidence',async()=>{
 const c=new AbortController();await assert.rejects(collectDrafts({...base,signal:c.signal,pause:async()=>c.abort()}),{name:'AbortError'});
 await assert.rejects(collectDrafts({...base,limits:{sources:1}}),e=>e.code==='limit-or-source-error');
});

test('unavailable BroadcastChannel does not break app and excessive responders cause refusal',async()=>{
 assert.equal(openDraftObserver(()=>[],{Channel:class{constructor(){throw Error('unavailable')}}}),null);
 const many=Array.from({length:33},(_,i)=>({id:String(i),sources:[]}));
 await assert.rejects(collectDrafts({...base,peers:{observe:async()=>many}}),e=>e.code==='peer-limit');
});

test('abort stops waiting even if an underlying readonly source never responds',async()=>{
 const controller=new AbortController();
 const pending=collectDrafts({...base,database:{readDraftObservation:()=>new Promise(()=>{})},signal:controller.signal});
 controller.abort();await assert.rejects(pending,{name:'AbortError'});
});
