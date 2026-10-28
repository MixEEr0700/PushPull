import {canonical} from './backup-json.mjs';
import {rangeText,tempoText} from './v2-plan.mjs';
import {newPerformance,flatten} from './performance.mjs';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const drafts=new Map(),key=(id,sid)=>sid+'::'+id;
export const clear=()=>drafts.clear();
export function state(id,sid){const d=drafts.get(key(id,sid));if(!d)return null;return structuredClone({performance:d.performance,open:d.open,custom:d.custom,sidePairs:d.sidePairs});}
export function restore(id,sid,value){drafts.delete(key(id,sid));drafts.set(key(id,sid),{...structuredClone(value),ex:null});}
export function discard(id,sid){drafts.delete(key(id,sid));}
export function editor(ex,sid,entry,last){
 const k=key(ex.id,sid);let d=drafts.get(k);
 if(!d){
  const performance=entry?.performance?structuredClone(entry.performance):prefill(ex,last?.performance);
  const first=performance.rows[0].segments[0];
  const custom=performance.rows.some(r=>r.segments.some(s=>s.kg!==first.kg||s.reps!==first.reps));
  d={ex,performance,open:false,custom};drafts.set(k,d);
 }
 d.ex=ex;d.allowSideDeclaration=!entry;preparePairs(d);
 return `<div class="panel result-panel"><form class="performanceForm" novalidate data-id="${ex.id}" data-session="${sid}">${contents(d)}</form></div>`;
}
// A comparable saved result is an editor seed, not a new planned result.
// Retain removed/added rows and all segments; only fresh result identities change.
function prefill(ex,previous){
 if(!previous?.rows?.length||previous.loadConvention.unit!==ex.loadConvention.unit||ex.loadConvention.basis!==null&&previous.loadConvention.basis!==ex.loadConvention.basis)return newPerformance(ex);
 if(previous.rows.some(r=>r.setId!==null&&!ex.targets.some(t=>t.id===r.setId)))return newPerformance(ex);
 const p=structuredClone(previous);for(const row of p.rows){row.id=crypto.randomUUID();for(const s of row.segments)s.id=crypto.randomUUID();}return p;
}
// Pairing is editor state, never a new workout/result field. Prescribed rows
// match by stable set/group/round. Unprescribed ambiguous old rows stay separate.
function equalSides(a,b){return a.segments.length===b.segments.length&&a.segments.every((s,i)=>s.kg===b.segments[i].kg&&s.reps===b.segments[i].reps);}
function sameSet(a,b){return a.setId===b.setId&&a.groupId===b.groupId&&a.round===b.round;}
function preparePairs(d){
 const rows=d.performance.rows,used=new Set(),pairs=[];
 for(const p of Array.isArray(d.sidePairs)?d.sidePairs:[]){
  const left=rows.find(r=>r.id===p.leftId&&r.side==='left'),right=rows.find(r=>r.id===p.rightId&&r.side==='right');
  if(!left||!right||!sameSet(left,right)||used.has(left.id)||used.has(right.id))continue;
  pairs.push({leftId:left.id,rightId:right.id,linked:p.linked===true&&equalSides(left,right)});used.add(left.id);used.add(right.id);
 }
 for(const left of rows.filter(r=>r.side==='left'&&!used.has(r.id))){
  const candidates=rows.filter(r=>r.side==='right'&&!used.has(r.id)&&sameSet(left,r));
  const unambiguous=rows.filter(r=>r.side==='left'&&sameSet(left,r)).length===1;
  if(candidates.length===1&&unambiguous){const right=candidates[0];pairs.push({leftId:left.id,rightId:right.id,linked:false});used.add(left.id);used.add(right.id);}
 }
 // New unprescribed pairs have an explicit adjacent L/R order. Accept that
 // order only when the entire remaining context alternates; odd/ambiguous
 // historical layouts stay untouched and require an explicit pairing choice.
 for(const row of rows.filter(r=>r.side&&!used.has(r.id)&&r.setId===null)){
  if(used.has(row.id))continue;
  const context=rows.filter(r=>r.side&&!used.has(r.id)&&sameSet(r,row));
  if(context.length%2||!context.every((r,i)=>i%2===0||r.side!==context[i-1].side))continue;
  for(let i=0;i<context.length;i+=2){const a=context[i],b=context[i+1];pairs.push({leftId:a.side==='left'?a.id:b.id,rightId:a.side==='right'?a.id:b.id,linked:false});used.add(a.id);used.add(b.id);}
 }
 d.sidePairs=pairs;
}
const pairFor=(d,row)=>d.sidePairs.find(p=>p.leftId===row.id||p.rightId===row.id);
const otherSide=(d,row)=>{const p=pairFor(d,row);return p&&d.performance.rows.find(r=>r.id===(row.side==='left'?p.rightId:p.leftId));};
function copySegments(from,to){const retained=to.segments.slice(from.segments.length);to.segments=from.segments.map((s,i)=>to.segments[i]?{...to.segments[i],kg:s.kg,reps:s.reps}:{...s,id:crypto.randomUUID()}).concat(retained);}
/** Display only: compress equal prescriptions, retaining every differing target. */
export function parameters(ex){
 if(!ex.targets)return `${ex.sets} × ${ex.target} | tempo ${String(ex.tempo).replace(/\s+(?=\d)/g,'')} | RIR ${ex.rir}`;
 const groups=[];
 for(const t of ex.targets){
  const text=`${t.role==='backoff'?'back-off ':''}${rangeText(t.reps)}${t.drop?' drop':''} | tempo ${tempoText(t.tempo).replace(/ /g,'')} | RIR ${rangeText(t.rir)}`;
  const last=groups.at(-1);if(last?.text===text)last.count++;else groups.push({text,count:1});
 }
 return groups.map(g=>`${g.count} × ${g.text}`).join(' / ')||'Liczba serii nieokreślona';
}
function contents(d){const ex=d.ex,p=d.performance,first=p.rows[0]?.segments[0];return `${ex.loadConvention.basis===null?`<label>Znaczenie ciężaru<select data-load-basis><option value="">Nieokreślone</option>${[['per-implement','Jeden hantel'],['machine-indication','Wskazanie urządzenia'],['combined','Łącznie']].map(([v,l])=>`<option value="${v}" ${p.loadConvention.basis===v?'selected':''}>${l}</option>`).join('')}</select></label>`:''}<div class="grid2 quick-result"><input ${sideExceptions(d)?'readonly':''} data-quick="reps" inputmode="numeric" aria-label="Szybkie powtórzenia" placeholder="powtórzenia" value="${esc(first?.reps)}"><input ${sideExceptions(d)?'readonly':''} data-quick="kg" inputmode="decimal" aria-label="Ciężar (kg)" placeholder="kg" value="${esc(first?.kg)}"></div><p class="hint warning" data-side-guard ${sideExceptions(d)?'':'hidden'}>Zachowano różnice lub niejednoznaczność stron. Otwórz Edytuj serie i szczegóły.</p><div data-rich-details ${d.open?'':'hidden'}>${details(d)}</div><p class="series-total sr-only">Tonaż: <strong>${flatten(p).reduce((n,s)=>n+(Number(s.kg.replace(',','.'))||0)*(Number(s.reps)||0),0).toLocaleString('pl-PL')} kg</strong></p><div class="result-controls"><div class="result-buttons"><button class="btn primary" type="submit">${d.open?'Zapisz korektę':'Zapisz wynik'}</button><button type="button" class="btn" data-rich-action="toggle">✎ ${d.open?'Zwiń':'Edytuj'} serie</button></div><div class="result-secondary"><button type="button" class="btn" data-panel="history" data-id="${esc(ex.id)}">Historia</button><button type="button" class="btn" data-panel="stats" data-id="${esc(ex.id)}">Statystyki</button></div></div>`;}
const trash='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6m4-6v6"/></svg>';
const sideMetadata=r=>canonical({...r,id:null,side:null,segments:r.segments.map(s=>({...s,id:null,kg:null,reps:null}))});
const perSide=d=>d.performance.loadConvention.unit==='kg'&&['per-implement','machine-indication'].includes(d.performance.loadConvention.basis);
function sharedPair(d,p){
 if(!p||!perSide(d))return false;
 const left=d.performance.rows.find(r=>r.id===p.leftId),right=d.performance.rows.find(r=>r.id===p.rightId);
 return !!left&&!!right&&equalSides(left,right)&&sideMetadata(left)===sideMetadata(right);
}
function sideExceptions(d){return d.performance.rows.some(r=>r.side!==null&&!sharedPair(d,pairFor(d,r)));}
function sideCaption(rows){return rows.map(r=>(r.side==='left'?'L':'P')+': '+r.segments.map(s=>`${s.reps||'?'} × ${s.kg||'?'} kg`).join(' → ')).join(' | ');}
function updateSideGuard(form,d){const blocked=sideExceptions(d);form.querySelectorAll('[data-quick]').forEach(el=>el.readOnly=blocked);const hint=form.querySelector('[data-side-guard]');if(hint)hint.hidden=!blocked;}
function details(d){
 const rows=d.performance.rows,used=new Set();let number=0;
 const groups=rows.map((row,i)=>{
  if(used.has(row.id))return '';number++;
  if(row.side===null)return rowHTML(d,row,i,number,false);
  const pair=pairFor(d,row),members=pair?[rows.find(r=>r.id===pair.leftId),rows.find(r=>r.id===pair.rightId)]:[row];members.forEach(r=>used.add(r.id));
  if(sharedPair(d,pair))return `<div data-side-pair>${rowHTML(d,members[0],rows.indexOf(members[0]),number,true)}</div>`;
  const choices=rows.filter(r=>r.side&&r.side!==row.side&&!pairFor(d,r)&&sameSet(row,r));
  return `<details class="side-exception" data-side-pair data-side-exception open><summary><span class="compact-number">${number}</span><span data-side-caption>${esc(sideCaption(members))}</span></summary><p class="hint warning">${!perSide(d)?'Konwencja kg nie pozwala na wspólny wpis L/P. Zachowano zapis; sprawdź znaczenie ciężaru.':!pair?'Brak ustalonej strony/pary. Niczego nie dopisano.':'Różne wartości lub metadane stron. Zachowano obie wersje.'}</p>${members.map(r=>rowHTML(d,r,rows.indexOf(r),number,false,true)).join('')}${pair&&perSide(d)?`<div class="exception-actions"><button type="button" class="btn" data-rich-action="merge-left" data-row="${i}">Użyj L dla obu</button><button type="button" class="btn" data-rich-action="merge-right" data-row="${i}">Użyj P dla obu</button></div>`:''}${!pair?`${choices.length?`<label>Druga strona<select data-pair-choice>${choices.map(r=>`<option value="${esc(r.id)}">Wiersz ${rows.indexOf(r)+1}</option>`).join('')}</select></label><button type="button" class="btn" data-rich-action="pair-existing" data-row="${i}">Ustal parę L/P</button>`:''}<span class="hint warning" data-missing-side>Brakująca strona wymaga decyzji.</span><button type="button" class="btn" data-rich-action="missing-side" data-row="${i}">Dodaj brakującą stronę (puste pola)</button>`:''}<button type="button" class="btn flat" data-rich-action="exception-done">Gotowe</button></details>`;
 }).join('');
 const canAdd=!d.ex.group||d.ex.targets.some(t=>!rows.some(r=>r.setId===t.id));
 return `${groups}<button type="button" class="btn wide compact-add" data-rich-action="add-set" ${canAdd?'':'disabled'}>＋ Dodaj serię</button>${d.ex.sideMode==='optional'&&d.allowSideDeclaration&&perSide(d)&&rows.length&&rows.every(r=>r.side===null)?'<details class="execution-choice"><summary>Sposób wykonania</summary><p class="hint">Wybierz tylko dla nowego wyniku, jeśli faktycznie wykonano obie strony. Dotychczasowe zapisy pozostają bez przeliczeń.</p><button type="button" class="btn" data-rich-action="sides">Wykonano osobno obie strony</button></details>':''}`;
}
function rowHTML(d,row,i,number,shared=false,exception=false){
 const drop=d.ex.targets.some(t=>t.id===row.setId&&t.drop),tag=shared?' data-common-pair="true"':'',side=row.side==='left'?'L':'P';
 const remove=(act,label,segment='')=>`<button type="button" class="btn flat compact-remove" data-rich-action="${act}" data-row="${i}" ${segment}${tag} aria-label="${esc(label)}">${trash}</button>`;
 return `<div class="compact-set" data-compact-set>${row.segments.map((segment,j)=>`<div class="individual-line${j?' drop-segment':''}" data-compact-row><span class="compact-number" aria-hidden="true">${exception?side+(j?' +'+j:''):j?'+'+j:number}</span><input data-row="${i}" data-segment="${j}" data-field="reps"${tag} aria-label="Powtórzenia serii ${number}${exception?' '+side:''}${j?', segment '+j:''}" placeholder="powt." inputmode="numeric" value="${esc(segment.reps)}" required><input data-row="${i}" data-segment="${j}" data-field="kg"${tag} aria-label="Ciężar serii ${number}${exception?' '+side:''}${j?', segment '+j:''}" placeholder="kg" inputmode="decimal" value="${esc(segment.kg)}" required>${j?remove('remove-segment','Usuń segment '+j+' serii '+number,`data-segment="${j}"`):remove('remove-set','Usuń serię '+number)}</div>`).join('')}${drop?`<button type="button" class="btn flat compact-add-segment" data-rich-action="add-segment" data-row="${i}"${tag}>＋ Dodaj segment</button>`:''}</div>`;
}
function refresh(form,d){form.innerHTML=contents(d);}
export function input(event){if(event.target.matches('[data-load-basis]')){change(event);return;}const form=event.target.closest('.performanceForm');if(!form)return;const d=drafts.get(key(form.dataset.id,form.dataset.session)),el=event.target;
 if(el.dataset.quick){const field=el.dataset.quick;if(sideExceptions(d)){el.value=d.performance.rows[0]?.segments[0]?.[field]??'';return;}if(d.custom&&d.quickInput!==el&&!confirm('Zastąpić wpisane wartości głównych segmentów? Pozostałe segmenty pozostaną bez zmian.')){el.value=d.performance.rows[0]?.segments[0]?.[field]??'';return;}d.quickInput=el;d.performance.rows.forEach(r=>r.segments[0][field]=el.value);d.custom=d.performance.rows.some(r=>!equalSides(r,d.performance.rows[0]));form.querySelector('[data-rich-details]').innerHTML=details(d);}
 else if(el.dataset.row!==undefined){
  d.quickInput=null;
  const row=d.performance.rows[+el.dataset.row],segment=+el.dataset.segment,field=el.dataset.field;
  const common=el.dataset.commonPair==='true';if(common&&!sharedPair(d,pairFor(d,row))){refresh(form,d);return;}
  row.segments[segment][field]=el.value;
  if(common){const other=otherSide(d,row);other.segments[segment][field]=el.value;const input=form.querySelector(`[data-row="${d.performance.rows.indexOf(other)}"][data-segment="${segment}"][data-field="${field}"]`);if(input)input.value=el.value;}
  d.custom=true;for(const field of ['reps','kg'])form.querySelector(`[data-quick="${field}"]`).value=d.performance.rows[0]?.segments[0]?.[field]??'';
 }
 updateSideGuard(form,d);
 form.querySelectorAll('[data-side-exception]').forEach(section=>{const first=section.querySelector('[data-row]');if(first){const r=d.performance.rows[+first.dataset.row],p=pairFor(d,r),members=p?[d.performance.rows.find(x=>x.id===p.leftId),d.performance.rows.find(x=>x.id===p.rightId)]:[r];section.querySelector('[data-side-caption]').textContent=sideCaption(members);}});
 form.querySelector('.series-total strong').textContent=flatten(d.performance).reduce((n,s)=>n+(Number(s.kg.replace(',','.'))||0)*(Number(s.reps)||0),0).toLocaleString('pl-PL')+' kg';
}
export function change(event){if(event.target.matches('[data-quick]')){const form=event.target.closest('.performanceForm');if(form)drafts.get(key(form.dataset.id,form.dataset.session)).quickInput=null;return;}if(!event.target.matches('[data-load-basis]'))return;const form=event.target.closest('form'),d=drafts.get(key(form.dataset.id,form.dataset.session));d.performance.loadConvention.basis=event.target.value||null;d.performance.loadConvention.description=event.target.selectedOptions[0].textContent;form.querySelector('[data-rich-details]').innerHTML=details(d);updateSideGuard(form,d);}
export function click(event){const b=event.target.closest('[data-rich-action]');if(!b)return;const form=b.closest('form'),d=drafts.get(key(form.dataset.id,form.dataset.session)),rows=d.performance.rows,row=rows[+b.dataset.row],act=b.dataset.richAction;
 const pair=row&&pairFor(d,row),other=row&&otherSide(d,row),common=b.dataset.commonPair==='true';
 if(common&&!sharedPair(d,pair)){alert('Strony zmieniły się. Zachowano wartości; sprawdź szczegóły.');refresh(form,d);return;}
 if(act==='toggle')d.open=!d.open;
 if((act==='side-mode'||act==='merge-left'||act==='merge-right')&&pair){
  if(act==='side-mode'&&pair.linked)pair.linked=false;
  else {
   const left=rows.find(r=>r.id===pair.leftId),right=rows.find(r=>r.id===pair.rightId);
   if(!perSide(d)){alert('Najpierw wyjaśnij konwencję kg. Nie skopiowano wartości stron.');return;}
   if(sideMetadata(left)!==sideMetadata(right)){alert('Strony mają różną strukturę segmentów lub metadane. Uporządkuj je ręcznie; niczego nie scalono.');return;}
   if(act==='side-mode'&&!equalSides(left,right)){b.closest('[data-side-pair]').querySelector('[data-merge-choice]').hidden=false;return;}
   if(!equalSides(left,right)){const from=act==='merge-left'?left:right,to=from===left?right:left;if(!confirm('Zastąpić wszystkie wartości '+(from===left?'prawej danymi lewej':'lewej danymi prawej')+' strony, także segmenty drop? Obie strony i ich identyfikatory pozostaną zapisane.'))return;copySegments(from,to);}
   pair.linked=true;
  }
 }
 if(act==='pair-existing'){
  const dest=rows.find(r=>r.id===b.closest('[data-side-pair]').querySelector('[data-pair-choice]').value);
  if(!dest||pairFor(d,dest)||!sameSet(row,dest)||dest.side===row.side)return;
  d.sidePairs.push({leftId:row.side==='left'?row.id:dest.id,rightId:row.side==='right'?row.id:dest.id,linked:false});
  rows.splice(rows.indexOf(dest),1);rows.splice(rows.indexOf(row)+1,0,dest);
 }
 if(act==='missing-side'){
  if(!confirm('Dodać brakującą stronę z pustymi polami? Uzupełnij rzeczywisty wynik przed zapisem.'))return;
  const dest={...row,id:crypto.randomUUID(),side:row.side==='left'?'right':'left',segments:row.segments.map(s=>({...s,id:crypto.randomUUID(),kg:'',reps:''}))};rows.splice(rows.indexOf(row)+1,0,dest);d.sidePairs.push({leftId:row.side==='left'?row.id:dest.id,rightId:row.side==='right'?row.id:dest.id,linked:false});
 }
 if(act==='add-segment'){row.segments.push({id:crypto.randomUUID(),kg:'',reps:''});if(common)other.segments.push({id:crypto.randomUUID(),kg:'',reps:''});}
 if(act==='remove-segment'&&row.segments.length>1){row.segments.splice(+b.dataset.segment,1);if(common)other.segments.splice(+b.dataset.segment,1);}
 if(act==='remove-set'){if(row.side&&!confirm('Usunąć '+(pair?'obie strony tej pary wraz z segmentami':'tę serię wraz z segmentami')+'? Zmiana trafi do wyniku dopiero po zapisie.'))return;const ids=new Set(pair?[pair.leftId,pair.rightId]:[row.id]);d.performance.rows=rows.filter(r=>!ids.has(r.id));d.sidePairs=d.sidePairs.filter(p=>p!==pair);}
 if(act==='add-set'){
  const target=d.ex.group?d.ex.targets.find(t=>!rows.some(r=>r.setId===t.id)):null;if(d.ex.group&&!target)return;
  const sides=d.ex.sideMode==='required'||rows.some(r=>r.side!==null)?['left','right']:[null],added=[];
  for(const side of sides){const r={id:crypto.randomUUID(),setId:target?.id??null,side,groupId:d.ex.group?.id??null,round:target?target.order+1:null,segments:Array.from({length:target?.drop?2:1},()=>({id:crypto.randomUUID(),kg:'',reps:''}))};rows.push(r);added.push(r);}
  if(added.length===2)d.sidePairs.push({leftId:added[0].id,rightId:added[1].id,linked:false});d.open=true;
 }
 if(act==='copy'){
  if(!confirm('Skopiować wartości na drugą stronę? Dodatkowe segmenty docelowe pozostaną bez zmian; możesz je poprawić osobno.'))return;
  let dest=other;
  if(!dest){dest={...row,id:crypto.randomUUID(),side:row.side==='left'?'right':'left',segments:[]};rows.push(dest);d.sidePairs.push({leftId:row.side==='left'?row.id:dest.id,rightId:row.side==='right'?row.id:dest.id,linked:false});}
  copySegments(row,dest);
 }
 if(act==='sides'&&d.allowSideDeclaration&&perSide(d)&&rows.every(r=>r.side===null)){
  if(!confirm('Rozdzielić L/P i skopiować obecne wartości na obie strony? Kg zachowają dotychczasowe znaczenie. Tonaż będzie sumą faktycznie zapisanych stron; możesz je edytować osobno.'))return;
  for(const r of [...rows]){r.side='left';const right={...r,id:crypto.randomUUID(),side:'right',segments:[]};copySegments(r,right);rows.push(right);d.sidePairs.push({leftId:r.id,rightId:right.id,linked:false});}d.open=true;
 }
 if(!['toggle','exception-done'].includes(act))d.custom=true;refresh(form,d);
}
export function performanceValue(value){
 const d=structuredClone({performance:value.performance,sidePairs:value.sidePairs});preparePairs(d);const p=d.performance;
 if(!p.rows.length)throw Error('Brak serii. Dodaj przynajmniej jedną rzeczywistą serię.');
 if(p.rows.some(r=>r.side!==null&&!pairFor(d,r)))throw Error('Niepełna lub nieustalona para L/P. Ustal brakującą stronę w edytorze.');
 for(const [i,row] of p.rows.entries())for(const [j,s] of row.segments.entries()){s.kg=s.kg.trim().replace(',','.');s.reps=s.reps.trim();if(!/^\d+(\.\d+)?$/.test(s.kg)||!/^[1-9]\d*$/.test(s.reps))throw Error(`Seria ${i+1}${row.side?' '+(row.side==='left'?'L':'P'):''}, segment ${j+1}: uzupełnij poprawne kg i powtórzenia.`);}
 return p;
}
export function performanceFor(id,sid){const d=drafts.get(key(id,sid));d.open=true;return performanceValue(d);}
export function forget(id,sid){drafts.delete(key(id,sid));}
/** Display only: pair by the editor's existing identity rules, never by values. */
export function summary(e,targets=[],asSets=false){
 if(!e)return '<span class="detail last-result">Brak zapisanego wyniku</span>';
 const rows=e.performance?.rows??[];if(!rows.length)return '<span class="detail last-result">Brak pełnych danych</span>';
 const d={performance:{rows:rows.filter(r=>Array.isArray(r.segments))}};preparePairs(d);
 const pairs=d.sidePairs.filter(p=>{const r=rows.find(r=>r.id===p.leftId);return rows.filter(x=>x.id===p.leftId).length===1&&rows.filter(x=>x.id===p.rightId).length===1;}),used=new Set(),groups=[];
 for(const [index,row] of rows.entries()){
  if(used.has(row))continue;
  const pair=pairs.find(p=>p.leftId===row.id||p.rightId===row.id),members=pair?[rows.find(r=>r.id===pair.leftId),rows.find(r=>r.id===pair.rightId)]:[row];
  members.forEach(r=>used.add(r));groups.push({members,index,target:targets.find(t=>t.id===row.setId)});
 }
 // Preserve the actual order of the recorded groups.
 const complete=r=>Array.isArray(r.segments)&&r.segments.length>0&&r.segments.every(s=>/^\d+(\.\d+)?$/.test(s.kg??'')&&/^[1-9]\d*$/.test(s.reps??''));
 const equal=g=>g.members.length===2&&equalSides(...g.members),unpaired=g=>g.members.length===1&&g.members[0].side!==null;
 const special=g=>g.members.some(r=>r.round&&!asSets);
 const role=r=>targets.find(t=>t.id===r.setId)?.role??(r.setId===null&&r.groupId===null&&r.segments?.length===1?'main':null);
 const drop=r=>!!targets.find(t=>t.id===r.setId)?.drop;
 const semantic=r=>canonical({...r,id:null,setId:null,side:null,round:asSets?null:r.round,segments:r.segments.map(s=>({...s,id:null,kg:Number(s.kg),reps:Number(s.reps)}))});
 const prescribedPairs=rows.every(r=>r.setId===null||r.side===null||rows.some(other=>other.side&&other.side!==r.side&&sameSet(r,other)));
 const first=rows[0],balanced=rows.every(r=>r.side===null)||rows.every(r=>r.side==='left'||r.side==='right')&&rows.filter(r=>r.side==='left').length===rows.filter(r=>r.side==='right').length;
 if(first&&balanced&&prescribedPairs&&rows.every(r=>complete(r)&&semantic(r)===semantic(first)&&role(r)===role(first)&&drop(r)===drop(first)&&r.groupId===first.groupId&&(asSets||r.round===null))){
  return `<span class="detail last-result">${role(first)==='backoff'?'back-off: ':''}${drop(first)?'dropset: ':''}${first.side?'L/P ':''}${first.segments.map(s=>`${esc(s.reps)} × ${esc(s.kg)} kg`).join(' → ')}</span>`;
 }
 const value=r=>(r.segments??[]).map(s=>`${esc(s.reps||'?')} × ${esc(s.kg||'?')} kg`).join(' → ')||'Brak pełnych danych';
 let extra=Math.max(0,...groups.filter(g=>g.target).map(g=>g.target.order+1));
 return `<span class="last-series">${groups.map(g=>{
  const r=g.members[0],label=r.round&&!asSets?'Runda '+r.round:'Seria '+(g.target?g.target.order+1:++extra),side=x=>x.side==='left'?'L':x.side==='right'?'P':'';
  const result=equal(g)?'L/P '+value(r):g.members.map(x=>`${side(x)?side(x)+' ':''}${value(x)}`).join(' · ');
  return `<span class="last-series-row"><span class="${g.target?.role==='backoff'||g.target?.drop||r.round&&!asSets?'set-kind':'sr-only'}">${esc(label)}${g.target?.role==='backoff'?' · back-off':''}${g.target?.drop?' · dropset':''}: </span>${result}${unpaired(g)?' · para L/P nieustalona':''}${g.members.every(complete)?'':' · niepełny wynik'}</span>`;
 }).join('')}</span>`;
}
