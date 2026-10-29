"""B1/B2 regressions: real UI/IndexedDB, explicitly gated Google HTTP."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_simple_data as simple
import test_drive_sync as cloud
import test_fast_start as fast
import test_indexeddb as legacy


class DriveAudit(BrowserHarness):
    configure = cloud.ManualDriveFlow.configure
    prepare = fast.FastStart.prepare
    records = legacy.IndexedDBMigration.records
    seed_cloud = simple.SimpleData.seed_cloud

    def cancelled_selected_download(self, status):
        mock = self.seed_cloud()
        before = self.records()
        downloads = []
        self.page.on('download', lambda d: downloads.append(d))
        self.backup_flow('download')
        self.page.locator('[data-drive-action=download]').click()
        expect(self.page.locator('#driveCopy option')).to_have_count(2)
        self.page.locator('#driveCopy').select_option('file-0')
        held = []
        pattern = 'https://www.googleapis.com/drive/v3/files/*?alt=media'
        def hold(route):
            held.append(route)
            self.page.evaluate('window.__heldDownload=true')
        self.context.route(pattern, hold)
        with self.page.expect_request(pattern):
            self.page.locator('[data-drive-action=download-file]').evaluate('(b)=>{b.click();b.click()}')
        self.page.wait_for_function('window.__heldDownload===true')
        self.assertEqual(len(held), 1)
        self.page.get_by_role('button', name='Anuluj pobieranie', exact=True).click()
        # Release only after cancellation, without timers or a racing sleep.
        self.context.unroute(pattern)
        if status:
            held.pop().fulfill(status=status, headers={'Access-Control-Allow-Origin': '*'},
                               content_type='application/json', body='{"error":"synthetic late error"}')
        else:
            mock.route(held.pop())
        expect(self.page.locator('[data-drive-action=download]')).to_be_enabled()
        expect(self.page.locator('[data-drive-status]')).not_to_contain_text('zlecono pobranie')
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Anulowano pobieranie')
        expect(self.page.locator('[data-drive-detail]')).to_contain_text('Anulowano pobieranie')
        self.assertFalse(downloads)
        self.assertEqual(self.records(), before)
        self.assertEqual(mock.posts, 0)
        self.page.locator('[data-tab=training]').click()
        self.page.locator('[data-tab=settings]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Anulowano pobieranie')
        self.backup_flow('download')
        self.page.locator('[data-drive-action=download]').click()
        expect(self.page.locator('#driveCopy option')).to_have_count(2)
        with self.page.expect_download() as pending:
            self.page.locator('[data-drive-action=download-file]').click()
        self.assertEqual(Path(pending.value.path()).read_text(), json.loads(mock.files['file-1']['text'])['backup'])
        expect(self.page.locator('[data-drive-status]')).to_contain_text('zlecono pobranie')
        self.assertEqual(self.records(), before)
        self.assertFalse(self.alerts, self.alerts)

    def test_cancel_selected_download_ignores_late_success_and_status(self):
        self.cancelled_selected_download(0)

    def test_cancel_selected_download_ignores_late_http_error_and_status(self):
        self.cancelled_selected_download(500)

    def test_same_turn_upload_clicks_are_not_queued_before_full_audit(self):
        self.page.add_init_script("""const original=window.fetch;window.__uploadCalls=0;
          window.fetch=(url,...args)=>{if(String(url).includes('/upload/'))__uploadCalls++;return original(url,...args)};""")
        mock = self.seed_cloud()
        mock.files = {'seed-'+key: {**value, 'id': 'seed-'+key} for key, value in mock.files.items()}
        old_copies = {key: value['text'] for key, value in mock.files.items()}
        before = self.records()
        # Both events precede the first await in the UI action queue. Hold the
        # real full audit, then let it validate every original record as usual.
        self.page.evaluate("""()=>{const audit=__fastDB.ensureFull.bind(__fastDB);window.__audits=0;
          const gate=new Promise(r=>window.__releaseAudit=r);
          __fastDB.ensureFull=async()=>{__audits++;await gate;return audit()};
        }""")
        mock.hold = True
        self.backup_flow('save')
        self.page.locator('[data-drive-action=upload]').evaluate('(b)=>{b.click();b.click()}')
        expect(self.page.locator('[data-full-audit]')).to_be_visible()
        self.page.evaluate('__releaseAudit()')
        self.page.wait_for_function('__uploadCalls===1')
        self.assertEqual(self.page.evaluate('__audits'), 1)
        self.assertTrue(mock.held)
        # Drain the UI event queue while the first network request is held.
        self.page.locator('[data-tab=training]').click()
        expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.page.locator('[data-tab=settings]').click()
        expect(self.page.locator('[data-drive-action=upload]')).to_be_disabled()
        mock.release()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zapisana i zweryfikowana', timeout=60000)
        expect(self.page.locator('[data-drive-action=upload]')).to_be_enabled()
        self.assertEqual(self.page.evaluate('__uploadCalls'), 1)
        self.assertEqual(mock.posts, 1)
        self.assertEqual(len(mock.files), 3)
        for key, text in old_copies.items():
            self.assertEqual(mock.files[key]['text'], text)
        self.assertEqual(self.records(), before)
        # A later deliberate action is a new backup, never permanently locked.
        self.backup_flow('save')
        self.page.locator('[data-drive-action=upload]').click()
        self.page.wait_for_function('__uploadCalls===2')
        expect(self.page.locator('[data-drive-action=upload]')).to_be_enabled(timeout=60000)
        self.assertEqual(mock.posts, 2)
        self.assertEqual(self.records(), before)
        self.assertFalse(self.alerts, self.alerts)

    def test_cancelled_full_audit_releases_upload_reservation_without_post(self):
        mock = self.seed_cloud()
        before = self.records()
        self.page.evaluate("""()=>{const audit=__fastDB.ensureFull.bind(__fastDB);
          const gate=new Promise(r=>window.__releaseAudit=r);
          __fastDB.ensureFull=async()=>{await gate;return audit()};
        }""")
        # Assert reservation is visible synchronously, before the queue runs.
        self.backup_flow('save')
        self.assertTrue(self.page.locator('[data-drive-action=upload]').evaluate('(b)=>{b.click();return b.disabled}'))
        expect(self.page.locator('[data-full-audit]')).to_be_visible()
        self.page.locator('[data-full-audit-cancel]').click()
        self.page.evaluate('__releaseAudit()')
        expect(self.page.locator('[data-drive-action=upload]')).to_be_enabled()
        self.assertEqual(mock.posts, 0)
        self.assertEqual(self.records(), before)
        cloud.ManualDriveFlow.upload(self)
        self.assertEqual(mock.posts, 1)
        self.assertEqual(self.records(), before)
        self.assertFalse(self.alerts, self.alerts)

    def test_upload_retries_after_offline_http_post_readback_and_integrity_errors(self):
        mock = cloud.MockGoogle()
        mock.install(self.context)
        legacy.IndexedDBMigration.prepare(self)
        self.configure()
        before = self.records()
        # Every refused or failed operation must unlock; none automatically retries.
        self.context.set_offline(True)
        self.backup_flow('save')
        self.page.locator('[data-drive-action=upload]').evaluate('(b)=>{b.click();b.click()}')
        expect(self.page.locator('[data-drive-detail]')).to_contain_text('Brak Internetu')
        expect(self.page.locator('[data-drive-action=upload]')).to_be_enabled()
        self.assertEqual(mock.posts, 0)
        self.context.set_offline(False)
        mock.error = 500
        self.backup_flow('save')
        self.page.locator('[data-drive-action=upload]').evaluate('(b)=>{b.click();b.click()}')
        expect(self.page.locator('[data-drive-detail]')).to_contain_text('(500)')
        expect(self.page.locator('[data-drive-action=upload]')).to_be_enabled()
        self.assertEqual(mock.posts, 0)
        mock.error = 0
        pattern = 'https://www.googleapis.com/drive/v3/files/*?alt=media'
        self.context.route(pattern, lambda r: r.abort('failed'))
        self.backup_flow('save')
        self.page.locator('[data-drive-action=upload]').evaluate('(b)=>{b.click();b.click()}')
        expect(self.page.locator('[data-drive-detail]')).to_contain_text('Failed to fetch')
        expect(self.page.locator('[data-drive-action=upload]')).to_be_enabled()
        self.assertEqual(mock.posts, 1)
        expect(self.page.locator('[data-drive-status]')).not_to_contain_text('Kopia zapisana i zweryfikowana')
        self.context.unroute(pattern)
        mock.corrupt = True
        self.backup_flow('save')
        self.page.locator('[data-drive-action=upload]').evaluate('(b)=>{b.click();b.click()}')
        expect(self.page.locator('[data-drive-detail]')).to_contain_text('integralności')
        expect(self.page.locator('[data-drive-action=upload]')).to_be_enabled()
        self.assertEqual(mock.posts, 2)
        mock.corrupt = False
        old_copies = {key: value['text'] for key, value in mock.files.items()}
        cloud.ManualDriveFlow.upload(self)
        self.assertEqual(mock.posts, 3)
        for key, text in old_copies.items():
            self.assertEqual(mock.files[key]['text'], text)
        self.assertEqual(self.records(), before)
        self.assertFalse(self.alerts, self.alerts)

    def test_local_export_only_acknowledges_download_request_offline(self):
        legacy.IndexedDBMigration.prepare(self)
        self.page.locator('[data-tab=settings]').click()
        before = self.records()
        self.context.set_offline(True)
        with self.page.expect_download() as pending:
            self.backup_flow('save')
            self.page.locator('[data-act=export]').click()
        expect(self.page.locator('.toast')).to_have_text('Zlecono pobranie kopii na telefon')
        parsed = self.page.evaluate('async text=>JSON.parse(text).version===3?(await PushPullDB.parseModelBackup(text)).data:PushPullDB.parseBackup(JSON.parse(text)).data', Path(pending.value.path()).read_text())
        self.assertEqual(parsed, self.state())
        self.assertEqual(self.records(), before)
        self.assertFalse(self.alerts, self.alerts)
