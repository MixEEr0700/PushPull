/** Experimental read-only entry point. No storage, network, import or restore API. */
import {readCompactModel} from './compact-backup-writer.mjs';
import {COMPACT_LIMITS} from './compact-backup-reader.mjs';
import {validateStructuredSource,backupSummary} from './legacy-model.mjs';
import {storedPlanModel} from './plan-import.mjs';
import {freeze,record} from './backup-json.mjs';
const messages=Object.freeze({
 'invalid-container':'Nieprawidłowy lub uszkodzony kontener PPC1.',
 'unsupported-model':'Nieobsługiwany lub niekompletny model kopii PPC1.',
 'invalid-model':'Niespójne dane treningowe, plany lub archiwa w kopii PPC1.',
 limit:'Przekroczono limit rozmiaru, czasu lub złożoności podglądu PPC1.',
 revision:'Bieżące dane zmieniły się. Otwórz podgląd ponownie.',
 'source-unavailable':'Nie można potwierdzić rewizji bieżących danych.'
});
export class CompactPreviewError extends Error{constructor(code){super(messages[code]);this.name='CompactPreviewError';this.code=code;}}
const check=(v,code)=>{if(!v)throw new CompactPreviewError(code);};
const cancelled=()=>new DOMException('Anulowano podgląd PPC1.','AbortError');
const token=v=>typeof v==='string'&&v.length>0&&v.length<=256||Number.isSafeInteger(v)&&v>=0;
async function revision(probe,signal){
 if(!probe)return null;
 try{
  const pending=probe();
  const v=signal?await new Promise((resolve,reject)=>{
   const stop=()=>{signal.removeEventListener('abort',stop);reject(cancelled());};
   signal.addEventListener('abort',stop,{once:true});if(signal.aborted)stop();
   Promise.resolve(pending).then(value=>{signal.removeEventListener('abort',stop);resolve(value);},error=>{signal.removeEventListener('abort',stop);reject(error);});
  }):await pending;
  check(token(v),'source-unavailable');return v;
 }catch(error){if(signal?.aborted)throw cancelled();throw new CompactPreviewError('source-unavailable');}
}
function supported(source){
 check(record(source)&&source.format==='pushpull-backup'&&source.version===2&&record(source.data)&&record(source.catalog)&&Array.isArray(source.archives),'unsupported-model');
 check(Object.keys(source).every(k=>['format','version','data','catalog','archives','settings','metadata'].includes(k)),'unsupported-model');
 for(const key of ['settings','metadata'])if(Object.hasOwn(source,key))check(record(source[key]),'unsupported-model');
 // Same reserved-key restriction as the production v1 data boundary, with DAG memoization.
 const seen=new WeakSet();function keys(v){if(v&&typeof v==='object'&&!seen.has(v)){seen.add(v);for(const k of Object.keys(v)){check(!['__proto__','prototype','constructor'].includes(k),'unsupported-model');keys(v[k]);}}}keys(source);
}
function validatePlans(data){
 const j=data.trainingJournal;if(j==null){check(!data.sessions.some(s=>s.journalSnapshotId!=null)&&!data.entries.some(e=>['journalSnapshotId','journalPositionId','journalVariantId','performance'].some(k=>e[k]!=null)),'invalid-model');return;}check(record(j),'invalid-model');
 const seen=new WeakSet();for(const model of [j.model,...j.sessionSnapshots.map(s=>s.model)])if(!seen.has(model)){seen.add(model);for(const v of model.planVersions)check(!Object.hasOwn(v,'executionVersion')||v.executionVersion===2,'unsupported-model');}
 if(j.importedPlans!==undefined){
  check(Array.isArray(j.importedPlans),'invalid-model');const ids=new Set();
  for(const packet of j.importedPlans){
   const id=packet?.planVersion?.id;check(typeof id==='string'&&!ids.has(id),'invalid-model');ids.add(id);
   // Remove fallback definitions of this version so a corrupt packet cannot be masked
   // by its already valid current/snapshot model. Existing resolver validates its shape.
   const model={...j.model,planVersions:j.model.planVersions.filter(v=>v.id!==id)};
   const probe={trainingJournal:{model,sessionSnapshots:[],importedPlans:[packet]}};
   check(storedPlanModel(probe,id),'invalid-model');
   check(packet.continuity.length===packet.positions.length&&new Set(packet.continuity.map(c=>c.positionId)).size===packet.positions.length,'invalid-model');
   for(const c of packet.continuity){
    check(packet.positions.some(p=>p.id===c.positionId)&&['new','same-variant','new-variant','replacement'].includes(c.relation),'invalid-model');
    const pos=packet.positions.find(p=>p.id===c.positionId);
    check(typeof c.reason==='string'&&c.reason.trim()&&c.source.kind==='owner'&&typeof c.source.reference==='string'&&c.source.reference.trim()&&(c.source.recordedAt===null||typeof c.source.recordedAt==='string'&&Number.isFinite(Date.parse(c.source.recordedAt))),'invalid-model');
    if(c.relation==='new')check([c.previousExerciseId,c.previousVariantId,c.previousPositionId].every(v=>v===null),'invalid-model');
    if(c.relation==='same-variant')check(c.previousExerciseId===pos.exerciseId&&c.previousVariantId===pos.variantId,'invalid-model');
    if(c.relation==='new-variant')check(c.previousExerciseId===pos.exerciseId&&c.previousVariantId!==pos.variantId,'invalid-model');
    if(c.relation==='replacement')check(c.previousExerciseId!==null&&c.previousExerciseId!==pos.exerciseId,'invalid-model');
    check(pos.replacesPositionId===null||pos.replacesPositionId===c.previousPositionId,'invalid-model');
    const previous=j.model.exercises.find(e=>e.id===c.previousExerciseId),variant=j.model.variants.find(v=>v.id===c.previousVariantId),position=j.model.positions.find(p=>p.id===c.previousPositionId);
    check(c.previousExerciseId===null||previous,'invalid-model');
    check(c.previousVariantId===null||variant?.exerciseId===c.previousExerciseId,'invalid-model');
    check(c.previousPositionId===null||position?.exerciseId===c.previousExerciseId&&position?.variantId===c.previousVariantId,'invalid-model');
   }
  }
 }
 for(const version of j.model.planVersions)if(version.executionVersion===2)check(storedPlanModel(data,version.id),'invalid-model');
}
/** Shared semantic boundary for already decoded immutable PPC1 models. No writes. */
export function validateCompactSource(source,guard=()=>{}){
 supported(source);guard();const owner=source.data.trainingJournal?.model?.ownerId??'ppc1-preview-legacy';
 validateStructuredSource(source,owner);guard();validatePlans(source.data);guard();
 const summary=backupSummary(source.data);guard();check(summary.plans.every(p=>p.complete),'invalid-model');return summary;
}
/** One controller = one latest operation. Consumers use read() to recheck freshness. */
export function createCompactPreview(){
 let operation=0,controller=null,published=null;
 const clear=()=>{operation++;controller?.abort();published?.controller.abort();controller=null;published=null;};
 return Object.freeze({
  cancel:clear,
  async read(){
   const saved=published;if(!saved)return null;
   if(saved.probe){let current;try{current=await revision(saved.probe,saved.controller.signal);}catch(error){if(published===saved){saved.controller.abort();published=null;}throw error;}if(published!==saved)return null;if(current!==saved.revision){saved.controller.abort();published=null;throw new CompactPreviewError('revision');}}
   return published===saved?saved.report:null;
  },
  async preview(file,{signal,getRevision,limits}={}){
   clear();const id=operation,c=new AbortController();controller=c;
   const abort=()=>c.abort();signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
   const start=performance.now(),max=limits?.ms??COMPACT_LIMITS.ms;
   const guard=()=>{if(c.signal.aborted||id!==operation)throw cancelled();check(performance.now()-start<=max,'limit');};
   let stage='container';
   try{
    guard();check(getRevision===undefined||typeof getRevision==='function','source-unavailable');
    const before=await revision(getRevision,c.signal);guard();
    const source=await readCompactModel(file,{limits,signal:c.signal});guard();stage='schema';supported(source);guard();stage='semantic';
    const summary=validateCompactSource(source,guard);
    const after=await revision(getRevision,c.signal);guard();check(before===after,'revision');
    const report=freeze({format:'PPC1',modelVersion:2,status:'validated-training-preview',canRestore:false,revisionChecked:!!getRevision,
     sessions:summary.sessions,completed:summary.completed,ongoing:summary.ongoing,results:summary.results,snapshots:summary.snapshots,
     plans:source.catalog.plans.length,catalogVersions:source.catalog.planVersions.length,nativePlanVersions:summary.plans.length,activeVersion:summary.activePlanId!==null,archives:source.archives.length,
     opaqueArchives:source.archives.filter(a=>a.raw!==null).length,settingsPresent:Object.hasOwn(source,'settings'),
     warnings:['To podgląd, nie zgoda na przywrócenie.','Archiwa raw oraz rozszerzenia i ustawienia są zachowane jako dane; ich wewnętrznej semantyki nie potwierdzono.',...(!getRevision?['Podgląd nie jest powiązany z rewizją bieżącej bazy.']:[])]});
    guard();published={report,probe:getRevision,revision:before,controller:c};return report;
   }catch(error){
    if(c.signal.aborted||id!==operation||error.name==='AbortError')throw cancelled();
    if(error instanceof CompactPreviewError)throw error;
    if(/limit|budget|size|depth|tokens|time/i.test(error.message))throw new CompactPreviewError('limit');
    throw new CompactPreviewError(stage==='container'?'invalid-container':stage==='schema'?'unsupported-model':'invalid-model');
   }finally{signal?.removeEventListener('abort',abort);if(id===operation)controller=null;}
  }
 });
}
