/* Version-1 data boundary. No migration and no writes during load. */
'use strict';
const PushPullStorage = (() => {
  const TYPES = ['PUSH A', 'PULL A', 'PUSH B', 'PULL B'];
  const KEY = 'pushpull_skeleton_v1';
  const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  const text = x => typeof x === 'string';
  const id = x => text(x) && /^[A-Za-z0-9_.-]+$/.test(x) && !Object.hasOwn(Object.prototype, x);
  const date = x => text(x) && /^\d{4}-\d{2}-\d{2}$/.test(x) &&
    Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0, 10) === x;
  const number = (x, integer = false) => (typeof x === 'number' || text(x)) &&
    /^\d+(?:\.\d+)?$/.test(String(x)) && Number.isFinite(Number(x)) &&
    Number(x) >= 0 && (!integer || Number.isSafeInteger(Number(x)) && Number(x) > 0);
  function validate(value) {
    const fail = reason => { throw Error('Nieprawidłowe dane: ' + reason); };
    if (!object(value) || value.version !== 1) fail('nieobsługiwana wersja');
    // Preserve unknown fields, but reject prototype keys throughout the JSON tree.
    function keys(x) {
      if (x && typeof x === 'object') for (const k of Object.keys(x)) {
        if (['__proto__', 'prototype', 'constructor'].includes(k)) fail('niedozwolony klucz');
        keys(x[k]);
      }
    }
    keys(value);
    const declared=(value.trainingJournal?.model?.planVersions||[]).filter(v=>v.executionVersion===2).flatMap(v=>(v.units||[]).map(u=>u.id));
    const types=Object.keys(value.exercises||{});
    if (!object(value.exercises) || TYPES.some(k=>!types.includes(k)) || types.some(k => !TYPES.includes(k)&&(!id(k)||!declared.includes(k))) || !Array.isArray(value.sessions) || !Array.isArray(value.entries) ||
        !TYPES.includes(value.nextType) || !(value.activeId === null || id(value.activeId))) fail('struktura bazy');
    const exercises = new Map(), sessions = new Map(), entryIds = new Set(), pairs = new Set(), sequences = new Set();
    for (const type of types) {
      if (!Array.isArray(value.exercises[type]) || !value.exercises[type].length && TYPES.includes(type)) fail('plan ' + type);
      for (const ex of value.exercises[type]) {
        if (!object(ex) || !id(ex.id) || exercises.has(ex.id) || !text(ex.name) || !ex.name.trim() ||
            !Number.isSafeInteger(ex.sets) || ex.sets < 1 ||
            !['target', 'initialKg', 'tempo', 'rir', 'notes'].every(k => text(ex[k])) ||
            ex.description !== undefined && !text(ex.description)) fail('ćwiczenie');
        exercises.set(ex.id, type);
      }
    }
    for (const s of value.sessions) {
      if (!object(s) || !id(s.id) || sessions.has(s.id) || !types.includes(s.type) || !date(s.date) ||
          !Number.isSafeInteger(s.seq) || s.seq < 1 || sequences.has(s.seq) ||
          !['active', 'done'].includes(s.status)) fail('sesja');
      sessions.set(s.id, s); sequences.add(s.seq);
    }
    const active = value.sessions.filter(s => s.status === 'active');
    if (active.length > 1 || (active[0]?.id ?? null) !== value.activeId) fail('aktywna sesja');
    for (const e of value.entries) {
      const s = sessions.get(e?.sessionId), pair = JSON.stringify([e?.sessionId, e?.exerciseId]);
      if (!object(e) || !id(e.id) || entryIds.has(e.id) || !s || (!exercises.has(e.exerciseId) || exercises.get(e.exerciseId)!==s.type && !value.trainingJournal?.sessionSnapshots?.some(n=>n.id===s.journalSnapshotId && n.sessionId===s.id && n.unitId===s.type && e.journalSnapshotId===n.id && n.model.positions.some(p=>p.id===e.journalPositionId && p.exerciseId===e.exerciseId && p.unitId===s.type && p.planVersionId===n.planVersionId))) ||
          pairs.has(pair) || !number(e.kg) || !number(e.reps, true)) fail('wynik lub relacje');
      if (e.series != null && (!Array.isArray(e.series) || !e.series.length || e.series.some(r =>
        !object(r) || !number(r.kg) || !number(r.reps, true) || !Number.isFinite(Number(r.kg) * Number(r.reps))))) fail('serie');
      if (e.series?.length && (Number(e.kg) !== Number(e.series[0].kg) || Number(e.reps) !== Number(e.series[0].reps))) fail('pierwsza seria');
      for (const k of ['createdAt', 'correctedAt']) if (e[k] !== undefined && (!text(e[k]) || !Number.isFinite(Date.parse(e[k])))) fail('data wyniku');
      entryIds.add(e.id); pairs.add(pair);
    }
    if (value.changes !== undefined) {
      if (!object(value.changes)) fail('historia zmian');
      for (const [exId, changes] of Object.entries(value.changes)) {
        if (!exercises.has(exId) || !Array.isArray(changes) || changes.some(c =>
          !object(c) || !date(c.date) || !text(c.kind) || !text(c.text))) fail('znacznik zmiany');
      }
    }
    return value;
  }
  function open(storage, fresh) {
    let raw, current, error = null;
    try {
      raw = storage.getItem(KEY);
      if(storage.getItem('pushpull_indexeddb_owner')!==null)throw Error('Dane przeniesiono do IndexedDB. Otwórz aktualną wersję aplikacji.');
      current = raw === null ? fresh() : validate(JSON.parse(raw));
    } catch (failure) { error = failure; }
    // A failed read is distinct from an absent key. Never initialize over it.
    function commit(next, {importing = false} = {}) {
      if (storage.getItem('pushpull_indexeddb_owner')!==null)throw Error('Zapis starej wersji jest zablokowany po migracji.');
      if (raw === undefined || error && !importing) throw Error('Zapis zablokowany. Najpierw zabezpiecz i odzyskaj dane.');
      validate(next);
      const serialized = JSON.stringify(next);
      if (storage.getItem(KEY) !== raw) throw Error('Dane zmieniły się w innej karcie. Wyeksportuj pracę i odśwież stronę.');
      let backupKey = null;
      if (importing && raw !== null) {
        // Each import keeps its own exact preimage, including invalid/unsupported data.
        backupKey = KEY + '_backup_' + new Date().toISOString() + '_' + globalThis.crypto.randomUUID();
        storage.setItem(backupKey, raw);
      }
      // setItem is atomic: quota/security failure leaves the original key intact.
      storage.setItem(KEY, serialized);
      raw = serialized; current = JSON.parse(serialized); error = null;
      return backupKey;
    }
    return {
      get raw() { return raw; }, get error() { return error; },
      get value() { return current && JSON.parse(JSON.stringify(current)); },
      commit,
      backups() {
        const result = [];
        for (let i = 0; i < storage.length; i++) {
          const key = storage.key(i);
          if (key?.startsWith(KEY + '_backup_')) result.push(key);
        }
        return result;
      },
      readBackup(key) {
        if (!key.startsWith(KEY + '_backup_')) throw Error('Nieprawidłowa kopia');
        const content = storage.getItem(key);
        if (content === null) throw Error('Brak kopii');
        return content;
      }
    };
  }
  return {KEY, validate, open};
})();
if (typeof module !== 'undefined') module.exports = PushPullStorage;
