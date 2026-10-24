"""Production local v4 controls, disposable mobile browser and real IndexedDB."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy

class LocalBackupV4(BrowserHarness):
    records=legacy.IndexedDBMigration.records

    def new_context(self, **options):
        options['service_workers']='allow'
        return super().new_context(**options)

    def settings(self):
        self.page.locator('[data-tab=settings]').click()

    def test_offline_mobile_download_preview_large_archive_and_no_writes(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        # Seed only this test profile through the existing supported legacy importer.
        self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{
         const s=db.export();s.archives=[{id:'synthetic-large',kind:'recovery',createdAt:'2026-10-24T00:00:00.000Z',raw:'x'.repeat(4*1024*1024)},
         {id:'synthetic-null',kind:'recovery',createdAt:'2026-10-24T00:00:00.000Z',raw:null}];await db.commit(s.data,{importing:true,importedCatalog:s.catalog,importedArchives:s.archives});
        }finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.settings();before=self.records()
        self.page.evaluate('navigator.serviceWorker.ready')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.context.set_offline(True);self.page.reload()
        expect(self.page.locator('[data-act=start]')).to_be_visible();self.settings()
        with self.page.expect_download(timeout=120000) as download:self.page.locator('[data-export-v4]').click()
        text=Path(download.value.path()).read_text()
        self.assertIn('v4',download.value.suggested_filename)
        self.assertEqual(json.loads(text)['version'],4)
        result=self.page.evaluate("""async text=>{const s=await(await import('./model/backup-v4.mjs')).decodeBackup(text);return {length:s.archives.find(a=>a.id==='synthetic-large').raw.length,nil:s.archives.find(a=>a.id==='synthetic-null').raw}}""",text)
        self.assertEqual(result,{'length':4*1024*1024,'nil':None})
        self.page.locator('[data-preview-v4]').set_input_files({'name':'copy.json','mimeType':'application/json','buffer':text.encode()})
        expect(self.page.locator('[data-v4-preview]')).to_contain_text('Archiwa: 3',timeout=120000)
        expect(self.page.locator('[data-restore-confirm]')).to_have_count(0)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.assertEqual(before,self.records())
        self.page.locator('[data-v4-close]').click();expect(self.page.locator('[data-v4-preview]')).to_have_count(0)
        # Corruption must remove stale preview and never unlock restore.
        bad=json.loads(text);bad['integrity']['digest']='0'*64
        self.page.locator('[data-preview-v4]').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':json.dumps(bad).encode()})
        expect(self.page.locator('[data-v4-error]')).to_be_visible(timeout=120000)
        expect(self.page.locator('[data-v4-preview]')).to_have_count(0)
        expect(self.page.locator('[data-restore-confirm]')).to_have_count(0)
        self.assertEqual(before,self.records())

    def test_export_failure_downloads_nothing_and_keeps_database(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible();self.settings();before=self.records()
        downloads=[];self.page.on('download',lambda d:downloads.append(d))
        self.page.evaluate("() => {window.CompressionStream=class{constructor(){throw Error('synthetic compression failure')}}}")
        self.page.locator('[data-export-v4]').click()
        expect(self.page.locator('[data-v4-error]')).to_contain_text('synthetic compression failure')
        self.assertEqual(downloads,[]);self.assertEqual(before,self.records())

    def test_native_v3_snapshot_and_existing_restore_candidate_are_kept_separate(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.evaluate("""async()=>{const f=await import('./tests/fixtures/backup-v4-fixture.mjs');
         const old=await(await fetch('./tests/fixtures/v1.json')).json(),plan=await(await fetch('./tests/fixtures/plan-v3.json')).json();
         const data=f.nativeData(old,plan),source={format:'pushpull-backup',version:2,data,catalog:PushPullDB.parseBackup(data).catalog,archives:[]};
         const db=await PushPullDB.open(()=>{});try{await db.importModelBackup(await f.sourceV3(source));}finally{db.close()}
        }""")
        self.page.reload();expect(self.page.locator('[data-tab=settings]')).to_be_visible();self.settings()
        before=self.records()
        with self.page.expect_download(timeout=120000) as download:self.page.locator('[data-export-v4]').click()
        text=Path(download.value.path()).read_text()
        self.assertTrue(self.page.evaluate("""async text=>{const s=await(await import('./model/backup-v4.mjs')).decodeBackup(text),db=await PushPullDB.open(()=>{});try{
         const {canonical}=await import('./model/backup-json.mjs');return canonical(s.live.data)===canonical(db.value)&&canonical(s.live.catalog)===canonical(db.export().catalog)&&canonical(s.archives)===canonical(db.export().archives);
        }finally{db.close()}}""",text))
        with self.page.expect_download(timeout=120000) as legacy:self.page.locator('[data-act=export]').click()
        old=Path(legacy.value.path()).read_bytes()
        self.page.locator('#importFile').set_input_files({'name':'legacy.json','mimeType':'application/json','buffer':old})
        expect(self.page.locator('[data-restore-confirm]')).to_be_visible(timeout=120000)
        self.page.locator('[data-preview-v4]').set_input_files({'name':'v4.json','mimeType':'application/json','buffer':text.encode()})
        expect(self.page.locator('[data-v4-preview]')).to_be_visible(timeout=120000)
        expect(self.page.locator('[data-restore-confirm]')).to_have_count(0)
        self.assertEqual(before,self.records())
