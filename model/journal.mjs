/** First functional slice: explicit opt-in, observed session plans and flat series.
 * This records the current app plan, never activates or interprets the V2 draft.
 */
import {createModel,captureSessionSnapshot,validateModel,validateSessionSnapshot,createResultReference} from './training-model.mjs';
import {canonical,requireThat as check} from './backup-json.mjs';
const source=(reference,recordedAt=null)=>({kind:'legacy',reference,recordedAt});
export function initialize(ownerId) {
  return {version:1,model:{schemaVersion:1,ownerId,exercises:[],variants:[],planVersions:[],positions:[],sets:[],drops:[],groups:[],coachInstructions:[],userNotes:[]},sessionSnapshots:[]};
}
export function snapshotFor(data,sessionId) {return data.trainingJournal?.sessionSnapshots.find(s=>s.sessionId===sessionId)??null;}
export function exercisesFor(data,session) {
  const snap=snapshotFor(data,session?.id);
  if(!snap)return data.exercises[session.type]||[];
  return snap.model.positions.filter(p=>p.planVersionId===snap.planVersionId && p.unitId===snap.unitId).sort((a,b)=>a.order-b.order).map(p=>({
    ...structuredClone(p.legacyExercise),initialKg:'',journalVariantId:p.variantId,
    notes:Object.values(data.exercises).flat().find(e=>e.id===p.exerciseId)?.notes??''}));
}
export async function startSession(data,session,startedAt) {
  const j=data.trainingJournal;check(j?.version===1,'unsupported journal');
  check(!snapshotFor(data,session.id),'session already has a snapshot');
  const exercises=data.exercises[session.type].map(e=>{const x=structuredClone(e);delete x.notes;return x;});
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
  entry.series=entry.series.map((r,i)=>({...r,id:r.id??crypto.randomUUID(),setId:Object.hasOwn(r,'setId')?r.setId:(snap.model.sets.find(s=>s.positionId===p.id && s.order===i)?.id??null)}));
}
/** Project known native records into backup B, retaining all legacy source too. */
export function project(data,base) {
  const j=data.trainingJournal;if(!j)return base;
  check(j.version===1 && j.model?.ownerId===base.model.ownerId,'journal version/owner mismatch');
  validateModel(j.model);
  check(j.model.drops.length===0 && j.model.groups.length===0 && j.model.sets.every(s=>s.role===null && s.side===null),'this journal version supports flat series only');
  check(Array.isArray(j.sessionSnapshots),'missing session snapshots');
  const snaps=new Map();
  for(const snap of j.sessionSnapshots) {
    validateSessionSnapshot(snap);check(!snaps.has(snap.sessionId),'duplicate session snapshot');snaps.set(snap.sessionId,snap);
    check(data.sessions.some(s=>s.id===snap.sessionId && s.journalSnapshotId===snap.id),'orphan snapshot');
  }
  const model=createModel({...j.model,exercises:[...base.model.exercises,...j.model.exercises.filter(e=>!base.model.exercises.some(b=>b.id===e.id))],userNotes:base.model.userNotes});
  const sessionRecords=base.sessionRecords.map(r=>{
    const snap=snaps.get(r.id);check(!r.data.journalSnapshotId || snap?.id===r.data.journalSnapshotId,'session snapshot missing');
    return snap?{...r,snapshotId:snap.id}:r;
  });
  const resultRecords=[],resultReferences=[];
  for(const r of base.resultRecords) {
    const e=r.data,snap=snaps.get(e.sessionId);
    if(!snap){check(!e.journalSnapshotId,'result snapshot missing');resultRecords.push(r);continue;}
    check(e.journalSnapshotId===snap.id && Array.isArray(e.series) && e.series.length,'native result lost its series');
    const metadata={...e};delete metadata.series;
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
  const current=data.exercises[type].map(e=>{const x={...e};delete x.notes;return x;});
  const match=data.trainingJournal?.sessionSnapshots.slice().reverse().find(s=>s.unitId===type &&
    canonical(s.model.positions.filter(p=>p.planVersionId===s.planVersionId && p.unitId===s.unitId).sort((a,b)=>a.order-b.order).map(p=>p.legacyExercise))===canonical(current));
  return match?exercisesFor(data,{id:match.sessionId,type}):data.exercises[type].map(e=>({...e,initialKg:'',journalVariantId:'unrecorded-context'}));
}
