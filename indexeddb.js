/* IndexedDB source records, verified transactions and lossless v1 projection. */
'use strict';
const PushPullDB = (() => {
  const NAME = 'pushpull', VERSION = 1, OWNER = 'pushpull_indexeddb_owner';
  const TYPES = ['PUSH A', 'PULL A', 'PUSH B', 'PULL B'];
  const TABLES = ['plans', 'planVersions', 'exercises', 'sessions', 'entries', 'sets', 'notes', 'changes'];
  const ALL = ['meta', ...TABLES, 'backups'];
  const MODEL_KEY = 'training-model-v1';
  const modelAPI = () => import('./model/legacy-model.mjs');
  const clone = value => structuredClone(value);
  const canonical = value => JSON.stringify(sort(value));
  const omittedJSON = value => value===undefined || typeof value==='function' || typeof value==='symbol';
  // Same canonical JSON equality for complete model CAS/readback, without two
  // escaped copies of every raw archive. No digest-only shortcut or cache.
  function sameStoredModel(a,b) {
    if(a===b && (a===null || typeof a==='string' || typeof a==='number' || typeof a==='boolean'))return true;
    if(a===null || b===null || typeof a!=='object' || typeof b!=='object')return canonical(a)===canonical(b);
    const aa=Array.isArray(a),bb=Array.isArray(b);
    if(aa!==bb)return false;
    if(aa){
      // Retain the old canonical handling of holes/non-JSON legacy values too.
      for(let i=0;i<a.length;i++)if(omittedJSON(a[i]))return canonical(a)===canonical(b);
      for(let i=0;i<b.length;i++)if(omittedJSON(b[i]))return canonical(a)===canonical(b);
      if(a.length!==b.length)return false;
      for(let i=0;i<a.length;i++)if(!sameStoredModel(a[i],b[i]))return false;
      return true;
    }
    const ak=Object.keys(a).sort(),bk=Object.keys(b).sort();
    if(ak.some(k=>omittedJSON(a[k])) || bk.some(k=>omittedJSON(b[k])))return canonical(a)===canonical(b);
    if(ak.length!==bk.length)return false;
    for(let i=0;i<ak.length;i++)if(ak[i]!==bk[i] || !sameStoredModel(a[ak[i]],b[bk[i]]))return false;
    return true;
  }
  function sort(value) {
    if (Array.isArray(value)) return value.map(sort);
    if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k => [k, sort(value[k])]));
    return value;
  }
  const request = req => new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  function transaction(db, mode, work) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(ALL, mode, mode === 'readwrite' ? {durability:'strict'} : undefined);
      let result, failure;
      tx.oncomplete = () => resolve(result);
      tx.onabort = () => reject(failure || tx.error || Error('Transakcja przerwana'));
      tx.onerror = () => {}; // onabort is the final outcome, never request success.
      Promise.resolve().then(() => work(tx)).then(value => { result = value; }, error => {
        failure = error;
        try { tx.abort(); } catch { reject(error); }
      });
    });
  }
  async function connect() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(NAME, VERSION);
      let abandoned = false;
      req.onupgradeneeded = () => {
        for (const table of ALL) req.result.createObjectStore(table, {keyPath: table === 'meta' ? 'key' : 'id'});
      };
      req.onblocked = () => { abandoned = true; reject(Error('Zamknij inne karty PushPull i ponów uruchomienie.')); };
      req.onerror = () => reject(req.error);
      req.onsuccess = () => {
        if (abandoned) { req.result.close(); return; }
        req.result.onversionchange = () => req.result.close();
        resolve(req.result);
      };
    });
  }
  const digest = async value => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical(value))))).map(x=>x.toString(16).padStart(2,'0')).join('');
  function catalogFor(data, previous = null, legacy = false) {
    const catalog = previous ? clone(previous) : {plans:[], planVersions:[], sessionVersions:{}};
    for (const type of Object.keys(data.exercises)) {
      const parameters = data.exercises[type].map(ex => { const value = clone(ex); delete value.notes; return value; });
      let plan = catalog.plans.find(p => p.id === type);
      if (!plan) { plan = {id:type, label:'V2 — niezweryfikowany', currentVersion:null}; catalog.plans.push(plan); }
      const current = catalog.planVersions.find(v => v.id === plan.currentVersion);
      if (!current || canonical(current.exercises) !== canonical(parameters)) {
        const versions = catalog.planVersions.filter(v => v.planId === type);
        let number=versions.length+1;while(catalog.planVersions.some(v=>v.id===type+':'+number))number++;
        const version = {id:type+':'+number, planId:type, exercises:parameters, provenance:legacy?'legacy-current-only':'recorded'};
        catalog.planVersions.push(version); plan.currentVersion = version.id;
      }
    }
    for (const session of data.sessions) if (!catalog.sessionVersions[session.id]) {
      catalog.sessionVersions[session.id] = {versionId:catalog.plans.find(p => p.id === session.type).currentVersion, provenance:legacy?'legacy-current-only':'session-start'};
    }
    // Removing sessions by a deliberate import uses that import's catalog instead.
    return catalog;
  }
  function validateCatalog(data, catalog) {
    if (!catalog || Object.keys(catalog).some(k=>!['plans','planVersions','sessionVersions'].includes(k)) || !Array.isArray(catalog.plans) || !Array.isArray(catalog.planVersions) ||
        !catalog.sessionVersions || typeof catalog.sessionVersions !== 'object' || Array.isArray(catalog.sessionVersions)) throw Error('Nieprawidłowe wersje planów');
    const ids = new Set(), plans = new Map();
    for (const p of catalog.plans) {
      if (!p || !Object.hasOwn(data.exercises,p.id) || plans.has(p.id) || typeof p.label !== 'string' || typeof p.currentVersion !== 'string') throw Error('Nieprawidłowy plan');
      plans.set(p.id,p);
    }
    if (plans.size !== Object.keys(data.exercises).length) throw Error('Brak planu');
    for (const v of catalog.planVersions) {
      if (!v || typeof v.id !== 'string' || !v.id || ids.has(v.id) || !plans.has(v.planId) || !['recorded','legacy-current-only'].includes(v.provenance)) throw Error('Nieprawidłowa wersja planu');
      // Validation is read-only. A separate exercises map allows replacing one
      // plan without cloning the whole history/snapshots for each plan version.
      const probe = {...data,exercises:{...data.exercises},sessions:[],entries:[],changes:{},activeId:null};
      probe.exercises[v.planId] = (v.exercises || []).map(ex=>({...ex,notes:''}));
      // Validate archived parameters independently of current sessions/entries.
      PushPullStorage.validate(probe);
      ids.add(v.id);
    }
    for (const p of catalog.plans) {
      const current = catalog.planVersions.find(v => v.id === p.currentVersion && v.planId === p.id);
      const parameters = data.exercises[p.id].map(ex=>{const x=clone(ex);delete x.notes;return x;});
      if (!current || canonical(current.exercises) !== canonical(parameters)) throw Error('Niezgodne parametry bieżącego planu');
    }
    const sessions = new Map(data.sessions.map(s=>[s.id,s]));
    if (Object.keys(catalog.sessionVersions).length !== sessions.size) throw Error('Niezgodna liczba wersji sesji');
    for (const [id, link] of Object.entries(catalog.sessionVersions)) {
      const session = sessions.get(id);
      if (!session || !link || !['legacy-current-only','session-start'].includes(link.provenance) ||
          !catalog.planVersions.some(v=>v.id===link.versionId && v.planId===session.type)) throw Error('Niezgodna wersja sesji');
    }
    return catalog;
  }
  function validateArchives(archives) {
    if(!Array.isArray(archives))throw Error('Nieprawidłowe archiwum kopii');
    const ids=new Set();
    for(const item of archives){
      if(!item || typeof item.id!=='string' || !item.id || ids.has(item.id) ||
         typeof item.kind!=='string' || typeof item.createdAt!=='string' || !Number.isFinite(Date.parse(item.createdAt)) ||
         !(typeof item.raw==='string' || item.raw===null))throw Error('Nieprawidłowa kopia w archiwum');
      ids.add(item.id);
    }
    return archives;
  }
  function parseBackup(value) {
    // Validate prototype keys for the entire envelope through the v1 boundary too.
    if (value?.format === 'pushpull-backup' && value.version !== 1) {
      if (value.version !== 2 || Object.keys(value).some(k=>!['format','version','data','catalog','archives'].includes(k))) throw Error('Nieobsługiwana wersja kopii');
      PushPullStorage.validate({...value.data, backupEnvelope:value});
      return {data:PushPullStorage.validate(value.data), catalog:validateCatalog(value.data,value.catalog),archives:validateArchives(value.archives || [])};
    }
    const data = PushPullStorage.validate(value);
    return {data, catalog:catalogFor(data,null,true),archives:[]};
  }
  function encode(data, catalog) {
    const rows = Object.fromEntries(TABLES.map(t=>[t,[]]));
    rows.plans = clone(catalog.plans); rows.planVersions = clone(catalog.planVersions);
    for (const type of Object.keys(data.exercises)) data.exercises[type].forEach((ex,position)=>{
      const value=clone(ex);delete value.notes;
      rows.exercises.push({id:ex.id,planId:type,position,value});
      rows.notes.push({id:ex.id,origin:'legacy-shared',value:ex.notes});
    });
    data.sessions.forEach((s,position)=>rows.sessions.push({id:s.id,position,value:clone(s),planVersion:clone(catalog.sessionVersions[s.id])}));
    data.entries.forEach((e,position)=>{
      const value=clone(e);delete value.series;
      rows.entries.push({id:e.id,position,value,seriesKind:!Object.hasOwn(e,'series')?'absent':e.series===null?'null':'array'});
      e.series?.forEach((value,position)=>rows.sets.push({id:JSON.stringify([e.id,position]),entryId:e.id,position,value:clone(value)}));
    });
    for (const [exerciseId, changes] of Object.entries(data.changes || {})) changes.forEach((value,position)=>rows.changes.push({id:JSON.stringify([exerciseId,position]),exerciseId,position,value:clone(value)}));
    const rest=clone(data);for(const key of ['exercises','sessions','entries','changes'])delete rest[key];
    return {rows,rest,changeKeys:Object.keys(data.changes || {}),hasChanges:Object.hasOwn(data,'changes')};
  }
  function decode(root, rows) {
    const order = values => [...values].sort((a,b)=>a.position-b.position);
    // Preserve per-entry position ordering, but visit each stored set only once.
    // verifyRows still detects orphan/mismatched rows through the full roundtrip.
    const setsByEntry=new Map();
    for(const row of rows.sets){
      if(!setsByEntry.has(row.entryId))setsByEntry.set(row.entryId,[]);
      setsByEntry.get(row.entryId).push(row);
    }
    const data=clone(root.rest);
    data.exercises=Object.fromEntries(root.catalogOrder.plans.map(type=>[type,order(rows.exercises.filter(e=>e.planId===type)).map(e=>({...e.value,notes:rows.notes.find(n=>n.id===e.id)?.value}))]));
    data.sessions=order(rows.sessions).map(s=>clone(s.value));
    data.entries=order(rows.entries).map(e=>{
      const value=clone(e.value);
      if(e.seriesKind==='null')value.series=null;
      else if(e.seriesKind==='array')value.series=order(setsByEntry.get(e.id)||[]).map(s=>clone(s.value));
      return value;
    });
    if(root.hasChanges)data.changes=Object.fromEntries(root.changeKeys.map(id=>[id,order(rows.changes.filter(c=>c.exerciseId===id)).map(c=>clone(c.value))]));
    const catalog={plans:root.catalogOrder.plans.map(id=>clone(rows.plans.find(v=>v.id===id))),planVersions:root.catalogOrder.planVersions.map(id=>clone(rows.planVersions.find(v=>v.id===id))),sessionVersions:Object.fromEntries(rows.sessions.map(s=>[s.id,clone(s.planVersion)]))};
    return {data,catalog};
  }
  async function read(tx,includeModel=true) {
    const [root,modelState,...values]=await Promise.all([request(tx.objectStore('meta').get('state')),includeModel?request(tx.objectStore('meta').get(MODEL_KEY)):null,...TABLES.map(t=>request(tx.objectStore(t).getAll()))]);
    return {root,modelState,rows:Object.fromEntries(TABLES.map((t,i)=>[t,values[i]]))};
  }
  function verifyRows(root, rows, expected) {
    for(const table of TABLES) {
      if(rows[table].length!==root.counts[table])throw Error('Niezgodna liczba rekordów: '+table);
      if(expected) {
        const ordered = list => [...list].sort((a,b)=>a.id.localeCompare(b.id));
        if(canonical(ordered(rows[table]))!==canonical(ordered(expected[table])))throw Error('Niezgodne rekordy: '+table);
      }
    }
    const value=decode(root,rows);
    PushPullStorage.validate(value.data); validateCatalog(value.data,value.catalog);
    const roundtrip=encode(value.data,value.catalog).rows;
    const ordered=list=>[...list].sort((a,b)=>a.id.localeCompare(b.id));
    for(const table of TABLES)if(canonical(ordered(rows[table]))!==canonical(ordered(roundtrip[table])))throw Error('Niespójne powiązania rekordów: '+table);
    return value;
  }
  // A full readback must equal the immutable, validated encoder output. The
  // encoder/decoder roundtrip was checked before opening this transaction.
  // Unknown row/root fields and every position/value still participate.
  function verifyPreparedRows(expectedRoot,expectedRows,actual) {
    if(!sameStoredModel(actual.root,expectedRoot))throw Error('Niepełny odczyt kontrolny metadanych.');
    for(const table of TABLES){
      const rows=actual.rows[table],byId=new Map(rows.map(row=>[row.id,row]));
      if(rows.length!==expectedRows[table].length || byId.size!==rows.length ||
        expectedRows[table].some(row=>!sameStoredModel(byId.get(row.id),row)))throw Error('Niezgodne rekordy: '+table);
    }
  }
  async function open(fresh) {
    let db, root, current, catalog, raw, error=null, backupRows=[], stale=false, unverified=null;
    let modelState=null;
    let notify=()=>{};
    const channel=typeof BroadcastChannel!=='undefined'?new BroadcastChannel('pushpull-indexeddb'):null;
    const legacy=()=>localStorage.getItem(PushPullStorage.KEY);
    const snapshot = (archives=false) => ({format:'pushpull-backup',version:2,data:clone(current),catalog:clone(catalog),archives:archives?clone(backupRows):[]});
    function blocked(message) { stale=true;error=Error(message);notify(error); }
    async function load() {
      const result=await transaction(db,'readonly',async tx=>({...(await read(tx)),backups:await request(tx.objectStore('backups').getAll())}));
      unverified=clone(result);backupRows=result.backups;
      if(!result.root) {
        if(TABLES.some(t=>result.rows[t].length) || result.backups.length)throw Error('Niekompletna baza. Odzyskaj kopię danych.');
        if(result.modelState)throw Error('Model bez źródłowej historii. Odzyskaj pełną kopię.');
        unverified=null;return null;
      }
      root=result.root; // The complete recovery copy was already captured above.
      if(!result.root.verified || !result.root.migration?.complete)throw Error('Migracja nie została potwierdzona.');
      const value=verifyRows(result.root,result.rows);
      if(await digest(value)!==result.root.digest)throw Error('Weryfikacja integralności bazy nie powiodła się.');
      if(value.data.trainingJournal && !result.modelState)throw Error('Nowy dziennik wymaga pełnej kopii v3. Nie zmieniono danych.');
      if(result.modelState)await (await modelAPI()).verifyLegacyModel(result.modelState,value,result.root.revision);
      modelState=result.modelState || null;
      root=result.root;current=value.data;catalog=value.catalog;backupRows=result.backups;unverified=null;
      return root;
    }
    async function save(data, nextCatalog, {importing=false, initializing=false, importedArchives=[],modelOwnerId=null,backupBefore=false,requiredRevision=null,requiredLegacyRaw=undefined}={}) {
      if(requiredRevision!==null&&(root?.revision||0)!==requiredRevision)throw Error('Dane zmieniły się od podglądu kopii. Otwórz podgląd ponownie.');
      const expectedRevision=root?.revision || 0,expectedModel=modelState || (importing?unverified?.modelState || null:null);
      if(data.trainingJournal && !expectedModel && modelOwnerId===null)throw Error('Nowy dziennik wymaga importu pełnej kopii v3.');
      PushPullStorage.validate(data);validateCatalog(data,nextCatalog);
      if(stale && !importing)throw Error('Dane zmieniły się. Odśwież aplikację przed zapisem.');
      const source=legacy();
      if(requiredLegacyRaw!==undefined&&source!==requiredLegacyRaw)throw Error('Starsza wersja zmieniła dane od podglądu. Otwórz kopię ponownie.');
      if(!importing && root && source!==root.legacyRaw)throw Error('Starsza wersja zmieniła dane. Zachowaj obie kopie i odzyskaj historię przez import.');
      if(initializing && source!==raw)throw Error('Dane źródłowe zmieniły się podczas migracji. Uruchom ponownie.');
      const encoded=encode(data,nextCatalog), checksum=await digest({data,catalog:nextCatalog});
      let next={key:'state',rest:encoded.rest,changeKeys:encoded.changeKeys,hasChanges:encoded.hasChanges,
        catalogOrder:{plans:nextCatalog.plans.map(p=>p.id),planVersions:nextCatalog.planVersions.map(v=>v.id)},
        revision:expectedRevision+1,legacyRaw:source,digest:checksum,verified:false,
        counts:Object.fromEntries(TABLES.map(t=>[t,encoded.rows[t].length])),
        migration:root?.migration || {complete:false,source:source===null?'new':'localStorage-v1',completedAt:null}};
      const backups=[];
      if(!root) {
        if(importing && unverified)backups.push({id:'recovery-records:'+crypto.randomUUID(),kind:'before-import',createdAt:new Date().toISOString(),raw:JSON.stringify({format:'pushpull-idb-recovery',version:1,...unverified})});
        if(source!==null)backups.push({id:'migration-original:'+crypto.randomUUID(),kind:'migration',createdAt:new Date().toISOString(),raw:source});
        for(let i=0;i<localStorage.length;i++) {
          const id=localStorage.key(i);
          if(id?.startsWith(PushPullStorage.KEY+'_backup_'))backups.push({id,kind:'legacy-backup',createdAt:new Date().toISOString(),raw:localStorage.getItem(id)});
        }
      }
      if((importing || backupBefore) && root)backups.push({id:'idb:'+crypto.randomUUID(),kind:'before-import',createdAt:new Date().toISOString(),raw:JSON.stringify(expectedModel?expectedModel.document:current?snapshot():{format:'pushpull-idb-recovery',version:1,...unverified})});
      if(importing && root && source!==root.legacyRaw)backups.push({id:'legacy-conflict:'+crypto.randomUUID(),kind:'legacy-conflict',createdAt:new Date().toISOString(),raw:source});
      backups.push(...clone(validateArchives(importedArchives)));
      const additions=[];
      for(const record of backups){
        const existing=[...backupRows,...additions].find(b=>b.id===record.id);
        if(existing && canonical(existing)===canonical(record))continue;
        if(existing){record.sourceId=record.id;record.id='imported:'+crypto.randomUUID();}
        additions.push(record);
      }
      backups.splice(0,backups.length,...additions);
      const api=expectedModel || modelOwnerId!==null?await modelAPI():null;
      const modelSource=api?{format:'pushpull-backup',version:2,data,catalog:nextCatalog,archives:[...backupRows,...backups]}:null;
      if(api)api.portable(modelSource); // Never silently discard non-JSON legacy extensions.
      const nextModel=api?{key:MODEL_KEY,revision:next.revision,document:await api.createLegacyModelFromSource(
        modelSource,{ownerId:modelOwnerId??expectedModel.document.payload.model.ownerId,createdAt:new Date().toISOString()})}:null;
      const preparedSource=!!api&&!importing&&!initializing;
      if(preparedSource){
        api.freeze(encoded);api.freeze(next);
        if(!sameStoredModel(decode(next,encoded.rows),{data,catalog:nextCatalog}))throw Error('Niepełna migracja — dane różnią się od źródła.');
      }
      await transaction(db,'readwrite',async tx=>{
        const stored=await request(tx.objectStore('meta').get('state'));
        const storedModel=await request(tx.objectStore('meta').get(MODEL_KEY));
        if(!sameStoredModel(storedModel || null,expectedModel))throw Error('Model zmienił się w innej karcie. Odśwież aplikację.');
        if((stored?.revision || 0)!==expectedRevision)throw Error('Inna karta zapisała nowsze dane. Odśwież aplikację.');
        if(legacy()!==source)throw Error('Starsza wersja zmieniła dane w trakcie operacji.');
        for(const table of TABLES) {
          tx.objectStore(table).clear();
          for(const record of encoded.rows[table])tx.objectStore(table).add(record);
        }
        for(const record of backups)tx.objectStore('backups').add(record);
        tx.objectStore('meta').put(next);
        for(const backup of backups){const saved=await request(tx.objectStore('backups').get(backup.id));if(canonical(saved)!==canonical(backup))throw Error('Kopia nie przeszła weryfikacji.');}
        const actual=await read(tx,!preparedSource);
        const decoded=preparedSource?verifyPreparedRows(next,encoded.rows,actual):verifyRows(actual.root,actual.rows,encoded.rows);
        if(!preparedSource && canonical(decoded)!==canonical({data,catalog:nextCatalog}))throw Error('Niepełna migracja — dane różnią się od źródła.');
        if(legacy()!==source)throw Error('Dane źródłowe zmieniły się podczas weryfikacji.');
        if(nextModel){
          tx.objectStore('meta').put(nextModel);
          if(!sameStoredModel(await request(tx.objectStore('meta').get(MODEL_KEY)),nextModel))throw Error('Model nie przeszedł weryfikacji zapisu.');
        }
        next={...next,verified:true,migration:{...next.migration,complete:true,completedAt:next.migration.completedAt || new Date().toISOString()}};
        tx.objectStore('meta').put(next);
      });
      if(importing){
        try{
          const actual=await transaction(db,'readonly',read);
          if(actual.root?.revision!==next.revision)throw Error('Inna karta zmieniła dane po przywróceniu. Nie potwierdzono aktualnej zawartości.');
          if(canonical(verifyRows(actual.root,actual.rows,encoded.rows))!==canonical({data,catalog:nextCatalog})||canonical(actual.modelState||null)!==canonical(nextModel))throw Error('Nie potwierdzono kompletności przywróconej bazy.');
        }catch(failure){backupRows.push(...backups);blocked('Nie potwierdzono odczytu po przywróceniu. Kopia sprzed przywrócenia została zachowana. Odśwież aplikację. '+failure.message);throw error;}
      }
      // No visible success and no in-memory publication before transaction.oncomplete.
      modelState=nextModel;
      root=clone(next);current=clone(data);catalog=clone(nextCatalog);backupRows.push(...backups);raw=source;error=null;stale=false;
      if(localStorage.getItem(OWNER)!==NAME+':'+VERSION)localStorage.setItem(OWNER,NAME+':'+VERSION);
      channel?.postMessage({revision:root.revision});
    }
    try {
      raw=legacy();
      db=await connect();
      if(await load()) {
        if(raw!==root.legacyRaw)throw Error('Wykryto zapis starszej wersji. Pobierz obie historie i wybierz kopię do odzyskania.');
        if(localStorage.getItem(OWNER)!==NAME+':'+VERSION)localStorage.setItem(OWNER,NAME+':'+VERSION);
      } else {
        if(localStorage.getItem(OWNER)!==null)throw Error('Brak wcześniej używanej bazy IndexedDB. Nie odtwarzamy automatycznie starej historii. Wczytaj pełną kopię.');
        const value=raw===null?fresh():PushPullStorage.validate(JSON.parse(raw));
        try { await save(value,catalogFor(value,null,true),{initializing:true}); }
        catch(failure) {
          if(!failure.message.startsWith('Inna karta') || !await load() || legacy()!==root.legacyRaw)throw failure;
        }
      }
    } catch(failure) {error=failure;}
    channel && (channel.onmessage=event=>{if(event.data?.modelChanged || event.data?.revision>(root?.revision || 0))blocked('Dane zapisano w innej karcie. Odśwież stronę.');});
    const storageListener=event=>{if(event.key===PushPullStorage.KEY || event.key===null)blocked('Starsza wersja zmieniła dane. Zapis wstrzymany.');};
    window.addEventListener('storage',storageListener);
    async function prepareModel({backupText,ownerId}={}) {
      if(error)throw error;
      if(!db || !current)throw Error('Brak zweryfikowanej historii.');
      const api=await modelAPI();
      if(modelState){
        if(ownerId!==modelState.document.payload.model.ownerId)throw Error('Inny właściciel modelu.');
        return api.verifyLegacyModel(modelState,{data:current,catalog},root.revision);
      }
      const original=snapshot(true),expectedRevision=root.revision,expectedLegacy=root.legacyRaw;
      api.portable(original);
      // The supplied backup must contain this exact complete source, including archives.
      if(canonical(api.readLegacyBackup(backupText).original)!==canonical(original))throw Error('Kopia nie odpowiada pełnej bieżącej bazie.');
      const document=await api.createLegacyModel(backupText,{ownerId,createdAt:new Date().toISOString()});
      const next={key:MODEL_KEY,revision:expectedRevision,document};
      const backup={id:'model-migration:'+expectedRevision,kind:'before-model-migration',createdAt:document.createdAt,raw:backupText};
      await transaction(db,'readwrite',async tx=>{
        const live=await read(tx);
        if(live.root?.revision!==expectedRevision || live.modelState)throw Error('Baza zmieniła się podczas migracji. Otwórz ponownie i ponów.');
        if(legacy()!==expectedLegacy)throw Error('Starsza wersja zmieniła dane.');
        const value=verifyRows(live.root,live.rows);
        if(canonical(value)!==canonical({data:original.data,catalog:original.catalog}))throw Error('Źródłowa historia zmieniła się.');
        tx.objectStore('backups').add(backup);
        tx.objectStore('meta').add(next);
        if(canonical(await request(tx.objectStore('backups').get(backup.id)))!==canonical(backup) ||
           canonical(await request(tx.objectStore('meta').get(MODEL_KEY)))!==canonical(next))throw Error('Migracja nie przeszła weryfikacji.');
      });
      modelState=next;backupRows.push(backup);
      channel?.postMessage({modelChanged:true});
      return clone(document);
    }
    return {
      prepareModel,
      // Drive settings and archived legacy queues stay outside workout backups.
      async readDriveState(){
        if(!db)throw Error('IndexedDB niedostępne.');
        return transaction(db,'readonly',tx=>request(tx.objectStore('meta').get('drive-sync-v1')));
      },
      async writeDriveState(value,expectedToken){
        if(!db)throw Error('IndexedDB niedostępne.');
        const next={...clone(value),key:'drive-sync-v1',token:crypto.randomUUID()};
        return transaction(db,'readwrite',async tx=>{
          const store=tx.objectStore('meta'),old=await request(store.get(next.key));
          if((old?.token??null)!==expectedToken)throw Error('Ustawienia Google zmieniły się w innej karcie. Odśwież aplikację.');
          // Once manual mode is chosen, stale callers must not re-enable timers.
          if(old?.mode==='manual'){next.mode='manual';next.enabled=false;}
          store.put(next);
          if(canonical(await request(store.get(next.key)))!==canonical(next))throw Error('Nie zweryfikowano stanu Drive.');
          return next;
        });
      },
      // Drafts live in the existing meta store, outside source/model/statistics.
      // They remain writable even when a stale official-history handle is blocked.
      async readDraftObservation(){
        if(!db)throw Error('IndexedDB niedostępne.');
        return transaction(db,'readonly',async tx=>{
          const store=tx.objectStore('meta');
          const [state,rows]=await Promise.all([request(store.get('state')),request(store.getAll(IDBKeyRange.bound('workout-draft:','workout-draft;',false,true),1025))]);
          if(!Number.isSafeInteger(state?.revision))throw Error('Nie odczytano rewizji historii.');
          if(rows.length>1024)throw Object.assign(Error('Limit odczytu szkiców'),{code:'draft-read-limit'});
          return {historyRevision:state.revision,sources:rows.filter(r=>typeof r?.key==='string'&&r.key.startsWith('workout-draft:')).map(value=>({source:'idb-meta',storageKey:value.key,value}))};
        });
      },
      async readDrafts(){
        if(!db)throw Error('IndexedDB niedostępne.');
        return transaction(db,'readonly',async tx=>(await request(tx.objectStore('meta').getAll())).filter(r=>r.key.startsWith('workout-draft:')));
      },
      async writeDraft(record,expectedToken){
        if(!db)throw Error('IndexedDB niedostępne.');
        if(record.key!=='workout-draft:'+record.id)throw Error('Nieprawidłowy klucz szkicu.');
        const safe=clone(record);
        await transaction(db,'readwrite',async tx=>{
          const store=tx.objectStore('meta'),old=await request(store.get(safe.key));
          if((old?.token??null)!==expectedToken)throw Error('Szkic zmienił się w innej karcie. Zachowano obie wersje.');
          store.put(safe);
          if(canonical(await request(store.get(safe.key)))!==canonical(safe))throw Error('Nie udało się zweryfikować szkicu.');
        });
      },
      async removeDraft(record){
        if(typeof record.id!=='string'||record.key!=='workout-draft:'+record.id)throw Error('Nieprawidłowy klucz szkicu.');
        if(!db)throw Error('IndexedDB niedostępne.');
        return transaction(db,'readwrite',async tx=>{
          const store=tx.objectStore('meta'),old=await request(store.get(record.key));
          if(old && old.token!==record.token && !(old.id===record.id && old.sequence<record.sequence))return false; // Preserve newer edits; an older row may be covered by the recovered buffer.
          store.delete(record.key);return true;
        });
      },
      async importModelBackup(text,{expectedRevision=null,expectedLegacyRaw=undefined}={}){
        if(!db)throw Error('IndexedDB niedostępne.');
        const parsed=await (await modelAPI()).parseModelBackup(text);
        await save(clone(parsed.data),clone(parsed.catalog),{importing:true,importedArchives:clone(parsed.archives || []),modelOwnerId:parsed.document.payload.model.ownerId,requiredRevision:expectedRevision,requiredLegacyRaw:expectedLegacyRaw});
      },
      async exportModelBackup(){
        if(error)throw error;
        if(!modelState)throw Error('Model nie został przygotowany.');
        const api=await modelAPI();
        await api.verifyLegacyModel(modelState,{data:current,catalog},root.revision);
        const source=snapshot(true);api.portable(source);
        return api.exportBackup(await api.createLegacyModel(JSON.stringify(source),{ownerId:modelState.document.payload.model.ownerId,createdAt:new Date().toISOString()}));
      },
      get model(){return modelState && clone(modelState.document.payload);},
      get error(){return error;},get value(){return current && clone(current);},get raw(){try{return legacy()}catch{return raw}},get revision(){return root?.revision || 0;},
      set onchange(callback){notify=callback;},
      recovery(){return unverified?{format:'pushpull-idb-recovery',version:1,...clone(unverified)}:current?snapshot(true):null;},
      export(){if(!current)throw Error('Brak zweryfikowanej bazy do eksportu.');return snapshot(true);},
      async commit(data,{importing=false,importedCatalog=null,importedArchives=[],backupBefore=false,expectedRevision=null,expectedLegacyRaw=undefined}={}) {
        if(!db)throw Error('IndexedDB niedostępne. Odblokuj pamięć i uruchom ponownie.');
        if(error && !importing)throw error;
        const safe=clone(data),nextCatalog=importedCatalog?clone(importedCatalog):catalogFor(safe,catalog),archives=clone(importedArchives);
        try{await save(safe,nextCatalog,{importing,importedArchives:archives,backupBefore,requiredRevision:expectedRevision,requiredLegacyRaw:expectedLegacyRaw});}catch(failure){if(/Inna karta|Starsza wersja|Dane źródłowe|Model zmienił/.test(failure.message))blocked(failure.message);throw failure;}
      },
      backups(){return backupRows.map(b=>b.id);},
      backupLabel(id){const item=backupRows.find(b=>b.id===id);const label={migration:'Przed migracją','before-import':'Przed przywróceniem / importem','legacy-conflict':'Zapis starszej wersji','legacy-backup':'Wcześniejsza kopia'}[item.kind] || 'Kopia';return label+' · '+new Date(item.createdAt).toLocaleString('pl-PL');},
      async readBackup(id){const item=backupRows.find(b=>b.id===id);if(!item)throw Error('Brak kopii');return item.raw;},
      close(){channel?.close();db?.close();window.removeEventListener('storage',storageListener);}
    };
  }
  // Read-only oracle for the separately staged v2 converter. It uses the same
  // complete row/digest/model validators as a normal v1 startup.
  async function verifyEvidence(evidence) {
    const state=evidence.meta?.find(row=>row.key==='state'),model=evidence.meta?.find(row=>row.key===MODEL_KEY);
    if(!state?.verified||!state.migration?.complete)throw Error('Niepotwierdzony checkpoint v1.');
    const value=verifyRows(state,Object.fromEntries(TABLES.map(table=>[table,evidence[table]])));
    if(await digest(value)!==state.digest)throw Error('Integralność checkpointu v1.');
    if(value.data.trainingJournal&&!model)throw Error('Brak pełnego modelu checkpointu v1.');
    if(model)await (await modelAPI()).verifyLegacyModel(model,value,state.revision);
    return {format:'pushpull-backup',version:2,...value,archives:clone(validateArchives(evidence.backups))};
  }
  return {open,parseBackup,verifyEvidence,async parseModelBackup(text){return (await modelAPI()).parseModelBackup(text)},NAME,VERSION,TABLES};
})();
