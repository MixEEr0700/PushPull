import test from 'node:test';
import assert from 'node:assert/strict';
import {buildPlan,views,activate,PLAN_ID,SLOTS} from '../model/v2-plan.mjs';
import {initialize,startSession,recordEntry,project} from '../model/journal.mjs';
import {newPerformance,flatten,validatePerformance} from '../model/performance.mjs';
import {captureSessionSnapshot} from '../model/training-model.mjs';

test('approved 34 slots: owner decisions, unknown targets, back-offs and independent pair',()=>{
 const m=buildPlan('owner');assert.equal(SLOTS.length,34);assert.equal(m.positions.length,35);
 assert.equal(m.positions.filter(p=>p.setState==='unspecified').length,4);
 assert.equal(m.sets.filter(s=>s.role==='backoff').length,5);assert.equal(m.drops.length,6);
 assert.equal(m.groups[0].rounds,2);assert.equal(m.groups[0].betweenMembersSeconds,15);assert.equal(m.groups[0].afterRoundSeconds,null);
 const chest=m.positions.find(p=>p.slotId==='PUSH-A-4');assert.equal(chest.exerciseId,'PUSH-A-4-CHEST-PRESS');assert.equal(m.exercises.find(e=>e.id===chest.exerciseId).legacyId,null);
 assert.deepEqual(m.sets.filter(s=>s.positionId===chest.id).map(s=>s.reps),[{min:8,max:10},{min:8,max:10}]);
 assert.deepEqual(m.sets.find(s=>s.positionId===chest.id).tempo,[3,1,1,1]);
 assert.deepEqual(['PUSH A','PULL A','PUSH B','PULL B'].map(t=>views(m,PLAN_ID,t,{}).length),[8,8,9,10]);
 const pair=views(m,PLAN_ID,'PULL B',{}).filter(v=>v.group);
 assert.deepEqual(pair.map(v=>v.id),['PULL-B-6-SKI','PULL-B-6-SHRUGS']);
 assert.deepEqual(pair.map(v=>v.positionId),m.groups[0].positionIds);
 assert.ok(pair[0].name.startsWith('PULL-B-6A · Narciarz'));
 assert.ok(pair[1].name.startsWith('PULL-B-6B · Szrugsy'));
 assert.ok(pair.every(v=>!v.members&&v.sets===2&&v.tempo==='2 0 1 0'&&v.rir===0&&v.instructions));
 assert.ok(m.sets.every(s=>s.rir.min===0));assert.ok(!JSON.stringify(m).includes('initialKg'));
});

test('structured result rejects changed projection, invalid side, duplicate segments and invented drop',()=>{
 const m=buildPlan('owner'),ex=views(m,PLAN_ID,'PULL A',{})[0];
 const snap=captureSessionSnapshot(m,{id:'snapshot',sessionId:'session',planVersionId:PLAN_ID,unitId:'PULL A',startedAt:'2026-10-22T12:00:00.000Z'});
 const p=newPerformance(ex);for(const row of p.rows)for(const s of row.segments){s.kg='10';s.reps='8';}
 const e={exerciseId:ex.id,journalPositionId:ex.positionId,journalVariantId:ex.journalVariantId,performance:p,series:flatten(p),kg:'10',reps:'8'};
 assert.equal(validatePerformance(p,snap,e).length,6);
 const wrong=structuredClone(e);wrong.series[0].kg='100';assert.throws(()=>validatePerformance(p,snap,wrong),/projection/);
 const bad=structuredClone(p);bad.rows[0].side=null;assert.throws(()=>validatePerformance(bad,snap,e),/left\/right/);
 const dup=structuredClone(p);dup.rows[1].segments[0].id=dup.rows[0].segments[0].id;assert.throws(()=>validatePerformance(dup,snap,e),/duplicate/);
 const drop=structuredClone(p);drop.rows[0].segments.push({id:'extra',kg:'5',reps:'8'});assert.throws(()=>validatePerformance(drop,snap,e),/drop prescription/);
 assert.equal(flatten(p).reduce((s,r)=>s+Number(r.kg)*Number(r.reps),0),480);
});

test('activation affects only future snapshots, does not add new chest to old sessions',async()=>{
 const exercises=Object.fromEntries(['PUSH A','PULL A','PUSH B','PULL B'].map(type=>[type,SLOTS.filter(s=>s.unit===type).map(s=>({id:s.slot,name:s.slot,sets:2,target:'legacy',tempo:'unknown',rir:'unknown',initialKg:'',notes:'original'}))]));
 const data={exercises,trainingJournal:initialize('owner'),sessions:[],entries:[]};
 const old={id:'old',type:'PUSH A'};await startSession(data,old,'2026-10-22T10:00:00.000Z');
 const before=structuredClone(data.trainingJournal.sessionSnapshots),original=structuredClone(exercises['PUSH A']);
 activate(data,'2026-10-22T11:00:00.000Z');
 assert.deepEqual(data.trainingJournal.sessionSnapshots,before);assert.deepEqual(data.exercises['PUSH A'].slice(0,8),original);
 const current={id:'new',type:'PUSH A'};await startSession(data,current,'2026-10-22T12:00:00.000Z');
 assert.equal(data.trainingJournal.sessionSnapshots[1].planVersionId,PLAN_ID);
 assert.equal(data.trainingJournal.sessionSnapshots[0].model.sets[0].reps,null);
 // An opaque pre-V2 extension named 'performance' must not be reinterpreted or lost.
 data.sessions=[old,current];const entry={id:'old-entry',exerciseId:'PUSH-A-1',sessionId:old.id,kg:'10',reps:'8',series:[{kg:'10',reps:'8'}],performance:{unknown:'legacy extension'}};
 recordEntry(data,entry);
 const projected=project(data,{model:data.trainingJournal.model,sessionRecords:data.sessions.map(s=>({id:s.id,data:s,snapshotId:null})),resultRecords:[{id:entry.id,data:entry}],legacySources:[]});
 assert.deepEqual(projected.resultRecords[0].data.entryMetadata.performance,entry.performance);
});

