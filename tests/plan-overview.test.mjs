import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {plans,sessionPlanId,weekOf,warsawDate,weeklyStats,entryTotals,SOURCE,UNASSIGNED} from '../model/plan-overview.mjs';
import {initialize,startSession,recordEntry} from '../model/journal.mjs';
import {activate,views,PLAN_ID} from '../model/v2-plan.mjs';
import {newPerformance,flatten} from '../model/performance.mjs';
import {stagePlan,stageActivation} from '../model/plan-import.mjs';
const fixture=()=>JSON.parse(readFileSync(new URL('fixtures/v1.json',import.meta.url)));
const incoming=()=>JSON.parse(readFileSync(new URL('fixtures/plan-v3.json',import.meta.url)));
function fresh(){const d=fixture();d.sessions=[];d.entries=[];d.activeId=null;d.trainingJournal=initialize('owner');return d;}
async function session(d,type,date,ids,status='done'){
 const s={id:crypto.randomUUID(),type,date,status,seq:d.sessions.length+1};d.sessions.push(s);await startSession(d,s,date+'T10:00:00.000Z');
 for(const id of ids){const ex=views(d.trainingJournal.model,d.trainingJournal.activePlanVersionId,type,d).find(e=>e.id===id),p=newPerformance(ex);
  for(const r of p.rows)for(const seg of r.segments){seg.kg='20';seg.reps='8';}
  const e={id:crypto.randomUUID(),sessionId:s.id,exerciseId:id,performance:p,series:flatten(p),kg:'20',reps:'8'};recordEntry(d,e);d.entries.push(e);
 }
 return s;
}

test('ISO weeks cross calendar year and DST; current day is Europe/Warsaw',()=>{
 assert.deepEqual(weekOf('2021-01-01'),{id:'2020-W53',from:'2020-12-28',to:'2021-01-03'});
 assert.equal(weekOf('2021-01-04').id,'2021-W01');assert.equal(weekOf('2026-03-29').from,'2026-03-23');
 assert.equal(warsawDate(new Date('2021-01-03T23:30:00Z')),'2021-01-04');
 assert.equal(warsawDate(new Date('2026-03-29T22:30:00Z')),'2026-03-30');
 assert.throws(()=>weekOf('2026-02-30'),/data/);
});

test('weekly totals use each actual side/segment once, drops count one set, A/B separately, plan snapshots isolate histories',async()=>{
 let d=fresh();activate(d,'2020-12-01T10:00:00.000Z');
 await session(d,'PULL A','2020-12-31',['PULL-A-1']);await session(d,'PUSH A','2021-01-01',['PUSH-A-5']);
 await session(d,'PULL B','2021-01-04',['PULL-B-6-SKI','PULL-B-6-SHRUGS']);await session(d,'PUSH A','2021-01-18',['PUSH-A-3']);
 await session(d,'PUSH A','2021-01-05',['PUSH-A-3'],'active');
 const p=incoming();d=stageActivation(stagePlan(d,p,'owner'),p.planVersion.id,'2021-01-01T12:00:00.000Z');
 await session(d,'TEST-B','2021-01-04',['TEST-5']);const before=structuredClone(d);
 const r=weeklyStats(d,PLAN_ID,{from:'2020-12-28',to:'2021-01-24',today:'2021-01-20'});
 assert.deepEqual(r.rows.map(w=>[w.id,w.tonnage,w.sets,w.reps,w.workouts]),[['2020-W53',1920,9,96,2],['2021-W01',640,4,32,1],['2021-W02',0,0,0,0],['2021-W03',480,3,24,1]]);
 assert.equal(r.rows[1].delta.tonnage.absolute,-1280);assert.equal(r.rows[2].delta.tonnage.percent,-100);assert.equal(r.rows[3].partial,true);assert.equal(r.rows[3].delta.tonnage,null);
 const v3=weeklyStats(d,p.planVersion.id,{from:'2020-12-28',to:'2021-01-24',today:'2021-01-25'});assert.equal(v3.totals.tonnage,640);assert.equal(v3.totals.sets,4);
 assert.deepEqual(d,before);assert.equal(plans(d).find(p=>p.current).id,p.planVersion.id);
});

