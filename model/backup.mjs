/** Offline backup boundary. No storage, DOM, transport, migration or active-plan I/O. */
import {validateModel, validateSessionSnapshot, validateResultReferences} from './training-model.mjs';
import {readLegacyBackup,legacySourceVersion} from './legacy-backup.mjs';
import {parseJson, portable, immutableJSON, requireThat as check, record, identifier, canonical, freeze} from './backup-json.mjs';
export {readLegacyBackup};
export const BACKUP_VERSION=3;
const TABLES=['exercises','variants','planVersions','positions','sets','drops','groups','coachInstructions','userNotes'];
const RECORDS=['sessionSnapshots','resultReferences','sessionRecords','resultRecords','legacySources'];
const previews=new WeakMap();
function fields(value,names) {
  check(record(value),'expected record');
  for (const name of names.split(' ')) check(Object.hasOwn(value,name),`missing ${name}`);
}
function index(rows,key,label) {
  check(Array.isArray(rows),`${label} must be an array`);const map=new Map();
  for (const row of rows) {
    check(record(row) && identifier(row[key]) && !map.has(row[key]),`${label}: invalid or duplicate ${key}`);
    map.set(row[key],row);
  }
  return map;
}
const payloadVersion=x=>x===null || Number.isSafeInteger(x) && x>0;
function validatePayload(p) {
  fields(p,'model '+RECORDS.join(' '));portable(p);
  if (p.model!==null) validateModel(p.model);
  const snapshots=index(p.sessionSnapshots,'id','snapshots'),sessions=index(p.sessionRecords,'id','sessions');
  const refs=index(p.resultReferences,'resultId','references'),results=index(p.resultRecords,'id','results');
  index(p.legacySources,'id','legacy sources');
  check(p.model!==null || [snapshots,sessions,refs,results].every(m=>m.size===0),'new records require a model');
  for (const s of sessions.values()) {
    fields(s,'id snapshotId payloadVersion data');
    check(payloadVersion(s.payloadVersion),'session payload version');
    check(s.snapshotId===null || identifier(s.snapshotId) && snapshots.get(s.snapshotId)?.sessionId===s.id,'session snapshot relation');
  }
  const snapshotSessions=new Set();
  for (const s of snapshots.values()) {
    validateSessionSnapshot(s);
    check(s.model.ownerId===p.model.ownerId && !snapshotSessions.has(s.sessionId),'snapshot owner or duplicate session');
    check(sessions.get(s.sessionId)?.snapshotId===s.id,'snapshot missing its complete session record');
    snapshotSessions.add(s.sessionId);
  }
  for (const r of results.values()) {
    fields(r,'id sessionId binding payloadVersion data');
    check(sessions.has(r.sessionId) && payloadVersion(r.payloadVersion),'result session relation or payload version');
    check(['snapshot','uninterpreted'].includes(r.binding),'result binding');
    check(r.binding==='snapshot' ? refs.has(r.id) : !refs.has(r.id),'result reference completeness');
  }
  const snapshotReferences=new Map();
  for (const r of refs.values()) {
    const snapshot=snapshots.get(r.snapshotId),result=results.get(r.resultId);
    check(snapshot && result?.binding==='snapshot' && result.sessionId===snapshot.sessionId,'reference result relation');
    if(!snapshotReferences.has(snapshot))snapshotReferences.set(snapshot,[]);
    snapshotReferences.get(snapshot).push(r);
  }
  for(const [snapshot,references] of snapshotReferences)validateResultReferences(references,snapshot);
  // UserNote's session FK could not be checked by step A's model alone.
  for (const model of [p.model,...p.sessionSnapshots.map(s=>s.model)].filter(Boolean)) {
    for (const note of model.userNotes) check(note.sessionId===null || sessions.has(note.sessionId),'note session relation');
  }
  for (const l of p.legacySources) {
    fields(l,'id formatVersion semantics raw');
    check(l.semantics==='legacy-unknown','legacy semantics must remain explicit');
    check(legacySourceVersion(l)===l.formatVersion,'legacy source version mismatch');
  }
  return p;
}
function counts(p) {
  return Object.fromEntries([...TABLES.map(t=>[t,p.model===null?0:p.model[t].length]),...RECORDS.map(t=>[t,p[t].length])]);
}
async function digest(document) {
  // Include all extension fields too; omit only the digest value itself.
  const input={...document,integrity:{...document.integrity}};delete input.integrity.digest;
  const bytes=new TextEncoder().encode(canonical(input));
  return Array.from(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
}
function header(d) {
  fields(d,'format version createdAt metadata payload integrity');portable(d);
  check(d.format==='pushpull-backup' && d.version===BACKUP_VERSION,'unsupported backup version');
  check(typeof d.createdAt==='string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(d.createdAt) &&
    Number.isFinite(Date.parse(d.createdAt)) && new Date(d.createdAt).toISOString()===d.createdAt,'createdAt must be an explicit ISO UTC timestamp');
  check(record(d.metadata),'metadata must be a record');
  fields(d.integrity,'algorithm counts digest');
  check(d.integrity.algorithm==='SHA-256' && /^[a-f0-9]{64}$/.test(d.integrity.digest),'integrity algorithm or digest');
}
/** Verify structure, all known relations, counts and integrity; never mutate input. */
export async function validateBackup(document) {
  // Snapshot before awaiting crypto: caller edits cannot change what was checked.
  portable(document);const d=structuredClone(document);header(d);validatePayload(d.payload);
  check(canonical(d.integrity.counts)===canonical(counts(d.payload)),'record counts mismatch');
  check(d.integrity.digest===await digest(d),'checksum mismatch');
  return freeze(d);
}
/** All arrays and metadata are supplied explicitly. No guessed IDs/timestamps/data. */
export async function createBackup(payload,{createdAt,metadata}={}) {
  const immutable=immutableJSON(payload);portable(metadata);
  const p=immutable?payload:freeze(structuredClone(payload));validatePayload(p);
  const document={format:'pushpull-backup',version:BACKUP_VERSION,createdAt,metadata:structuredClone(metadata),payload:p,
    integrity:{algorithm:'SHA-256',counts:counts(p),digest:'0'.repeat(64)}};
  header(document);document.integrity.digest=await digest(document);
  return freeze(document);
}
/** Complete JSON text suitable for saving as a file by a future caller. */
export async function exportBackup(document) {
  return JSON.stringify(await validateBackup(document),null,2);
}
async function read(raw) {
  const document=parseJson(raw);portable(document);
  if (document?.format==='pushpull-backup' && document.version===BACKUP_VERSION) {
    return {formatVersion:BACKUP_VERSION,document:await validateBackup(document),kind:'model'};
  }
  const legacy=readLegacyBackup(raw);
  return {formatVersion:legacy.formatVersion,document:legacy.original,kind:'legacy'};
}
/** Read and verify only. The opaque handle binds confirmation to this exact file. */
export async function previewBackup(raw) {
  const state=await read(raw);
  const preview=freeze({formatVersion:state.formatVersion,kind:state.kind,
    counts:state.kind==='model'?structuredClone(state.document.integrity.counts):{
      sessions:(state.document.data??state.document).sessions.length,
      results:(state.document.data??state.document).entries.length},
    validation:state.kind==='model'?'known-structure-and-relations; result data opaque':'legacy-unknown-semantics'});
  previews.set(preview,{raw,...state});return preview;
}
/** Restore a detached state in memory, NEVER into production storage.
 * Replacing a caller's isolated state requires its valid, exact previous backup
 * and explicit confirmation. That backup is returned intact with the new state.
 */
export async function restoreBackup(preview,{currentBackup=null,confirmReplacement=false}={}) {
  const state=previews.get(preview);check(state,'use a verified preview from previewBackup');
  check(currentBackup===null || typeof currentBackup==='string','previous backup must be JSON text');
  if (currentBackup!==null) {
    check(confirmReplacement===true,'replacement requires explicit confirmation');await read(currentBackup);
  }
  // Revalidate before restoration; no callbacks or writes can partially commit.
  const verified=await read(state.raw);
  return freeze({formatVersion:verified.formatVersion,restored:structuredClone(verified.document),raw:state.raw,previousBackup:currentBackup});
}
