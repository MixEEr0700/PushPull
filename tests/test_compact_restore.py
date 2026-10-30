"""Local PPC1 confirmation uses the existing native transaction and no cloud path."""
from test_browser import BrowserHarness,wait_for_service_worker_controller,ROOT
import test_indexeddb as legacy
from playwright.sync_api import expect
import base64

class CompactRestore(BrowserHarness):
    records=legacy.IndexedDBMigration.records

    def make_file(self,extra=False):
        encoded=self.page.evaluate("""async extra=>{const {previewFixture}=await import('./tests/fixtures/compact-preview-fixture.mjs'),{writeCompactModel}=await import('./model/compact-backup-writer.mjs');
         const s=previewFixture(await(await fetch('./tests/fixtures/v1.json')).json(),await(await fetch('./tests/fixtures/plan-test-3x5.json')).json());delete s.settings;delete s.metadata;s.data.syntheticSettings={unicode:'Ł😀\\ud800',kept:true};if(extra)s.settings={keep:true};window.incoming=s;
         const bytes=new Uint8Array(await(await writeCompactModel(s)).arrayBuffer());let raw='';for(let i=0;i<bytes.length;i+=8192)raw+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(raw)}""",extra)
        return {'name':'test.ppc1','mimeType':'application/octet-stream','buffer':base64.b64decode(encoded)}

    def open_file(self,payload):
        self.page.locator('[data-tab=settings]').click();self.backup_flow('restore');self.page.locator('#importFile').set_input_files(payload)

    def test_full_restore_offline_mobile_strict_complete_preimage_and_restart(self):
        self.context.close();self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        legacy.IndexedDBMigration.prepare(self);wait_for_service_worker_controller(self.page)
        payload=self.make_file();before=self.records();local=self.page.evaluate('({...localStorage})');self.context.set_offline(True)
        self.open_file(payload);expect(self.page.locator('[data-ppc1-preview]')).to_be_visible(timeout=60000)
        self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
        for w in (360,390,412):
            self.page.set_viewport_size({'width':w,'height':844});self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.evaluate(legacy.PAUSE);self.page.locator('[data-restore-confirm]').click();self.page.wait_for_function('window.__held===true',timeout=60000)
        expect(self.page.locator('[data-restore-success]')).to_have_count(0);self.page.evaluate('__hold=false')
        expect(self.page.locator('[data-restore-success]')).to_be_visible(timeout=60000)
        result=self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{const actual=await h.auditExport(),{sameTrialData}=await import('./model/backup-v5-preview.mjs');return {data:sameTrialData(actual.data,incoming.data),catalog:sameTrialData(actual.catalog,incoming.catalog),archives:incoming.archives.every(a=>actual.archives.some(b=>sameTrialData(a,b))),preimage:actual.archives.some(a=>a.kind==='before-import')}}finally{h.close()}}""")
        self.assertTrue(all(result.values()),result);saved=self.records();self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible(timeout=60000);self.assertEqual(self.records(),saved)
        self.assertEqual(self.page.evaluate('({...localStorage})'),local)

    def test_unsupported_corrupt_cancel_and_late_worker_never_write(self):
        legacy.IndexedDBMigration.prepare(self);payload=self.make_file();bad=self.make_file(True);before=self.records();local=self.page.evaluate('({...localStorage})')
        self.open_file(bad);expect(self.page.locator('[data-restore-error]')).to_contain_text('Nie zmieniono danych',timeout=60000);expect(self.page.locator('[data-restore-confirm]')).to_have_count(0)
        corrupt={**payload,'buffer':payload['buffer'][:-1]};self.open_file(corrupt);expect(self.page.locator('[data-restore-error]')).to_be_visible(timeout=60000)
        self.page.evaluate("""()=>{const Native=Worker;window.Worker=class extends Native{constructor(url,opts){super(url,opts);if(String(url).includes('compact-backup-restore')){const send=this.postMessage.bind(this);this.postMessage=v=>window.releasePPC=()=>send(v)}}}}""")
        self.open_file(payload);self.page.wait_for_function('!!window.releasePPC');self.page.locator('[data-tab=training]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible(timeout=1500);self.page.evaluate('releasePPC()')
        self.page.locator('[data-tab=settings]').click();expect(self.page.locator('[data-restore-preview]')).to_have_count(0)
        self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)

    def test_quota_abort_and_concurrent_root_preserve_database(self):
        legacy.IndexedDBMigration.prepare(self);payload=self.make_file();self.open_file(payload);expect(self.page.locator('[data-ppc1-preview]')).to_be_visible(timeout=60000)
        before=self.records();local=self.page.evaluate('({...localStorage})')
        self.page.evaluate("""()=>{window.originalPPCPut=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...a){if(this.name==='journalState')throw new DOMException('test quota','QuotaExceededError');return originalPPCPut.apply(this,a)}}""")
        self.page.locator('[data-restore-confirm]').click();expect(self.page.locator('[data-restore-error]')).to_be_visible(timeout=60000);self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
        self.page.evaluate('()=>{IDBObjectStore.prototype.put=originalPPCPut}')
        self.open_file(payload);expect(self.page.locator('[data-ppc1-preview]')).to_be_visible(timeout=60000)
        self.page.evaluate("""()=>{IDBObjectStore.prototype.put=function(...a){if(this.name==='journalState'){this.transaction.abort();throw new DOMException('test abort','AbortError')}return originalPPCPut.apply(this,a)}}""")
        self.page.locator('[data-restore-confirm]').click();expect(self.page.locator('[data-restore-error]')).to_be_visible(timeout=60000);self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
        self.page.evaluate('()=>{IDBObjectStore.prototype.put=originalPPCPut}')
        self.open_file(payload);expect(self.page.locator('[data-ppc1-preview]')).to_be_visible(timeout=60000)
        self.page.evaluate("""async()=>{window.BroadcastChannel=undefined;const h=await PushPullDB.open(()=>{});try{const d=h.value;d.concurrentPPC=true;await h.commit(d)}finally{h.close()}}""")
        changed=self.records();self.page.locator('[data-restore-confirm]').click();expect(self.page.locator('[data-restore-error]')).to_contain_text('zmieni',timeout=60000);expect(self.page.locator('[data-restore-success]')).to_have_count(0);self.assertEqual(self.records(),changed);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