test('missing series stay unknown, empty weeks are zero, comparisons require complete calendar weeks and a nonzero percent base',async()=>{
 const d=fresh();activate(d,'2020-12-01T10:00:00.000Z');
 const s=await session(d,'PUSH A','2021-01-11',[]);
 let r=weeklyStats(d,PLAN_ID,{from:'2021-01-04',to:'2021-01-17',today:'2021-01-18'});
 assert.equal(r.rows[1].missing.tonnage,1);assert.equal(r.rows[1].delta.tonnage,null);assert.deepEqual(r.rows[1].delta.workouts,{absolute:1,percent:null});
 assert.deepEqual(entryTotals(d,{sessionId:'old',kg:'99',reps:'99',performance:{opaque:'legacy'}}),{tonnage:null,sets:null,reps:null});
 s.date='2021-01-04';r=weeklyStats(d,PLAN_ID,{from:'2021-01-06',to:'2021-01-17',today:'2021-01-18'});
 assert.equal(r.totals.workouts,0);assert.equal(r.rows[0].partial,true);assert.equal(r.rows[1].delta.workouts,null);
 assert.throws(()=>weeklyStats(d,PLAN_ID,{from:'2021-02-01',to:'2021-01-01'}),/Początek/);
});

test('editing historical date or weight updates aggregates without rewriting snapshot IDs or plans',async()=>{
 const d=fresh();activate(d,'2020-12-01T10:00:00.000Z');const s=await session(d,'PULL A','2021-01-03',['PULL-A-1']);
 const snapshots=structuredClone(d.trainingJournal.sessionSnapshots),e=d.entries[0],ids=e.performance.rows.map(r=>r.id);
 s.date='2021-01-04';e.performance.rows[0].segments[0].kg='10';e.kg='10';recordEntry(d,e);
 const r=weeklyStats(d,PLAN_ID,{from:'2020-12-28',to:'2021-01-10',today:'2021-01-11'});
 assert.deepEqual(r.rows.map(w=>w.tonnage),[0,880]);assert.deepEqual(e.performance.rows.map(r=>r.id),ids);assert.deepEqual(d.trainingJournal.sessionSnapshots,snapshots);
});

test('plan catalogue is read-only, retains source snapshots and unassigned sessions, activation is idempotent for imported plans',async()=>{
 let d=fresh();const old={id:'observed',type:'PUSH A',date:'2026-10-21',status:'done',seq:1};d.sessions.push(old);await startSession(d,old,'2026-10-21T12:00:00.000Z');
 d.sessions.push({id:'unversioned',type:'PUSH A',date:'2026-10-20',status:'done',seq:2},{id:'source',type:'PULL B',date:'2026-10-19',status:'done',seq:3,sourceExerciseIds:['PULL-B-6-SKI']});
 activate(d,'2026-10-22T12:00:00.000Z');const original=structuredClone(d),index=plans(d);
 assert.equal(index.filter(p=>p.current).length,1);assert.equal(index.find(p=>p.current).id,PLAN_ID);
 assert.equal(sessionPlanId(d,d.sessions[1]),UNASSIGNED);assert.equal(sessionPlanId(d,d.sessions[2]),SOURCE);
 assert.ok(index.some(p=>p.kind==='observed'&&p.status==='previous'));assert.ok(index.some(p=>p.id===UNASSIGNED));assert.deepEqual(d,original);
 const p=incoming();d=stageActivation(stagePlan(d,p,'owner'),p.planVersion.id,'2026-10-23T12:00:00.000Z');
 const before=structuredClone(d);assert.deepEqual(stageActivation(d,p.planVersion.id,'2026-10-24T12:00:00.000Z'),before);
});

test('legacy recorded session-start versions are read-only; migration current-only labels never prove past plan identity',()=>{
 const d=fixture(),s=d.sessions[0],catalog={sessionVersions:{[s.id]:{versionId:'PUSH A:2',provenance:'session-start'}},planVersions:[{id:'PUSH A:2',planId:'PUSH A',provenance:'recorded',exercises:d.exercises['PUSH A']}]};
 const before=structuredClone({d,catalog}),id='@legacy:PUSH A:2';
 assert.equal(sessionPlanId(d,s,catalog),id);assert.equal(plans(d,catalog).find(p=>p.id===id).kind,'recorded');
 const report=weeklyStats(d,id,{from:s.date,to:s.date,today:s.date,catalog});
 assert.equal(report.totals.workouts,s.status==='done'?1:0);assert.deepEqual({d,catalog},before);
 catalog.sessionVersions[s.id].provenance='legacy-current-only';assert.equal(sessionPlanId(d,s,catalog),UNASSIGNED);
 catalog.sessionVersions[s.id].provenance='session-start';catalog.planVersions[0].provenance='legacy-current-only';assert.equal(sessionPlanId(d,s,catalog),UNASSIGNED);
});
