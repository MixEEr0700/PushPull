"""Production local v4 controls, disposable mobile browser and real IndexedDB."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,wait_for_service_worker_controller
import test_indexeddb as legacy

class LocalBackupV5(BrowserHarness):
    records=legacy.IndexedDBMigration.records

    def new_context(self, **options):
        options['service_workers']='allow'
        return super().new_context(**options)

    def settings(self):
        self.page.locator('[data-tab=settings]').click();self.advanced_data()

    def test_offline_mobile_download_preview_large_archive_and_no_writes(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        # Seed only this test profile through the existing supported legacy importer.
        self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{
         const s=db.export();s.archives=[{id:'synthetic-large',kind:'recovery',createdAt:'2026-10-24T00:00:00.000Z',raw:'x'.repeat(65*1024*1024)},
         {id:'synthetic-null',kind:'recovery',createdAt:'2026-10-24T00:00:00.000Z',raw:null}];await db.commit(s.data,{importing:true,importedCatalog:s.catalog,importedArchives:s.archives});
        }finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.settings();before=self.records()
        self.page.evaluate('navigator.serviceWorker.ready')
        wait_for_service_worker_controller(self.page)
        self.context.set_offline(True);self.page.reload()
        expect(self.page.locator('[data-act=start]')).to_be_visible();self.settings()
        with self.page.expect_download(timeout=120000) as download:self.page.locator('[data-export-v5]').click()
        text=Path(download.value.path()).read_text()
        self.assertIn('v5',download.value.suggested_filename)
        expect(self.page.locator('[data-v4-metrics]')).to_contain_text('Plik:')
        with self.page.expect_download(timeout=120000) as repeated:self.page.locator('[data-export-v5]').click()
        self.assertTrue(self.page.evaluate("""async ([a,b])=>{const {decodeBackup}=await import('./model/backup-v5.mjs'),{canonical}=await import('./model/backup-json.mjs');const x=await decodeBackup(a),y=await decodeBackup(b);return canonical(x.live.data)===canonical(y.live.data)&&canonical(x.live.catalog)===canonical(y.live.catalog)&&canonical(x.archives)===canonical(y.archives)}""",[text,Path(repeated.value.path()).read_text()]))
        self.assertEqual(json.loads(text)['version'],5)
        result=self.page.evaluate("""async text=>{const s=await(await import('./model/backup-v5.mjs')).decodeBackup(text);return {length:s.archives.find(a=>a.id==='synthetic-large').raw.length,nil:s.archives.find(a=>a.id==='synthetic-null').raw}}""",text)
        self.assertEqual(result,{'length':65*1024*1024,'nil':None})
        expect(self.page.locator('[data-restore-confirm]')).to_have_count(0)
        self.assertEqual(before,self.records())
