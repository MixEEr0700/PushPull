/** Read-only compatibility adapter for actual v1 and v2 documents.
 * Preserve the complete original and exact input text. Do not migrate to the new
 * domain model, infer old plan snapshots, split notes or normalize performances.
 */
import {parseJson, requireThat as check, record, canonical, freeze, portable, immutableJSON} from './backup-json.mjs';
const verifiedViews=new WeakSet(),sourceVersions=new WeakMap();
const TYPES=['PUSH A','PULL A','PUSH B','PULL B'];
const text=x=>typeof x==='string';
const id=x=>text(x) && /^[A-Za-z0-9_.-]+$/.test(x) && !Object.hasOwn(Object.prototype,x);
const date=x=>text(x) && /^\d{4}-\d\d-\d\d$/.test(x) && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0,10)===x;
const number=(x,integer=false)=>(typeof x==='number'||text(x)) && /^\d+(?:\.\d+)?$/.test(String(x)) && Number.isFinite(Number(x)) && Number(x)>=0 && (!integer || Number.isSafeInteger(Number(x)) && Number(x)>0);
function validateV1(x) {
  const declared=(x?.trainingJournal?.model?.planVersions||[]).filter(v=>v.executionVersion===2).flatMap(v=>(v.units||[]).map(u=>u.id));
  const types=Object.keys(x?.exercises||{});
  check(record(x) && x.version===1 && record(x.exercises) && TYPES.every(t=>types.includes(t)) && types.every(t=>TYPES.includes(t)||id(t)&&declared.includes(t)) &&
    Array.isArray(x.sessions) && Array.isArray(x.entries) && TYPES.includes(x.nextType) && (x.activeId===null || id(x.activeId)), 'legacy v1 structure');
  const exercises=new Map(),sessions=new Map(),sequences=new Set(),entries=new Set(),pairs=new Set();
  for (const type of types) {
    check(Array.isArray(x.exercises[type]) && (x.exercises[type].length>0||!TYPES.includes(type)), 'legacy workout');
    for (const e of x.exercises[type]) {
      check(record(e) && id(e.id) && !exercises.has(e.id) && text(e.name) && e.name.trim() && Number.isSafeInteger(e.sets) && e.sets>0 &&
        ['target','initialKg','tempo','rir','notes'].every(k=>text(e[k])) && (e.description===undefined || text(e.description)), 'legacy exercise');
      exercises.set(e.id,type);
    }
  }
  for (const s of x.sessions) {
    check(record(s) && id(s.id) && !sessions.has(s.id) && types.includes(s.type) && date(s.date) && Number.isSafeInteger(s.seq) && s.seq>0 &&
      !sequences.has(s.seq) && ['active','done'].includes(s.status), 'legacy session');
    sessions.set(s.id,s);sequences.add(s.seq);
  }
  const active=x.sessions.filter(s=>s.status==='active');
  check(active.length<=1 && (active[0]?.id??null)===x.activeId, 'legacy active session');
  for (const e of x.entries) {
    const s=sessions.get(e?.sessionId),pair=JSON.stringify([e?.sessionId,e?.exerciseId]);
    check(record(e) && id(e.id) && !entries.has(e.id) && s && exercises.has(e.exerciseId) && (exercises.get(e.exerciseId)===s.type||x.trainingJournal?.sessionSnapshots?.some(n=>n.id===s.journalSnapshotId&&n.sessionId===s.id&&n.unitId===s.type&&e.journalSnapshotId===n.id&&n.model.positions.some(p=>p.id===e.journalPositionId&&p.exerciseId===e.exerciseId&&p.unitId===s.type&&p.planVersionId===n.planVersionId))) && !pairs.has(pair) && number(e.kg) && number(e.reps,true), 'legacy result relation');
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
    check(record(p) && Object.hasOwn(x.data.exercises,p.id) && !plans.has(p.id) && text(p.label) && text(p.currentVersion), 'legacy catalog plan');plans.set(p.id,p);
  }
  check(plans.size===Object.keys(x.data.exercises).length, 'legacy catalog missing plan');
  for (const v of c.planVersions) {
    check(record(v) && text(v.id) && v.id && !versions.has(v.id) && plans.has(v.planId) && ['recorded','legacy-current-only'].includes(v.provenance) && Array.isArray(v.exercises), 'legacy plan version');
    // validateV1 is read-only; only this map is replaced for archived plans.
    const probe={...x.data,exercises:{...x.data.exercises},sessions:[],entries:[],changes:{},activeId:null};
    probe.exercises[v.planId]=v.exercises.map(e=>({...e,notes:''}));
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
/** Same complete structured validation, without manufacturing backup text. */
export function validateLegacyStructure(value){portable(value);validateV2(value);return value;}
function legacyValue(original,raw) {
  portable(original);
  check(original?.format!=='pushpull-backup' || [1,2].includes(original.version),
    'Nieobsługiwana wersja kopii. Użyj aplikacji obsługującej ten format.');
  if (original?.format==='pushpull-backup' && original.version===2) validateV2(original);
  else validateV1(original);
  const view=freeze({formatVersion:original.version,semantics:'legacy-unknown',raw:raw??JSON.stringify(original),original,
    data:original.version===1?original:original.data,
    catalog:original.version===2?original.catalog:null});
  verifiedViews.add(view);return view;
}
export function readLegacyBackup(raw) { return legacyValue(parseJson(raw),raw); }
/** Structured writer boundary: validate and detach before any await. The text
 * reader still scans untrusted files for duplicate keys/lossy decimal tokens. */
export function prepareLegacyBackup(value) {
  const own=immutableJSON(value)?value:freeze(structuredClone(value));
  return legacyValue(own);
}
/** Only a view issued by one of the full boundaries can certify this raw text.
 * The proof retains a version number, never a second parsed history/cache. */
export function legacySource(view,id) {
  check(verifiedViews.has(view),'expected verified legacy view');
  const source=freeze({id,formatVersion:view.formatVersion,semantics:'legacy-unknown',raw:view.raw});
  sourceVersions.set(source,view.formatVersion);return source;
}
export function legacySourceVersion(source) {
  return sourceVersions.has(source)?sourceVersions.get(source):readLegacyBackup(source.raw).formatVersion;
}
