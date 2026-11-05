/** Build new session results from verified comparable finished history. */
import {canonical} from './backup-json.mjs';
import {snapshotFor,recordEntry} from './journal.mjs';
const signature=(snap,id)=>{const m=snap.model,p=m.positions.find(p=>p.id===id);if(!p)return null;const sets=m.sets.filter(s=>s.positionId===id);return canonical({p,variant:m.variants.find(v=>v.id===p.variantId),sets,drops:m.drops.filter(d=>sets.some(s=>s.id===d.setId)),groups:m.groups.filter(g=>g.positionIds.includes(id))});};
export function repeatResults(data,session,exercises,{omit=[],uuid=()=>crypto.randomUUID(),now=()=>new Date().toISOString()}={}){
 const entries=[],missing=[],skip=new Set([...(session.skippedExerciseIds??[]),...omit]);
 for(const ex of exercises.flatMap(e=>e.members??[e])){
  if(skip.has(ex.id)||data.entries.some(e=>e.sessionId===session.id&&e.exerciseId===ex.id))continue;
  const history=data.entries.filter(e=>e.exerciseId===ex.id&&data.sessions.some(s=>s.id===e.sessionId&&s.status==='done'&&s.seq<session.seq&&s.date<=session.date)).sort((a,b)=>{const sa=data.sessions.find(s=>s.id===a.sessionId),sb=data.sessions.find(s=>s.id===b.sessionId);return sb.date.localeCompare(sa.date)||sb.seq-sa.seq;});
  const target=snapshotFor(data,session.id);
  const previous=history.find(e=>{
   const source=snapshotFor(data,e.sessionId);
   if(target||source)return !!(target&&source&&target.planVersionId===source.planVersionId&&target.unitId===source.unitId&&e.journalPositionId===ex.positionId&&e.journalVariantId===ex.journalVariantId&&signature(source,e.journalPositionId)===signature(target,ex.positionId));
   // No immutable context means comparability cannot be established.
   return false;
  });
  if(!previous){missing.push(ex.name);continue;}
  try{
   const e={id:uuid(),sessionId:session.id,exerciseId:ex.id,createdAt:now(),kg:previous.kg,reps:previous.reps};
   if(previous.performance){e.performance=structuredClone(previous.performance);for(const r of e.performance.rows){r.id=uuid();for(const s of r.segments)s.id=uuid();}e.series=structuredClone(previous.series);}
   else {e.series=structuredClone(previous.series);if(!e.series?.length)throw Error('missing series');for(const s of e.series)s.id=uuid();}
   recordEntry(data,e);entries.push(e);
  }catch{missing.push(ex.name);}
 }
 return {entries,missing};
}
