from test_browser import BrowserHarness
from playwright.sync_api import expect
import test_indexeddb as native
class Data146(BrowserHarness):
    def test_mobile_default_controls_and_service_tools_are_read_only(self):
        self.page.wait_for_selector('[data-act=start]');before=native.IndexedDBMigration.records(self);local=self.page.evaluate('({...localStorage})');self.page.locator('[data-tab=settings]').click()
        self.assertEqual(self.page.locator('[data-data-section] > summary').all_text_contents(),['Zapisz kopię','Przywróć kopię','Google Drive','Punkty cofnięcia','Narzędzia serwisowe'])
        for section in self.page.locator('[data-data-section]').all():expect(section).not_to_have_attribute('open','')
        self.data_section('google');self.data_section('undo')
        for width in (360,390,412):
            self.page.set_viewport_size({'width':width,'height':844})
            for selector in ('[data-auto-ppc1]','[data-drive-action=connect]','[data-rescue-points]','[data-backup-flow=save]','[data-backup-flow=restore]'):expect(self.page.locator(selector)).to_be_visible()
            expect(self.page.locator('[data-backup-advanced]')).not_to_have_attribute('open','');expect(self.page.locator('[data-export-v4]')).to_be_hidden();expect(self.page.locator('[data-backup-size-check]')).to_be_hidden()
            for header in self.page.locator('[data-data-section] > summary').all():self.assertGreaterEqual(header.bounding_box()['height'],48)
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
        self.page.get_by_text('Narzędzia serwisowe',exact=True).click();expect(self.page.locator('[data-technical]')).to_be_attached();self.assertEqual(native.IndexedDBMigration.records(self),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)

    def test_accordion_state_survives_render_and_save_restore_are_exclusive(self):
        self.page.wait_for_selector('[data-act=start]');self.page.locator('[data-tab=settings]').click()
        self.data_section('google');self.data_section('undo')
        self.backup_flow('save')
        expect(self.page.locator('[data-ppc1-send]')).to_be_visible()
        save=self.page.locator('[data-data-section=save]')
        self.assertEqual(save.locator('button').all_text_contents(),['Pobierz kopię na urządzenie','Zapisz kopię na Google Drive'])
        self.assertNotIn('PPC1',save.inner_text())
        expect(self.page.locator('[data-act=export]')).to_be_hidden()
        self.assertEqual(self.page.locator('[data-data-section=service] [data-act=export]').count(),1)
        self.assertEqual(self.page.locator('[data-data-section=service] [data-drive-action=upload]').count(),1)
        self.backup_flow('restore')
        expect(self.page.locator('[data-data-section=save]')).not_to_have_attribute('open','')
        expect(self.page.locator('[data-data-section=restore]')).to_have_attribute('open','')
        for name in ('google','undo'):expect(self.page.locator('[data-data-section='+name+']')).to_have_attribute('open','')
        self.assertEqual(self.page.locator('[data-data-section=undo] [data-load-backups]').count(),1)
        self.assertEqual(self.page.locator('[data-data-section=service] [data-load-backups]').count(),0)
        self.page.locator('[data-backup-flow=restore]').focus();self.page.keyboard.press('Enter')
        expect(self.page.locator('[data-data-section=restore]')).not_to_have_attribute('open','')

    def test_primary_download_and_drive_buttons_use_canonical_backups(self):
        import json
        from pathlib import Path
        from test_drive_incremental import IncrementalGoogle
        from test_drive_sync import ManualDriveFlow
        from test_canonical_export_ui import CanonicalExportUI
        cloud=IncrementalGoogle();cloud.install(self.context)
        self.page.wait_for_selector('[data-act=start]');ManualDriveFlow.configure(self,automatic=False)
        self.page.locator('[data-tab=training]').click();self.start();self.result('22','9');self.save()
        self.page.locator('[data-tab=settings]').click();self.backup_flow('save')
        with self.page.expect_download() as item:self.page.get_by_role('button',name='Pobierz kopię na urządzenie',exact=True).click()
        raw=Path(item.value.path()).read_bytes();value=CanonicalExportUI.decode(self,raw)
        data=value['source']['data'];self.assertTrue(data.get('sessions') or data.get('trainingJournal',{}).get('model',{}).get('sessions'))
        self.page.get_by_role('button',name='Zapisz kopię na Google Drive',exact=True).click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000)
        self.assertEqual(cloud.posts,1)
        self.assertEqual(json.loads(next(iter(cloud.files.values()))['text'])['format'],'pushpull-drive-ppc1')
