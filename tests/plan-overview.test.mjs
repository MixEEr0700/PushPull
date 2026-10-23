import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {plans,sessionPlanId,weekOf,warsawDate,weeklyStats,entryTotals,activationPeriods,exerciseTimeline,SOURCE,UNASSIGNED} from '../model/plan-overview.mjs';
import {initialize,startSession,recordEntry,advance,nextType,project} from '../model/journal.mjs';
import {activate,views,PLAN_ID} from '../model/v2-plan.mjs';
import {newPerformance,flatten} from '../model/performance.mjs';
import {stagePlan,stageActivation,storedPlanModel} from '../model/plan-import.mjs';
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


test('reactivation has distinct actual intervals, no fabricated bounds and no date-import fallback',()=>{
 let d=fresh();activate(d,'2026-10-01T22:30:00.000Z');d=stageActivation(stagePlan(d,incoming(),'owner'),'synthetic-v3','2026-10-10T10:00:00.000Z');activate(d,'2026-10-20T10:00:00.000Z');
 const before=structuredClone(d),p=plans(d).find(p=>p.id===PLAN_ID);
 assert.deepEqual(p.periods,[{from:'2026-10-01T22:30:00.000Z',to:'2026-10-10T10:00:00.000Z',ongoing:false,uncertain:false},{from:'2026-10-20T10:00:00.000Z',to:null,ongoing:true,uncertain:false}]);
 assert.equal(warsawDate(new Date(p.periods[0].from)),'2026-10-02');assert.equal(p.activatedAt,'2026-10-20T10:00:00.000Z');assert.deepEqual(d,before);
 d.trainingJournal.activations[1].at=null;assert.equal(activationPeriods(d,PLAN_ID)[0].uncertain,true);
 d.trainingJournal.activations[1].at='2026-02-30T10:00:00.000Z';assert.equal(activationPeriods(d,PLAN_ID)[0].to,null);
 d.trainingJournal.activations[1].at='2026-09-01T10:00:00.000Z';assert.equal(activationPeriods(d,PLAN_ID)[0].to,null,'a backwards phone clock must not produce an invented/sorted interval');
});

test('missing activation timestamps show only trustworthy completed session dates; correction never shifts activation',async()=>{
 const d=fresh();activate(d,'2026-10-01T10:00:00.000Z');const s=await session(d,'PUSH A','2026-10-05',[]);d.trainingJournal.activations=[];
 let p=plans(d).find(p=>p.id===PLAN_ID);assert.equal(p.activatedAt,null);assert.deepEqual(p.periods,[]);assert.deepEqual(p.trainingRange,{from:'2026-10-05',to:'2026-10-05'});
 s.date='2026-09-01';assert.deepEqual(plans(d).find(p=>p.id===PLAN_ID).trainingRange,{from:'2026-09-01',to:'2026-09-01'});assert.deepEqual(activationPeriods(d,PLAN_ID),[]);
 d.trainingJournal.activations=[{planVersionId:PLAN_ID,at:'2026-10-01T10:00:00.000Z'}];assert.equal(plans(d).find(p=>p.id===PLAN_ID).periods[0].from,'2026-10-01T10:00:00.000Z');
 d.sessions.push({id:'unknown',status:'done',date:'2020-01-01',type:'PUSH A'},{id:'source-only',status:'done',date:'2020-01-01',type:'PULL B',sourceExerciseIds:['PULL-B-6-SKI']});
 assert.equal(plans(d).find(p=>p.id===UNASSIGNED).trainingRange,null);assert.equal(plans(d).find(p=>p.id===SOURCE).trainingRange,null);
 const catalog={sessionVersions:{unknown:{versionId:'stored',provenance:'session-start'}},planVersions:[{id:'stored',planId:'PUSH A',provenance:'recorded',exercises:[]}]};
 assert.deepEqual(plans(d,catalog).find(p=>p.id==='@legacy:stored').trainingRange,{from:'2020-01-01',to:'2020-01-01'});
 catalog.planVersions[0].provenance='legacy-current-only';assert.equal(plans(d,catalog).find(p=>p.id===UNASSIGNED).trainingRange,null);
});

