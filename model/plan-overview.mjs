/** Read-only plan/session index and calendar aggregates. Never migrates history. */
import {snapshotFor,structuredSnapshot} from './journal.mjs';
import {flatten} from './performance.mjs';
import {PLAN_ID,buildPlan} from './v2-plan.mjs';
import {storedPlanModel} from './plan-import.mjs';
export const SOURCE='@source',UNASSIGNED='@unassigned';
export const METRICS=['tonnage','sets','reps','workouts'];
const DAY=86400000,iso=d=>d.toISOString().slice(0,10);
export function warsawDate(now=new Date()){return new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Warsaw',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);}
function date(value){const d=new Date(value+'T12:00:00Z');if(!/^\d{4}-\d{2}-\d{2}$/.test(value??'')||!Number.isFinite(+d)||iso(d)!==value)throw Error('Nieprawidłowa data zakresu.');return d;}
export function weekOf(value){
 const d=date(value),monday=new Date(+d-((d.getUTCDay()+6)%7)*DAY),thursday=new Date(+monday+3*DAY),year=thursday.getUTCFullYear();
 const jan4=date(year+'-01-04'),firstMonday=new Date(+jan4-((jan4.getUTCDay()+6)%7)*DAY);
 return {id:year+'-W'+String(1+Math.round((monday-firstMonday)/(7*DAY))).padStart(2,'0'),from:iso(monday),to:iso(new Date(+monday+6*DAY))};
}
function recordedVersion(catalog,session){
 const link=catalog?.sessionVersions?.[session?.id];
 return link?.provenance==='session-start'?catalog.planVersions.find(v=>v.id===link.versionId&&v.provenance==='recorded'):null;
}
export function sessionPlanId(data,session,catalog=null){
 if(!session)return UNASSIGNED;
 const snap=snapshotFor(data,session.id);
 if(snap&&snap.id===session.journalSnapshotId)return snap.planVersionId;
 const recorded=!session.journalSnapshotId&&recordedVersion(catalog,session);
 return recorded?'@legacy:'+recorded.id:!session.journalSnapshotId&&Array.isArray(session.sourceExerciseIds)?SOURCE:UNASSIGNED;
}
// Append order records transitions. Invalid/missing timestamps never become dates.
function activationTime(value){
 if(typeof value!=='string'||!/^\d{4}-\d\d-\d\dT(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,3})?(?:Z|[+-]\d\d:\d\d)$/.test(value))return null;
 try{date(value.slice(0,10));}catch{return null;}
 return Number.isFinite(Date.parse(value))?value:null;
}
export function activationPeriods(data,planId){
 const log=Array.isArray(data.trainingJournal?.activations)?data.trainingJournal.activations:[];
 return log.flatMap((a,i)=>{
  if(a?.planVersionId!==planId)return [];
  const from=activationTime(a.at),next=log[i+1],ongoing=i===log.length-1&&data.trainingJournal.activePlanVersionId===planId;
  let to=activationTime(next?.at);if(from&&to&&Date.parse(to)<Date.parse(from))to=null;
  return [{from,to,ongoing,uncertain:!from||!ongoing&&!to}];
 });
}
/** Actual session dates on the existing exercise plot; no invented observations.
 * A missing ISO week or a known intervening plan activation breaks the line.
 */
