import {SLOTS,PLAN_ID} from './v2-plan-data.mjs';
import {canonical,freeze,requireThat as check} from './backup-json.mjs';
import {createModel,validateModel} from './training-model.mjs';
export {SLOTS,PLAN_ID};
/** Own notes only. An arbitrary historical ID cannot prove a plan binding.
 * Keep the existing ID contract. Multiple variants of one exercise within a
 * version cannot be distinguished by that contract: fail closed, retain data.
 */
export function userNoteBinding(model,versionId,exerciseId,variantId){
 const positions=model?.positions.filter(p=>p.planVersionId===versionId&&p.exerciseId===exerciseId)??[];
 if(!positions.some(p=>p.variantId===variantId))return null;
 if(new Set(positions.map(p=>p.variantId)).size!==1)return null;
 const version=model.planVersions.find(v=>v.id===versionId);if(!version)return null;
 const id='user:'+versionId+':'+exerciseId;
 const record=model.userNotes.find(n=>n.id===id);
 const valid=record?.exerciseId===exerciseId&&record.origin==='user'&&record.sessionId===null;
 return {id,context:version.executionVersion===2?versionId:variantId,text:valid?record.text:'',revision:valid?record.revision:0};
}
/** Only the current plan's own note changes. Snapshots/source text stay intact. */
export function editUserNote(model,command){
 const {versionId,exerciseId,variantId,noteId,base,revision,text,recordedAt}=command;
 const binding=userNoteBinding(model,versionId,exerciseId,variantId);
 check(binding&&binding.id===noteId,'Nie można potwierdzić kontekstu notatki. Zachowaj szkic.');
 check(binding.text===base&&binding.revision===revision,'Notatka zmieniła się od rozpoczęcia edycji. Zachowaj szkic.');
 check(typeof text==='string','Nieprawidłowa treść notatki.');
 const old=model.userNotes.find(n=>n.id===noteId);
 check(!old||old.exerciseId===exerciseId&&old.sessionId===null&&old.origin==='user','Identyfikator notatki należy do innego kontekstu. Zachowaj szkic.');
 const note=old?{...old,text,revision:old.revision+1}:{id:noteId,exerciseId,sessionId:null,text,origin:'user',revision:1,source:{kind:'owner',reference:'Własna notatka użytkownika',recordedAt}};
 const next=freeze({...model,userNotes:old?model.userNotes.map(n=>n.id===noteId?note:n):[...model.userNotes,note]});
 validateModel(next);return {model:next,note};
}
/** Presentation only: one shared slot number and A/B/C… for any group size. */
export function groupMemberNumber(slot,index){
 let suffix='';for(let n=index+1;n>0;n=Math.floor((n-1)/26))suffix=String.fromCharCode(65+(n-1)%26)+suffix;
 return String(slot)+suffix;
}
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
 const j=data.trainingJournal;
 if(j.activePlanVersionId===PLAN_ID)return;
 if(!j.model.planVersions.some(p=>p.id===PLAN_ID)){
 const plan=buildPlan(j.model.ownerId);
 for(const key of ['exercises','variants','planVersions','positions','sets','drops','groups','coachInstructions']){
  for(const row of plan[key]){const old=j.model[key].find(x=>x.id===row.id);if(!old)j.model[key].push(structuredClone(row));else if(key!=='exercises')check(canonical(old)===canonical(row),'Plan version conflict: preserve existing version and assign a new ID');}
 }
 for(const p of plan.positions)if(!Object.values(data.exercises).flat().some(x=>x.id===p.exerciseId))data.exercises[p.unitId].push({id:p.exerciseId,name:p.label,sets:plan.sets.filter(s=>s.positionId===p.id).length,target:'V2',initialKg:'',tempo:'',rir:'',notes:'',journalOnly:true});
 }else validateModel(j.model);
 const version=j.model.planVersions.find(p=>p.id===PLAN_ID);
 j.nextUnitId=version.units.slice().sort((a,b)=>a.order-b.order)[0].id;j.activePlanVersionId=PLAN_ID;(j.activations??=[]).push({planVersionId:PLAN_ID,at,...(data.activeId?{ongoingSessionId:data.activeId}:{})});
}
export const rangeText=r=>r===null||r===undefined?'nieokreślone':r.min===r.max?String(r.min):r.min+'–'+r.max;
export const tempoText=t=>t===null||t===undefined?'nieokreślone':t.map(x=>x??'?').join(' ');
export function views(model,versionId,type,data){
 const positions=model.positions.filter(p=>p.planVersionId===versionId&&p.unitId===type).sort((a,b)=>a.order-b.order);
 const version=model.planVersions.find(v=>v.id===versionId),imported=versionId!==PLAN_ID;
 let number=0;const numbers=new Map();for(const p of positions){const g=model.groups.find(g=>g.positionIds.includes(p.id));if(!g||g.positionIds[0]===p.id)number++;numbers.set(p.id,g?groupMemberNumber(number,g.positionIds.indexOf(p.id)):number);}
 const one=p=>{
  const targets=model.sets.filter(s=>s.positionId===p.id).sort((a,b)=>a.order-b.order),group=model.groups.find(g=>g.positionIds.includes(p.id));
  return {id:p.exerciseId,name:p.label,displayNumber:imported?numbers.get(p.id):p.slotOrder+1,sets:targets.length||'?',target:targets.map(t=>(t.role==='backoff'?'back-off ':'')+(t.reps? t.reps.min+'–'+t.reps.max:'nieokreślone')).join(' / ')||'nieokreślone',tempo:imported?[...new Set(targets.map(t=>tempoText(t.tempo)))].join(' / ')||'nieokreślone':tempoText(targets[0]?.tempo),rir:imported?[...new Set(targets.map(t=>rangeText(t.rir)))].join(' / ')||'nieokreślone':targets[0]?.rir?.min??'nieokreślone',initialKg:'',v2:true,imported,planLabel:version.label,planVersionId:versionId,journalVariantId:p.variantId,positionId:p.id,sideMode:p.sideMode,laterality:model.variants.find(v=>v.id===p.variantId)?.laterality??null,loadConvention:p.loadConvention,targets:targets.map(t=>({...t,drop:model.drops.some(d=>d.setId===t.id)})),group,notes:userNoteBinding(data?.trainingJournal?.model,versionId,p.exerciseId,p.variantId)?.text??'',sharedNotes:Object.values(data?.exercises??{}).flat().find(e=>e.id===p.exerciseId)?.notes??'',instructionSources:model.coachInstructions.filter(i=>i.planVersionId===versionId&&(i.positionId===p.id||i.positionId===null)),instructions:model.coachInstructions.filter(i=>i.planVersionId===versionId&&(i.positionId===p.id||i.positionId===null)).map(i=>i.text).join('\n')};
 };
 // One view per original position, including each independent group member.
 return positions.map(p=>{const view=one(p);if(!view.group||imported)return view;
  const index=view.group.positionIds.indexOf(p.id),number=groupMemberNumber(p.slotOrder+1,index);
  return {...view,displayNumber:number,name:groupMemberNumber(p.slotId,index)+' · '+view.name,description:'Superseria A/B · 2 rundy · 8–10 · 15 s między ćwiczeniami'};
 });
}
