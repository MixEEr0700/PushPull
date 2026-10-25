import {createResultReferences} from './training-model.mjs';
import {canonical,requireThat as check} from './backup-json.mjs';
export function flatten(performance){return performance.rows.flatMap(row=>row.segments.map(s=>({...s,parentId:row.id,side:row.side})));}
export function validatePerformance(performance,snapshot,entry){
 check(performance?.version===2&&Array.isArray(performance.rows)&&performance.rows.length,'missing performance');
 const position=snapshot.model.positions.find(p=>p.id===entry.journalPositionId);
 check(position?.exerciseId===entry.exerciseId&&position.variantId===entry.journalVariantId,'performance position mismatch');
 check(canonical(performance.loadConvention)===canonical(position.loadConvention)||position.loadConvention.basis===null&&performance.loadConvention.unit===position.loadConvention.unit&&['per-implement','combined','machine-indication',null].includes(performance.loadConvention.basis),'load convention mismatch');
 const ids=new Set(),specifications=[],bindings=new Set();
 for(const row of performance.rows){
  check(typeof row.id==='string'&&row.id&&!ids.has(row.id),'duplicate row ID');ids.add(row.id);
  specifications.push({resultId:row.id,positionId:position.id,setId:row.setId,side:row.side,groupId:row.groupId,round:row.round});
  if(position.sideMode==='required')check(row.side==='left'||row.side==='right','separate left/right required');
  const key=canonical([row.setId,row.side,row.groupId,row.round]);
  if(row.setId!==null){check(!bindings.has(key),'duplicate prescribed set/side');bindings.add(key);}
  check(Array.isArray(row.segments)&&row.segments.length,'empty segments');
  if(row.groupId!==null){const prescribed=snapshot.model.sets.find(s=>s.id===row.setId);check(prescribed&&row.round===prescribed.order+1,'group round/set mismatch');}
  const drop=snapshot.model.drops.some(d=>d.setId===row.setId);
  check(drop||row.segments.length===1,'segments require drop prescription');
  for(const s of row.segments){check(typeof s.id==='string'&&s.id&&!ids.has(s.id),'duplicate segment ID');ids.add(s.id);check(typeof s.kg==='string'&&/^\d+(\.\d+)?$/.test(s.kg)&&Number.isFinite(Number(s.kg))&&Number(s.kg)>=0,'invalid kg');check(typeof s.reps==='string'&&/^[1-9]\d*$/.test(s.reps)&&Number.isSafeInteger(Number(s.reps)),'invalid reps');check(Number.isFinite(Number(s.kg)*Number(s.reps)),'invalid tonnage');}
 }
 check(canonical(entry.series)===canonical(flatten(performance)),'performance projection mismatch');
 check(entry.kg===entry.series[0].kg&&entry.reps===entry.series[0].reps,'summary projection mismatch');
 return createResultReferences(snapshot,specifications);
}
export function newPerformance(ex,previous){
 const sides=ex.sideMode==='required'?['left','right']:[null],rows=[];
 const targets=ex.targets.length?ex.targets:[{id:null,order:0,drop:false}];
 for(const t of targets)for(const side of sides){
  const old=previous?.rows.find(r=>r.setId===t.id&&r.side===side);
  rows.push({id:crypto.randomUUID(),setId:t.id,side,groupId:ex.group?.id??null,round:ex.group?t.order+1:null,segments:old?old.segments.map(s=>({...s,id:crypto.randomUUID()})):Array.from({length:t.drop?2:1},()=>({id:crypto.randomUUID(),kg:'',reps:''}))});
 }
 return {version:2,loadConvention:structuredClone(ex.loadConvention),rows};
}

