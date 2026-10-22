/** Pure domain contracts, independent of the v1 document, IndexedDB and backup formats.
 * All IDs and timestamps are supplied by callers. No defaults, storage, activation,
 * conversion of legacy results or calculation of tonnage occur here.
 * Records accept additional JSON fields without discarding them.
 */
export const SCHEMA_VERSION = 1;
export const Side = Object.freeze({LEFT:'left', RIGHT:'right', BILATERAL:'bilateral', EACH:'each'});
const fail = message => { throw new TypeError(`Training model: ${message}`); };
const text = x => typeof x === 'string';
const nonempty = x => text(x) && x.trim().length > 0;
const id = x => nonempty(x) && !['__proto__','prototype','constructor'].includes(x);
const integer = x => Number.isSafeInteger(x) && x >= 0;
const positive = x => integer(x) && x > 0;
const finite = x => typeof x === 'number' && Number.isFinite(x) && x >= 0;
const nullable = (x, test) => x === null || test(x);
const oneOf = (x, choices) => choices.includes(x);
const timestamp = x => text(x) && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(x) &&
  Number.isFinite(Date.parse(x)) && new Date(x).toISOString() === x;
function requireThat(condition, message) { if (!condition) fail(message); }

// JSON serialization must not silently lose values, sparse slots or extra array keys.
function json(value, ancestors = new Set()) {
  if (value === null || text(value) || typeof value === 'boolean') return;
  if (typeof value === 'number') { requireThat(Number.isFinite(value), 'non-finite JSON number'); return; }
  requireThat(typeof value === 'object' && !ancestors.has(value), 'non-JSON value or cycle');
  const array = Array.isArray(value);
  requireThat(array || [Object.prototype, null].includes(Object.getPrototypeOf(value)), 'non-plain object');
  requireThat(Object.getOwnPropertySymbols(value).length === 0, 'symbol key');
  const keys = Object.getOwnPropertyNames(value).filter(k => !(array && k === 'length'));
  if (array) requireThat(keys.length === value.length && keys.every((k,i) => k === String(i)), 'sparse or decorated array');
  ancestors.add(value);
  for (const key of keys) {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    requireThat(!['__proto__','prototype','constructor'].includes(key) && descriptor.enumerable && 'value' in descriptor, 'unsafe JSON property');
    json(descriptor.value, ancestors);
  }
  ancestors.delete(value);
}
function record(value, fields) {
  requireThat(value !== null && typeof value === 'object' && !Array.isArray(value), 'expected record');
  for (const field of fields.split(' ')) requireThat(Object.hasOwn(value, field), `missing ${field}`);
}
function source(value) {
  record(value, 'kind reference recordedAt');
  requireThat(oneOf(value.kind, ['trainer','owner','legacy','unknown']) &&
    nullable(value.reference, nonempty) && nullable(value.recordedAt, timestamp), 'source');
}
function entity(value, fields) {
  json(value); record(value, `id source ${fields}`);
  requireThat(id(value.id), 'id'); source(value.source);
}
function range(value, whole = false, minimum = 0) {
  if (value === null) return;
  record(value, 'min max');
  requireThat((whole ? positive(value.min) && positive(value.max) : finite(value.min) && finite(value.max)) &&
    value.min >= minimum && value.min <= value.max, 'range');
}
function target(value) {
  record(value, 'reps rir tempo'); range(value.reps, true, 1); range(value.rir);
  requireThat(value.tempo === null || Array.isArray(value.tempo) && value.tempo.length === 4 &&
    value.tempo.every(x => nullable(x, finite)), 'tempo (four phases or null)');
}
function freeze(value) {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}

