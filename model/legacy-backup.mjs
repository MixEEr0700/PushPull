/** Read-only compatibility adapter for actual v1 and v2 documents.
 * Preserve the complete original and exact input text. Do not migrate to the new
 * domain model, infer old plan snapshots, split notes or normalize performances.
 */
import {parseJson, requireThat as check, record, canonical, freeze, portable} from './backup-json.mjs';
const TYPES=['PUSH A','PULL A','PUSH B','PULL B'];
const text=x=>typeof x==='string';
const id=x=>text(x) && /^[A-Za-z0-9_.-]+$/.test(x) && !Object.hasOwn(Object.prototype,x);
const date=x=>text(x) && /^\d{4}-\d\d-\d\d$/.test(x) && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0,10)===x;
const number=(x,integer=false)=>(typeof x==='number'||text(x)) && /^\d+(?:\.\d+)?$/.test(String(x)) && Number.isFinite(Number(x)) && Number(x)>=0 && (!integer || Number.isSafeInteger(Number(x)) && Number(x)>0);
function validateV1(x) {
  check(record(x) && x.version===1 && record(x.exercises) && Object.keys(x.exercises).every(t=>TYPES.includes(t)) &&
    Array.isArray(x.sessions) && Array.isArray(x.entries) && TYPES.includes(x.nextType) && (x.activeId===null || id(x.activeId)), 'legacy v1 structure');
  const exercises=new Map(),sessions=new Map(),sequences=new Set(),entries=new Set(),pairs=new Set();
  for (const type of TYPES) {
    check(Array.isArray(x.exercises[type]) && x.exercises[type].length>0, 'legacy workout');
    for (const e of x.exercises[type]) {
      check(record(e) && id(e.id) && !exercises.has(e.id) && text(e.name) && e.name.trim() && Number.isSafeInteger(e.sets) && e.sets>0 &&
        ['target','initialKg','tempo','rir','notes'].every(k=>text(e[k])) && (e.description===undefined || text(e.description)), 'legacy exercise');
      exercises.set(e.id,type);
    }
  }
  for (const s of x.sessions) {
    check(record(s) && id(s.id) && !sessions.has(s.id) && TYPES.includes(s.type) && date(s.date) && Number.isSafeInteger(s.seq) && s.seq>0 &&
      !sequences.has(s.seq) && ['active','done'].includes(s.status), 'legacy session');
    sessions.set(s.id,s);sequences.add(s.seq);
  }
  const active=x.sessions.filter(s=>s.status==='active');
  check(active.length<=1 && (active[0]?.id??null)===x.activeId, 'legacy active session');
  for (const e of x.entries) {
    const s=sessions.get(e?.sessionId),pair=JSON.stringify([e?.sessionId,e?.exerciseId]);
    check(record(e) && id(e.id) && !entries.has(e.id) && s && exercises.get(e.exerciseId)===s.type && !pairs.has(pair) && number(e.kg) && number(e.reps,true), 'legacy result relation');
    if (e.series!=null) check(Array.isArray(e.series) && e.series.length>0 && e.series.every(r=>record(r) && number(r.kg) && number(r.reps,true) && Number.isFinite(Number(r.kg)*Number(r.reps))), 'legacy series');
    if (e.series?.length) check(Number(e.kg)===Number(e.series[0].kg) && Number(e.reps)===Number(e.series[0].reps), 'legacy first series');
    for (const key of ['createdAt','correctedAt']) if (e[key]!==undefined) check(text(e[key]) && Number.isFinite(Date.parse(e[key])), 'legacy result timestamp');
    entries.add(e.id);pairs.add(pair);
  }
  if (x.changes!==undefined) {
    check(record(x.changes), 'legacy changes');
    for (const [key,changes] of Object.entries(x.changes)) check(exercises.has(key) && Array.isArray(changes) && changes.every(c=>record(c) && date(c.date) && text(c.kind) && text(c.text)), 'legacy technique change');
  }
  return x;
}
function parameters(exercises) {return exercises.map(ex=>{const value={...ex};delete value.notes;return value;});}
function validateV2(x) {
  check(record(x) && x.format==='pushpull-backup' && x.version===2, 'legacy v2 format');
  validateV1(x.data);
  const c=x.catalog;
  check(record(c) && Array.isArray(c.plans) && Array.isArray(c.planVersions) && record(c.sessionVersions), 'legacy catalog');
  const plans=new Map(),versions=new Map();
  for (const p of c.plans) {
    check(record(p) && TYPES.includes(p.id) && !plans.has(p.id) && text(p.label) && text(p.currentVersion), 'legacy catalog plan');plans.set(p.id,p);
  }
  check(plans.size===4, 'legacy catalog missing plan');
  for (const v of c.planVersions) {
    check(record(v) && text(v.id) && v.id && !versions.has(v.id) && plans.has(v.planId) && ['recorded','legacy-current-only'].includes(v.provenance) && Array.isArray(v.exercises), 'legacy plan version');
    const probe=structuredClone(x.data);
    probe.exercises[v.planId]=v.exercises.map(e=>({...e,notes:''}));probe.sessions=[];probe.entries=[];probe.changes={};probe.activeId=null;
    validateV1(probe); versions.set(v.id,v);
  }
  for (const p of plans.values()) {
    const v=versions.get(p.currentVersion);
    check(v && v.planId===p.id && canonical(v.exercises)===canonical(parameters(x.data.exercises[p.id])), 'legacy current parameters');
  }
  check(Object.keys(c.sessionVersions).length===x.data.sessions.length, 'legacy session version count');
  for (const s of x.data.sessions) {
    const link=c.sessionVersions[s.id],v=versions.get(link?.versionId);
    check(record(link) && ['legacy-current-only','session-start'].includes(link.provenance) && v?.planId===s.type, 'legacy session version relation');
  }
  if (x.archives!==undefined) {
    check(Array.isArray(x.archives), 'legacy archives');const ids=new Set();
    for (const a of x.archives) {
      check(record(a) && text(a.id) && a.id && !ids.has(a.id) && text(a.kind) && text(a.createdAt) && Number.isFinite(Date.parse(a.createdAt)) && (a.raw===null || text(a.raw)), 'legacy archive');ids.add(a.id);
    }
  }
}
export function readLegacyBackup(raw) {
  const original=parseJson(raw);portable(original);
  if (original?.format==='pushpull-backup' && original.version===2) validateV2(original);
  else validateV1(original);
  return freeze({formatVersion:original.version,semantics:'legacy-unknown',raw,original,
    data:original.version===1?original:original.data,
    catalog:original.version===2?original.catalog:null});
}
