import test from 'node:test';
import assert from 'node:assert/strict';
import {buildPlan,views,activate,PLAN_ID,SLOTS} from '../model/v2-plan.mjs';
import {initialize,startSession,recordEntry} from '../model/journal.mjs';
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
 assert.deepEqual(['PUSH A','PULL A','PUSH B','PULL B'].map(t=>views(m,PLAN_ID,t,{}).length),[8,8,9,9]);
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
});
