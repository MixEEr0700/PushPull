/** Native journal adapter: observed legacy snapshots and explicitly activated V2.
 * Existing flat results and opaque legacy metadata retain their original meaning.
 */
import {createModel,captureSessionSnapshot,validateModel,validateSessionSnapshot,createResultReference} from './training-model.mjs';
import {views,PLAN_ID,groupMemberNumber} from './v2-plan.mjs';
import {validatePerformance,flatten} from './performance.mjs';
import {canonical,requireThat as check} from './backup-json.mjs';
const source=(reference,recordedAt=null)=>({kind:'legacy',reference,recordedAt});
/** Additive source-plan revision, projected without changing any stored plan on load.
 * The opaque historical PULL-B-6 is retained; no kg/notes/technique are inferred.
 */
export function sourceExercises(data,type){
 const visible=data.exercises[type].filter(e=>!e.journalOnly);
 if(type!=='PULL B')return visible;
 return visible.flatMap((e,index)=>{
  if(e.id!=='PULL-B-6')return [{...e,displayNumber:index+1}];
  return [['SKI','Narciarz'],['SHRUGS','Szrugsy']].map(([id,name],index)=>({
   id:'PULL-B-6-'+id,name:groupMemberNumber('PULL-B-6',index)+' · '+name,
   displayNumber:groupMemberNumber(6,index),sets:2,target:'8–10',initialKg:'',
   tempo:'do uzupełnienia',rir:'do uzupełnienia',
   notes:data.exercises[type].find(x=>x.id==='PULL-B-6-'+id)?.notes??'',
   description:'Para A/B · szkielet źródłowy; parametry trenera dostępne po aktywacji V2',
   sourceGroupId:'PULL-B-6',journalOnly:true
  }));
 });
}
/** Called only after the user starts a new session; never edits an existing one.
 * The additive registry allows old backup validators to resolve the new IDs.
 */
