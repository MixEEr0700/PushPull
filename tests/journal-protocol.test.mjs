import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {createProtocol,materialize,objectRecord,readObject,protocolBudget} from '../model/journal-protocol.mjs';
import {editIndex,auditIndex,indexKey,hashJSON,sha,verifyNode,buildIndex} from '../model/journal-index.mjs';
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
 await bad(b=>{b.records.journalIndex.find(n=>n.id===b.state.indexRoot).left=b.state.indexRoot;});
 await bad(b=>{b.records.journalObjects.pop();});
 await bad(b=>{b.records.journalSessions[0].position=999;});
 await bad(b=>{b.state.ownerId='corrupt metadata without changing root';});
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
test('materialization and SHA readers detach mutable callers before the first await',async()=>{
 const source=fixture(false),bundle=structuredClone(await createProtocol(source)),pending=materialize(bundle);
 bundle.records.journalObjects[0].json='"changed after call"';bundle.state.root='0'.repeat(64);
 assert.equal(JSON.stringify(await pending),JSON.stringify(source));
 const object={...await objectRecord({value:'before'})},read=readObject(object);object.json='{"value":"after!"}';
 assert.deepEqual(await read,{value:'before'});
 const tree=await buildIndex([['before',await hashJSON(1)]]),node={...tree.nodes.get(tree.root)},verified=verifyNode(node);
 node.key='changed after SHA began';assert.equal((await verified).key,'before');
});
test('only a fully verified immutable bundle can reuse proofs and reduced limits still apply',async()=>{
 const bundle=await createProtocol(fixture(false));assert.throws(()=>protocolBudget(bundle),/verified/);
 const first=await materialize(bundle),budget=protocolBudget(bundle);assert.equal(await materialize(bundle),first);
 await assert.rejects(materialize(bundle,{limits:{totalBytes:budget.bytes-1}}),/limit/);
 const copy=structuredClone(bundle);copy.records.journalObjects[0].json+=' ';freeze(copy);
 assert.throws(()=>protocolBudget(copy),/verified/);await assert.rejects(materialize(copy));
 const cancelled=new AbortController();cancelled.abort();await assert.rejects(materialize(bundle,{signal:cancelled.signal}),{name:'AbortError'});
});
test('UTF-8 wire validation rejects surrogate replacement collisions and bounds encoded allocations',async()=>{
 const row=await objectRecord('\ufffd'),bad={...row,json:'"'+String.fromCharCode(0xd800)+'"'};
 // Native UTF-8 conversion alone cannot distinguish these two wire strings.
 assert.deepEqual(new TextEncoder().encode(row.json),new TextEncoder().encode(bad.json));
 await assert.rejects(readObject(bad),/UTF-8/);
 await assert.rejects(objectRecord('Ł😀'.repeat(100),{objectBytes:100}),/size/);
 for(const value of ['x'.repeat(80),'Ł'.repeat(40),'😀'.repeat(20)]){
  const row=await objectRecord(value,{objectBytes:100});assert.deepEqual(row,await objectRecord(value));assert.equal(await readObject(row,{objectBytes:100}),value);
 }
 await assert.rejects(objectRecord('Ł'.repeat(60),{objectBytes:100}),/size/);
 const valid=await objectRecord('\ud800');assert.equal(await readObject(valid),'\ud800');
});
test('legacy optional journal values retain their exact old-reader meaning',async()=>{
 for(const value of [null,false,0,'']){
  const source=fixture(false);source.archives=[];source.data.trainingJournal=value;
  assert.equal(JSON.stringify(await materialize(await createProtocol(source))),JSON.stringify(source));
 }
});
test('sealed root binds metadata and the exact complete checkpoint set',async()=>{
 const source=fixture(false);source.archives=[];
 const checkpoint={id:'recovery:test',protocol:2,raw:'{"original":true}'};checkpoint.sha256=await sha(checkpoint.raw);
 const bundle=await createProtocol(source,{checkpoints:[checkpoint]});assert.equal(JSON.stringify(await materialize(bundle)),JSON.stringify(source));
 const missing=structuredClone(bundle);missing.records.journalCheckpoints=[];await assert.rejects(materialize(missing),/completeness/);
 const tampered=structuredClone(bundle);tampered.records.journalCheckpoints[0].raw='{"original":false}';tampered.records.journalCheckpoints[0].sha256=await sha(tampered.records.journalCheckpoints[0].raw);
 await assert.rejects(materialize(tampered),/binding/);
 tampered.state.checkpointRefs[0].sha256=await hashJSON(tampered.records.journalCheckpoints[0]);await assert.rejects(materialize(tampered),/state SHA/);
});

test('structured-only validation rejects the same invalid native graph without constructing backup text',async()=>{
 const {validateStructuredSource}=await import('../model/legacy-model.mjs');
 for(const mutate of [s=>{s.data.entries[0].kg='invalid'},s=>{s.catalog.sessionVersions={}},s=>{s.data.trainingJournal.model.ownerId='other'},s=>{s.data.trainingJournal.sessionSnapshots[0].model.positions[0].exerciseId='missing'},s=>{s.data.entries.push(structuredClone(s.data.entries[0]))},s=>{s.archives[0].raw=42}]){
  const value=fixture();mutate(value);
  assert.throws(()=>validateStructuredSource(value,options.ownerId));
  await assert.rejects(createLegacyModelFromSource(value,options));
 }
 const valid=freeze(fixture());assert.doesNotThrow(()=>validateStructuredSource(valid,options.ownerId));
});
test('allocation is root-bound and verified against every retained byte and record on a full audit',async()=>{
 const {sealState,equalJSON}=await import('../model/journal-protocol.mjs');
 const bundle=await createProtocol(fixture(false));await materialize(bundle);assert.deepEqual(bundle.state.allocation,protocolBudget(bundle));
 for(const field of ['bytes','records','maxObjectBytes']){
  const copy=structuredClone(bundle);copy.state.allocation[field]++;
  await assert.rejects(materialize(copy),/state SHA/);
  copy.state=await sealState(copy.state);copy.records.journalState=[copy.state];await assert.rejects(materialize(copy),/allocation mismatch/);
 }
 const {allocation,...old}=bundle.state,oldState=await sealState(old);
 assert.equal(JSON.stringify(await materialize({state:oldState,records:{...bundle.records,journalState:[oldState]}})),JSON.stringify(await materialize(bundle)));
 assert.equal(equalJSON({z:1,a:[2]},{a:[2],z:1}),false);
 assert.equal(equalJSON({z:1,a:[2]},{a:[2],z:1},{ordered:false}),true);
 assert.equal(equalJSON([1,2],[2,1],{ordered:false}),false);
});