/** ExerciseIdentity: id,name,status,legacyId,source. legacyId never renames an old ID. */
export function validateExerciseIdentity(x) {
  entity(x, 'name status legacyId');
  requireThat(nonempty(x.name) && oneOf(x.status, ['confirmed','unresolved']) && nullable(x.legacyId,id), 'exercise identity');
  requireThat(x.legacyId === null || x.legacyId === x.id, 'legacy exercise ID must be preserved');
  return x;
}
/** ExerciseVariant: id,exerciseId,label,machine,grip,support,execution,laterality,source. */
export function validateExerciseVariant(x) {
  entity(x, 'exerciseId label machine grip support execution laterality');
  requireThat(id(x.exerciseId) && nonempty(x.label) &&
    ['machine','grip','support','execution'].every(k => nullable(x[k], text)) &&
    oneOf(x.laterality,[null,'unilateral','bilateral']), 'exercise variant');
  return x;
}
/** PlanVersion: id,planId,number,label,units:[{id,name,order}],source; no active state. */
export function validatePlanVersion(x) {
  entity(x, 'planId number label units');
  requireThat(id(x.planId) && nullable(x.number,positive) && nonempty(x.label) && Array.isArray(x.units) && x.units.length > 0, 'plan version');
  for (const unit of x.units) {
    record(unit, 'id name order');
    requireThat(id(unit.id) && nonempty(unit.name) && integer(unit.order), 'training unit');
  }
  unique(x.units, u=>u.id); unique(x.units, u=>u.order);
  return x;
}
/** LoadConvention: explicit unit/basis/description, null means unknown (including legacy). */
export function validateLoadConvention(x) {
  json(x); record(x, 'unit basis description');
  requireThat(oneOf(x.unit,[null,'kg','lb','stack-unit','bodyweight']) &&
    oneOf(x.basis,[null,'per-implement','combined','machine-indication','bodyweight']) && nullable(x.description,text), 'load convention');
  requireThat(x.unit !== 'bodyweight' || x.basis === null || x.basis === 'bodyweight', 'bodyweight convention');
  return x;
}
/** PlanPosition owns ordering/label and optional legacy/replacement lineage, not identity. */
export function validatePlanPosition(x) {
  entity(x, 'planVersionId unitId order label exerciseId variantId legacyPositionId replacesPositionId setState confirmation loadConvention');
  requireThat([x.planVersionId,x.unitId,x.exerciseId,x.variantId].every(id) && integer(x.order) && nonempty(x.label) &&
    nullable(x.legacyPositionId,id) && nullable(x.replacesPositionId,id) &&
    oneOf(x.setState,['unspecified','specified']) && oneOf(x.confirmation,['pending','confirmed','legacy-unknown']), 'plan position');
  validateLoadConvention(x.loadConvention);
  return x;
}
/** SetPrescription: one actual target; backoffFromSetId is a preceding main set, not a weight formula. */
export function validateSetPrescription(x) {
  entity(x, 'positionId order role reps rir tempo side backoffFromSetId restSeconds'); target(x);
  requireThat(id(x.positionId) && integer(x.order) && oneOf(x.role,[null,'main','backoff','warmup']) &&
    oneOf(x.side,[null,...Object.values(Side)]) && nullable(x.backoffFromSetId,id) && nullable(x.restSeconds,finite), 'set prescription');
  requireThat(x.role === 'backoff' || x.backoffFromSetId === null, 'backoff reference on a non-backoff set');
  return x;
}
/** DropPrescription: segments=null means a variable, unspecified segment list, never zero segments.
 * An explicit list describes optional target templates; actual segment count remains flexible.
 */
