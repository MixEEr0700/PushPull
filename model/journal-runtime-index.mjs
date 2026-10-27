/** Stage E. Derived, versioned indices. Never imported from a backup as authority. */
import {canonical,freeze,requireThat as check} from './backup-json.mjs';
import {buildIndex,auditIndex,hashJSON,verifyNode,checkAbort} from './journal-index.mjs';
import {objectRecord,readObject} from './journal-protocol.mjs';
import {projectEntry,sourceExercises} from './journal.mjs';
import {comparison} from './performance.mjs';
export const runtimeKey=(...parts)=>JSON.stringify(parts);
export function resultIds(data,entry){
 if(!data.trainingJournal)return [entry.id];
 const snapshot=data.trainingJournal.sessionSnapshots.find(s=>s.sessionId===entry.sessionId);
 return projectEntry({id:entry.id,sessionId:entry.sessionId,binding:'uninterpreted',payloadVersion:1,data:entry},snapshot).resultRecords.map(r=>r.id);
}
export const sessionHeader=s=>({id:s.id,date:s.date,seq:s.seq,status:s.status});
export function descriptor(data,entry){
 const session=data.sessions.find(s=>s.id===entry.sessionId),snapshot=data.trainingJournal?.sessionSnapshots.find(s=>s.sessionId===entry.sessionId);
 check(session,'context session');
 return {id:entry.id,exerciseId:entry.exerciseId,variant:entry.journalVariantId??null,session:sessionHeader(session),snapshotId:snapshot?.id??null,
  selector:[entry.journalVariantId??null,snapshot?.planVersionId??null,entry.performance?.loadConvention?.unit??null,entry.performance?.loadConvention?.basis??null],measurement:comparison(data,entry)};
}
const order=(a,b)=>b.session.date.localeCompare(a.session.date)||b.session.seq-a.session.seq;
export function contextSummary(history){
 const sorted=history.slice().sort(order),heads=[],selectors=new Set(),ages=[];
 for(const d of sorted){const key=canonical(d.selector);if(!selectors.has(key)){selectors.add(key);heads.push({id:d.id,sessionId:d.session.id,snapshotId:d.snapshotId,selector:d.selector});}}
 const measurements=new Map(sorted.filter(d=>d.measurement).map(d=>[d.measurement.context,d]));
 for(const [context,basis] of measurements){
  const candidates=sorted.filter(d=>d.variant===basis.variant&&d.session.status==='done');
  let age=0,latest=null,invalid=candidates.some(d=>!/^\d{4}-\d{2}-\d{2}$/.test(d.session.date)||!Number.isFinite(d.session.seq));const seen=new Set();
  if(!invalid)for(const d of candidates){
   if(!d.measurement){invalid=true;break}if(d.measurement.context!==context)continue;
   if(seen.has(d.session.id)){invalid=true;break}seen.add(d.session.id);
   if(latest!==null&&latest!==d.measurement.value)break;latest=d.measurement.value;age++;
  }
  ages.push([context,invalid?null:age||null]);
 }
 return {heads,ages};
}
export function runtimeInfo(data){
 const previews=[];
 if(data.trainingJournal&&!data.trainingJournal.activePlanVersionId)for(const type of Object.keys(data.exercises)){
  const current=canonical(sourceExercises(data,type).map(e=>{const v={...e};delete v.notes;return v}));
  const snap=data.trainingJournal.sessionSnapshots.slice().reverse().find(s=>s.unitId===type&&canonical(s.model.positions.filter(p=>p.planVersionId===s.planVersionId&&p.unitId===s.unitId).sort((a,b)=>a.order-b.order).map(p=>p.legacyExercise))===current);
  if(snap)previews.push(snap.id);
 }
 return {maxSeq:Math.max(0,...data.sessions.map(s=>s.seq)),lastDone:data.sessions.filter(s=>s.status==='done').sort((a,b)=>b.seq-a.seq)[0]?.id??null,previews};
}
/** Full independent derivation, only from a previously validated source. */
export function deriveRuntime(source){
 const d=source.data,values=new Map(),histories=new Map(),sessions=new Map(d.sessions.map(s=>[s.id,[]]));
 for(const e of d.entries){
  const ds=descriptor(d,e);if(!histories.has(e.exerciseId))histories.set(e.exerciseId,[]);histories.get(e.exerciseId).push(ds);
  values.set(runtimeKey('pair',e.sessionId,e.exerciseId),e.id);sessions.get(e.sessionId).push(e.id);
  for(const id of resultIds(d,e)){check(!values.has(runtimeKey('global',id)),'duplicate global result ID');values.set(runtimeKey('global',id),e.id);}
 }
 for(const [id,entries] of sessions)values.set(runtimeKey('session',id),entries);
 for(const [id,history] of histories){values.set(runtimeKey('history',id),history);values.set(runtimeKey('context',id),contextSummary(history));}
 values.set(runtimeKey('info'),runtimeInfo(d));return values;
}
export async function buildRuntime(source,{signal,sourceRoot}={}){
 const values=deriveRuntime(source),objects=new Map(),leaves=[];
 for(const [key,value] of values){checkAbort(signal);const row=await objectRecord(value);objects.set(row.id,row);leaves.push([key,row.id]);}
 const tree=await buildIndex(leaves,{signal});return {runtime:{version:1,indexRoot:tree.root,sourceRoot},objects:[...objects.values()],nodes:[...tree.nodes.values()]};
}
export async function auditRuntime(state,maps,source,{signal}={}){
 if(!state.runtime)return;
 const leaves=[];for(const [key,value] of deriveRuntime(source)){
  const row=await objectRecord(value);check(maps.journalObjects.get(row.id)?.json===row.json,'runtime semantic mismatch');leaves.push([key,row.id]);
 }
 await auditIndex(state.runtime.indexRoot,id=>maps.journalIndex.get(id),leaves,{signal});
}
/** Membership and absence proofs. Every fetched node is detached and hashed. */
export async function lookupIndex(root,key,read,{signal}={}){
 let id=root,lower=null,upper=null;const seen=new Set();
 while(id){checkAbort(signal);check(!seen.has(id),'index cycle');seen.add(id);const n=await verifyNode(await read(id));
  check((lower===null||n.key>lower)&&(upper===null||n.key<upper),'index path order');
  if(n.key===key)return n.value;if(key<n.key){upper=n.key;id=n.left}else{lower=n.key;id=n.right}
 }return null;
}
