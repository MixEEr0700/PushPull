import test from 'node:test';
import {readFileSync} from 'node:fs';
import {stagePlan,stageActivation} from '../model/plan-import.mjs';
import assert from 'node:assert/strict';
import {initialize,startSession,recordEntry} from '../model/journal.mjs';
import {activate,views,PLAN_ID} from '../model/v2-plan.mjs';
import {newPerformance,flatten,resultChangeAge as age,resultChangeLabel as label} from '../model/performance.mjs';

function fixture(){
 const d={exercises:Object.fromEntries(['PUSH A','PULL A','PUSH B','PULL B'].map(t=>[t,[]])),sessions:[],entries:[],activeId:null,trainingJournal:initialize('change-test')};
 activate(d,'2026-10-01T10:00:00.000Z');return d;
}
async function save(d,id='PULL-B-1',edit=()=>{},status='done'){
 const j=d.trainingJournal,p=j.model.positions.find(p=>p.exerciseId===id),seq=d.sessions.length+1;
 const s={id:crypto.randomUUID(),type:p.unitId,seq,date:`2026-10-${String(seq).padStart(2,'0')}`,status};d.sessions.push(s);
 await startSession(d,s,s.date+'T10:00:00.000Z');
 const ex=views(j.model,j.activePlanVersionId,p.unitId,d).find(e=>e.id===id),performance=newPerformance(ex);
 for(const r of performance.rows)for(const seg of r.segments){seg.kg='105';seg.reps='15';}
 edit(performance);
 const series=flatten(performance),e={id:crypto.randomUUID(),sessionId:s.id,exerciseId:id,performance,series,kg:series[0].kg,reps:series[0].reps};
 recordEntry(d,e);d.entries.push(e);return e;
}
const all=(p,kg,reps)=>p.rows.forEach(r=>r.segments.forEach(s=>{s.kg=kg;s.reps=reps;}));
function refresh(e){e.series=flatten(e.performance);e.kg=e.series[0].kg;e.reps=e.series[0].reps;}
const snap=(d,e)=>d.trainingJournal.sessionSnapshots.find(s=>s.sessionId===e.sessionId);

test('equal completed runs count only actual comparable exercise performances; decreases and increases both reset',async()=>{
 const d=fixture();await save(d);await save(d);const last=await save(d);
 await save(d,'PULL-B-2');d.sessions.push({id:'no-result',type:'PULL B',date:'2026-10-05',seq:5,status:'done'});
 const ongoing=await save(d,'PULL-B-1',p=>all(p,'1','1'),'active');d.activeId=ongoing.sessionId;
 d.changes={'PULL-B-1':[{kind:'Poprawa techniki',date:'2026-10-03'}]};
 assert.equal(age(d,last),3);assert.equal(age(d,ongoing),3);
 d.sessions.find(s=>s.id===ongoing.sessionId).status='done';assert.equal(age(d,ongoing),1);
 const lower=await save(d,'PULL-B-1',p=>all(p,'95','12'));assert.equal(age(d,lower),1);
 const higher=await save(d,'PULL-B-1',p=>all(p,'95','13'));assert.equal(age(d,higher),1);
 assert.equal(age(d,await save(d,'PULL-B-1',p=>all(p,'95.0','13'))),2);
 assert.equal(label(1),'Ostatnia zmiana: 1 sesję temu');assert.equal(label(3),'Ostatnia zmiana: 3 sesje temu');assert.equal(label(12),'Ostatnia zmiana: 12 sesji temu');assert.match(label(null),/nieustalona/);
});

test('UUIDs and decimal formatting ignored; prescribed order and L/P values preserved; renderer is pure',async()=>{
 const d=fixture(),first=await save(d),second=await save(d,'PULL-B-1',p=>all(p,'0105.000','15'));
 const model=snap(d,second).model,ids=new Map(model.sets.map(t=>[t.id,crypto.randomUUID()]));
 for(const t of model.sets){t.id=ids.get(t.id);if(t.backoffFromSetId)t.backoffFromSetId=ids.get(t.backoffFromSetId);}
 for(const x of model.drops)x.setId=ids.get(x.setId);
 for(const r of second.performance.rows)r.setId=ids.get(r.setId);
 second.performance.rows.reverse();refresh(second);assert.equal(age(d,second),2);
 const before=structuredClone(d);age(d,second);assert.deepEqual(d,before);
 second.performance.rows.find(r=>r.side==='right').segments[0].reps='14';refresh(second);assert.equal(age(d,second),1);
 assert.equal(age(d,first),1); // Recomputed from current chronology, not the anchor's timestamp.
});