export function exerciseTimeline(data,entries){
 const sessions=new Map(data.sessions.map(s=>[s.id,s]));
 const times=entries.map(e=>{try{return +date(sessions.get(e.sessionId)?.date);}catch{return null;}}),known=times.filter(t=>t!==null),min=Math.min(...known),max=Math.max(...known);
 return entries.map((e,i)=>{
  const previous=entries[i-1],s=sessions.get(e.sessionId),prior=previous&&sessions.get(previous.sessionId);
  let split=!previous||times[i]===null||times[i-1]===null;
  if(!split){
   const a=activationTime(snapshotFor(data,prior.id)?.startedAt),b=activationTime(snapshotFor(data,s.id)?.startedAt),priorPlan=sessionPlanId(data,prior),plan=sessionPlanId(data,s);
   split=+date(weekOf(s.date).from)-date(weekOf(prior.date).from)>7*DAY||priorPlan!==plan;
   if(a&&b)split||=(data.trainingJournal?.activations??[]).some(x=>x.planVersionId!==plan&&activationTime(x.at)&&Date.parse(x.at)>Date.parse(a)&&Date.parse(x.at)<=Date.parse(b));
  }
  return {x:times[i]===null?null:max===min?0.5:(times[i]-min)/(max-min),split};
 });
}
export function plans(data,catalog=null){
 const j=data.trainingJournal,current=j?.activePlanVersionId??SOURCE,rows=new Map();
 function add(version,model){if(rows.has(version.id))return;const observed=version.source?.reference==='observed-at-session-start';rows.set(version.id,{id:version.id,label:observed?'Szkielet źródłowy · '+version.units.map(u=>u.name).join(', '):version.label,version,model,kind:observed?'observed':'version'});}
 for(const v of j?.model.planVersions??[])add(v,j.model);
 for(const s of j?.sessionSnapshots??[]){const v=s.model.planVersions.find(v=>v.id===s.planVersionId);if(v)add(v,s.model);}
 for(const p of j?.importedPlans??[])if(p.planVersion)add(p.planVersion,null);
 if(!rows.has(PLAN_ID)){const model=buildPlan('preview');add(model.planVersions[0],model);}
 rows.set(SOURCE,{id:SOURCE,label:'Szkielet źródłowy · zapisane ID / bieżące dane',kind:'source',model:null,version:null});
 for(const s of data.sessions){const v=recordedVersion(catalog,s),id=v&&'@legacy:'+v.id;if(v&&sessionPlanId(data,s,catalog)===id)rows.set(id,{id,label:'Szkielet zapisany · '+v.planId+' · '+v.id,kind:'recorded',version:v,model:null});}
 if(data.sessions.some(s=>sessionPlanId(data,s,catalog)===UNASSIGNED))rows.set(UNASSIGNED,{id:UNASSIGNED,label:'Nieprzypisane / historyczne',kind:'unassigned',model:null,version:null});
 return [...rows.values()].map(p=>{
  const stored=p.kind==='version'?storedPlanModel(data,p.id):null;if(stored){p={...p,model:stored,version:stored.planVersions.find(v=>v.id===p.id)};}
  const sessions=data.sessions.filter(s=>sessionPlanId(data,s,catalog)===p.id),activations=(Array.isArray(j?.activations)?j.activations:[]).filter(a=>a?.planVersionId===p.id),periods=activationPeriods(data,p.id);
  const dates=sessions.filter(s=>s.status==='done'&&p.kind!=='unassigned'&&((snapshotFor(data,s.id)&&snapshotFor(data,s.id).id===s.journalSnapshotId)||!s.journalSnapshotId&&recordedVersion(catalog,s))).flatMap(s=>{try{date(s.date);return [s.date];}catch{return [];}}).sort();
  const trainingRange=dates.length?{from:dates[0],to:dates.at(-1)}:null;
  return {...p,current:p.id===current,sessions:sessions.length,activatedAt:activationTime(activations.at(-1)?.at),periods,trainingRange,currentPeriodUnknown:p.id===current&&!periods.some(p=>p.ongoing),status:p.id===current?'current':sessions.length||activations.length?'previous':p.id===PLAN_ID&&!stored&&!j?.model.planVersions.some(v=>v.id===PLAN_ID)?'available':'saved',canActivate:p.kind==='version'&&(!!stored||p.id===PLAN_ID&&!j?.model.planVersions.some(v=>v.id===PLAN_ID)&&!j?.sessionSnapshots.some(s=>s.planVersionId===PLAN_ID))};
 }).filter(p=>p.id!==SOURCE||p.current||p.sessions);
}
/** One execution row = one performed set (L/P separate); drop segments are not extra sets.
 * Unknown legacy series are missing metrics, never inferred from plan targets.
 */
export function entryTotals(data,entry){
 const native=structuredSnapshot(snapshotFor(data,entry.sessionId))&&entry.performance?.version===2;
 const segments=native?flatten(entry.performance):entry.series;
 if(!Array.isArray(segments)||!segments.length)return {tonnage:null,sets:null,reps:null};
 const valid=segments.every(s=>Number.isFinite(Number(s.kg))&&Number(s.kg)>=0&&Number.isSafeInteger(Number(s.reps))&&Number(s.reps)>0);
 return {sets:native?entry.performance.rows.length:segments.length,reps:valid?segments.reduce((n,s)=>n+Number(s.reps),0):null,tonnage:valid?segments.reduce((n,s)=>n+Number(s.kg)*Number(s.reps),0):null};
}
export function weeklyStats(data,planId,{from,to,today=warsawDate(),catalog=null}={}){
 date(today);to??=today;from??=iso(new Date(+date(weekOf(to).from)-77*DAY));date(from);date(to);
 if(from>to)throw Error('Początek zakresu musi poprzedzać koniec.');
 if((date(to)-date(from))/DAY>36400)throw Error('Wybierz zakres nie dłuższy niż 100 lat.');
 const rows=[],byWeek=new Map();
 for(let d=date(weekOf(from).from);iso(d)<=to;d=new Date(+d+7*DAY)){
  const w={...weekOf(iso(d)),tonnage:0,sets:0,reps:0,workouts:0,missing:{tonnage:0,sets:0,reps:0,workouts:0},unknownConvention:0};
  w.partial=w.from<from||w.to>to||w.to>today;rows.push(w);byWeek.set(w.id,w);
 }
 let invalidDates=0;
 for(const s of data.sessions){
  if(s.status!=='done'||sessionPlanId(data,s,catalog)!==planId)continue;
  let week;try{week=weekOf(s.date);}catch{invalidDates++;continue;}
  if(s.date<from||s.date>to)continue;const w=byWeek.get(week.id);w.workouts++;
  const entries=data.entries.filter(e=>e.sessionId===s.id);
  if(!entries.length){for(const k of ['tonnage','sets','reps'])w.missing[k]++;}
  for(const e of entries){
   const totals=entryTotals(data,e);
   for(const k of ['tonnage','sets','reps']){if(totals[k]===null)w.missing[k]++;else w[k]+=totals[k];}
   if(!e.performance?.loadConvention?.basis)w.unknownConvention++;
  }
 }
 rows.forEach((w,i)=>{const prev=rows[i-1];w.delta={};for(const k of METRICS){w.delta[k]=!prev||w.partial||prev.partial||w.missing[k]||prev.missing[k]?null:{absolute:w[k]-prev[k],percent:prev[k]===0?null:100*(w[k]/prev[k]-1)};}});
 const totals=Object.fromEntries(METRICS.map(k=>[k,rows.reduce((n,w)=>n+w[k],0)])),missing=Object.fromEntries(METRICS.map(k=>[k,rows.reduce((n,w)=>n+w.missing[k],0)]));
 return {from,to,rows,totals,missing,invalidDates};
}
