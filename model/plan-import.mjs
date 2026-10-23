/** Data-only plans. Pure staging: callers commit the returned clone atomically. */
import {parseJson,portable,canonical,record} from './backup-json.mjs';
import {validateModel} from './training-model.mjs';
import {PLAN_ID} from './v2-plan.mjs';
import {initialize,sourceExercises} from './journal.mjs';
const tables=['exercises','variants','positions','sets','drops','groups','coachInstructions'];
const fields={
 exercises:'id name status legacyId source',
 variants:'id exerciseId label machine grip support execution laterality source',
 positions:'id planVersionId unitId order label exerciseId variantId legacyPositionId replacesPositionId setState confirmation loadConvention sideMode source',
 sets:'id positionId order role reps rir tempo side backoffFromSetId restSeconds source',
 drops:'id setId segments source',
 groups:'id planVersionId unitId kind positionIds rounds betweenMembersSeconds afterRoundSeconds source',
 coachInstructions:'id planVersionId positionId revision text confirmation source'
};
const check=(ok,message)=>{if(!ok)throw TypeError('Plan: '+message);};
const id=x=>typeof x==='string'&&/^[A-Za-z0-9_.:-]+$/.test(x)&&!Object.hasOwn(Object.prototype,x)&&!['__proto__','constructor','prototype'].includes(x);
const exerciseId=x=>typeof x==='string'&&/^[A-Za-z0-9_.-]+$/.test(x)&&!Object.hasOwn(Object.prototype,x)&&!['__proto__','constructor','prototype'].includes(x);
function shape(x,keys){check(record(x),'oczekiwano obiektu');const names=keys.split(' ');check(Object.keys(x).every(k=>names.includes(k))&&names.every(k=>Object.hasOwn(x,k)),'brakujące pola lub nieznany protokół (wymaga obsługi w aplikacji): '+keys);}
function safeKeys(x){if(x&&typeof x==='object')for(const [k,v] of Object.entries(x)){check(!['__proto__','constructor','prototype'].includes(k),'niedozwolony klucz');safeKeys(v);}}
const same=(a,b)=>canonical(a)===canonical(b);
const ordered=(rows,key='order')=>rows.slice().sort((a,b)=>a[key]-b[key]);
export function parsePlan(text){try{const p=parseJson(text);portable(p);safeKeys(p);return p;}catch(error){throw TypeError('Plan: nieprawidłowy JSON. '+error.message);}}
function packetShape(p){
 portable(p);safeKeys(p);
 shape(p,'format version approval planVersion exercises variants positions sets drops groups coachInstructions continuity');
 check(p.format==='pushpull-plan'&&p.version===1,'nieobsługiwany format lub wersja');
 shape(p.approval,'status reference approvedAt');check(p.approval.status==='approved'&&typeof p.approval.reference==='string'&&p.approval.reference.trim()&&typeof p.approval.approvedAt==='string'&&Number.isFinite(Date.parse(p.approval.approvedAt)),'wymagana deklaracja zatwierdzenia planu przez właściciela');
 shape(p.planVersion,'id planId number label units executionVersion source');check(p.planVersion.executionVersion===2,'protokół wymaga obsługi w aplikacji');
 check(id(p.planVersion.id)&&id(p.planVersion.planId),'niepoprawne ID wersji/planu');
 check(p.planVersion.id!==PLAN_ID,'ID wbudowanego V2 jest zarezerwowane; użyj nowego ID wersji');
 check(Array.isArray(p.planVersion.units),'brak jednostek');
 for(const u of p.planVersion.units){shape(u,'id name order');check(['PUSH A','PULL A','PUSH B','PULL B'].includes(u.id)||exerciseId(u.id),'niepoprawne ID jednostki');}
 for(const key of tables){check(Array.isArray(p[key]),'brak tabeli '+key);for(const row of p[key]){shape(row,fields[key]);check(id(row.id),'niepoprawne ID '+key);shape(row.source,'kind reference recordedAt');}}
 shape(p.planVersion.source,'kind reference recordedAt');
 for(const s of p.sets)for(const k of ['reps','rir'])if(s[k]!==null)shape(s[k],'min max');
 check(Array.isArray(p.continuity),'brak deklaracji ciągłości');
 for(const c of p.continuity)shape(c,'positionId relation previousExerciseId previousVariantId previousPositionId reason source');
}
function merge(model,p){
 for(const [key,rows] of [...tables.map(k=>[k,p[k]]),['planVersions',[p.planVersion]]]){
  for(const row of rows){const old=model[key].find(x=>x.id===row.id);check(!old||same(old,row),'kolizja niezmiennego ID '+row.id+'; użyj nowego ID dla nowej wersji/maszyny');if(!old)model[key].push(structuredClone(row));}
 }
 try{validateModel(model);}catch(error){throw TypeError('Plan: niepoprawne parametry lub powiązania. '+error.message);}
}
export function stagePlan(data,packet,ownerId='plan-preview'){
 const p=structuredClone(packet);packetShape(p);
 const next=structuredClone(data),j=next.trainingJournal??=initialize(ownerId),prior=data.trainingJournal?.model;
 check(!j.model.planVersions.some(v=>v.id===p.planVersion.id),'ta wersja jest już zapisana; wybierz ją poniżej albo użyj nowego ID');
 const originalRegistry=Object.values(data.exercises).flat(),knownExercise=x=>prior?.exercises.some(e=>e.id===x)||originalRegistry.some(e=>e.id===x);
 for(const key of tables){check(new Set(p[key].map(x=>x.id)).size===p[key].length,'powtórzone ID '+key);}
 check(p.positions.length>0,'plan nie zawiera ćwiczeń');
 check(p.continuity.length===p.positions.length&&new Set(p.continuity.map(c=>c.positionId)).size===p.positions.length,'deklaracja ciągłości dla każdej pozycji jest obowiązkowa');
 for(const pos of p.positions){
  check(pos.planVersionId===p.planVersion.id,'pozycja spoza importowanej wersji');
  check(exerciseId(pos.exerciseId),'niepoprawne ID ćwiczenia');
  check(p.exercises.some(e=>e.id===pos.exerciseId)&&p.variants.some(v=>v.id===pos.variantId),'brak definicji ćwiczenia lub wariantu w pliku');
  check(['bilateral','optional','required'].includes(pos.sideMode),'sideMode wymaga bilateral / optional / required');
  const variant=p.variants.find(v=>v.id===pos.variantId);
  check((variant.laterality!=='bilateral'||pos.sideMode==='bilateral')&&(variant.laterality!=='unilateral'||pos.sideMode!=='bilateral'),'tryb formularza stron jest sprzeczny z wariantem ćwiczenia');
  shape(pos.loadConvention,'unit basis description');
  check([null,'kg'].includes(pos.loadConvention.unit),'jednostka obciążenia wymaga obsługi w aplikacji (obecnie kg lub null)');
  const c=p.continuity.find(c=>c.positionId===pos.id);check(c,'brak ciągłości '+pos.id);
  check(['new','same-variant','new-variant','replacement'].includes(c.relation)&&typeof c.reason==='string'&&c.reason.trim(),'określ ciągłość i jej uzasadnienie');
  shape(c.source,'kind reference recordedAt');
  check(c.source.kind==='owner'&&typeof c.source.reference==='string'&&c.source.reference.trim()&&(c.source.recordedAt===null||typeof c.source.recordedAt==='string'&&Number.isFinite(Date.parse(c.source.recordedAt))),'ciągłość musi wskazywać decyzję właściciela');
  if(c.relation==='new'){
   check(!knownExercise(pos.exerciseId)&&[c.previousExerciseId,c.previousVariantId,c.previousPositionId].every(x=>x===null),'istniejące ćwiczenie wymaga jawnej deklaracji ciągłości');
  }else{
   check(knownExercise(c.previousExerciseId),'nieznana poprzednia tożsamość');
   const oldVariant=prior?.variants.find(v=>v.id===c.previousVariantId);
   check(c.previousVariantId===null||oldVariant?.exerciseId===c.previousExerciseId,'nieznany poprzedni wariant');
   if(c.relation==='same-variant')check(c.previousExerciseId===pos.exerciseId&&oldVariant?.id===pos.variantId,'ciągłość wymaga tej samej tożsamości i wariantu');
   if(c.relation==='new-variant')check(c.previousExerciseId===pos.exerciseId&&c.previousVariantId!==pos.variantId&&!prior?.variants.some(v=>v.id===pos.variantId),'nowa maszyna/wykonanie wymaga nowego wariantu');
   if(c.relation==='replacement')check(c.previousExerciseId!==pos.exerciseId&&!knownExercise(pos.exerciseId),'zamiana wymaga nowej tożsamości');
  }
  if(c.previousPositionId!==null){const old=prior?.positions.find(x=>x.id===c.previousPositionId);check(old?.exerciseId===c.previousExerciseId&&old?.variantId===c.previousVariantId,'niezgodna poprzednia pozycja');}
  check(pos.replacesPositionId===null||pos.replacesPositionId===c.previousPositionId,'sprzeczna ścieżka zastąpienia');
  const targets=ordered(p.sets.filter(s=>s.positionId===pos.id));
  check(targets.every((s,i)=>s.order===i),'kolejność serii musi zaczynać się od 0 bez luk');
  check(targets.every(s=>pos.sideMode==='required'?s.side==='each':s.side===null),'cele strony wymagają obsługi w aplikacji; użyj each dla L/P');
 }
 for(const u of p.planVersion.units){const positions=ordered(p.positions.filter(x=>x.unitId===u.id));check(positions.length>0,'pusta jednostka '+u.id);check(new Set(positions.map(x=>x.exerciseId)).size===positions.length,'to samo ćwiczenie dwa razy w jednostce wymaga obsługi w aplikacji');}
 check(p.exercises.every(e=>p.positions.some(x=>x.exerciseId===e.id))&&p.variants.every(v=>p.positions.some(x=>x.variantId===v.id)),'nieużywane tożsamości lub warianty');
 check(p.sets.every(s=>p.positions.some(x=>x.id===s.positionId))&&p.drops.every(d=>p.sets.some(s=>s.id===d.setId)),'seria/dropset spoza planu');
 for(const s of p.sets)check([null,'main','backoff','warmup'].includes(s.role),'typ serii wymaga obsługi w aplikacji');
 for(const g of p.groups)check(['paired','superset'].includes(g.kind),'protokół grupy wymaga obsługi w aplikacji');
 for(const d of p.drops)check(d.segments===null,'szablony celów segmentów wymagają obsługi w aplikacji; obsługiwany dropset ma segments: null i dowolną liczbę wyników');
 check([...p.groups,...p.coachInstructions].every(x=>x.planVersionId===p.planVersion.id),'grupa/instrukcja spoza planu');
 for(const g of p.groups){
  check(Array.isArray(g.positionIds),'brak listy członów grupy');
  const positions=ordered(p.positions.filter(x=>x.unitId===g.unitId)),indices=g.positionIds.map(id=>positions.findIndex(x=>x.id===id));
  check(indices.every((n,i)=>n>=0&&(i===0||n===indices[i-1]+1)),'człony A/B/C muszą być kolejnymi pozycjami w tej samej jednostce');
  const counts=g.positionIds.map(id=>p.sets.filter(s=>s.positionId===id).length);
  check(counts.every(n=>n>0&&(g.rounds===null||n===g.rounds)),'rundy grupy wymagają zgodnych osobnych celów serii dla każdego członu');
 }
 // Only packet-owned prescriptions may refer to this newly introduced version.
 merge(j.model,p);
 for(const u of p.planVersion.units)next.exercises[u.id]??=[];
 for(const pos of p.positions)if(!Object.values(next.exercises).flat().some(e=>e.id===pos.exerciseId))next.exercises[pos.unitId].push({id:pos.exerciseId,name:pos.label,sets:Math.max(1,p.sets.filter(s=>s.positionId===pos.id).length),target:'',initialKg:'',tempo:'',rir:'',notes:'',journalOnly:true});
 (j.importedPlans??=[]).push(p);
 return next;
}
export function previewPlan(data,p){
 const saved=data.trainingJournal?.importedPlans?.find(x=>x.planVersion.id===p.planVersion.id);const next=saved&&same(saved,p)?data:stagePlan(data,p),j=data.trainingJournal,old=j?.model.positions.filter(x=>x.planVersionId===j.activePlanVersionId)??[],incoming=p.positions;
 const oldExercises=old.length?old:['PUSH A','PULL A','PUSH B','PULL B'].flatMap(type=>sourceExercises(data,type)).map(e=>({exerciseId:e.id,label:e.name,legacyParameters:{name:e.name,sets:e.sets,target:e.target,rir:e.rir,tempo:e.tempo}}));
 const added=incoming.filter(x=>!oldExercises.some(o=>o.exerciseId===x.exerciseId)).map(x=>x.label);
 const removed=oldExercises.filter(x=>!incoming.some(o=>o.exerciseId===x.exerciseId)).map(x=>x.label);
 const signature=(model,pos)=>({variant:pos.variantId,unit:pos.unitId,order:pos.order,label:pos.label,sideMode:pos.sideMode,confirmation:pos.confirmation,load:pos.loadConvention,
  sets:ordered(model.sets.filter(s=>s.positionId===pos.id)).map(({id,positionId,source,backoffFromSetId,...s})=>({...s,backoffFrom:backoffFromSetId===null?null:model.sets.find(x=>x.id===backoffFromSetId)?.order,drop:model.drops.some(d=>d.setId===id)})),
  groups:model.groups.filter(g=>g.positionIds.includes(pos.id)).map(g=>({kind:g.kind,members:g.positionIds.map(id=>model.positions.find(x=>x.id===id).exerciseId),rounds:g.rounds,betweenMembersSeconds:g.betweenMembersSeconds,afterRoundSeconds:g.afterRoundSeconds})),
  instructions:model.coachInstructions.filter(i=>i.planVersionId===pos.planVersionId&&(i.positionId===null||i.positionId===pos.id)).map(i=>({text:i.text,confirmation:i.confirmation,source:i.source}))});
 const incomingModel={...p,planVersions:[p.planVersion]};
 const changed=incoming.filter(x=>{const o=old.find(o=>o.exerciseId===x.exerciseId);return o?!same(signature(j.model,o),signature(incomingModel,x)):oldExercises.some(o=>o.exerciseId===x.exerciseId);}).map(x=>x.label);
 const unresolved=incoming.flatMap(x=>{const rows=p.sets.filter(s=>s.positionId===x.id),notes=[];if(x.setState==='unspecified')notes.push('liczba serii');for(const s of rows)for(const k of ['reps','rir','tempo','restSeconds'])if(s[k]===null||(Array.isArray(s[k])&&s[k].includes(null)))notes.push('seria '+(s.order+1)+' '+k);if(x.confirmation!=='confirmed')notes.push('potwierdzenie parametrów');if(p.exercises.find(e=>e.id===x.exerciseId).status==='unresolved')notes.push('tożsamość ćwiczenia');if(p.variants.find(v=>v.id===x.variantId).laterality===null)notes.push('stronność wariantu');if(x.source.kind==='unknown'||x.source.reference===null)notes.push('źródło parametrów');if(x.loadConvention.unit===null||x.loadConvention.basis===null)notes.push('konwencja ciężaru');return notes.length?[x.label+': '+notes.join(', ')]:[];});
 const details=incoming.filter(pos=>{const prior=old.find(o=>o.exerciseId===pos.exerciseId);return prior?!same(signature(j.model,prior),signature(incomingModel,pos)):oldExercises.some(o=>o.exerciseId===pos.exerciseId);}).map(pos=>{const prior=old.find(o=>o.exerciseId===pos.exerciseId);return {exerciseId:pos.exerciseId,label:pos.label,before:prior?signature(j.model,prior):oldExercises.find(o=>o.exerciseId===pos.exerciseId).legacyParameters,after:signature(incomingModel,pos)};});
 return {model:next.trainingJournal.model,added,removed,changed,details,unresolved};
}
export function stageActivation(data,versionId,at){
 const next=structuredClone(data),j=next.trainingJournal,p=j?.importedPlans?.find(x=>x.planVersion.id===versionId);
 check(p&&j.model.planVersions.some(v=>v.id===versionId),'najpierw zapisz poprawny plan');if(j.activePlanVersionId===versionId)return next;validateModel(j.model);
 j.activePlanVersionId=versionId;j.nextUnitId=ordered(p.planVersion.units)[0].id;(j.activations??=[]).push({planVersionId:versionId,at,...(data.activeId?{ongoingSessionId:data.activeId}:{})});return next;
}