// Read-only card annotation. Unknown legacy contexts are not inferred from names,
// today's plan, technique markers or a flattened summary of a structured result.
function comparison(data,entry){
 const snap=data.trainingJournal?.sessionSnapshots.find(s=>s.sessionId===entry.sessionId);
 if(!snap||snap.id!==entry.journalSnapshotId)return null;
 const p=snap.model.positions.find(p=>p.id===entry.journalPositionId),variant=snap.model.variants.find(v=>v.id===entry.journalVariantId);
 const performance=entry.performance,load=performance?.loadConvention;
 if(!p||!variant||p.exerciseId!==entry.exerciseId||p.variantId!==variant.id||variant.exerciseId!==entry.exerciseId||p.planVersionId!==snap.planVersionId||p.unitId!==snap.unitId||!load?.unit||!load.basis)return null;
 if(load.unit!==p.loadConvention.unit||p.loadConvention.basis!==null&&load.basis!==p.loadConvention.basis)return null;
 if(performance.version!==2||!Array.isArray(performance.rows)||!performance.rows.length||!snap.model.planVersions.some(v=>v.id===snap.planVersionId&&v.executionVersion===2))return null;
 const targets=snap.model.sets.filter(t=>t.positionId===p.id).slice().sort((a,b)=>a.order-b.order);
 const sides=[...new Set(performance.rows.map(r=>r.side))].sort();
 const context=canonical([entry.exerciseId,variant.id,variant.machine,variant.grip,variant.support,variant.execution,variant.laterality,p.sideMode??null,load.unit,load.basis,sides]);
 // Storage/import retain full model validation. Rendering checks the measurement
 // references only; revalidating every whole snapshot per row blocks long histories.
 const extra=performance.rows.filter(r=>r.setId===null),paired=extra.some(r=>r.side!==null);
 if(paired&&(extra.length!==2||extra.filter(r=>r.side==='left').length!==1||extra.filter(r=>r.side==='right').length!==1))return null;
 const number=s=>String(s).replace(/^0+(?=\d)/,'').replace(/(\.\d*?)0+$/,'$1').replace(/\.$/,'');
 const rows=[],bindings=new Set();
 for(const r of performance.rows){
  const target=targets.find(t=>t.id===r.setId),group=snap.model.groups.find(g=>g.id===r.groupId),drop=!!target&&snap.model.drops.some(d=>d.setId===target.id);
  if(r.setId!==null&&!target||![null,'left','right'].includes(r.side)||p.sideMode==='required'&&r.side===null)return null;
  if(r.groupId!==null&&(!group||!group.positionIds.includes(p.id)||r.round!==target?.order+1)||r.groupId===null&&r.round!==null)return null;
  const key=canonical([r.setId,r.side,r.groupId,r.round]);if(r.setId!==null&&bindings.has(key))return null;bindings.add(key);
  if(!Array.isArray(r.segments)||!r.segments.length||!drop&&r.segments.length!==1)return null;
  if(r.segments.some(s=>typeof s.kg!=='string'||typeof s.reps!=='string'||!(/^\d+(\.\d+)?$/.test(s.kg))||!Number.isFinite(Number(s.kg))||!/^[1-9]\d*$/.test(s.reps)||!Number.isSafeInteger(Number(s.reps))))return null;
  rows.push({order:target?targets.indexOf(target):targets.length+(paired?0:extra.indexOf(r)),side:r.side,
   value:[target?.role??null,drop,group?.kind??null,r.round,r.segments.map(s=>[number(s.kg),number(s.reps)])]});
 }
 rows.sort((a,b)=>a.order-b.order||String(a.side).localeCompare(String(b.side)));
 return {context,value:canonical(rows.map(r=>[r.side,r.value]))};
}
/** Age = length of the latest equal run among comparable completed performances.
 * An ongoing session may supply the displayed last result, but never adds a count.
 * UUIDs, notes, targets' kg examples and technique markers are not measurements.
 */
export function resultChangeAge(data,anchor){
 if(!anchor)return null;
 const basis=comparison(data,anchor);if(!basis)return null;
 const sessions=new Map(data.sessions.map(s=>[s.id,s]));
 const candidates=data.entries.filter(e=>e.exerciseId===anchor.exerciseId&&e.journalVariantId===anchor.journalVariantId&&sessions.get(e.sessionId)?.status==='done');
 if(candidates.some(e=>!/^\d{4}-\d{2}-\d{2}$/.test(sessions.get(e.sessionId).date)||!Number.isFinite(sessions.get(e.sessionId).seq)))return null;
 candidates.sort((a,b)=>{const sa=sessions.get(a.sessionId),sb=sessions.get(b.sessionId);return sb.date.localeCompare(sa.date)||sb.seq-sa.seq;});
 let age=0,latest=null;const seen=new Set();
 for(const e of candidates){
  const current=comparison(data,e);if(!current)return null;
  if(current.context!==basis.context)continue;
  if(seen.has(e.sessionId))return null;seen.add(e.sessionId);
  if(latest!==null&&latest!==current.value)return age;
  latest=current.value;age++;
 }
 return age||null;
}
export function resultChangeLabel(age){
 if(age===null)return 'Ostatnia zmiana: nieustalona';
 const noun=age===1?'sesję':age%10>=2&&age%10<=4&&(age%100<12||age%100>14)?'sesje':'sesji';
 return `Ostatnia zmiana: ${age} ${noun} temu`;
}
