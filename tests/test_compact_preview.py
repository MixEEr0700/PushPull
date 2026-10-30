"""Isolated synthetic PPC1 inspection against real, unchanged native IndexedDB."""
from test_browser import BrowserHarness
import test_fast_start as fast
import test_indexeddb as legacy
import shutil

class CompactPreview(BrowserHarness):
    prepare=fast.FastStart.prepare
    records=legacy.IndexedDBMigration.records

    def fixture(self):
        self.prepare()
        self.page.evaluate("""async()=>{
         window.previewAPI=await import('./model/compact-backup-preview.mjs');window.writer=await import('./model/compact-backup-writer.mjs');
         const source=structuredClone(await __fastDB.auditExport());source.settings={synthetic:true};window.previewFile=await writer.writeCompactModel(source);window.inspector=previewAPI.createCompactPreview();
         window.readRoot=async()=>{const db=await new Promise((ok,no)=>{const r=indexedDB.open('pushpull');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});
          try{return await new Promise((ok,no)=>{const tx=db.transaction('journalState'),r=tx.objectStore('journalState').get('active');let root;r.onsuccess=()=>root=r.result.root;tx.oncomplete=()=>ok(root);tx.onabort=()=>no(tx.error)})}finally{db.close()}};
        }""")

    def test_offline_complete_preview_errors_and_cancel_do_not_mutate_any_store(self):
        self.context.close();browser=self.pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--js-flags=--max-old-space-size=64'])
        self.addCleanup(browser.close);self.context=browser.new_context(viewport={'width':390,'height':844},service_workers='block');self.addCleanup(self.context.close);self.page=self.context.new_page();self.page.goto(self.url)
        self.fixture();before=self.records();local=self.page.evaluate('({...localStorage})');self.context.set_offline(True)
        result=self.page.evaluate("""async()=>{
         window.writeAttempts=0;for(const key of ['put','add','delete','clear'])IDBObjectStore.prototype[key]=function(){writeAttempts++;throw Error('write forbidden')};
         for(const key of ['setItem','removeItem','clear'])Storage.prototype[key]=function(){writeAttempts++;throw Error('storage write forbidden')};
         const report=await inspector.preview(previewFile,{getRevision:readRoot});let corrupt=false,limit=false;
         try{await inspector.preview(previewFile.slice(0,-1))}catch(e){corrupt=e.code==='invalid-container'}
         try{await inspector.preview(previewFile,{limits:{totalDecodedBytes:1}})}catch(e){limit=e.code==='limit'}
         const c=new AbortController();c.abort();let cancelled=false;try{await inspector.preview(previewFile,{signal:c.signal})}catch(e){cancelled=e.name==='AbortError'}
         return {report,corrupt,limit,cancelled,writes:writeAttempts,cleared:await inspector.read()===null};
        }""")
        self.assertFalse(result['report']['canRestore']);self.assertTrue(result['report']['revisionChecked']);self.assertTrue(result['report']['settingsPresent']);self.assertGreater(result['report']['sessions'],0);self.assertTrue(all(result[k] for k in ['corrupt','limit','cancelled','cleared']));self.assertEqual(result['writes'],0)
        self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)

    def test_other_handle_without_broadcast_invalidates_pending_and_published_reports(self):
        self.fixture();self.page.evaluate("""()=>{window.probes=0;window.releasePreview=null;window.pending=inspector.preview(previewFile,{getRevision:async()=>{if(++probes===2)await new Promise(r=>releasePreview=r);return readRoot()}}).then(()=>({ok:true}),e=>({code:e.code}));}""")
        self.page.wait_for_function('!!window.releasePreview')
        self.page.evaluate("""async()=>{window.BroadcastChannel=undefined;const h=await PushPullDB.open(()=>{});try{const d=h.value;d.syntheticConcurrent='changed';await h.commit(d)}finally{h.close()}}""")
        changed=self.records();local=self.page.evaluate('({...localStorage})');result=self.page.evaluate('async()=>{releasePreview();return pending}')
        self.assertEqual(result,{'code':'revision'});self.assertIsNone(self.page.evaluate('async()=>inspector.read()'));self.assertEqual(self.records(),changed);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
        self.page.evaluate('async()=>inspector.preview(previewFile,{getRevision:readRoot})')
        self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{const d=h.value;d.syntheticConcurrent='changed-again';await h.commit(d)}finally{h.close()}}""")
        changed=self.records();result=self.page.evaluate("async()=>{try{await inspector.read();return 'unexpected'}catch(e){return e.code}}")
        self.assertEqual(result,'revision');self.assertEqual(self.records(),changed)

    def test_cancelled_late_probe_cannot_publish_and_navigation_remains_unchanged(self):
        self.fixture();before=self.records();local=self.page.evaluate('({...localStorage})')
        self.page.evaluate("""()=>{window.late=null;window.pending=inspector.preview(previewFile,{getRevision:()=>new Promise(r=>late=r)}).then(()=>({ok:true}),e=>({name:e.name}));inspector.cancel()}""")
        self.assertEqual(self.page.evaluate('async()=>pending'),{'name':'AbortError'})
        self.page.locator('[data-tab=settings]').click();self.page.evaluate("late('old-root')")
        self.assertIsNone(self.page.evaluate('async()=>inspector.read()'));self.assertEqual(self.page.locator('[data-primary-backups] [data-backup-flow]').count(),2)
        self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