test('return to stored V2 preserves its definitions and snapshots; old same-version session cannot advance a new cycle even at identical timestamps',async()=>{
 let d=fresh();activate(d,'2026-10-01T10:00:00.000Z');const s=await session(d,'PULL A','2026-10-02',['PULL-A-1'],'active');d.activeId=s.id;
 d.trainingJournal.model.coachInstructions[0].text='Actual stored instructions from the previous release';const original=structuredClone(d);
 d=stageActivation(stagePlan(d,incoming(),'owner'),'synthetic-v3','2026-10-02T10:00:00.000Z');const saved=structuredClone(d.trainingJournal.model);
 activate(d,'2026-10-02T10:00:00.000Z');assert.deepEqual(d.trainingJournal.model,saved);assert.equal(nextType(d),'PUSH A');assert.equal(d.trainingJournal.activations.at(-1).ongoingSessionId,s.id);
 assert.deepEqual(d.sessions,original.sessions);assert.deepEqual(d.entries,original.entries);assert.deepEqual(d.trainingJournal.sessionSnapshots,original.trainingJournal.sessionSnapshots);
 advance(d,s);assert.equal(nextType(d),'PUSH A');const unchanged=structuredClone(d);activate(d,'2026-10-03T10:00:00.000Z');assert.deepEqual(d,unchanged);
 const newer=await session(d,'PUSH A','2026-10-02',[]);advance(d,newer);assert.equal(nextType(d),'PULL A');
 d.trainingJournal.activations.at(-1).ongoingSessionId='missing-session';assert.throws(()=>project(d,{model:{ownerId:'owner'}}),/activation session reference/);
});

test('new activation context survives full v3 export/restore with legacy source and without rewriting the old format',async()=>{
 const {runInNewContext}=await import('node:vm'),{createLegacyModel,parseModelBackup}=await import('../model/legacy-model.mjs'),{exportBackup}=await import('../model/backup.mjs');
 let d=fresh();activate(d,'2026-10-01T10:00:00.000Z');const s=await session(d,'PUSH A','2026-10-02',['PUSH-A-3'],'active');d.activeId=s.id;
 d=stageActivation(stagePlan(d,incoming(),'owner'),'synthetic-v3','2026-10-03T10:00:00.000Z');activate(d,'2026-10-04T10:00:00.000Z');
 const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto:globalThis.crypto});const {catalog}=db.parseBackup(d);
 const raw=JSON.stringify({format:'pushpull-backup',version:2,data:d,catalog,archives:[]}),doc=await createLegacyModel(raw,{ownerId:'owner',createdAt:'2026-10-05T10:00:00.000Z'});
 assert.deepEqual((await parseModelBackup(await exportBackup(doc))).data,d);
});


