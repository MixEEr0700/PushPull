import {SLOTS,PLAN_ID} from './v2-plan-data.mjs';
import {canonical,requireThat as check} from './backup-json.mjs';
import {createModel} from './training-model.mjs';
export {SLOTS,PLAN_ID};
const source=reference=>({kind:'owner',reference,recordedAt:null});
export function buildPlan(ownerId){
 const m={schemaVersion:1,ownerId,exercises:[],variants:[],planVersions:[],positions:[],sets:[],drops:[],groups:[],coachInstructions:[],userNotes:[]};
 const src=source('Zatwierdzony projekt D1–D9 oraz decyzje O1–O3 właściciela, 2026-10-22');
 m.planVersions.push({id:PLAN_ID,planId:'approved-v2',number:1,label:'V2 · decyzje właściciela 22.10.2026',executionVersion:2,units:['PUSH A','PULL A','PUSH B','PULL B'].map((name,order)=>({id:name,name,order})),source:src});
 for(const slot of SLOTS){
  const members=slot.slot==='PULL-B-6'?[{...slot,name:'Narciarz · drążek łamany',identity:'PULL-B-6-SKI',basis:'machine-indication'},{...slot,name:'Szrugsy · hantle',identity:'PULL-B-6-SHRUGS',basis:'per-implement'}]:[{...slot,identity:slot.slot==='PUSH-A-4'?'PUSH-A-4-CHEST-PRESS':slot.slot}];
  const positions=[];
  members.forEach((s,member)=>{
   const id=PLAN_ID+':'+s.identity;positions.push(id);
   const ref=source(s.parameterSource+'; docs/V2_NEXT_PLAN_DRAFT_STAGE_5A.md '+s.slot);
   m.exercises.push({id:s.identity,name:s.name,status:'confirmed',legacyId:s.identity===s.slot?s.slot:null,source:ref});
   m.variants.push({id,exerciseId:s.identity,label:s.name,machine:null,grip:s.slot==='PUSH-A-4'?'neutralny':null,support:s.slot==='PUSH-A-4'?'wysokie siedzisko':null,execution:s.name,laterality:s.sideMode==='required'?'unilateral':s.sideMode==='optional'?null:'bilateral',source:ref});
   m.positions.push({id,planVersionId:PLAN_ID,unitId:s.unit,order:s.order*2+member,label:s.name,exerciseId:s.identity,variantId:id,legacyPositionId:s.slot,replacesPositionId:null,replacesLegacyPositionId:s.slot==='PUSH-A-4'?s.slot:null,setState:s.reps.length?'specified':'unspecified',confirmation:'confirmed',loadConvention:{unit:'kg',basis:s.basis,description:s.basis==='per-implement'?'Ciężar jednego hantla; bez mnożenia ×2':s.basis==='machine-indication'?'Wskazanie maszyny lub wyciągu':'Konwencja do określenia; bez przeliczania'},source:ref,slotId:s.slot,slotOrder:s.order,sideMode:s.sideMode});
   s.reps.forEach(([min,max],order)=>{
    const setId=id+':set:'+order;
    m.sets.push({id:setId,positionId:id,order,role:s.backoff&&order===2?'backoff':'main',reps:{min,max},rir:{min:0,max:0},tempo:s.tempo,side:s.sideMode==='required'?'each':null,backoffFromSetId:s.backoff&&order===2?id+':set:1':null,restSeconds:null,source:ref});
    if(s.drop)m.drops.push({id:setId+':drop',setId,segments:null,source:ref});
   });
   m.coachInstructions.push({id:id+':instructions',planVersionId:PLAN_ID,positionId:id,revision:1,text:s.instruction,confirmation:'unverified',source:source('C1 / C2/U / D2 rozdzielone etykietami w tekście; niepewne autorstwo C2 zachowane')});
  });
  if(members.length===2)m.groups.push({id:PLAN_ID+':paired',planVersionId:PLAN_ID,unitId:slot.unit,kind:'paired',positionIds:positions,rounds:2,betweenMembersSeconds:15,afterRoundSeconds:null,source:src});
 }
 m.coachInstructions.push({id:PLAN_ID+':global',planVersionId:PLAN_ID,positionId:null,revision:1,text:'Przerwy w 1–2 ćwiczeniu 3–5 minut minimum. W pozostałych 2–3 minuty, masz być świeży w trakcie serii. KAŻDA SERIA DO UPADKU MAKSYMALNEGO. Nieokreślone parametry brzucha i łydek pozostają nieokreślone.',confirmation:'unverified',source:source('Dokument trenera T1; D1 pozostawia cztery pozycje bez parametrów')});
 return createModel(m);
}
/** Explicit activation only. Existing snapshots and legacy exercise rows are untouched. */
export function activate(data,at){
 const j=data.trainingJournal,plan=buildPlan(j.model.ownerId);
 for(const key of ['exercises','variants','planVersions','positions','sets','drops','groups','coachInstructions']){
  for(const row of plan[key]){const old=j.model[key].find(x=>x.id===row.id);if(!old)j.model[key].push(structuredClone(row));else if(key!=='exercises')check(canonical(old)===canonical(row),'Plan version conflict: preserve existing version and assign a new ID');}
 }
 for(const p of plan.positions)if(!Object.values(data.exercises).flat().some(x=>x.id===p.exerciseId))data.exercises[p.unitId].push({id:p.exerciseId,name:p.label,sets:plan.sets.filter(s=>s.positionId===p.id).length,target:'V2',initialKg:'',tempo:'',rir:'',notes:'',journalOnly:true});
 j.activePlanVersionId=PLAN_ID;(j.activations??=[]).push({planVersionId:PLAN_ID,at});
}
export function views(model,versionId,type,data){
 const positions=model.positions.filter(p=>p.planVersionId===versionId&&p.unitId===type).sort((a,b)=>a.order-b.order);
 const one=p=>{
  const targets=model.sets.filter(s=>s.positionId===p.id).sort((a,b)=>a.order-b.order),group=model.groups.find(g=>g.positionIds.includes(p.id));
  return {id:p.exerciseId,name:p.label,sets:targets.length||'?',target:targets.map(t=>(t.role==='backoff'?'back-off ':'')+t.reps.min+'–'+t.reps.max).join(' / ')||'nieokreślone',tempo:targets[0]?.tempo?.join(' ')??'nieokreślone',rir:targets[0]?.rir?.min??'nieokreślone',initialKg:'',v2:true,journalVariantId:p.variantId,positionId:p.id,sideMode:p.sideMode,loadConvention:p.loadConvention,targets:targets.map(t=>({...t,drop:model.drops.some(d=>d.setId===t.id)})),group,notes:data?.trainingJournal?.model.userNotes.find(n=>n.exerciseId===p.exerciseId&&n.origin==='user')?.text??'',sharedNotes:Object.values(data?.exercises??{}).flat().find(e=>e.id===p.exerciseId)?.notes??'',instructions:model.coachInstructions.filter(i=>i.positionId===p.id||i.positionId===null).map(i=>i.text).join('\n')};
 };
 const result=[];
 for(const p of positions){const g=model.groups.find(g=>g.positionIds.includes(p.id));if(g){if(g.positionIds[0]!==p.id)continue;const members=g.positionIds.map(id=>one(positions.find(p=>p.id===id)));result.push({...members[0],id:p.slotId,name:'Narciarz + szrugsy',members,description:'2 rundy · 8–10 każde ćwiczenie · 15 s między ćwiczeniami',notes:'',journalOnly:true});}else result.push(one(p));}
 return result;
}
