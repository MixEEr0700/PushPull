/** Minimal bridge to the existing journal, not a new plan or result editor. */
import {createModel} from './training-model.mjs';
import {createBackup,validateBackup,exportBackup,readLegacyBackup} from './backup.mjs';
import {canonical,portable,requireThat as check} from './backup-json.mjs';
export const MODEL_KEY='training-model-v1';
const source=id=>({kind:'legacy',reference:id,recordedAt:null});
function payload(raw,ownerId) {
  const legacy=readLegacyBackup(raw);
  check(legacy.formatVersion===2,'migration requires the complete v2 backup');
  const data=legacy.data,exercises=Object.values(data.exercises).flat();
  return {
    model:createModel({schemaVersion:1,ownerId,
      exercises:exercises.map(e=>({id:e.id,name:e.name,status:'unresolved',legacyId:e.id,source:source(e.id)})),
      // Legacy names/targets do not identify historical machines or prescriptions.
      variants:[],planVersions:[],positions:[],sets:[],drops:[],groups:[],coachInstructions:[],
      userNotes:exercises.map(e=>({id:e.id,exerciseId:e.id,sessionId:null,text:e.notes,origin:'legacy-shared',revision:1,source:source(e.id)}))}),
    sessionSnapshots:[],resultReferences:[],
    sessionRecords:data.sessions.map(s=>({id:s.id,snapshotId:null,payloadVersion:1,data:s,
      legacyPlanLink:legacy.catalog.sessionVersions[s.id]})),
    resultRecords:data.entries.map(e=>({id:e.id,sessionId:e.sessionId,binding:'uninterpreted',payloadVersion:1,data:e})),
    legacySources:[{id:'current-legacy',formatVersion:2,semantics:'legacy-unknown',raw}]
  };
}
/** Retain every legacy record/extension, with no inferred plan, role, side or kg. */
export async function createLegacyModel(raw,{ownerId,createdAt}) {
  return createBackup(payload(raw,ownerId),{createdAt,metadata:{bridgeVersion:1}});
}
/** Full validation plus equality to the committed source, not merely its counts. */
export async function verifyLegacyModel(state,{data,catalog},revision) {
  check(state?.key===MODEL_KEY && state.revision===revision,'model/source revision mismatch; use the current application');
  const document=await validateBackup(state.document);
  check(document.metadata.bridgeVersion===1,'unsupported model bridge');
  const raw=document.payload.legacySources[0]?.raw,legacy=readLegacyBackup(raw);
  check(canonical({data:legacy.data,catalog:legacy.catalog})===canonical({data,catalog}),'model differs from committed history');
  check(canonical(document.payload)===canonical(payload(raw,document.payload.model?.ownerId)),'incomplete or unsupported legacy bridge model');
  return document;
}
export {exportBackup,readLegacyBackup,portable};
