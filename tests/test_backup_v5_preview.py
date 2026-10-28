"""C1 production preview controls; synthetic profile, no real restore."""
from pathlib import Path
import shutil
from playwright.sync_api import expect
from test_browser import BrowserHarness,wait_for_service_worker_controller
import test_indexeddb as legacy
import test_v2_training as native

class BackupV5Preview(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    records=legacy.IndexedDBMigration.records
    activate=native.V2Training.activate
    open_result=native.V2Training.open_result
    fill_rows=native.V2Training.fill_rows

    def new_context(self,**options):
        options['service_workers']='allow'
        return super().new_context(**options)

    def test_mobile_offline_trial_preserves_all_stores_and_real_local_draft(self):
        self.activate();form=self.open_result('PUSH A','PUSH-A-3');self.fill_rows(form,'100','6')
        expect(form.locator('[data-draft-status]')).to_have_text('Szkic zapisany lokalnie · wynik niezatwierdzony')
        before=self.records()
        text=self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const source=d.export();source.archives.push({id:'c1-large',kind:'opaque',createdAt:'2026-10-24T00:00:00.000Z',raw:'x'.repeat(4*1024*1024)+'\\ud800'});return (await(await import('./model/backup-v5.mjs')).exportBackupV5(source,{createdAt:'2026-10-24T00:00:00.000Z'})).text}finally{d.close()}}""")
        self.page.evaluate('navigator.serviceWorker.ready');wait_for_service_worker_controller(self.page)
        self.context.set_offline(True);self.page.reload();self.page.locator('[data-tab=settings]').click();self.advanced_data()
        self.page.locator('[data-preview-v5]').set_input_files({'name':'v5.json','mimeType':'application/json','buffer':text.encode()})
        expect(self.page.locator('[data-v5-preview]')).to_contain_text('Szkice nie są zawarte',timeout=120000)
        expect(self.page.locator('[data-v5-trial]')).to_contain_text('pełna zgodność')
        expect(self.page.locator('[data-restore-confirm]')).to_have_count(0)
        self.assertEqual(before,self.records())
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.locator('[data-v5-cancel]').click();expect(self.page.locator('[data-v5-preview]')).to_have_count(0)
        self.page.locator('[data-preview-v5]').set_input_files({'name':'broken.json','mimeType':'application/json','buffer':text[:-1].encode()})
        expect(self.page.locator('[data-v5-error]')).to_be_visible(timeout=120000)
        expect(self.page.locator('[data-v5-preview]')).to_have_count(0)
        self.assertEqual(before,self.records())
        # Hold the read to prove cancel is actionable without waiting for the file operation.
        self.page.evaluate("() => {File.prototype.text=function(){return new Promise(resolve=>window.releaseC1=()=>resolve('{}'))}}")
        self.page.locator('[data-preview-v5]').set_input_files({'name':'held.json','mimeType':'application/json','buffer':b'{}'})
        expect(self.page.locator('[data-v5-busy]')).to_be_visible()
        self.page.locator('[data-v5-cancel]').click();self.page.evaluate('releaseC1()')
        expect(self.page.locator('[data-v5-preview]')).to_have_count(0)
        expect(self.page.locator('[data-v5-error]')).to_have_count(0)
        self.assertEqual(before,self.records())

    def test_preview_memory_limit_renderer(self):
        browser=self.pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--js-flags=--max-old-space-size=128'])
        context=browser.new_context(viewport={'width':390,'height':844})
        try:
            page=context.new_page();page.goto(self.url);expect(page.locator('[data-act=start]')).to_be_visible()
            page.evaluate("""async()=>{window.preview=await import('./model/backup-v5-preview.mjs');const d=await PushPullDB.open(()=>{});try{const source=d.export();source.archives.push({id:'synthetic',kind:'recovery',createdAt:'2026-10-24T00:00:00.000Z',raw:'x'.repeat(4*1024*1024)});window.copy=(await(await import('./model/backup-v5.mjs')).exportBackupV5(source,{createdAt:'2026-10-24T00:00:00.000Z'})).text}finally{d.close()}}""")
            context.set_offline(True)
            report=page.evaluate("async()=>preview.previewBackupV5(new Blob([copy]))")
            self.assertTrue(report['trialEqual']);self.assertGreater(report['archives'],0)
        finally:context.close();browser.close()

    def test_advanced_open_and_file_selection_in_one_turn_keep_preview_and_cancel_visible(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        raw=self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{return (await(await import('./model/backup-v5.mjs')).exportBackupV5(h.export(),{createdAt:'2026-10-24T00:00:00.000Z'})).text}finally{h.close()}}""")
        before=self.records();self.page.locator('[data-tab=settings]').click()
        # details.toggle is queued. A File selection may render before it runs.
        # Reproduce that ordering in one task instead of adding timing sleeps.
        self.page.evaluate("""raw=>{const drawer=document.querySelector('[data-backup-advanced]');drawer.open=true;const input=drawer.querySelector('[data-preview-v5]'),transfer=new DataTransfer();transfer.items.add(new File([raw],'v5.json',{type:'application/json'}));input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}))}""",raw)
        expect(self.page.locator('[data-backup-advanced]')).to_have_attribute('open','')
        expect(self.page.locator('[data-v5-preview]')).to_be_visible(timeout=120000)
        expect(self.page.locator('[data-v5-cancel]')).to_be_visible()
        self.page.locator('[data-v5-cancel]').click()
        expect(self.page.locator('[data-v5-preview]')).to_have_count(0)
        self.assertEqual(self.records(),before)