export function validateDropPrescription(x) {
  entity(x, 'setId segments');
  requireThat(id(x.setId) && (x.segments === null || Array.isArray(x.segments) && x.segments.length > 0), 'drop prescription');
  if (x.segments !== null) {
    for (const segment of x.segments) {
      record(segment, 'id order reps rir tempo');
      requireThat(id(segment.id) && integer(segment.order), 'drop segment'); target(segment);
    }
    unique(x.segments, s=>s.id); unique(x.segments, s=>s.order);
  }
  return x;
}
/** GroupPrescription: distinct exercises in a unit; ordered members, optional rounds and rests. */
export function validateGroupPrescription(x) {
  entity(x, 'planVersionId unitId kind positionIds rounds betweenMembersSeconds afterRoundSeconds');
  requireThat(id(x.planVersionId) && id(x.unitId) && oneOf(x.kind,['paired','superset']) &&
    Array.isArray(x.positionIds) && x.positionIds.length >= 2 && x.positionIds.every(id) &&
    nullable(x.rounds,positive) && nullable(x.betweenMembersSeconds,finite) && nullable(x.afterRoundSeconds,finite), 'group prescription');
  unique(x.positionIds, p=>p); return x;
}
export function validateCoachInstruction(x) {
  entity(x, 'planVersionId positionId revision text confirmation');
  requireThat(id(x.planVersionId) && nullable(x.positionId,id) && positive(x.revision) && text(x.text) &&
    oneOf(x.confirmation,['confirmed','unverified']), 'coach instruction');
  requireThat(x.confirmation !== 'confirmed' || x.source.kind === 'trainer', 'unattributed instruction cannot be confirmed as trainer-authored');
  return x;
}
export function validateUserNote(x) {
  entity(x, 'exerciseId sessionId text origin revision');
  requireThat(nullable(x.exerciseId,id) && nullable(x.sessionId,id) && (x.exerciseId !== null || x.sessionId !== null) &&
    text(x.text) && positive(x.revision) && oneOf(x.origin,['user','legacy-shared','source-note']), 'user note');
  requireThat(x.origin !== 'legacy-shared' || x.source.kind === 'legacy', 'legacy note provenance');
  return x;
}
function unique(values, key) {
  const keys=values.map(key); requireThat(new Set(keys).size === keys.length, 'duplicate ID or order');
}
const TABLES = Object.freeze({
  exercises:validateExerciseIdentity, variants:validateExerciseVariant, planVersions:validatePlanVersion,
  positions:validatePlanPosition, sets:validateSetPrescription, drops:validateDropPrescription,
  groups:validateGroupPrescription, coachInstructions:validateCoachInstruction, userNotes:validateUserNote
});
/** A model is scoped to one owner. This is a domain boundary, not browser authentication. */
export function validateModel(model) {
  json(model); record(model, `schemaVersion ownerId ${Object.keys(TABLES).join(' ')}`);
  requireThat(model.schemaVersion === SCHEMA_VERSION && id(model.ownerId), 'model version or owner');
  const maps = {};
  for (const [table, validate] of Object.entries(TABLES)) {
    requireThat(Array.isArray(model[table]), `table ${table}`);
    model[table].forEach(validate); unique(model[table], x=>x.id);
    maps[table]=new Map(model[table].map(x=>[x.id,x]));
  }
  const ref = (table,key) => { const value=maps[table].get(key); requireThat(value, `missing ${table} reference ${key}`); return value; };
  unique(model.planVersions.filter(v=>v.number!==null),v=>JSON.stringify([v.planId,v.number]));
  for (const variant of model.variants) ref('exercises',variant.exerciseId);
  for (const position of model.positions) {
    const version=ref('planVersions',position.planVersionId), variant=ref('variants',position.variantId);
    ref('exercises',position.exerciseId);
    requireThat(version.units.some(u=>u.id===position.unitId) && variant.exerciseId===position.exerciseId, 'position variant or unit mismatch');
    const sets=model.sets.filter(s=>s.positionId===position.id);
    requireThat(position.setState==='specified' ? sets.length>0 : sets.length===0, 'unspecified sets cannot be invented');
    unique(sets,s=>s.order);
    if (position.replacesPositionId !== null) {
      const prior=ref('positions',position.replacesPositionId), priorVersion=ref('planVersions',prior.planVersionId);
      requireThat(prior.planVersionId!==position.planVersionId && priorVersion.planId===version.planId &&
        (priorVersion.number===null || version.number===null || priorVersion.number<version.number), 'replacement must refer to a prior version of the same plan');
      const visited=new Set([position.id]); let current=prior;
      while (current) {
        requireThat(!visited.has(current.id), 'replacement cycle'); visited.add(current.id);
        current=current.replacesPositionId===null ? null : ref('positions',current.replacesPositionId);
      }
    }
  }
  unique(model.positions,p=>JSON.stringify([p.planVersionId,p.unitId,p.order]));
  for (const set of model.sets) {
    const position=ref('positions',set.positionId), variant=ref('variants',position.variantId);
    requireThat(!(variant.laterality==='bilateral' && [Side.LEFT,Side.RIGHT,Side.EACH].includes(set.side)) &&
      !(variant.laterality==='unilateral' && set.side===Side.BILATERAL), 'set side contradicts variant');
    if (set.backoffFromSetId!==null) {
      const main=ref('sets',set.backoffFromSetId);
      requireThat(main.positionId===set.positionId && main.order<set.order && main.role==='main' &&
        (main.side===null || set.side===null || main.side===set.side || main.side===Side.EACH || set.side===Side.EACH), 'backoff must refer to a compatible preceding main set in the same position');
    }
  }
  unique(model.drops,d=>d.setId);
  for (const drop of model.drops) ref('sets',drop.setId);
  const grouped=new Set();
  for (const group of model.groups) {
    const version=ref('planVersions',group.planVersionId);
    requireThat(version.units.some(u=>u.id===group.unitId), 'group unit');
    const members=group.positionIds.map(p=>ref('positions',p));
    requireThat(members.every(p=>p.planVersionId===group.planVersionId && p.unitId===group.unitId), 'group crosses versions or units');
    unique(members,p=>p.exerciseId);
    for (const member of members) { requireThat(!grouped.has(member.id), 'position in multiple groups'); grouped.add(member.id); }
  }
  for (const instruction of model.coachInstructions) {
    ref('planVersions',instruction.planVersionId);
    if (instruction.positionId!==null) requireThat(ref('positions',instruction.positionId).planVersionId===instruction.planVersionId, 'instruction version mismatch');
  }
  for (const note of model.userNotes) if (note.exerciseId!==null) ref('exercises',note.exerciseId);
  return model;
}
/** Detach and deeply freeze a validated graph without mutating the caller's input. */
export function createModel(input) { validateModel(input); return freeze(structuredClone(input)); }