test('group labels support A/B/C and retain independent position identities',()=>{
 const m=structuredClone(buildPlan('owner')),g=m.groups[0],p=m.positions.find(p=>p.id===g.positionIds[1]);
 const third={...p,id:p.id+':third',exerciseId:'test-third',order:p.order+0.5,label:'Third member'};
 m.positions.push(third);g.positionIds.push(third.id);
 const pair=views(m,PLAN_ID,'PULL B',{}).filter(e=>e.group);
 assert.deepEqual(pair.map(e=>e.displayNumber),['6A','6B','6C']);
 assert.deepEqual(pair.map(e=>e.positionId),g.positionIds);
 assert.ok(pair[2].name.startsWith('PULL-B-6C'));
});

test('source pair revision is additive and preserves legacy sessions and observed snapshots',async()=>{
 const {readFileSync}=await import('node:fs');
 const {sourceExercises,prepareSourceSession,exercisesFor,previewExercises}=await import('../model/journal.mjs');
 for(const native of [false,true]){
  const data=JSON.parse(readFileSync(new URL('fixtures/v1.json',import.meta.url)));
  const legacy=data.sessions.find(s=>s.type==='PULL B'),before=structuredClone(data);
  if(native){data.trainingJournal=initialize('owner');await startSession(data,legacy,'2026-10-22T10:00:00.000Z');}
  const snapshots=structuredClone(data.trainingJournal?.sessionSnapshots);
  const preview=sourceExercises(data,'PULL B');
  assert.equal(preview.length,10);assert.equal(data.exercises['PULL B'].length,9);
  assert.deepEqual(preview.filter(e=>e.sourceGroupId).map(e=>[e.id,e.initialKg,e.notes]),[['PULL-B-6-SKI','',''],['PULL-B-6-SHRUGS','','']]);
  const current={id:'source-new',type:'PULL B'};prepareSourceSession(data,current);
  if(native)await startSession(data,current,'2026-10-22T11:00:00.000Z');
  assert.equal(exercisesFor(data,current).length,10);
  assert.equal(exercisesFor(data,current).find(e=>e.id==='PULL-B-7').displayNumber,7);
  assert.equal(exercisesFor(data,legacy).length,9);
  assert.ok(exercisesFor(data,legacy).some(e=>e.id==='PULL-B-6'));
  assert.deepEqual(data.exercises['PULL B'].slice(0,9),before.exercises['PULL B']);
  assert.deepEqual(data.entries,before.entries);assert.deepEqual(data.changes,before.changes);
  assert.equal(data.exercises['PULL B'].length,11);
  prepareSourceSession(data,{id:'next',type:'PULL B'});assert.equal(data.exercises['PULL B'].length,11);
  if(native){
   assert.deepEqual(data.trainingJournal.sessionSnapshots.slice(0,1),snapshots);
   assert.equal(previewExercises(data,'PULL B').length,10);
   assert.ok(data.trainingJournal.sessionSnapshots[1].model.sets.every(s=>s.rir===null&&s.tempo===null));
   activate(data,'2026-10-22T12:00:00.000Z');
   assert.ok(exercisesFor(data,current).every(e=>!e.v2));
   assert.equal(previewExercises(data,'PULL B').length,10);
  }
 }
});

test('repeated activation of already active V2 is a complete no-op, including rotation and activation log',async()=>{
 const {readFileSync}=await import('node:fs');
 const data=JSON.parse(readFileSync(new URL('fixtures/v1.json',import.meta.url)));
 data.trainingJournal=initialize('owner');activate(data,'2026-10-23T08:00:00Z');
 data.trainingJournal.nextUnitId='PULL B';const before=structuredClone(data);
 activate(data,'2026-10-23T09:00:00Z');assert.deepEqual(data,before);
});

test('side linking is recoverable editor state; old asymmetric results and drafts are never normalized',async()=>{
 const editor=await import('../model/performance-editor.mjs');
 const ex=views(buildPlan('owner'),PLAN_ID,'PULL A',{}).find(e=>e.id==='PULL-A-1');
 editor.editor(ex,'test-side-state',null,null);
 const fresh=editor.state(ex.id,'test-side-state');assert.equal(fresh.sidePairs.length,3);assert.ok(fresh.sidePairs.every(p=>!p.linked));
 fresh.sidePairs[1].linked=false;editor.restore(ex.id,'test-side-state',fresh);editor.editor(ex,'test-side-state',null,null);
 assert.deepEqual(editor.state(ex.id,'test-side-state'),fresh,'separate mode persists even with equal or empty values');
 const old=structuredClone(fresh);delete old.sidePairs;old.performance.rows[0].segments[0].kg='40';old.performance.rows[1].segments[0].kg='35';
 editor.restore(ex.id,'test-side-state',old);editor.editor(ex,'test-side-state',null,null);
 const recovered=editor.state(ex.id,'test-side-state');assert.equal(recovered.sidePairs[0].linked,false);assert.deepEqual(recovered.performance,old.performance);
 editor.forget(ex.id,'test-side-state');
});