test('drops, back-off, set count and group rounds are compared as structure, never as total/best weight',async()=>{
 for(const id of ['PUSH-A-5','PUSH-A-3','PULL-B-6-SKI']){
  const d=fixture();await save(d,id);const last=await save(d,id);assert.equal(age(d,last),2);
  last.performance.rows.at(-1).segments.at(-1).reps='14';refresh(last);assert.equal(age(d,last),1);
 }
 const d=fixture();await save(d,'PUSH-A-5');const drop=await save(d,'PUSH-A-5',p=>p.rows[0].segments.push({id:crypto.randomUUID(),kg:'5',reps:'4'}));assert.equal(age(d,drop),1);
 const b=fixture();await save(b,'PUSH-A-3');const backoff=await save(b,'PUSH-A-3');const target=snap(b,backoff).model.sets.find(t=>t.id===backoff.performance.rows.at(-1).setId);target.role='main';target.backoffFromSetId=null;assert.equal(age(b,backoff),1);
 const c=fixture();await save(c);const fewer=await save(c,'PULL-B-1',p=>p.rows.splice(4,2));assert.equal(age(c,fewer),1);
});

test('other variants, machine definitions and kg meanings are excluded; unknown context is neutral',async()=>{
 const d=fixture();await save(d);const other=await save(d),m=snap(d,other).model;
 m.variants.find(v=>v.id===other.journalVariantId).machine='another machine';
 const basis=await save(d);basis.performance.loadConvention.basis='combined';snap(d,basis).model.positions.find(p=>p.id===basis.journalPositionId).loadConvention.basis='combined';
 const different=await save(d),sm=snap(d,different).model;const v=sm.variants.find(v=>v.id===different.journalVariantId);v.id='different-variant';sm.positions.find(p=>p.id===different.journalPositionId).variantId=v.id;different.journalVariantId=v.id;
 const last=await save(d);assert.equal(age(d,last),2);
 const unknown=await save(d);delete unknown.journalSnapshotId;assert.equal(age(d,unknown),null);assert.equal(age(d,last),null);
 assert.equal(age(d,{exerciseId:'legacy',kg:'105',reps:'15'}),null);assert.equal(age(d,null),null);
});

test('date/seq corrections recompute chronological runs; ambiguous duplicates never inflate them',async()=>{
 const d=fixture(),a=await save(d),b=await save(d,'PULL-B-1',p=>all(p,'95','12')),c=await save(d,'PULL-B-1',p=>all(p,'95','12'));
 assert.equal(age(d,c),2);
 d.sessions.find(s=>s.id===a.sessionId).date='2026-10-04';assert.equal(age(d,a),1);
 d.sessions.find(s=>s.id===a.sessionId).date='2026-10-02';d.sessions.find(s=>s.id===c.sessionId).date='2026-10-02';assert.equal(age(d,c),2);
 d.entries.push(structuredClone(c));assert.equal(age(d,c),null);
});


test('imported V3+ keeps comparisons across compatible snapshots and ignores new plan/set/group UUIDs',async()=>{
 const p=JSON.parse(readFileSync(new URL('fixtures/plan-v3.json',import.meta.url)));
 let d=stageActivation(stagePlan(fixture(),p),'synthetic-v3','2026-10-01T10:00:00.000Z');
 await save(d,'TEST-1');const second=await save(d,'TEST-1');assert.equal(age(d,second),2);
 const q=JSON.parse(JSON.stringify(p).replaceAll('synthetic-v3','synthetic-v4').replaceAll('v3-position','v4-position').replaceAll('v3-group','v4-group').replaceAll('v3-global','v4-global'));
 q.planVersion.number=4;q.planVersion.label='TEST V4';
 q.continuity=q.positions.map((pos,i)=>({...p.continuity[i],positionId:pos.id,relation:'same-variant',previousExerciseId:pos.exerciseId,previousVariantId:pos.variantId,previousPositionId:p.positions[i].id}));
 d=stageActivation(stagePlan(d,q),'synthetic-v4','2026-10-02T10:00:00.000Z');
 const third=await save(d,'TEST-1');assert.equal(age(d,third),3);
});


test('extra L/P rows use a unique pair only; ambiguous extra pairs and unknown kg are neutral',async()=>{
 const d=fixture();
 const add=p=>{const pair=structuredClone(p.rows.slice(0,2));for(const r of pair){r.id=crypto.randomUUID();r.setId=null;for(const s of r.segments)s.id=crypto.randomUUID();}p.rows.push(...pair);};
 await save(d,'PULL-B-1',add);const b=await save(d,'PULL-B-1',add);b.performance.rows.reverse();refresh(b);assert.equal(age(d,b),2);
 const ambiguous=await save(d,'PULL-B-1',p=>{add(p);add(p);});assert.equal(age(d,ambiguous),null);
 const unknown=await save(d);unknown.performance.loadConvention.basis=null;snap(d,unknown).model.positions.find(p=>p.id===unknown.journalPositionId).loadConvention.basis=null;assert.equal(age(d,unknown),null);
});
