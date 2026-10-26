/** Minimal bridge to the existing journal, not a new plan or result editor. */
import {project} from './journal.mjs';
import {storedPlanModel} from './plan-import.mjs';
import {createModel} from './training-model.mjs';
import {createBackup,validateBackup,exportBackup,readLegacyBackup} from './backup.mjs';
import {prepareLegacyBackup,legacySource} from './legacy-backup.mjs';
import {canonical,portable,freeze,requireThat as check} from './backup-json.mjs';
export const MODEL_KEY='training-model-v1';
const source=id=>({kind:'legacy',reference:id,recordedAt:null});
function payload(legacy,ownerId) {
  check(legacy.formatVersion===2,'migration requires the complete v2 backup');
  const data=legacy.data,exercises=Object.values(data.exercises).flat();
  return project(data,{
    model:createModel({schemaVersion:1,ownerId,
      exercises:exercises.map(e=>({id:e.id,name:e.name,status:'unresolved',legacyId:e.id,source:source(e.id)})),
      // Legacy names/targets do not identify historical machines or prescriptions.
      variants:[],planVersions:[],positions:[],sets:[],drops:[],groups:[],coachInstructions:[],
      userNotes:exercises.map(e=>({id:e.id,exerciseId:e.id,sessionId:null,text:e.notes,origin:'legacy-shared',revision:1,source:source(e.id)}))}),
    sessionSnapshots:[],resultReferences:[],
    sessionRecords:data.sessions.map(s=>({id:s.id,snapshotId:null,payloadVersion:1,data:s,
      legacyPlanLink:legacy.catalog.sessionVersions[s.id]})),
    resultRecords:data.entries.map(e=>({id:e.id,sessionId:e.sessionId,binding:'uninterpreted',payloadVersion:1,data:e})),
    legacySources:[legacySource(legacy,'current-legacy')]
  });
}
/** Retain every legacy record/extension, with no inferred plan, role, side or kg. */
export async function createLegacyModel(raw,{ownerId,createdAt}) {
  return createBackup(freeze(payload(readLegacyBackup(raw),ownerId)),{createdAt,metadata:{bridgeVersion:1}});
}
/** Same v3 bytes/validation, without reparsing a writer's own JSON string. */
export async function createLegacyModelFromSource(value,{ownerId,createdAt}) {
  return createBackup(freeze(payload(prepareLegacyBackup(value),ownerId)),{createdAt,metadata:{bridgeVersion:1}});
}
/** Synchronous compatibility view, only on explicit model inspection. Normal
 * result writes use a small ack and never request this complete projection. */
export function legacyPayload(value,ownerId){return freeze(payload(prepareLegacyBackup(value),ownerId));}
/** Full validation plus equality to the committed source, not merely its counts. */
export async function verifyLegacyModel(state,{data,catalog},revision) {
  check(state?.key===MODEL_KEY && state.revision===revision,'model/source revision mismatch; use the current application');
  const document=await validateBackup(state.document);
  check(document.metadata.bridgeVersion===1,'unsupported model bridge');
  const raw=document.payload.legacySources[0]?.raw,legacy=readLegacyBackup(raw);
  check(canonical({data:legacy.data,catalog:legacy.catalog})===canonical({data,catalog}),'model differs from committed history');
  check(canonical(document.payload)===canonical(payload(legacy,document.payload.model?.ownerId)),'incomplete or unsupported legacy bridge model');
  return document;
}
export {exportBackup,readLegacyBackup,portable,freeze};
/** Restore only this journal's lossless source-backed format; never flatten a
 * generic future v3 document into legacy data and silently discard its records. */
export async function parseModelBackup(raw) {
  const {previewBackup,restoreBackup}=await import('./backup.mjs');
  const restored=await restoreBackup(await previewBackup(raw)),d=restored.restored;
  check(restored.formatVersion===3 && d.payload.model,'expected source-backed v3');
  const original=d.payload.legacySources[0]?.raw,legacy=readLegacyBackup(original);
  const expected=await createLegacyModel(original,{ownerId:d.payload.model.ownerId,createdAt:d.createdAt});
  check(canonical(expected)===canonical(d),'unsupported backup contents; original file must be preserved');
  return {...legacy.original,document:d};
}

/** Small factual summaries; no preview-only/built-in plans or invented dates. */
export function backupSummary(data,{createdAt=null}={}){
 if(!data)return null;
 const j=data.trainingJournal,versions=new Map();
 for(const m of [j?.model,...(j?.sessionSnapshots??[]).map(s=>s.model)].filter(Boolean))for(const v of m.planVersions)if(v.executionVersion===2&&!versions.has(v.id))versions.set(v.id,v);
 for(const p of j?.importedPlans??[])if(p.planVersion?.executionVersion===2&&!versions.has(p.planVersion.id))versions.set(p.planVersion.id,p.planVersion);
 const plans=[...versions.values()].map(v=>({id:v.id,label:v.label,complete:!!storedPlanModel(data,v.id)}));
 const activePlanId=j?.activePlanVersionId??null;
 return {completePlans:plans.filter(p=>p.complete).length,createdAt:typeof createdAt==='string'&&Number.isFinite(Date.parse(createdAt))?createdAt:null,plans,activePlanId,
  activePlan:plans.find(p=>p.id===activePlanId)?.label??(activePlanId?'Nieustalona wersja · '+activePlanId:'Szkielet źródłowy'),
  sessions:data.sessions.length,completed:data.sessions.filter(s=>s.status==='done').length,ongoing:data.sessions.filter(s=>s.status==='active').length,results:data.entries.length,
  snapshots:j?.sessionSnapshots.length??0,activations:Array.isArray(j?.activations)?j.activations.length:0,
  latestSession:data.sessions.map(s=>s.date).sort().at(-1)??null};
}
export function compareBackupData(current,incoming){
 if(!current)return null;
 const records=(before,after)=>{const a=new Map(before.map(r=>[r.id,r])),b=new Map(after.map(r=>[r.id,r]));return {localOnly:before.filter(r=>!b.has(r.id)).length,copyOnly:after.filter(r=>!a.has(r.id)).length,changed:after.filter(r=>a.has(r.id)&&canonical(a.get(r.id))!==canonical(r)).length};};
 return {identical:canonical(current)===canonical(incoming),sessions:records(current.sessions,incoming.sessions),results:records(current.entries,incoming.entries)};
}
export async function inspectFullBackup(raw,current=null){
 const candidate=JSON.parse(raw),parsed=candidate?.version===3?await parseModelBackup(raw):readLegacyBackup(raw);
 const data=parsed.data;
 return {version:candidate.version,summary:backupSummary(data,{createdAt:parsed.document?.createdAt}),comparison:compareBackupData(current,data)};
}
// Reuse this already precached module for large preview verification off the UI
// thread. Storage and final import validation remain in the established importer.
if(typeof DedicatedWorkerGlobalScope!=='undefined'&&globalThis instanceof DedicatedWorkerGlobalScope){
 globalThis.onmessage=async({data})=>{try{globalThis.postMessage({preview:await inspectFullBackup(data.raw,data.current)});}catch(error){globalThis.postMessage({error:error.message});}};
}
