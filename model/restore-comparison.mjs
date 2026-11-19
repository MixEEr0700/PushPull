/** Compare verified backup contents without using timestamps as a proxy for lineage. */
import {equalJSON} from './journal-protocol.mjs';

const equal=(a,b)=>equalJSON(a,b,{ordered:false});
const byId=rows=>new Map((rows??[]).map(row=>[row.id,row]));
const fields=(values={})=>new Map(Object.entries(values));
function without(value,keys){return Object.fromEntries(Object.entries(value??{}).filter(([key])=>!keys.includes(key)));}
function difference(before,after){
 const result={localOnly:0,copyOnly:0,changed:0};
 for(const [key,value] of before){
  if(!after.has(key))result.localOnly++;
  else if(!equal(value,after.get(key)))result.changed++;
 }
 for(const key of after.keys())if(!before.has(key))result.copyOnly++;
 return result;
}

function compareSource(before,after){
 const a=before.data,b=after.data,j=a.trainingJournal,k=b.trainingJournal;
 const catalog=(source,key)=>byId(source.catalog[key]);
 return {
  sessions:difference(byId(a.sessions),byId(b.sessions)),
  results:difference(byId(a.entries),byId(b.entries)),
  snapshots:difference(byId(j?.sessionSnapshots),byId(k?.sessionSnapshots)),
  sessionVersions:difference(fields(before.catalog.sessionVersions),fields(after.catalog.sessionVersions)),
  plans:difference(catalog(before,'plans'),catalog(after,'plans')),
  planVersions:difference(catalog(before,'planVersions'),catalog(after,'planVersions')),
  currentExercises:difference(fields(a.exercises),fields(b.exercises)),
  planModel:difference(fields(without(j?.model,['userNotes'])),fields(without(k?.model,['userNotes']))),
  notes:difference(byId(j?.model?.userNotes),byId(k?.model?.userNotes)),
  technique:difference(fields(a.changes),fields(b.changes)),
  journal:difference(fields(without(j,['model','sessionSnapshots','nextUnitId'])),fields(without(k,['model','sessionSnapshots','nextUnitId']))),
  other:difference(fields(without(a,['sessions','entries','trainingJournal','exercises','changes','activeId','nextType'])),fields(without(b,['sessions','entries','trainingJournal','exercises','changes','activeId','nextType'])))
 };
}

export function compareCanonicalRestore(before,after,starter){
 const clean=!!starter&&!before.drafts.length&&!before.buffers.length&&!Object.keys(before.preferences).length&&equal(before.source.data,starter.data)&&equal(before.source.catalog,starter.catalog);
 const sections={
  ...compareSource(before.source,after.source),
  drafts:difference(new Map(before.drafts.map(d=>[d.key,d.value])),new Map(after.drafts.map(d=>[d.key,d.value]))),
  buffers:difference(new Map(before.buffers.map(d=>[d.key,d.raw])),new Map(after.buffers.map(d=>[d.key,d.raw]))),
  preferences:difference(fields(before.preferences),fields(after.preferences)),
  // An empty OAuth client is a default, not a user configuration to lose.
  drive:difference(fields(before.drive.clientId?before.drive:{}),fields(after.drive.clientId?after.drive:{}))
 };
 const sameContent=Object.values(sections).every(d=>!d.localOnly&&!d.copyOnly&&!d.changed)&&equal(before,after);
 const risky=Object.entries(sections).some(([key,delta])=>(!clean||key==='drive')&&(delta.localOnly>0||delta.changed>0));
 return {sections,risky,sameContent};
}
