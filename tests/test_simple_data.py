"""Stage G: four manual actions, real native stores, only Google HTTP is mocked."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_drive_sync as cloud
import test_indexeddb as legacy
import test_fast_start as fast

class SimpleData(BrowserHarness):
    configure=cloud.ManualDriveFlow.configure
    prepare=fast.FastStart.prepare
    records=legacy.IndexedDBMigration.records

    def seed_cloud(self):
        mock=cloud.MockGoogle();mock.install(self.context);self.prepare()
        nodes=self.page.evaluate("""async()=>{const m=await import('./model/drive-sync.mjs'),raw=await(await fetch('./tests/fixtures/v1.json')).text(),out=[];for(let i=0;i<2;i++){const n=await m.makeNode(raw,[]);out.push({text:JSON.stringify(n),appProperties:m.properties(n)})}return out}""")
        for i,n in enumerate(nodes):
            key='file-'+str(i);mock.files[key]={**n,'id':key,'createdTime':'2026-10-0'+str(i+1)+'T00:00:00Z'}
        self.configure()
        # The configuration does not need live history or archive materialization.
        self.assertTrue(self.page.evaluate('__fastDB.archivesDeferred&&__fastDB.historyDeferred'))
        self.page.locator('[data-backup-advanced] > summary').click()
        return mock

    def test_four_actions_download_exact_file_without_restore_or_local_audit(self):
        mock=self.seed_cloud();before=self.records();downloads=[];self.page.on('download',lambda d:downloads.append(d))
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            primary=self.page.locator('[data-primary-backups]')
            self.assertEqual(primary.locator(':scope > button,:scope > label').evaluate_all('(es)=>es.map(e=>e.textContent.trim())'),['Zapisz kopię na Google Drive','Pobierz kopię na telefon','Pobierz kopię z Google Drive','Importuj kopię z telefonu'])
            expect(self.page.locator('#driveConfig input')).not_to_be_visible()
            expect(self.page.locator('[data-export-v5]')).not_to_be_visible()
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            for box in primary.locator(':scope > button,:scope > label').all():self.assertGreaterEqual(box.bounding_box()['height'],44)
        self.page.locator('[data-drive-action=download]').click()
        expect(self.page.locator('#driveCopy option')).to_have_count(2)
        self.assertEqual(self.page.locator('#driveCopy option').first.get_attribute('value'),'file-1')
        expect(self.page.locator('[data-restore-confirm]')).to_have_count(0)
        self.assertEqual(self.records(),before)
        self.page.locator('#driveCopy').select_option('file-0')
        self.assertEqual(self.records(),before)
        with self.page.expect_download() as pending:self.page.locator('[data-drive-action=download-file]').click()
        text=Path(pending.value.path()).read_text()
        self.assertEqual(text,json.loads(mock.files['file-0']['text'])['backup'])
        self.assertEqual(self.records(),before);self.assertEqual(mock.posts,0)
        self.assertTrue(self.page.evaluate('__fastDB.archivesDeferred&&__fastDB.historyDeferred'))
        self.assertFalse(self.page.locator('[data-restore-preview],[data-restore-confirm]').count())
        self.assertEqual(len(downloads),1)
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Nie przywrócono danych')

    def test_corrupt_unavailable_and_offline_cloud_copy_preserve_all_native_stores(self):
        mock=self.seed_cloud();before=self.records();downloads=[];self.page.on('download',lambda d:downloads.append(d))
        self.page.locator('[data-drive-action=download]').click();expect(self.page.locator('#driveCopy option')).to_have_count(2)
        del mock.files['file-1']  # Explicit selection disappears; no silent fallback.
        self.page.locator('[data-drive-action=download-file]').click()
        expect(self.page.locator('[data-drive-detail]')).to_contain_text('nie jest już dostępna')
        self.assertEqual(self.records(),before)
        mock.corrupt=True;self.page.locator('[data-drive-action=download]').click()
        expect(self.page.locator('[data-drive-detail]')).to_contain_text('Nie znaleziono prawidłowej kopii')
        self.context.set_offline(True);self.page.locator('[data-drive-action=download]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Brak Internetu')
        self.assertFalse(downloads);self.assertEqual(mock.posts,0);self.assertEqual(self.records(),before)
        self.assertTrue(self.page.evaluate('__fastDB.archivesDeferred&&__fastDB.historyDeferred'))
        self.advanced_data();expect(self.page.locator('[data-export-v4]')).to_be_visible()
        self.page.locator('[data-tab=training]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()

    def test_cancel_late_readonly_download_and_double_click_do_not_deliver_a_file(self):
        mock=self.seed_cloud();before=self.records();held=[];downloads=[];self.page.on('download',lambda d:downloads.append(d))
        self.context.route('https://www.googleapis.com/drive/v3/files?*',lambda r:held.append(r))
        with self.page.expect_request('https://www.googleapis.com/drive/v3/files?*'):
            self.page.locator('[data-drive-action=download]').evaluate('(b)=>{b.click();b.click()}')
        expect(self.page.locator('[data-drive-download-busy]')).to_be_visible()
        self.assertEqual(len(held),1)
        self.page.locator('[data-restore-cancel]').click()
        self.page.locator('[data-tab=training]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        mock.route(held.pop())
        self.page.locator('[data-tab=settings]').click()
        expect(self.page.locator('[data-drive-action=download]')).to_be_enabled()
        expect(self.page.locator('#driveCopy,[data-restore-confirm]')).to_have_count(0)
        self.assertFalse(downloads);self.assertEqual(mock.posts,0);self.assertEqual(self.records(),before)
