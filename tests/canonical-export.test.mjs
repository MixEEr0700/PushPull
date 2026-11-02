import {test} from 'node:test';import assert from 'node:assert/strict';
import {localCanonicalBuffers,exportCanonicalLocal} from '../model/canonical-export.mjs';
test('readonly buffer inventory, worker cancellation, conflicts and late responses',async()=>{
 const names=['localStorage','Worker','addEventListener','removeEventListener'],saved=names.map(k=>[k,globalThis[k]]),events=new EventTarget(),map=new Map([['pushpull_skeleton_v1','not exported'],['other-app','private'],['pushpull-note-ui-v1:b','unfinished'],['pushpull_workout_draft_v1:a','conflict']]);
 const workers=[];globalThis.localStorage={get length(){return map.size},key:i=>[...map.keys()][i],getItem:k=>map.get(k)??null};globalThis.addEventListener=events.addEventListener.bind(events);globalThis.removeEventListener=events.removeEventListener.bind(events);
 globalThis.Worker=class{constructor(){workers.push(this)}postMessage(v){this.input=v}terminate(){this.terminated=true}};
 try{
  const before=[...map];assert.deepStrictEqual(localCanonicalBuffers().map(r=>r.key),['pushpull-note-ui-v1:b','pushpull_workout_draft_v1:a']);assert.deepStrictEqual([...map],before);
  const c=new AbortController(),pending=exportCanonicalLocal({getRevision:()=>1,signal:c.signal}),worker=workers.at(-1);c.abort();await assert.rejects(pending,{name:'AbortError'});assert.equal(worker.terminated,true);worker.onmessage({data:{result:{ignored:true}}});
  let rev=1;const changed=exportCanonicalLocal({getRevision:()=>rev});rev=2;workers.at(-1).onmessage({data:{result:{}}});await assert.rejects(changed,/zmieniły/);
  const buffers=exportCanonicalLocal({getRevision:()=>1});map.set('pushpull-note-ui-v1:b','changed');workers.at(-1).onmessage({data:{result:{}}});await assert.rejects(buffers,/zmieniły/);
  const failed=exportCanonicalLocal({getRevision:()=>1});workers.at(-1).onmessage({data:{error:'read denied'}});await assert.rejects(failed,/read denied/);assert.equal(workers.at(-1).terminated,true);
  map.set('pushpull-new-unclassified','future');await assert.rejects(exportCanonicalLocal({getRevision:()=>1}),/Nieznane/);
 }finally{for(const [k,v] of saved)if(v===undefined)delete globalThis[k];else globalThis[k]=v;}
});
