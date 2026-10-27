"""Issue90: navigation is read-only, explicit operations retain full audit."""
from test_browser import BrowserHarness
import test_fast_start
from playwright.sync_api import expect

class LazyData(BrowserHarness):
    prepare=test_fast_start.FastStart.prepare

    def test_navigation_offline_sizes_and_weekly_history(self):
        self.prepare();self.context.set_offline(True)
        self.page.evaluate('window.__reads=[]')
        for width in (360,390,412):
            self.page.set_viewport_size({'width':width,'height':844})
            self.page.locator('[data-tab=settings]').click()
            expect(self.page.locator('h1')).to_have_text('Dane i kopia zapasowa')
            self.assertTrue(self.page.evaluate('__fastDB.archivesDeferred&&__fastDB.historyDeferred'))
            self.assertEqual(self.page.evaluate('__reads.length'),0)
            self.page.locator('[data-tab=training]').click()
        for view,title in (('plans','Plany treningowe'),('weekly','Statystyki ogólne')):
            self.context.set_offline(False)  # Instrumented app route is not a hash-matched SW artifact.
            self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
            self.context.set_offline(True)
            self.page.locator('[data-tab=settings]').click()
            self.page.locator('[data-view='+view+']').click()
            expect(self.page.locator('h1')).to_have_text(title)
            self.assertTrue(self.page.evaluate('__fastDB.archivesDeferred&&!__fastDB.historyDeferred'))

    def test_corrupt_archive_refuses_all_exports_and_drive_without_navigation_failure(self):
        self.prepare()
        self.page.evaluate("""async()=>{const a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull');try{await a.transact(db,['journalArchives','journalObjects'],'readwrite',async tx=>{const arc=await a.request(tx.objectStore('journalArchives').get('large-raw')),o=await a.request(tx.objectStore('journalObjects').get(arc.ref));tx.objectStore('journalObjects').put({...o,json:o.json+' '})})}finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.page.locator('[data-tab=settings]').click();expect(self.page.locator('h1')).to_have_text('Dane i kopia zapasowa')
        downloads=[];self.page.on('download',lambda d:downloads.append(d))
        for selector in ('[data-act=export]','[data-export-v4]','[data-export-v5]','[data-drive-action=upload]','[data-load-backups]'):
            self.page.locator(selector).click();expect(self.page.locator('[data-full-audit]')).to_have_count(0,timeout=60000)
        self.assertFalse(downloads)
        self.assertGreaterEqual(len(self.alerts),5,self.alerts)
        self.assertTrue(self.page.evaluate('__fastDB.archivesDeferred'))

    def test_cancel_before_operation_no_download_and_navigation_remains_available(self):
        self.prepare()
        self.page.evaluate("""()=>{const original=__fastDB.ensureFull;__fastDB.ensureFull=async()=>{await new Promise(r=>window.__releaseAudit=r);return original()}}""")
        self.page.locator('[data-tab=settings]').click();downloads=[];self.page.on('download',lambda d:downloads.append(d))
        self.page.locator('[data-act=export]').click();expect(self.page.locator('[data-full-audit]')).to_be_visible()
        self.page.wait_for_function('!!window.__releaseAudit')
        self.page.locator('[data-full-audit-cancel]').click();self.page.locator('[data-tab=training]').click()
        expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.page.evaluate('__releaseAudit()');expect(self.page.locator('[data-full-audit]')).to_have_count(0,timeout=60000)
        self.assertFalse(downloads);self.assertFalse(self.alerts,self.alerts)

    def test_explicit_backup_listing_and_export_preserve_complete_source(self):
        self.prepare();self.page.locator('[data-tab=settings]').click()
        self.page.locator('[data-load-backups]').click();expect(self.page.locator('[data-backup-export]')).to_be_visible(timeout=60000)
        self.assertFalse(self.page.evaluate('__fastDB.archivesDeferred'))
        with self.page.expect_download() as item:self.page.locator('[data-act=export]').click()
        import json
        from pathlib import Path
        raw=Path(item.value.path()).read_text();self.assertIn('large-raw',raw)
        self.assertFalse(self.alerts,self.alerts)

    def test_cancelled_file_selection_can_be_selected_again(self):
        self.prepare();self.page.locator('[data-tab=settings]').click()
        self.page.evaluate("""()=>{const original=__fastDB.ensureFull;__fastDB.ensureFull=async()=>{await new Promise(r=>window.__releaseAudit=r);return original()}}""")
        self.page.locator('#importFile').set_input_files({'name':'cancelled.json','mimeType':'application/json','buffer':b'{}'})
        self.page.wait_for_function('!!window.__releaseAudit')
        self.page.locator('[data-full-audit-cancel]').click();self.page.evaluate('__releaseAudit()')
        expect(self.page.locator('[data-full-audit]')).to_have_count(0,timeout=60000)
        expect(self.page.locator('#importFile')).to_have_value('')
        expect(self.page.locator('[data-restore-preview]')).to_have_count(0)
        self.assertFalse(self.alerts,self.alerts)
