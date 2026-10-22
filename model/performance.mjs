import {createResultReference} from './training-model.mjs';
import {canonical,requireThat as check} from './backup-json.mjs';
export function flatten(performance){return performance.rows.flatMap(row=>row.segments.map(s=>({...s,parentId:row.id,side:row.side})));}
export function validatePerformance(performance,snapshot,entry){
 check(performance?.version===2&&Array.isArray(performance.rows)&&performance.rows.length,'missing performance');
 const position=snapshot.model.positions.find(p=>p.id===entry.journalPositionId);
 check(position?.exerciseId===entry.exerciseId&&position.variantId===entry.journalVariantId,'performance position mismatch');
 check(canonical(performance.loadConvention)===canonical(position.loadConvention)||position.loadConvention.basis===null&&performance.loadConvention.unit===position.loadConvention.unit&&['per-implement','combined','machine-indication',null].includes(performance.loadConvention.basis),'load convention mismatch');
 const ids=new Set(),refs=[],bindings=new Set();
 for(const row of performance.rows){
  check(typeof row.id==='string'&&row.id&&!ids.has(row.id),'duplicate row ID');ids.add(row.id);
  const ref=createResultReference(snapshot,{resultId:row.id,positionId:position.id,setId:row.setId,side:row.side,groupId:row.groupId,round:row.round});refs.push(ref);
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
 return refs;
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
