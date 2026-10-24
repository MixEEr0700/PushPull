"""Actual editors/IDB/LS, same-origin peers and read-only observation."""
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy
import test_v2_training as native
import shutil

class DraftCollector(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    records=legacy.IndexedDBMigration.records
    activate=native.V2Training.activate
    open_result=native.V2Training.open_result
    fill_rows=native.V2Training.fill_rows

    def new_context(self,**options):
        options['service_workers']='allow'
        return super().new_context(**options)

    def test_native_editor_and_two_pages_are_observed_without_modifying_stores_or_buffers(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-3');self.fill_rows(f,'100','6')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        other=self.context.new_page();other.goto(self.url);expect(other.locator('[data-act=finish]')).to_be_visible()
        other.locator('[data-expand="PUSH-A-3"]').click();other.locator('[data-panel=result]').click()
        other.locator('[data-rich-action=toggle]').click();other.locator('[data-field=kg]').first.fill('77')
        expect(other.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.records();ls=self.page.evaluate('Object.entries(localStorage)')
        self.page.evaluate('navigator.serviceWorker.ready');self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.context.set_offline(True)
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-collect-drafts]').click()
        expect(self.page.locator('[data-draft-collect-report]')).to_contain_text('Odpowiadające inne karty: 1',timeout=20000)
        self.assertEqual(before,self.records());self.assertEqual(ls,self.page.evaluate('Object.entries(localStorage)'))
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        other.close()
        # Test actual closed/restarted offline app with persisted sources.
        self.page.reload();self.page.locator('[data-tab=settings]').click();self.page.locator('[data-collect-drafts]').click()
        expect(self.page.locator('[data-draft-collect-report]')).to_contain_text('Stan pozostałych kart jest nieznany',timeout=20000)
        self.assertEqual(before,self.records())

    def test_legacy_pending_buffer_and_memory_survive_failed_idb_and_reader_writes_nothing(self):
        self.start();self.result('100','6')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.records()
        result=self.page.evaluate("""async()=>{
         const db=await PushPullDB.open(()=>{}),{openDrafts}=await import('./model/workout-drafts.mjs'),c=await import('./model/draft-collector.mjs');
         const adapter={readDrafts:()=>db.readDrafts(),writeDraft:async()=>{throw Error('synthetic quota')}};
         const drafts=await openDrafts(adapter),binding={context:{sessionId:'synthetic-session',exerciseId:'synthetic-exercise',sessionType:'PUSH A',status:'active',snapshotId:null,planVersionId:null,positionId:null,variantId:null,legacyDefinition:null},baseline:null};
         drafts.capture(binding,'legacy',{kg:'1,',reps:'',series:[{kg:'',reps:''}]});await drafts.flush();
         const before=JSON.stringify(Object.entries(localStorage));
         try{const out=await c.collectDrafts({database:db,getMemory:()=>drafts.readEvidence(),storage:()=>localStorage});return {memory:out.evidence.sources.some(s=>s.source==='editor-memory'&&s.record.value.kg==='1,'),buffer:out.evidence.sources.some(s=>s.source==='local-buffer'),unchanged:before===JSON.stringify(Object.entries(localStorage))}}finally{db.close()}
        }""")
        self.assertTrue(all(result.values()));self.assertEqual(before,self.records())

    def test_offline_reader_under_memory_limit(self):
        browser=self.pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--js-flags=--max-old-space-size=128'])
        context=browser.new_context(viewport={'width':390,'height':844})
        try:
            page=context.new_page();page.goto(self.url);expect(page.locator('[data-act=start]')).to_be_visible()
            page.evaluate("""async()=>{window.c=await import('./model/draft-collector.mjs');window.db=await PushPullDB.open(()=>{});localStorage.setItem('pushpull_workout_draft_v1:opaque','x'.repeat(500000));
             const idb=await new Promise((resolve,reject)=>{const r=indexedDB.open('pushpull');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
             try{await new Promise((resolve,reject)=>{const tx=idb.transaction('backups','readwrite');tx.objectStore('backups').put({id:'synthetic-large-archive',kind:'recovery',createdAt:'2026-10-24T00:00:00.000Z',raw:'x'.repeat(4*1024*1024)});tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error)})}finally{idb.close()}
            }""")
            before=self.records(page)
            context.set_offline(True)
            result=page.evaluate("""async()=>{const before=JSON.stringify(Object.entries(localStorage)),r=await c.collectDrafts({database:db,getMemory:()=>[]});return {n:r.evidence.sources.length,q:r.diagnostics.quarantined,same:before===JSON.stringify(Object.entries(localStorage)),coverage:r.coverage.otherTabs}}""")
            self.assertEqual(result['n'],1);self.assertEqual(result['q'],1);self.assertTrue(result['same']);self.assertEqual(result['coverage'],'unknown');self.assertEqual(before,self.records(page))
        finally:context.close();browser.close()

    def test_real_storage_change_between_reads_refuses_and_abort_leaves_all_stores_unchanged(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible();before=self.records()
        result=self.page.evaluate("""async()=>{const c=await import('./model/draft-collector.mjs'),d=await PushPullDB.open(()=>{});let sequence=0;
         try{let unstable=false,cancelled=false;
          try{await c.collectDrafts({database:d,getMemory:()=>[],pause:async()=>localStorage.setItem('pushpull_workout_draft_v1:changing',String(++sequence))})}catch(e){unstable=e.code==='unstable'}
          const controller=new AbortController();try{await c.collectDrafts({database:d,getMemory:()=>[],signal:controller.signal,pause:async()=>controller.abort()})}catch(e){cancelled=e.name==='AbortError'}
          return {unstable,cancelled,attempts:sequence};
         }finally{d.close()}}""")
        self.assertEqual(result,{'unstable':True,'cancelled':True,'attempts':2});self.assertEqual(before,self.records())
