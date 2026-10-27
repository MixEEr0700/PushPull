"""Selective startup reads and lossless live operations against native IndexedDB."""
from playwright.sync_api import expect
from test_browser import BrowserHarness,ROOT

TRACE=r"""(()=>{window.__reads=[];for(const op of ['get','getAll']){const f=IDBObjectStore.prototype[op];IDBObjectStore.prototype[op]=function(...a){const r=f.apply(this,a),name=this.name;r.addEventListener('success',()=>__reads.push({name,op,ids:op==='getAll'?r.result.map(x=>x.id):[r.result?.id]}));return r}}})();"""

class FastStart(BrowserHarness):
    def prepare(self):
        self.page.wait_for_selector('[data-act=start]')
        self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{
         const {nativeData,AT}=await import('./tests/fixtures/backup-v4-fixture.mjs'),data=nativeData(await(await fetch('./tests/fixtures/v1.json')).json(),await(await fetch('./tests/fixtures/plan-v3.json')).json());
         await h.commit(data,{importing:true,importedArchives:[{id:'large-raw',kind:'opaque',createdAt:AT,raw:'Ł😀\\\"\\n'.repeat(262144)}]});
        }finally{h.close()}}""")
        code=(ROOT/'app.js').read_text();marker='const database=await PushPullDB.open(fresh,{training:true});';self.assertEqual(code.count(marker),1)
        self.page.route('**/app.js',lambda r:r.fulfill(body=code.replace(marker,marker+'window.__fastDB=database;'),content_type='text/javascript'))
        self.page.add_init_script(TRACE);self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()

    def test_startup_avoids_raw_checkpoint_and_retained_objects_and_full_export_still_audits(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const reads=structuredClone(__reads),deferred=__fastDB.archivesDeferred;let refused=false,modelRefused=false;
         try{__fastDB.export()}catch{refused=true}
         try{void __fastDB.model}catch{modelRefused=true}
         const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull'),before=await api.readRecords(db);
         const archive=before.records.journalArchives.find(r=>r.id==='large-raw');
         const untouched=!reads.some(r=>r.name==='journalCheckpoints'||r.name==='journalObjects'&&(r.op==='getAll'||r.ids.includes(archive.ref)));
         const actual=await __fastDB.auditExport();await __fastDB.ensureFull();
         const same=api.same(actual,__fastDB.export()),after=await api.readRecords(db);db.close();return {deferred,refused,modelRefused,untouched,same,unchanged:api.same(before,after),raw:actual.archives.find(r=>r.id==='large-raw').raw.length};
        }""")
        self.assertTrue(all(result[k] for k in ['deferred','refused','modelRefused','untouched','same','unchanged']),result)
        self.assertGreater(result['raw'],1000000)

    def test_live_session_finish_preserves_every_archive_checkpoint_and_retained_object(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull'),before=await api.readRecords(db);
         await __fastDB.ensureHistory();const d=__fastDB.value;d.sessions.find(s=>s.id===d.activeId).status='done';d.activeId=null;
         __reads=[];await __fastDB.commit(d);const reads=structuredClone(__reads),deferred=__fastDB.archivesDeferred,after=await api.readRecords(db),audited=await __fastDB.auditExport();db.close();
         const kept=s=>before.records[s].every(r=>after.records[s].some(v=>api.same(r,v)));
         return {deferred,unchangedCheckpoints:api.same(before.records.journalCheckpoints,after.records.journalCheckpoints),unchangedArchives:api.same(before.records.journalArchives,after.records.journalArchives),objectsKept:kept('journalObjects'),indexKept:kept('journalIndex'),noRaw:!reads.some(r=>r.name==='journalCheckpoints'||r.name==='journalObjects'&&r.op==='getAll'),data:api.same(audited.data,d)};
        }""")
        self.assertTrue(all(result.values()),result)
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.assertFalse(self.alerts,self.alerts)

    def test_archive_corruption_is_deferred_but_never_exported_as_verified(self):
        self.prepare()
        self.page.evaluate("""async()=>{const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull');try{await api.transact(db,['journalArchives','journalObjects'],'readwrite',async tx=>{const a=await api.request(tx.objectStore('journalArchives').get('large-raw')),r=await api.request(tx.objectStore('journalObjects').get(a.ref));tx.objectStore('journalObjects').put({...r,json:r.json+' '})})}finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        result=self.page.evaluate("""async()=>{let rejected=0;for(const f of [()=>__fastDB.auditExport(),()=>__fastDB.ensureFull()])try{await f()}catch{rejected++}return {rejected,deferred:__fastDB.archivesDeferred}}""")
        self.assertEqual(result,{'rejected':2,'deferred':True})

    def test_current_live_object_corruption_refuses_startup_and_preserves_evidence(self):
        self.prepare()
        self.page.evaluate("""async()=>{const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull');try{const b=await api.readRecords(db),row=b.records.journalSessions[0],obj=b.records.journalObjects.find(r=>r.id===row.ref);await api.transact(db,['journalObjects'],'readwrite',tx=>tx.objectStore('journalObjects').put({...obj,json:obj.json+' '}))}finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[role=alert]').first).to_contain_text('object')
        self.assertEqual(self.page.locator('[data-act=start],[data-act=finish]').count(),0)
        result=self.page.evaluate("""async()=>{const raw=await __fastDB.recoveryEvidence();return {version:raw.version,sessions:raw.records.journalSessions.length,archives:raw.records.journalArchives.length}}""")
        self.assertEqual(result['version'],2);self.assertGreater(result['sessions'],0);self.assertGreater(result['archives'],0)

    def test_old_c_root_certification_is_once_and_does_not_rewrite_history(self):
        self.prepare()
        self.page.evaluate("""async()=>{const api=await import('./model/journal-idb.mjs'),codec=await import('./model/journal-protocol.mjs'),db=await api.connectV2('pushpull');try{
         const b=await api.readRecords(db),{allocation,runtime,...old}=b.state,state=await codec.sealState(old);window.__oldRows=b.records;
         await api.transact(db,['journalState'],'readwrite',tx=>tx.objectStore('journalState').put(state));
        }finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        result=self.page.evaluate("""async()=>{const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull');try{const b=await api.readRecords(db);return {allocated:!!b.state.allocation,revision:b.state.revision,source:JSON.stringify(await __fastDB.auditExport())}}finally{db.close()}}""")
        self.assertTrue(result['allocated'])
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        again=self.page.evaluate("""async()=>({revision:__fastDB.revision,deferred:__fastDB.archivesDeferred,source:JSON.stringify(await __fastDB.auditExport())})""")
        self.assertEqual(again['revision'],result['revision']);self.assertEqual(again['source'],result['source']);self.assertTrue(again['deferred'])

    def test_lazy_full_upgrade_rejects_concurrent_root_and_keeps_last_result(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull'),w=await api.openWriter(db),e=structuredClone(w.source.data.entries.find(e=>e.performance));
         e.performance.rows[0].segments[0].kg='44';const {flatten}=await import('./model/performance.mjs');e.series=flatten(e.performance);e.kg=e.series[0].kg;
         await w.saveResult({sessionId:e.sessionId,exerciseId:e.exerciseId,entry:e,...w.context(e.sessionId,e.exerciseId)});
         let rejected=false;try{await __fastDB.ensureFull()}catch{rejected=true}
         const complete=await w.audit();db.close();return {rejected,retained:complete.data.entries.find(r=>r.id===e.id).kg==='44'};
        }""")
        self.assertEqual(result,{'rejected':True,'retained':True})

    def test_live_abort_and_quota_leave_every_store_and_memory_unchanged(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull'),before=await api.readRecords(db);await __fastDB.ensureHistory();const value=__fastDB.value;let failures=0;
         for(const kind of ['QuotaExceededError','AbortError']){
          const add=IDBObjectStore.prototype.add;let fired=false;
          IDBObjectStore.prototype.add=function(...args){if(this.name==='journalSessions'&&!fired){fired=true;if(kind==='AbortError')this.transaction.abort();throw new DOMException('injected',kind)}return add.apply(this,args)};
          try{const d=structuredClone(value);d.sessions.find(s=>s.id===d.activeId).status='done';d.activeId=null;await __fastDB.commit(d)}catch{failures++}finally{IDBObjectStore.prototype.add=add}
          if(!api.same(before,await api.readRecords(db))||!api.same(value,__fastDB.value))throw Error('rollback changed data');
         }db.close();return failures;
        }""")
        self.assertEqual(result,2)

    def test_partial_writer_preserves_strict_complete_cas_and_archive_bytes(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull'),before=await api.readRecords(db),e=structuredClone(__fastDB.value.entries.find(e=>e.performance));
         const {flatten}=await import('./model/performance.mjs');e.performance.rows[0].segments[0].kg='45';e.series=flatten(e.performance);e.kg=e.series[0].kg;
         const cmd={sessionId:e.sessionId,exerciseId:e.exerciseId,entry:e,...__fastDB.resultContext(e.sessionId,e.exerciseId)},transaction=IDBDatabase.prototype.transaction;let completed=false,strict=false;
         IDBDatabase.prototype.transaction=function(...args){const tx=transaction.apply(this,args);if(tx.mode==='readwrite'&&[...tx.objectStoreNames].includes('journalResults')){strict=tx.durability==='strict';tx.addEventListener('complete',()=>completed=true)}return tx};
         __reads=[];let ack;try{ack=await __fastDB.saveResult(cmd)}finally{IDBDatabase.prototype.transaction=transaction}
         const reads=structuredClone(__reads);let stale=false;try{await __fastDB.saveResult(cmd)}catch{stale=true}
         const after=await api.readRecords(db),source=await api.openWriter(db);db.close();
         const refs=new Set(before.records.journalArchives.map(r=>r.ref));
         return {completed,strict,stale,noRaw:!reads.some(r=>r.name==='journalCheckpoints'||r.name==='journalObjects'&&(r.op==='getAll'||r.ids.some(id=>refs.has(id)))),checkpoint:api.same(before.records.journalCheckpoints,after.records.journalCheckpoints),raw:before.records.journalObjects.filter(r=>refs.has(r.id)).every(r=>after.records.journalObjects.some(v=>api.same(r,v))),result:source.source.data.entries.find(r=>r.id===ack.entry.id).kg==='45'};
        }""")
        self.assertTrue(all(result.values()),result)

    def test_failed_preload_reports_error_without_enabling_training_or_unhandled_rejection(self):
        self.page.wait_for_selector('[data-act=start]')
        self.page.route('**/model/plan-overview.mjs',lambda r:r.abort())
        self.page.reload()
        expect(self.page.locator('#app')).to_contain_text('Nie udało się otworzyć bazy')
        self.assertEqual(self.page.locator('[data-act=start],[data-act=finish]').count(),0)
        self.assertFalse(self.errors,self.errors)

    def test_pending_conversion_recovery_download_contains_legacy_and_native_stores_atomically(self):
        context=self.new_context();page=context.new_page();page.goto(self.url+'tests/')
        page.add_script_tag(url=self.url+'storage.js');page.add_script_tag(url=self.url+'indexeddb.js')
        result=page.evaluate("""async()=>{
         const old=await(await fetch('./fixtures/v1.json')).json();localStorage.setItem(PushPullStorage.KEY,JSON.stringify(old));
         const legacy=await PushPullDB.openV1(()=>old);if(legacy.error)throw legacy.error;
         await legacy.prepareModel({backupText:JSON.stringify(legacy.export()),ownerId:'recovery-test'});legacy.close();
         const api=await import('../model/journal-idb.mjs'),one=await api.request(indexedDB.open('pushpull',1)),evidence=await api.legacyEvidence(one);one.close();
         const pending=await api.connectV2('pushpull');pending.close();
         const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(...args){if(this.name==='journalObjects')throw new DOMException('synthetic conversion quota','QuotaExceededError');return add.apply(this,args)};
         let handle;try{handle=await PushPullDB.open(()=>{throw Error('no reset')})}finally{IDBObjectStore.prototype.add=add}
         try{const dump=await handle.recoveryEvidence();
          return {blocked:!!handle.error,version:dump.version,pending:dump.state===null,nativeEmpty:dump.records.journalSessions.length===0,legacy:!!dump.records.sessions&&api.same(dump.records.sessions,evidence.sessions),models:dump.records.meta?.some(r=>r.key==='training-model-v1')??false,archives:!!dump.records.backups&&api.same(dump.records.backups,evidence.backups)};
         }finally{handle.close()}
        }""")
        self.assertEqual(result,{'blocked':True,'version':2,'pending':True,'nativeEmpty':True,'legacy':True,'models':True,'archives':True})