export function prepareSourceSession(data,session){
 if(data.trainingJournal?.activePlanVersionId||session.type!=='PULL B')return;
 const exercises=sourceExercises(data,session.type);
 if(!exercises.some(e=>e.sourceGroupId==='PULL-B-6'))return;
 for(const ex of exercises)if(!data.exercises[session.type].some(e=>e.id===ex.id))data.exercises[session.type].push(structuredClone(ex));
 session.sourceExerciseIds=exercises.map(e=>e.id);
}
export function initialize(ownerId) {
  return {version:1,model:{schemaVersion:1,ownerId,exercises:[],variants:[],planVersions:[],positions:[],sets:[],drops:[],groups:[],coachInstructions:[],userNotes:[]},sessionSnapshots:[]};
}
export function structuredSnapshot(snap){return !!snap?.model.planVersions.some(v=>v.id===snap.planVersionId&&v.executionVersion===2);}
export function units(data,session=null){
 const snap=session&&snapshotFor(data,session.id),m=snap?.model??data.trainingJournal?.model,id=snap?.planVersionId??data.trainingJournal?.activePlanVersionId;
 return (m?.planVersions.find(v=>v.id===id)?.units??['PUSH A','PULL A','PUSH B','PULL B'].map((id,order)=>({id,name:id,order}))).slice().sort((a,b)=>a.order-b.order);
}
export function nextType(data){const list=units(data);return list.some(u=>u.id===data.trainingJournal?.nextUnitId)?data.trainingJournal.nextUnitId:list.some(u=>u.id===data.nextType)?data.nextType:list[0].id;}
export function unitLabel(data,session){return units(data,session).find(u=>u.id===session.type)?.name??session.type;}
export function advance(data,session){
 const list=units(data),snap=snapshotFor(data,session.id);
 if(data.trainingJournal?.activePlanVersionId){if(snap?.planVersionId!==data.trainingJournal.activePlanVersionId)return;data.trainingJournal.nextUnitId=list[(list.findIndex(u=>u.id===session.type)+1)%list.length].id;}
 const legacy=['PUSH A','PULL A','PUSH B','PULL B'];if(legacy.includes(session.type))data.nextType=legacy[(legacy.indexOf(session.type)+1)%legacy.length];
}
export function snapshotFor(data,sessionId) {return data.trainingJournal?.sessionSnapshots.find(s=>s.sessionId===sessionId)??null;}
export function exercisesFor(data,session) {
  const snap=snapshotFor(data,session?.id);
  if(!snap){
    const registry=data.exercises[session.type]||[],original=registry.filter(e=>!e.journalOnly);
    return session.sourceExerciseIds?session.sourceExerciseIds.map(id=>{
      const ex=registry.find(e=>e.id===id);return {...ex,displayNumber:ex.displayNumber??original.findIndex(e=>e.id===id)+1};
    }):original;
  }
  if(structuredSnapshot(snap))return views(snap.model,snap.planVersionId,session.type,data);
  return snap.model.positions.filter(p=>p.planVersionId===snap.planVersionId && p.unitId===snap.unitId).sort((a,b)=>a.order-b.order).map(p=>({
    ...structuredClone(p.legacyExercise),initialKg:'',journalVariantId:p.variantId,
    notes:Object.values(data.exercises).flat().find(e=>e.id===p.exerciseId)?.notes??''}));
}
export async function startSession(data,session,startedAt) {
  const j=data.trainingJournal;check(j?.version===1,'unsupported journal');
  check(!snapshotFor(data,session.id),'session already has a snapshot');
  if(j.activePlanVersionId){const snapshot=captureSessionSnapshot(j.model,{id:crypto.randomUUID(),sessionId:session.id,planVersionId:j.activePlanVersionId,unitId:session.type,startedAt});j.sessionSnapshots.push(structuredClone(snapshot));session.journalSnapshotId=snapshot.id;return;}
  const exercises=(session.sourceExerciseIds?sourceExercises(data,session.type):data.exercises[session.type].filter(e=>!e.journalOnly)).map(e=>{const x=structuredClone(e);delete x.notes;return x;});
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(exercises)))),b=>b.toString(16).padStart(2,'0')).join('');
  const versionId='observed:'+session.type+':'+hash,m=j.model;
  if(!m.planVersions.some(v=>v.id===versionId)) {
    m.planVersions.push({id:versionId,planId:'observed:'+session.type,number:null,label:'Bieżący plan aplikacji — niezweryfikowany',units:[{id:session.type,name:session.type,order:0}],source:source('observed-at-session-start',startedAt)});
    exercises.forEach((e,order)=>{
      if(!m.exercises.some(x=>x.id===e.id))m.exercises.push({id:e.id,name:e.name,status:'unresolved',legacyId:e.id,source:source(e.id)});
      const id=versionId+':'+e.id;
      m.variants.push({id,exerciseId:e.id,label:'Wariant źródłowy nieustalony',machine:null,grip:null,support:null,execution:null,laterality:null,source:source(e.id)});
      m.positions.push({id,planVersionId:versionId,unitId:session.type,order,label:e.name,exerciseId:e.id,variantId:id,legacyPositionId:e.id,replacesPositionId:null,
        setState:'specified',confirmation:'legacy-unknown',loadConvention:{unit:null,basis:null,description:null},source:source(e.id),legacyExercise:e});
      for(let i=0;i<e.sets;i++)m.sets.push({id:id+':'+i,positionId:id,order:i,role:null,reps:null,rir:null,tempo:null,side:null,backoffFromSetId:null,restSeconds:null,source:source(e.id)});
    });
  }
  const snapshot=captureSessionSnapshot(m,{id:crypto.randomUUID(),sessionId:session.id,planVersionId:versionId,unitId:session.type,startedAt});
  j.sessionSnapshots.push(structuredClone(snapshot));session.journalSnapshotId=snapshot.id;
}
/** Stable series IDs survive correction/removal/reordering; new rows get IDs once. */
export function recordEntry(data,entry) {
  const snap=snapshotFor(data,entry.sessionId);if(!snap)return;
  const p=snap.model.positions.find(p=>p.exerciseId===entry.exerciseId && p.planVersionId===snap.planVersionId && p.unitId===snap.unitId);
  check(p && Array.isArray(entry.series) && entry.series.length,'native result needs complete series');
  entry.journalSnapshotId=snap.id;entry.journalPositionId=p.id;entry.journalVariantId=p.variantId;
  if(structuredSnapshot(snap)&&entry.performance){entry.series=flatten(entry.performance);validatePerformance(entry.performance,snap,entry);return;}
  entry.series=entry.series.map((r,i)=>({...r,id:r.id??crypto.randomUUID(),setId:Object.hasOwn(r,'setId')?r.setId:(snap.model.sets.find(s=>s.positionId===p.id && s.order===i)?.id??null)}));
}
/** Project known native records into backup B, retaining all legacy source too. */
export function project(data,base) {
  const j=data.trainingJournal;if(!j)return base;
  check(j.version===1 && j.model?.ownerId===base.model.ownerId,'journal version/owner mismatch');
  validateModel(j.model);
  if(j.activePlanVersionId)check(j.model.planVersions.some(p=>p.id===j.activePlanVersionId),'active plan missing');
  check(Array.isArray(j.sessionSnapshots),'missing session snapshots');
  const snaps=new Map();
  for(const snap of j.sessionSnapshots) {
    validateSessionSnapshot(snap);check(!snaps.has(snap.sessionId),'duplicate session snapshot');snaps.set(snap.sessionId,snap);
    check(data.sessions.some(s=>s.id===snap.sessionId && s.journalSnapshotId===snap.id),'orphan snapshot');
  }
  const model=createModel({...j.model,exercises:[...base.model.exercises,...j.model.exercises.filter(e=>!base.model.exercises.some(b=>b.id===e.id))],userNotes:[...base.model.userNotes,...j.model.userNotes]});
  const sessionRecords=base.sessionRecords.map(r=>{
    const snap=snaps.get(r.id);check(!r.data.journalSnapshotId || snap?.id===r.data.journalSnapshotId,'session snapshot missing');
    return snap?{...r,snapshotId:snap.id}:r;
  });
  const resultRecords=[],resultReferences=[];
  for(const r of base.resultRecords) {
    const e=r.data,snap=snaps.get(e.sessionId);
    if(!snap){check(!e.journalSnapshotId,'result snapshot missing');resultRecords.push(r);continue;}
    check(e.journalSnapshotId===snap.id && Array.isArray(e.series) && e.series.length,'native result lost its series');
    const metadata={...e};delete metadata.series;if(structuredSnapshot(snap))delete metadata.performance;
    check(!structuredSnapshot(snap)||e.performance,'V2 result requires structured performance');
    if(structuredSnapshot(snap)&&e.performance){const refs=validatePerformance(e.performance,snap,e);resultReferences.push(...refs);e.performance.rows.forEach((row,order)=>resultRecords.push({id:row.id,sessionId:e.sessionId,binding:'snapshot',payloadVersion:2,data:{...row,order,loadConvention:e.performance.loadConvention,entryId:e.id,entryMetadata:metadata}}));continue;}
    e.series.forEach((row,order)=>{
      check(!Object.hasOwn(row,'segments') && !Object.hasOwn(row,'side') && !Object.hasOwn(row,'groupId'),'unsupported performance structure');
      check(typeof row.id==='string' && Object.hasOwn(row,'setId'),'series identity missing');
      const reference=createResultReference(snap,{resultId:row.id,positionId:e.journalPositionId,setId:row.setId,side:null,groupId:null,round:null});
      check(reference.exerciseId===e.exerciseId && reference.variantId===e.journalVariantId,'native variant mismatch');
      resultReferences.push(reference);resultRecords.push({id:row.id,sessionId:e.sessionId,binding:'snapshot',payloadVersion:1,data:{...row,order,entryId:e.id,entryMetadata:metadata}});
    });
  }
  return {...base,model,sessionSnapshots:structuredClone(j.sessionSnapshots),sessionRecords,resultRecords,resultReferences};
}
/** Preview only a context whose actual source parameters still match. */
export function previewExercises(data,type) {
  if(data.trainingJournal?.activePlanVersionId)return views(data.trainingJournal.model,data.trainingJournal.activePlanVersionId,type,data);
  const projected=sourceExercises(data,type);
  const current=projected.map(e=>{const x={...e};delete x.notes;return x;});
  const match=data.trainingJournal?.sessionSnapshots.slice().reverse().find(s=>s.unitId===type &&
    canonical(s.model.positions.filter(p=>p.planVersionId===s.planVersionId && p.unitId===s.unitId).sort((a,b)=>a.order-b.order).map(p=>p.legacyExercise))===canonical(current));
  return match?exercisesFor(data,{id:match.sessionId,type}):projected.map(e=>({...e,initialKg:'',journalVariantId:'unrecorded-context'}));
}
