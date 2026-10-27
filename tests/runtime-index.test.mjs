import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {nativeData,AT} from './fixtures/backup-v4-fixture.mjs';
import {createProtocol,materialize,sealState,allocationFor} from '../model/journal-protocol.mjs';
import {buildRuntime,deriveRuntime,contextSummary,descriptor,lookupIndex} from '../model/journal-runtime-index.mjs';
import {resultChangeAge} from '../model/performance.mjs';
import {buildIndex,editIndex,auditIndex,hashJSON} from '../model/journal-index.mjs';
import {freeze} from '../model/backup-json.mjs';
const storage=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{crypto,structuredClone});
function fixture(){const d=nativeData(JSON.parse(readFileSync('tests/fixtures/v1.json')),JSON.parse(readFileSync('tests/fixtures/plan-v3.json')));return {format:'pushpull-backup',version:2,data:d,catalog:structuredClone(storage.parseBackup(d).catalog),archives:[]};}
test('context index exactly preserves full change-age oracle, contexts, sides, drops and unknown comparisons',()=>{
 const {data}=fixture(),groups=new Map();for(const e of data.entries){if(!groups.has(e.exerciseId))groups.set(e.exerciseId,[]);groups.get(e.exerciseId).push(descriptor(data,e));}
 for(const e of data.entries){const ds=descriptor(data,e),summary=contextSummary(groups.get(e.exerciseId)),age=ds.measurement?new Map(summary.ages).get(ds.measurement.context)??null:null;assert.equal(age,resultChangeAge(data,e),e.id);}
 const source=fixture(),values=deriveRuntime(source);assert.ok(values.size>100);assert.equal(values.get('["info"]').maxSeq,Math.max(...data.sessions.map(s=>s.seq)));
});
test('runtime indices are part of the authenticated root and full semantic oracle',async()=>{
 const source=fixture(),base=await createProtocol(source),built=await buildRuntime(source,{sourceRoot:base.state.indexRoot}),records=structuredClone(base.records);
 records.journalObjects=[...new Map([...records.journalObjects,...built.objects].map(r=>[r.id,r])).values()];records.journalIndex=[...new Map([...records.journalIndex,...built.nodes].map(r=>[r.id,r])).values()];
 const state=await sealState({...base.state,allocation:await allocationFor(records),runtime:built.runtime});records.journalState=[state];
 assert.deepEqual(await materialize(freeze({state,records})),source);
 const bad=structuredClone({state,records});bad.state.runtime.version=99;await assert.rejects(materialize(bad),/version/);
 const mismatch=await buildRuntime({...source,data:{...source.data,entries:[]}},{sourceRoot:base.state.indexRoot}),wrong=structuredClone(records);
 wrong.journalObjects=[...new Map([...wrong.journalObjects,...mismatch.objects].map(r=>[r.id,r])).values()];wrong.journalIndex=[...new Map([...wrong.journalIndex,...mismatch.nodes].map(r=>[r.id,r])).values()];
 const resealed=await sealState({...state,allocation:await allocationFor(wrong),runtime:mismatch.runtime});wrong.journalState=[resealed];await assert.rejects(materialize({state:resealed,records:wrong}),/mismatch/);
});
test('Merkle membership, absence and removals retain exact AVL proofs',async()=>{
 const leaves=new Map();for(let i=0;i<80;i++)leaves.set('id-'+i,await hashJSON(i));const tree=await buildIndex(leaves);let root=tree.root;const nodes=tree.nodes;
 for(const key of [...leaves.keys()].filter((_,i)=>i%2===0)){const t=await editIndex(root,id=>nodes.get(id),[[key,null]]);root=t.root;for(const [id,n] of t.added)nodes.set(id,n);leaves.delete(key);await auditIndex(root,id=>nodes.get(id),leaves);assert.equal(await lookupIndex(root,key,id=>nodes.get(id)),null);}
 for(const [key,value] of leaves)assert.equal(await lookupIndex(root,key,id=>nodes.get(id)),value);
 const c=new AbortController();c.abort();await assert.rejects(lookupIndex(root,'no',id=>nodes.get(id),{signal:c.signal}),{name:'AbortError'});
});
test('long equal runs, corrections, invalid comparisons and date/sequence order agree with full age oracle',()=>{
 const {data}=fixture(),anchor=data.entries.find(e=>e.performance),session=data.sessions.find(s=>s.id===anchor.sessionId),snap=data.trainingJournal.sessionSnapshots.find(s=>s.sessionId===session.id);
 data.entries=[];data.sessions=[];data.trainingJournal.sessionSnapshots=[];
 for(let i=0;i<90;i++){
  const s={...session,id:'age-s-'+i,seq:i,date:'2026-10-'+String(1+Math.floor(i/3)).padStart(2,'0'),status:i===89?'active':'done',journalSnapshotId:'age-snap-'+i},snapshot={...snap,id:s.journalSnapshotId,sessionId:s.id},e=structuredClone(anchor);
  e.id='age-e-'+i;e.sessionId=s.id;e.journalSnapshotId=snapshot.id;
  if(i<75)e.performance.rows[0].segments[0].kg='9';
  if(i===50)e.performance.rows[0].segments[0].kg='bad';
  data.entries.push(e);data.sessions.push(s);data.trainingJournal.sessionSnapshots.push(snapshot);
 }
 const history=data.entries.map(e=>descriptor(data,e)),summary=contextSummary(history),ages=new Map(summary.ages);
 for(const e of data.entries){const d=descriptor(data,e);assert.equal(d.measurement?(ages.get(d.measurement.context)??null):null,resultChangeAge(data,e));}
});
test('committing a batch retains final AVL paths and all old nodes, without transient preparation versions',async()=>{
 const {committedNodes}=await import('../model/journal-index.mjs'),leaves=new Map();for(let i=0;i<100;i++)leaves.set('batch-'+i,await hashJSON(i));
 const original=await buildIndex(leaves),changes=[];for(let i=0;i<35;i++){const key='batch-'+i,value=await hashJSON({corrected:i});changes.push([key,value]);leaves.set(key,value)}
 const edit=await editIndex(original.root,id=>original.nodes.get(id),changes),kept=committedNodes([edit.root],edit.added),nodes=new Map([...original.nodes,...kept]);
 assert.ok(kept.size<edit.added.size/2);for(const id of original.nodes.keys())assert.ok(nodes.has(id));await auditIndex(edit.root,id=>nodes.get(id),leaves);
});
