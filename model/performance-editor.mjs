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
  const performance=entry?.performance?structuredClone(entry.performance):newPerformance(ex,last?.performance);
  const first=performance.rows[0].segments[0];
  const custom=performance.rows.some(r=>r.segments.some(s=>s.kg!==first.kg||s.reps!==first.reps));
  d={ex,performance,open:false,custom};drafts.set(k,d);
 }
 d.ex=ex;preparePairs(d);
 return `<div class="panel"><h3>${esc(ex.name)}</h3><form class="performanceForm" novalidate data-id="${ex.id}" data-session="${sid}">${contents(d)}<button class="btn primary wide spaced" type="submit">${entry?'Zapisz korektę':'Zapisz wynik'}</button></form></div>`;
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
  const unambiguous=left.setId!==null||rows.filter(r=>r.side==='left'&&sameSet(left,r)).length===1;
  if(candidates.length===1&&unambiguous){const right=candidates[0];pairs.push({leftId:left.id,rightId:right.id,linked:equalSides(left,right)});used.add(left.id);used.add(right.id);}
 }
 d.sidePairs=pairs;
}
const pairFor=(d,row)=>d.sidePairs.find(p=>p.leftId===row.id||p.rightId===row.id);
const otherSide=(d,row)=>{const p=pairFor(d,row);return p&&d.performance.rows.find(r=>r.id===(row.side==='left'?p.rightId:p.leftId));};
function copySegments(from,to){to.segments=from.segments.map((s,i)=>({...s,id:to.segments[i]?.id??crypto.randomUUID()}));}
function contents(d){const ex=d.ex,p=d.performance;return `<p class="hint">${esc(p.loadConvention.description)}. Tonaż: suma zapisanych kg × powtórzenia; bez mnożenia przez dwa.</p>${ex.loadConvention.basis===null?`<label>Znaczenie ciężaru<select data-load-basis><option value="">Nieokreślone</option>${[['per-implement','Jeden hantel'],['machine-indication','Wskazanie urządzenia'],['combined','Łącznie']].map(([v,l])=>`<option value="${v}" ${p.loadConvention.basis===v?'selected':''}>${l}</option>`).join('')}</select></label>`:''}<div class="grid2"><label>Powtórzenia<input data-quick="reps" inputmode="numeric" aria-label="Szybkie powtórzenia"></label><label>Ciężar (kg)<input data-quick="kg" inputmode="decimal" aria-label="Ciężar (kg)"></label></div><p class="hint">Szybki wpis uzupełnia główne segmenty wszystkich serii. ${p.rows.some(r=>r.side!==null)?'Domyślnie uzupełnia obie strony L/P; osobne wartości zastępuje dopiero po potwierdzeniu. ':''}Back-off i drop poprawisz poniżej.</p><button type="button" class="btn wide" data-rich-action="toggle">✎ ${d.open?'Zwiń':'Edytuj'} serie</button><div data-rich-details ${d.open?'':'hidden'}>${details(d)}</div><p class="series-total">Tonaż: <strong>${flatten(p).reduce((n,s)=>n+(Number(s.kg.replace(',','.'))||0)*(Number(s.reps)||0),0).toLocaleString('pl-PL')} kg</strong></p>`;}
function details(d){const ex=d.ex,p=d.performance;return `${ex.sideMode==='optional'&&p.rows.every(r=>r.side===null)?'<button type="button" class="btn spaced" data-rich-action="sides">Rozdziel L/P i skopiuj wartości</button>':''}${p.rows.map((row,i)=>rowHTML(d,row,i)).join('')}${!ex.group?'<button type="button" class="btn wide spaced" data-rich-action="add-set">＋ Dodaj serię bez określonego celu</button>':''}`;}
function rowHTML(d,row,i){const t=d.ex.targets.find(t=>t.id===row.setId);const side=row.side==='left'?'Lewa':row.side==='right'?'Prawa':'';return `<div class="spaced"><b>${row.round?'Runda '+row.round:'Seria '+(t?t.order+1:i+1)} ${side}${t?.role==='backoff'?' · back-off':''}</b><div class="hint">${t?`${rangeText(t.reps)} powt. · RIR ${rangeText(t.rir)} · tempo ${tempoText(t.tempo)}${t.drop?' · dropset':''}`:'Cel nieokreślony'}</div>${row.segments.map((s,j)=>`<div class="grid2"><label>Powtórzenia<input data-row="${i}" data-segment="${j}" data-field="reps" aria-label="Powtórzenia ${i+1}.${j+1}" inputmode="numeric" value="${esc(s.reps)}" required></label><label>${t?.drop?'Segment '+(j+1)+' · ':''}kg<input data-row="${i}" data-segment="${j}" data-field="kg" aria-label="Ciężar ${i+1}.${j+1}" inputmode="decimal" value="${esc(s.kg)}" required></label></div>${t?.drop?`<button type="button" class="btn" data-rich-action="remove-segment" data-row="${i}" data-segment="${j}">− Segment ${j+1}</button>`:''}`).join('')}${t?.drop?`<button type="button" class="btn" data-rich-action="add-segment" data-row="${i}">＋ Segment</button>`:''}${row.side?`${pairFor(d,row)&&row.side==='left'?`<button type="button" class="btn spaced" data-rich-action="side-mode" data-row="${i}" aria-pressed="${!pairFor(d,row).linked}">${pairFor(d,row).linked?'Razem L/P · Edytuj osobno':'Osobno L/P · Połącz L → P'}</button>`:''}<button type="button" class="btn spaced" data-rich-action="copy" data-row="${i}">Kopiuj ${side==='Lewa'?'L → P':'P → L'}</button>`:''}${!d.ex.group?`<button type="button" class="btn spaced" data-rich-action="remove-set" data-row="${i}">− Seria ${i+1}</button>`:''}</div>`;}
function refresh(form,d){const submit=form.querySelector('[type=submit]').outerHTML;form.innerHTML=contents(d)+submit;}
export function input(event){if(event.target.matches('[data-load-basis]')){change(event);return;}const form=event.target.closest('.performanceForm');if(!form)return;const d=drafts.get(key(form.dataset.id,form.dataset.session)),el=event.target;
 if(el.dataset.quick){const field=el.dataset.quick;if((d.custom||d.sidePairs.some(p=>!p.linked)&&d.quickInput!==el)&&!confirm('Zastąpić wpisane wartości głównych segmentów? Pozostałe segmenty pozostaną bez zmian.')){el.value='';return;}d.custom=false;d.quickInput=el;d.performance.rows.forEach(r=>r.segments[0][field]=el.value);form.querySelector('[data-rich-details]').innerHTML=details(d);}
 else if(el.dataset.row!==undefined){
  const row=d.performance.rows[+el.dataset.row],segment=+el.dataset.segment,field=el.dataset.field;
  row.segments[segment][field]=el.value;
  if(pairFor(d,row)?.linked){const other=otherSide(d,row);other.segments[segment][field]=el.value;const input=form.querySelector(`[data-row="${d.performance.rows.indexOf(other)}"][data-segment="${segment}"][data-field="${field}"]`);if(input)input.value=el.value;}
  d.custom=true;
 }
 form.querySelector('.series-total strong').textContent=flatten(d.performance).reduce((n,s)=>n+(Number(s.kg.replace(',','.'))||0)*(Number(s.reps)||0),0).toLocaleString('pl-PL')+' kg';
}
export function change(event){if(event.target.matches('[data-quick]')){const form=event.target.closest('.performanceForm');if(form)drafts.get(key(form.dataset.id,form.dataset.session)).quickInput=null;return;}if(!event.target.matches('[data-load-basis]'))return;const form=event.target.closest('form'),d=drafts.get(key(form.dataset.id,form.dataset.session));d.performance.loadConvention.basis=event.target.value||null;d.performance.loadConvention.description=event.target.selectedOptions[0].textContent;}
export function click(event){const b=event.target.closest('[data-rich-action]');if(!b)return;const form=b.closest('form'),d=drafts.get(key(form.dataset.id,form.dataset.session)),rows=d.performance.rows,row=rows[+b.dataset.row],act=b.dataset.richAction;
 const pair=row&&pairFor(d,row),other=row&&otherSide(d,row);
 if(act==='toggle')d.open=!d.open;
 if(act==='side-mode'&&pair){
  if(pair.linked)pair.linked=false;
  else {if(!equalSides(row,other)&&!confirm('Połączyć L/P tej serii? Wartości lewej strony zastąpią prawą, również segmenty. Inne serie pozostaną bez zmian.'))return;copySegments(row,other);pair.linked=true;}
 }
 if(act==='add-segment'){row.segments.push({id:crypto.randomUUID(),kg:'',reps:''});if(pair?.linked)other.segments.push({id:crypto.randomUUID(),kg:'',reps:''});}
 if(act==='remove-segment'&&row.segments.length>1){row.segments.splice(+b.dataset.segment,1);if(pair?.linked)other.segments.splice(+b.dataset.segment,1);}
 if(act==='remove-set'&&rows.length>1){rows.splice(+b.dataset.row,1);d.sidePairs=d.sidePairs.filter(p=>p!==pair);}
 if(act==='add-set'){
  const sides=d.ex.sideMode==='required'||rows.some(r=>r.side!==null)?['left','right']:[null],added=[];
  for(const side of sides){const r={id:crypto.randomUUID(),setId:null,side,groupId:null,round:null,segments:[{id:crypto.randomUUID(),kg:'',reps:''}]};rows.push(r);added.push(r);}
  if(added.length===2)d.sidePairs.push({leftId:added[0].id,rightId:added[1].id,linked:true});d.open=true;
 }
 if(act==='copy'){
  if(!confirm('Skopiować wartości na drugą stronę? Potem możesz je poprawić.'))return;
  let dest=other;
  if(!dest){dest={...row,id:crypto.randomUUID(),side:row.side==='left'?'right':'left',segments:[]};rows.push(dest);d.sidePairs.push({leftId:row.side==='left'?row.id:dest.id,rightId:row.side==='right'?row.id:dest.id,linked:false});}
  copySegments(row,dest);
 }
 if(act==='sides'&&rows.every(r=>r.side===null)){
  if(!confirm('Rozdzielić L/P i skopiować obecne wartości na obie strony? Kg zachowają dotychczasowe znaczenie. Tonaż będzie sumą faktycznie zapisanych stron; możesz je edytować osobno.'))return;
  for(const r of [...rows]){r.side='left';const right={...r,id:crypto.randomUUID(),side:'right',segments:[]};copySegments(r,right);rows.push(right);d.sidePairs.push({leftId:r.id,rightId:right.id,linked:true});}d.open=true;
 }
 if(act!=='toggle')d.custom=true;refresh(form,d);
}
export function performanceFor(id,sid){const d=drafts.get(key(id,sid));d.open=true;const p=structuredClone(d.performance);for(const row of p.rows)for(const s of row.segments){s.kg=s.kg.trim().replace(',','.');s.reps=s.reps.trim();if(!/^\d+(\.\d+)?$/.test(s.kg)||!/^[1-9]\d*$/.test(s.reps))throw Error('Sprawdź ciężary i powtórzenia wszystkich serii, stron i segmentów.');}return p;}
export function forget(id,sid){drafts.delete(key(id,sid));}
/** Display only: pair by the editor's existing identity rules, never by values. */
export function summary(e,targets=[],asSets=false){
 if(!e)return '<span class="detail last-result">Brak zapisanego wyniku</span>';
 const rows=e.performance?.rows??[];if(!rows.length)return '<span class="detail last-result">Brak pełnych danych</span>';
 const d={performance:{rows:rows.filter(r=>Array.isArray(r.segments))}};preparePairs(d);
 const pairs=d.sidePairs.filter(p=>{const r=rows.find(r=>r.id===p.leftId);return rows.filter(x=>x.id===p.leftId).length===1&&rows.filter(x=>x.id===p.rightId).length===1&&rows.filter(x=>x.side==='left'&&sameSet(x,r)).length===1&&rows.filter(x=>x.side==='right'&&sameSet(x,r)).length===1;}),used=new Set(),groups=[];
 for(const [index,row] of rows.entries()){
  if(used.has(row))continue;
  const pair=pairs.find(p=>p.leftId===row.id||p.rightId===row.id),members=pair?[rows.find(r=>r.id===pair.leftId),rows.find(r=>r.id===pair.rightId)]:[row];
  members.forEach(r=>used.add(r));groups.push({members,index,target:targets.find(t=>t.id===row.setId)});
 }
 groups.sort((a,b)=>(a.target?.order??Infinity)-(b.target?.order??Infinity)||a.index-b.index);
 const complete=r=>Array.isArray(r.segments)&&r.segments.length>0&&r.segments.every(s=>/^\d+(\.\d+)?$/.test(s.kg??'')&&/^[1-9]\d*$/.test(s.reps??''));
 const equal=g=>g.members.length===2&&equalSides(...g.members),unpaired=g=>g.members.length===1&&g.members[0].side!==null;
 const special=g=>g.target?.role==='backoff'||g.target?.drop||g.members.some(r=>r.segments?.length!==1||r.round&&!asSets);
 if(groups.length&&groups.every(g=>!unpaired(g)&&!special(g)&&g.members.every(complete)&&(g.members.length===1||equal(g)))&&groups.every(g=>equalSides(g.members[0],groups[0].members[0])&&g.members[0].groupId===groups[0].members[0].groupId)){
  const s=groups[0].members[0].segments[0];return `<span class="detail last-result">${esc(s.reps)} × ${esc(s.kg)} kg</span>`;
 }
 const value=r=>(r.segments??[]).map(s=>`${esc(s.reps||'?')} × ${esc(s.kg||'?')} kg`).join(' → ')||'Brak pełnych danych';
 let extra=Math.max(0,...groups.filter(g=>g.target).map(g=>g.target.order+1));
 return `<span class="last-series">${groups.map(g=>{
  const r=g.members[0],label=r.round&&!asSets?'Runda '+r.round:'Seria '+(g.target?g.target.order+1:++extra),side=x=>x.side==='left'?'L':x.side==='right'?'P':'';
  const result=equal(g)?value(r):g.members.map(x=>`${side(x)?side(x)+' ':''}${value(x)}`).join(' · ');
  return `<span class="last-series-row"><span class="${g.target?.role==='backoff'||g.target?.drop||r.round&&!asSets?'set-kind':'sr-only'}">${esc(label)}${g.target?.role==='backoff'?' · back-off':''}${g.target?.drop?' · dropset':''}: </span>${result}${unpaired(g)?' · para L/P nieustalona':''}${g.members.every(complete)?'':' · niepełny wynik'}</span>`;
 }).join('')}</span>`;
}
