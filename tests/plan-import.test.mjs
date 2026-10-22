import test from 'node:test';
import assert from 'node:assert/strict';
import {runInNewContext} from 'node:vm';
import {readFileSync} from 'node:fs';
import {parsePlan,stagePlan,previewPlan,stageActivation} from '../model/plan-import.mjs';
import {startSession,exercisesFor,recordEntry,advance,nextType} from '../model/journal.mjs';
import {newPerformance,flatten} from '../model/performance.mjs';
import {createLegacyModel,parseModelBackup} from '../model/legacy-model.mjs';
import {exportBackup} from '../model/backup.mjs';
const fixture=()=>JSON.parse(readFileSync(new URL('fixtures/plan-v3.json',import.meta.url)));
const legacy=()=>JSON.parse(readFileSync(new URL('fixtures/v1.json',import.meta.url)));
export function v4(p){const x=JSON.parse(JSON.stringify(p).replaceAll('synthetic-v3','synthetic-v4').replaceAll('v3-position','v4-position').replaceAll('v3-group','v4-group').replaceAll('v3-global','v4-global'));x.planVersion.number=4;x.planVersion.label='TEST V4';x.continuity=x.positions.map((pos,i)=>({...p.continuity[i],positionId:pos.id,relation:'same-variant',previousExerciseId:pos.exerciseId,previousVariantId:pos.variantId,previousPositionId:p.positions[i].id,reason:'Only prescription changes'}));x.sets[0].reps={min:4,max:6};return x;}

test('data-only preview, inactive storage, independent A/B/C, manual future-only activation',async()=>{
 const data=legacy(),before=structuredClone(data),p=fixture();
 const diff=previewPlan(data,parsePlan(JSON.stringify(p)));assert.equal(diff.added.length,6);assert.ok(diff.unresolved.some(x=>x.includes('Test bez celów')));assert.deepEqual(data,before);
 const imported=stagePlan(data,p,'owner');assert.equal(imported.trainingJournal.activePlanVersionId,undefined);assert.deepEqual(imported.sessions,data.sessions);assert.deepEqual(imported.entries,data.entries);
 const active=stageActivation(imported,p.planVersion.id,'2026-10-22T12:01:00.000Z');assert.equal(nextType(active),'TEST-A');
 const oldSnapshots=structuredClone(active.trainingJournal.sessionSnapshots),s={id:'test-new',seq:99,date:'2026-10-22',status:'active',type:'TEST-A'};active.sessions.push(s);active.activeId=s.id;await startSession(active,s,'2026-10-22T12:02:00.000Z');
 const views=exercisesFor(active,s);assert.deepEqual(views.map(v=>v.displayNumber),['1A','1B','1C']);assert.ok(views.every(v=>!v.members));
 const q=v4(p),withV4=stageActivation(stagePlan(active,q),q.planVersion.id,'2026-10-22T12:03:00.000Z');
 assert.deepEqual(withV4.trainingJournal.sessionSnapshots,active.trainingJournal.sessionSnapshots);assert.deepEqual(exercisesFor(withV4,s),views);assert.deepEqual(oldSnapshots,[]);
 advance(withV4,s);assert.equal(nextType(withV4),'TEST-A'); // finishing old version cannot move new rotation
 assert.deepEqual(withV4.entries,data.entries);assert.deepEqual(withV4.exercises['PUSH A'],data.exercises['PUSH A']);
});

test('structured new units, backoff, drops, sides, unknown targets and complete v3 restore',async()=>{
 let data=stageActivation(stagePlan(legacy(),fixture(),'owner'),'synthetic-v3','2026-10-22T12:00:00.000Z');
 const s={id:'new-session',seq:99,type:'TEST-B',date:'2026-10-22',status:'active'};data.sessions.forEach(x=>x.status='done');data.sessions.push(s);data.activeId=s.id;await startSession(data,s,'2026-10-22T12:01:00.000Z');
 const views=exercisesFor(data,s);assert.equal(views[2].targets.length,0);
 for(const ex of views){const performance=newPerformance(ex);for(const row of performance.rows)for(const seg of row.segments){seg.kg='12';seg.reps='9';}const series=flatten(performance),e={id:'entry-'+ex.id,sessionId:s.id,exerciseId:ex.id,kg:series[0].kg,reps:series[0].reps,series,performance};recordEntry(data,e);data.entries.push(e);}
 assert.equal(data.entries.at(-2).performance.rows.length,4);assert.ok(data.entries.at(-3).performance.rows[0].segments.length>=2);
 const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto:globalThis.crypto});
 const {catalog}=db.parseBackup(data);
 const doc=await createLegacyModel(JSON.stringify({format:'pushpull-backup',version:2,data,catalog,archives:[]}),{ownerId:'owner',createdAt:'2026-10-22T12:03:00.000Z'});
 const restored=await parseModelBackup(await exportBackup(doc));assert.deepEqual(restored.data,data);
});