/** Capture the selected plan version and replacement ancestry with identities and instructions.
 * User notes are not plan instructions. No inference for legacy sessions is provided.
 * snapshotId/sessionId/startedAt must come from a future explicit session-start operation.
 */
export function captureSessionSnapshot(model, {id:snapshotId, sessionId, planVersionId, unitId, startedAt}) {
  validateModel(model);
  const version=model.planVersions.find(p=>p.id===planVersionId);
  requireThat(version && version.units.some(u=>u.id===unitId), 'snapshot plan or unit');
  // Retain replacement ancestry intact; do not rewrite position IDs or lineage fields.
  const versionIds=new Set([planVersionId]);
  let changed=true;
  while (changed) {
    changed=false;
    for (const position of model.positions.filter(p=>versionIds.has(p.planVersionId))) {
      if (position.replacesPositionId===null) continue;
      const prior=model.positions.find(p=>p.id===position.replacesPositionId);
      if (!versionIds.has(prior.planVersionId)) { versionIds.add(prior.planVersionId); changed=true; }
    }
  }
  const positions=model.positions.filter(p=>versionIds.has(p.planVersionId));
  const positionIds=new Set(positions.map(p=>p.id)), variantIds=new Set(positions.map(p=>p.variantId)), exerciseIds=new Set(positions.map(p=>p.exerciseId));
  const sets=model.sets.filter(s=>positionIds.has(s.positionId)), setIds=new Set(sets.map(s=>s.id));
  const selected={schemaVersion:SCHEMA_VERSION,ownerId:model.ownerId,
    exercises:model.exercises.filter(e=>exerciseIds.has(e.id)),variants:model.variants.filter(v=>variantIds.has(v.id)),
    planVersions:model.planVersions.filter(p=>versionIds.has(p.id)),positions,sets,
    drops:model.drops.filter(d=>setIds.has(d.setId)),groups:model.groups.filter(g=>versionIds.has(g.planVersionId)),
    coachInstructions:model.coachInstructions.filter(i=>versionIds.has(i.planVersionId)),userNotes:[]};
  const snapshot={schemaVersion:SCHEMA_VERSION,id:snapshotId,sessionId,planVersionId,unitId,startedAt,model:selected};
  validateSessionSnapshot(snapshot); return freeze(structuredClone(snapshot));
}
export function validateSessionSnapshot(x) {
  json(x); record(x,'schemaVersion id sessionId planVersionId unitId startedAt model');
  requireThat(x.schemaVersion===SCHEMA_VERSION && [x.id,x.sessionId,x.planVersionId,x.unitId].every(id) && timestamp(x.startedAt), 'session snapshot');
  validateModel(x.model);
  requireThat(x.model.planVersions.some(v=>v.id===x.planVersionId && v.units.some(u=>u.id===x.unitId)), 'snapshot version mismatch');
  return x;
}
/** A binding for a future result, not a conversion or reassignment of a legacy entry.
 * Numeric results/segments stay outside this reference; no weight or tonnage math.
 */
