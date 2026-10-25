/** Neutral diagnostics: actual draft module, isolated fake storage only. No browser/profile or production writes. */
import test,{afterEach} from 'node:test';
afterEach(()=>{delete globalThis.localStorage;});
import assert from 'node:assert/strict';
import {openDrafts,editorValueValid} from '../model/workout-drafts.mjs';
const PREFIX='pushpull_workout_draft_v1:';
function storage(rows=[]){const map=new Map(rows);return {get length(){return map.size;},key:i=>[...map.keys()][i]??null,getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};}
const row=(sequence,token,id='synthetic')=>({key:'workout-draft:'+id,id,version:1,token,sequence,sessionId:'session',exerciseId:'exercise',context:{sessionId:'session',exerciseId:'exercise'},baseline:null,kind:'legacy',value:{kg:'',reps:'unfinished',series:[{kg:'1,',reps:''}]},updatedAt:'2026-10-24T00:00:00.000Z'});
const database=rows=>({readDrafts:async()=>structuredClone(rows)});
test('read-only reload selects newer buffered token and preserves equal-sequence branches',async()=>{
 const a=row(1,'a'),b=row(2,'b'),c=row(2,'c');
 globalThis.localStorage=storage([[PREFIX+b.id+':b',JSON.stringify(b)],[PREFIX+c.id+':c',JSON.stringify(c)]]);
 const before=Array.from({length:localStorage.length},(_,i)=>localStorage.getItem(localStorage.key(i)));
 const drafts=await openDrafts(database([a]));
 assert.deepEqual(drafts.records.map(x=>x.token),['b','c']);
 assert.deepEqual(Array.from({length:localStorage.length},(_,i)=>localStorage.getItem(localStorage.key(i))),before);
});
test('multiple independent page IDs survive; incomplete legacy and v2 numeric strings are draft values',async()=>{
 globalThis.localStorage=storage();const drafts=await openDrafts(database([row(1,'a','page-a'),row(1,'b','page-b')]));
 assert.equal(drafts.records.length,2);assert.ok(editorValueValid('legacy',row(1,'a').value));
 assert.ok(editorValueValid('v2',{performance:{version:2,rows:[{id:'r',segments:[{id:'s',kg:'1,',reps:''}]}]}}));
});
test('read failures are distinguishable from an empty draft list and malformed buffers remain evidence',async()=>{
 globalThis.localStorage=storage([[PREFIX+'bad','not-json']]);
 const drafts=await openDrafts({readDrafts:async()=>{throw Error('synthetic read failure')}});
 assert.ok(drafts.readError);assert.equal(drafts.records[0].raw,'not-json');assert.equal(drafts.records[0].corrupt,true);
});
test('flush resolves after failed IndexedDB write; pending raw evidence remains in synthetic localStorage',async()=>{
 globalThis.localStorage=storage();let writes=0;
 const drafts=await openDrafts({...database([]),writeDraft:async()=>{writes++;throw Error('synthetic quota')}});
 const binding={context:{sessionId:'session',exerciseId:'exercise'},baseline:null};
 drafts.capture(binding,'legacy',row(1,'a').value);await drafts.flush();
 assert.equal(writes,1);assert.ok(drafts.error);assert.equal(localStorage.length,1);
 assert.match(drafts.status('session','exercise'),/buforze/);assert.equal(drafts.records.length,1);
});
test('reload branch retention depends on evidence order; it is not a raw snapshot',async()=>{
 const a=row(1,'a'),b=row(1,'b'),c=row(2,'c');
 globalThis.localStorage=storage([[PREFIX+'synthetic:b',JSON.stringify(b)],[PREFIX+'synthetic:c',JSON.stringify(c)]]);
 const first=await openDrafts(database([a]));assert.deepEqual(first.records.map(r=>r.token),['c','b']);
 globalThis.localStorage=storage([[PREFIX+'synthetic:c',JSON.stringify(c)],[PREFIX+'synthetic:b',JSON.stringify(b)]]);
 const second=await openDrafts(database([a]));assert.deepEqual(second.records.map(r=>r.token),['c']);
});
