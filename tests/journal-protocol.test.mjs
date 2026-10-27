import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {createProtocol,materialize,objectRecord,readObject} from '../model/journal-protocol.mjs';
import {editIndex,auditIndex,indexKey,hashJSON} from '../model/journal-index.mjs';
import {freeze} from '../model/backup-json.mjs';
import {createLegacyModelFromSource} from '../model/legacy-model.mjs';
import {nativeData,AT} from './fixtures/backup-v4-fixture.mjs';
const storage=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
const options={ownerId:'synthetic-v4-owner',createdAt:AT};
function fixture(native=true){
 const old=JSON.parse(readFileSync('tests/fixtures/v1.json','utf8')),packet=JSON.parse(readFileSync('tests/fixtures/plan-v3.json','utf8'));
 const data=native?nativeData(old,packet):old,{catalog}=storage.parseBackup(data);
 data.future={ordered:{z:1,a:2},referenceLookalike:{kind:'object',ref:'keep as user data'},unicode:'Ł😀\ud800\u0000'};
 return {format:'pushpull-backup',version:2,data,catalog:structuredClone(catalog),archives:[{id:'raw',kind:'opaque',createdAt:AT,extension:{original:true},raw:'\\"\nŁ😀\ud800'.repeat(131072)},{id:'null',kind:'opaque',createdAt:AT,raw:null}]};
}
test('protocol materializes exact ordered JSON and current v3 backup for legacy and native V2/V3',async()=>{
 for(const native of [false,true]){
  const source=fixture(native),json=JSON.stringify(source),bundle=await createProtocol(source),actual=await materialize(bundle);
  assert.equal(JSON.stringify(actual),json);assert.equal(JSON.stringify(source),json);assert.equal(Object.isFrozen(source.data),false);
  assert.equal(JSON.stringify(await createLegacyModelFromSource(actual,options)),JSON.stringify(await createLegacyModelFromSource(source,options)));
  assert.ok(Object.isFrozen(actual.data));
  if(native){
   const snapshots=actual.data.trainingJournal.sessionSnapshots;
   assert.equal(snapshots[0].model,snapshots[1].model,'byte-identical models may share only frozen objects');
   assert.throws(()=>{snapshots[0].model.exercises[0].name='corrupt'},TypeError);
  }
 }
});
test('400 logical snapshots retain IDs, metadata, unknown fields and ordering with model deduplication',async()=>{
 const source=fixture(),d=source.data,original=d.sessions.find(s=>s.journalSnapshotId),snap=d.trainingJournal.sessionSnapshots.find(s=>s.id===original.journalSnapshotId);
 for(let i=0;i<400;i++){
  const id='large-'+i,snapshotId='large-snapshot-'+i;
  d.sessions.push({...original,id,seq:1000+i,status:'done',journalSnapshotId:snapshotId});
  d.trainingJournal.sessionSnapshots.push({...snap,id:snapshotId,sessionId:id,unknown:{i,notCollapsed:true}});
 }
 source.catalog=structuredClone(storage.parseBackup(d).catalog);
 const bundle=await createProtocol(freeze(source)),actual=await materialize(bundle);
 assert.equal(JSON.stringify(actual),JSON.stringify(source));
 const rows=bundle.records.journalSnapshots.slice(-400),refs=rows.map(r=>r.fields.find(([k])=>k==='model')[1]);
 assert.equal(new Set(refs).size,1);assert.equal(new Set(rows.map(r=>r.id)).size,400);
 assert.equal(actual.data.trainingJournal.sessionSnapshots.at(-1).unknown.i,399);
});
test('content and index corruption cannot be hidden behind unchanged IDs, counts or root',async()=>{
 const bundle=await createProtocol(fixture(false));
 const bad=async change=>{const copy=structuredClone(bundle);change(copy);await assert.rejects(materialize(copy));};
 await bad(b=>{b.records.journalObjects[0].json+=' ';});
 await bad(b=>{b.records.journalObjects[0].json=b.records.journalObjects[0].json.replace('pushpull','changed');});
 await bad(b=>{b.records.journalResults[0].ref=b.records.journalSessions[0].ref;});
 await bad(b=>{b.records.journalResults.pop();});
 await bad(b=>{b.records.journalIndex.find(n=>n.id===b.state.root).left=b.state.root;});
 await bad(b=>{b.records.journalObjects.pop();});
 await bad(b=>{b.records.journalSessions[0].position=999;});
});
test('persistent AVL updates authenticate all leaves after adversarial insertion order and corrections',async()=>{
 let root=null;const nodes=new Map(),leaves=new Map();
 for(let i=0;i<100;i++){
  const key=indexKey('results','r'+i),value=await hashJSON({i});leaves.set(key,value);
  const edit=await editIndex(root,id=>nodes.get(id),[[key,value]]);root=edit.root;for(const [id,n] of edit.added)nodes.set(id,n);
  assert.ok(edit.observed.size<30);
 }
 for(const key of [...leaves.keys()].reverse()){
  const value=await hashJSON({corrected:key});leaves.set(key,value);
  const edit=await editIndex(root,id=>nodes.get(id),[[key,value]]);root=edit.root;for(const [id,n] of edit.added)nodes.set(id,n);
 }
 await auditIndex(root,id=>nodes.get(id),leaves);
 await assert.rejects(auditIndex(root,id=>nodes.get(id),new Map([...leaves].slice(1))),/mismatch/);
});
test('limits, cancellation, malformed JSON and unknown nonportable fields fail without normalizing data',async()=>{
 const source=fixture(false),before=JSON.stringify(source);
 await assert.rejects(createProtocol(source,{limits:{objectBytes:32}}),/size/);
 const c=new AbortController();c.abort();await assert.rejects(createProtocol(source,{signal:c.signal}),{name:'AbortError'});
 for(const value of [undefined,Infinity,()=>1,new Date(),-0]){
  const copy=structuredClone(source);copy.data.future.invalid=value;await assert.rejects(createProtocol(copy));
 }
 const row=await objectRecord({unicode:'Ł😀\ud800'});assert.deepEqual(await readObject(row),{unicode:'Ł😀\ud800'});
 const invalid={...row,json:'{"a":1,"a":2}'};invalid.id=await hashJSON({unused:1});await assert.rejects(readObject(invalid));
 assert.equal(JSON.stringify(source),before);
});