test('invalid plans, unsupported protocols and ID collisions leave source intact',()=>{
 const data=legacy(),before=structuredClone(data),valid=fixture();
 for(const mutate of [p=>p.version=2,p=>p.sets[0].reps={min:10,max:2},p=>p.positions[0].sideMode='magic',p=>p.groups[0].kind='circuit',p=>p.groups[0].rounds=3,p=>p.groups[0].positionIds.reverse(),p=>p.drops[0].segments=[],p=>p.positions[0].loadConvention.unit='lb',p=>p.continuity.pop(),p=>p.userNotes=[],p=>p.positions[0].exerciseId='PUSH-A-1',p=>p.sets[0].unknownProtocol=true,p=>p.sets[0].positionId='missing']){const bad=structuredClone(valid);mutate(bad);assert.throws(()=>stagePlan(data,bad));assert.deepEqual(data,before);}
 assert.throws(()=>parsePlan('{"format":1,"format":2}'),/duplicate/);
 const imported=stagePlan(data,valid);assert.throws(()=>stagePlan(imported,valid),/już zapisana/);
 const collision=v4(valid);collision.variants[0].machine='Different machine under old ID';assert.throws(()=>stagePlan(imported,collision),/kolizja/);
 const changed=v4(valid);changed.continuity[0].relation='new';assert.throws(()=>stagePlan(imported,changed),/ciągłości/);
 assert.equal(previewPlan(stageActivation(imported,valid.planVersion.id,'2026-10-22T12:00:00.000Z'),v4(valid)).changed.length,1);
});

test('identity continuity distinguishes new variants and replacements without moving legacy records',async()=>{
 const original=legacy(),p=fixture(),data=stageActivation(stagePlan(original,p,'owner'),p.planVersion.id,'2026-10-22T12:00:00.000Z'),q=v4(p);
 const old=structuredClone(data),pos=q.positions[0],c=q.continuity[0];
 pos.variantId='test-new-machine';q.variants[0].id=pos.variantId;q.variants[0].machine='Synthetic new machine';c.relation='new-variant';
 const replacement=q.positions[1],r=q.continuity[1],newId='TEST-REPLACEMENT';
 replacement.exerciseId=newId;replacement.variantId='test-replacement-variant';q.exercises[1].id=newId;q.variants[1].id=replacement.variantId;q.variants[1].exerciseId=newId;r.relation='replacement';
 const next=stageActivation(stagePlan(data,q),q.planVersion.id,'2026-10-22T12:01:00.000Z');assert.deepEqual(data,old);
 assert.deepEqual(next.entries,original.entries);assert.deepEqual(next.sessions,original.sessions);
 const s={id:'future',type:'TEST-A'};await startSession(next,s,'2026-10-22T12:02:00.000Z');
 const ex=exercisesFor(next,s);assert.equal(ex[0].id,'TEST-1');assert.notEqual(ex[0].journalVariantId,p.positions[0].variantId);assert.equal(ex[1].id,newId);
 assert.ok(previewPlan(data,q).added.includes(q.positions[1].label));
 const moved=v4(p);moved.positions[3].unitId='TEST-A';moved.positions[3].order=3;
 const movedData=stageActivation(stagePlan(data,moved),moved.planVersion.id,'2026-10-22T12:03:00.000Z');
 const ms={id:'moved',seq:99,type:'TEST-A',date:'2026-10-22',status:'active'};movedData.sessions.forEach(s=>s.status='done');movedData.sessions.push(ms);movedData.activeId=ms.id;await startSession(movedData,ms,'2026-10-22T12:04:00.000Z');
 const view=exercisesFor(movedData,ms).find(e=>e.id==='TEST-4'),performance=newPerformance(view);for(const row of performance.rows)for(const seg of row.segments){seg.kg='1';seg.reps='1';}
 const series=flatten(performance),entry={id:'moved-entry',sessionId:ms.id,exerciseId:view.id,performance,series,kg:'1',reps:'1'};recordEntry(movedData,entry);movedData.entries.push(entry);
 const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto:globalThis.crypto});
 const {catalog}=db.parseBackup(movedData);const full={format:'pushpull-backup',version:2,data:movedData,catalog,archives:[]};
 const restored=await parseModelBackup(await exportBackup(await createLegacyModel(JSON.stringify(full),{ownerId:'owner',createdAt:'2026-10-22T12:05:00.000Z'})));assert.deepEqual(restored.data,movedData);
});
