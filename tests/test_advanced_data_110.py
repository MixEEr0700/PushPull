"""Read-only rescue previews and the advanced controls on native IndexedDB v2."""
from playwright.sync_api import expect
from test_browser import BrowserHarness, wait_for_service_worker_controller
import test_fast_start as fast
import test_indexeddb as legacy

class AdvancedData110(BrowserHarness):
    prepare=fast.FastStart.prepare
    records=legacy.IndexedDBMigration.records

    def panel(self):
        self.page.locator('[data-tab=settings]').click()
        drawer=self.page.locator('[data-backup-advanced]')
        if not drawer.evaluate('(e)=>e.open'):
            drawer.locator(':scope > summary').focus();self.page.keyboard.press('Enter')
            expect(drawer).to_have_attribute('open','')
        return drawer

    def test_groups_offline_preview_and_records_are_unchanged(self):
        self.context.close();self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog);self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.goto(self.url)
        self.prepare();wait_for_service_worker_controller(self.page);self.context.set_offline(True)
        before=self.records();local=self.page.evaluate('({...localStorage})');self.page.evaluate('__reads=[]');drawer=self.panel()
        self.assertFalse(self.page.evaluate("__reads.some(r=>r.name==='journalObjects'||r.name==='journalCheckpoints')"))
        self.assertEqual(drawer.locator('section > h3').all_text_contents(),['Połączenie Google Drive','Zachowane kopie ratunkowe','Diagnostyka kopii'])
        for heading in ('Połączenie Google Drive','Zachowane kopie ratunkowe','Diagnostyka kopii'):expect(drawer.get_by_role('heading',name=heading,level=3)).to_be_visible()
        expect(drawer.locator('[data-technical]')).not_to_have_attribute('open','')
        expect(drawer.locator('[data-export-v4]')).to_be_hidden()
        for width in (360,390,412):
            self.page.set_viewport_size({'width':width,'height':844});self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        expect(drawer.locator('[data-load-backups]')).to_be_visible()
        archive_ref=next(row['ref'] for row in before['journalArchives'] if row['id']=='large-raw')
        self.page.evaluate('__reads=[]')
        drawer.locator('[data-load-backups]').click();expect(drawer.locator('#backupKey')).to_be_visible(timeout=60000)
        self.assertTrue(self.page.evaluate("ref=>__reads.some(r=>r.name==='journalObjects'&&r.ids.includes(ref))",archive_ref))
        for width in (360,390,412):
            self.page.set_viewport_size({'width':width,'height':844})
            for button in drawer.locator('[data-rescue-preview],[data-backup-export]').all():self.assertGreaterEqual(button.bounding_box()['height'],44)
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        # The preserved legacy migration preimage is a valid v1 backup.
        self.page.locator('[data-rescue-preview]').click();expect(self.page.locator('[data-rescue-result]')).to_be_visible(timeout=60000)
        expect(self.page.locator('[data-rescue-result]')).to_contain_text('Podgląd bez przywracania')
        expect(self.page.locator('[data-restore-preview],[data-restore-confirm]')).to_have_count(0)
        self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
        drawer.locator('[data-technical] > summary').click();expect(drawer.locator('[data-export-v4]')).to_be_visible();expect(drawer.locator('[data-preview-v5]')).to_be_attached();expect(drawer.locator('[data-collect-drafts]')).to_be_visible()
        self.assertFalse(self.alerts,self.alerts)

    def test_cancel_and_concurrent_revision_never_publish_stale_preview(self):
        self.prepare();before=self.records();self.panel();self.page.locator('[data-load-backups]').click();expect(self.page.locator('#backupKey')).to_be_visible(timeout=60000)
        self.page.evaluate("""()=>{const Native=Worker;window.Worker=class extends Native{constructor(url,opts){super(url,opts);if(String(url).endsWith('/legacy-model.mjs')){const send=this.postMessage.bind(this);this.postMessage=v=>window.__releaseRescue=()=>send(v)}}}}""")
        self.page.locator('[data-rescue-preview]').focus();self.page.keyboard.press('Enter');self.page.wait_for_function('!!window.__releaseRescue')
        expect(self.page.locator('[data-rescue-cancel]')).to_be_focused();self.page.keyboard.press('Enter');expect(self.page.locator('[data-rescue-preview]')).to_be_focused();self.page.evaluate('__releaseRescue()')
        expect(self.page.locator('[data-rescue-result]')).to_have_count(0);self.assertEqual(self.records(),before)
        self.page.evaluate('window.__releaseRescue=null');self.page.locator('[data-rescue-preview]').click();self.page.wait_for_function('!!window.__releaseRescue')
        self.page.evaluate("""async()=>{const d=__fastDB.value;d.diagnosticSentinel='concurrent';await __fastDB.commit(d)}""")
        changed=self.records();self.page.evaluate('__releaseRescue()')
        expect(self.page.locator('[data-rescue-result]')).to_have_count(0)
        expect(self.page.get_by_role('alert')).to_contain_text('Dane zmieniły się',timeout=60000)
        self.assertEqual(self.records(),changed);self.assertFalse(self.alerts,self.alerts)

    def test_google_connection_and_account_change_are_available_in_group(self):
        import test_drive_sync as cloud
        mock=cloud.MockGoogle();mock.install(self.context);legacy.IndexedDBMigration.prepare(self)
        before=self.state();drawer=self.panel()
        drawer.get_by_text('Opcje zaawansowane Google',exact=True).click()
        drawer.locator('#driveConfig input').fill('123-test.apps.googleusercontent.com');drawer.locator('#driveConfig button').click()
        expect(drawer.locator('[data-drive-action=connect]')).to_be_visible()
        drawer.locator('[data-drive-action=connect]').click();expect(drawer.locator('[data-drive-action=connect]')).to_be_hidden()
        drawer.get_by_text('Opcje zaawansowane Google',exact=True).click();drawer.locator('[data-drive-action=disconnect]').click()
        self.backup_flow('save')
        expect(drawer.locator('[data-connect-from-advanced]')).to_be_visible()
        drawer.locator('[data-connect-from-advanced]').click();expect(drawer.locator('[data-connect-from-advanced]')).to_be_hidden()
        self.assertEqual(self.state(),before);self.assertEqual(mock.posts,0);self.assertFalse(self.alerts,self.alerts)

    def test_opaque_archive_reports_error_without_import_or_mutation(self):
        self.prepare();before=self.records();self.panel();self.page.locator('[data-load-backups]').click();expect(self.page.locator('#backupKey')).to_be_visible(timeout=60000)
        self.page.locator('#backupKey').select_option('large-raw');self.page.locator('[data-rescue-preview]').click()
        expect(self.page.get_by_role('alert')).to_contain_text('Nie można zweryfikować tej kopii',timeout=60000)
        expect(self.page.locator('#backupKey')).to_have_value('large-raw')
        expect(self.page.locator('[data-rescue-result],[data-restore-confirm]')).to_have_count(0)
        self.assertEqual(self.records(),before);self.assertFalse(self.alerts,self.alerts)

    def test_preview_finishing_after_navigation_does_not_redraw_training(self):
        self.prepare();before=self.records();self.panel();self.page.locator('[data-load-backups]').click();expect(self.page.locator('#backupKey')).to_be_visible(timeout=60000)
        self.page.evaluate("""()=>{const Native=Worker;window.Worker=class extends Native{constructor(url,opts){super(url,opts);if(String(url).endsWith('/legacy-model.mjs')){this.addEventListener('message',()=>window.__rescueDelivered=true);const send=this.postMessage.bind(this);this.postMessage=v=>window.__releaseRescue=()=>send(v)}}}}""")
        self.page.locator('[data-rescue-preview]').click();self.page.wait_for_function('!!window.__releaseRescue')
        self.page.locator('[data-tab=training]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.page.evaluate('window.__trainingScreen=document.querySelector("main")');self.page.evaluate('__releaseRescue()');self.page.wait_for_function('window.__rescueDelivered===true')
        self.assertTrue(self.page.evaluate('window.__trainingScreen===document.querySelector("main")'))
        self.assertEqual(self.records(),before)
        self.panel();expect(self.page.locator('[data-rescue-result]')).to_be_visible(timeout=60000)

    def test_other_tab_without_broadcast_invalidates_preview(self):
        self.page.add_init_script('window.BroadcastChannel=undefined');self.prepare();self.panel();self.page.locator('[data-load-backups]').click();expect(self.page.locator('#backupKey')).to_be_visible(timeout=60000)
        self.page.evaluate("""()=>{const Native=Worker;window.Worker=class extends Native{constructor(url,opts){super(url,opts);if(String(url).endsWith('/legacy-model.mjs')){const send=this.postMessage.bind(this);this.postMessage=v=>window.__releaseRescue=()=>send(v)}}}}""")
        self.page.locator('[data-rescue-preview]').click();self.page.wait_for_function('!!window.__releaseRescue')
        self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const v=d.value;v.diagnosticSentinel='other-tab';await d.commit(v)}finally{d.close()}}""")
        changed=self.records();self.page.evaluate('__releaseRescue()')
        expect(self.page.get_by_role('alert')).to_be_visible(timeout=60000)
        expect(self.page.locator('[data-rescue-result]')).to_have_count(0);self.assertEqual(self.records(),changed)

    def test_cancel_during_final_audit_never_publishes_or_writes(self):
        self.prepare();before=self.records();local=self.page.evaluate('({...localStorage})');self.panel();self.page.locator('[data-load-backups]').click();expect(self.page.locator('#backupKey')).to_be_visible(timeout=60000)
        self.page.evaluate("""()=>{const original=__fastDB.auditExport.bind(__fastDB);__fastDB.auditExport=async()=>{window.__auditWaiting=true;await new Promise(r=>window.__releaseAudit=r);try{return await original()}finally{window.__auditDone=true}}}""")
        self.page.locator('[data-rescue-preview]').click();self.page.wait_for_function('window.__auditWaiting===true')
        self.page.locator('[data-rescue-cancel]').click();self.page.evaluate('__releaseAudit()');self.page.wait_for_function('window.__auditDone===true')
        expect(self.page.locator('[data-rescue-result]')).to_have_count(0);expect(self.page.get_by_role('alert')).to_have_count(0)
        self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