export function createResultReference(snapshot, {resultId,positionId,setId,side,groupId,round}) {
  validateSessionSnapshot(snapshot);
  const position=snapshot.model.positions.find(p=>p.id===positionId);
  requireThat(position, 'result position');
  const value={schemaVersion:SCHEMA_VERSION,ownerId:snapshot.model.ownerId,resultId,snapshotId:snapshot.id,sessionId:snapshot.sessionId,
    planVersionId:snapshot.planVersionId,positionId,exerciseId:position.exerciseId,variantId:position.variantId,setId,side,groupId,round};
  validateResultReference(value,snapshot); return freeze(value);
}
export function validateResultReference(x,snapshot) {
  json(x); validateSessionSnapshot(snapshot);
  record(x,'schemaVersion ownerId resultId snapshotId sessionId planVersionId positionId exerciseId variantId setId side groupId round');
  requireThat(x.schemaVersion===SCHEMA_VERSION && x.ownerId===snapshot.model.ownerId && id(x.resultId) &&
    x.snapshotId===snapshot.id && x.sessionId===snapshot.sessionId && x.planVersionId===snapshot.planVersionId, 'result snapshot binding');
  const model=snapshot.model, position=model.positions.find(p=>p.id===x.positionId);
  requireThat(position && position.planVersionId===snapshot.planVersionId && position.unitId===snapshot.unitId && position.exerciseId===x.exerciseId && position.variantId===x.variantId, 'result exercise/variant/unit binding');
  requireThat(nullable(x.setId,id) && oneOf(x.side,[null,Side.LEFT,Side.RIGHT,Side.BILATERAL]) && nullable(x.groupId,id) && nullable(x.round,positive), 'result reference');
  const variant=model.variants.find(v=>v.id===position.variantId);
  requireThat(!(variant.laterality==='unilateral' && x.side===Side.BILATERAL) &&
    !(variant.laterality==='bilateral' && [Side.LEFT,Side.RIGHT].includes(x.side)), 'result side contradicts variant');
  if (x.setId!==null) {
    const set=model.sets.find(s=>s.id===x.setId);
    requireThat(set && set.positionId===position.id && (set.side===null || x.side===null ||
      set.side===Side.EACH && [Side.LEFT,Side.RIGHT].includes(x.side) || set.side===x.side), 'result set binding');
  }
  const membership=model.groups.find(g=>g.positionIds.includes(position.id));
  requireThat(x.groupId===null ? !membership && x.round===null : membership?.id===x.groupId &&
    x.round!==null && (membership.rounds===null || x.round<=membership.rounds), 'result group/round binding');
  return x;
}