test('complete registry/snapshot plans activate without an import packet; incomplete skeletons and collisions never become V1',async()=>{
 let d=fresh();activate(d,'2026-01-01T10:00:00.000Z');const p=incoming();d=stagePlan(d,p);
 await session(d,'PUSH A','2026-01-02',['PUSH-A-1']);
 d=stageActivation(d,p.planVersion.id,'2026-01-03T10:00:00.000Z');await session(d,'TEST-A','2026-01-04',['TEST-1']);
 delete d.trainingJournal.importedPlans;const before=structuredClone(d);
 assert.ok(plans(d).find(x=>x.id===p.planVersion.id).canActivate);assert.ok(storedPlanModel(d,p.planVersion.id));
 d=stageActivation(d,PLAN_ID,'2026-01-05T10:00:00.000Z');assert.equal(d.trainingJournal.nextUnitId,'PUSH A');
 // A complete snapshot still contains all original units and definitions.
 const preserved=d.trainingJournal.sessionSnapshots.find(s=>s.planVersionId===p.planVersion.id).model;
 for(const key of ['exercises','variants','planVersions','positions','sets','drops','groups','coachInstructions'])d.trainingJournal.model[key]=d.trainingJournal.model[key].filter(row=>!preserved[key].some(x=>x.id===row.id));
 const source=structuredClone(d);assert.ok(plans(d).find(x=>x.id===p.planVersion.id).canActivate);assert.deepEqual(d,source);
 const restored=stageActivation(d,p.planVersion.id,'2026-01-06T10:00:00.000Z');assert.equal(restored.trainingJournal.nextUnitId,'TEST-A');assert.deepEqual(restored.sessions,before.sessions);assert.deepEqual(restored.entries,before.entries);assert.deepEqual(restored.trainingJournal.sessionSnapshots,before.trainingJournal.sessionSnapshots);
 const packetOnly=structuredClone(d);packetOnly.trainingJournal.sessionSnapshots=[];packetOnly.trainingJournal.importedPlans=[p];assert.ok(plans(packetOnly).find(x=>x.id===p.planVersion.id).canActivate);assert.equal(stageActivation(packetOnly,p.planVersion.id,'2026-01-06T10:00:00.000Z').trainingJournal.activePlanVersionId,p.planVersion.id);
 const conflict=structuredClone(d);conflict.trainingJournal.model.exercises.push({...preserved.exercises[0],name:'conflicting definition'});assert.equal(storedPlanModel(conflict,p.planVersion.id),null);
 const incomplete=structuredClone(d);incomplete.trainingJournal.sessionSnapshots=[];incomplete.trainingJournal.model.planVersions.push(p.planVersion);assert.equal(storedPlanModel(incomplete,p.planVersion.id),null);assert.equal(plans(incomplete).find(x=>x.id===p.planVersion.id).canActivate,false);
 const skeleton=fresh();await session(skeleton,'PUSH A','2026-01-01',[]);assert.ok(plans(skeleton).filter(x=>['observed','source','unassigned'].includes(x.kind)).every(x=>!x.canActivate));
 assert.throws(()=>stageActivation(skeleton,'imaginary-v1','2026-01-01T10:00:00.000Z'),/brak kompletnej/);
});

test('V2 A + C statistics continue across a six-month V3 period; plots keep dated gaps and no reset',async()=>{
 let d=fresh();activate(d,'2026-01-01T10:00:00.000Z');await session(d,'PUSH A','2026-01-05',['PUSH-A-1']);await session(d,'PUSH A','2026-01-06',['PUSH-A-1']);
 const p=incoming();d=stageActivation(stagePlan(d,p),p.planVersion.id,'2026-01-07T10:00:00.000Z');await session(d,'TEST-A','2026-04-05',['TEST-1']);
 d=stageActivation(d,PLAN_ID,'2026-07-01T10:00:00.000Z');await session(d,'PUSH A','2026-07-06',['PUSH-A-1']);
 const old=structuredClone(d),r=weeklyStats(d,PLAN_ID,{from:'2026-01-05',to:'2026-07-12',today:'2026-07-13'});
 assert.equal(r.totals.workouts,3);assert.equal(r.totals.tonnage,1440);assert.ok(r.rows.slice(1,-1).every(w=>w.workouts===0&&w.tonnage===0));
 assert.equal(activationPeriods(d,PLAN_ID).length,2);const es=d.entries.filter(e=>e.exerciseId==='PUSH-A-1'),timeline=exerciseTimeline(d,es);
 assert.equal(timeline[0].x,0);assert.ok(timeline[1].x<0.01);assert.equal(timeline[2].x,1);assert.equal(timeline[1].split,false);assert.equal(timeline[2].split,true);assert.deepEqual(d,old);
 // An actual switch also separates nearby periods, with no empty ISO week.
 d.sessions.at(-1).date='2026-01-08';const last=d.trainingJournal.sessionSnapshots.find(s=>s.sessionId===es.at(-1).sessionId);last.startedAt='2026-07-06T10:00:00.000Z';assert.equal(exerciseTimeline(d,es)[2].split,true);
});
