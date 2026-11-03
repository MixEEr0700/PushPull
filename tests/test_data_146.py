from test_browser import BrowserHarness
from playwright.sync_api import expect
import test_indexeddb as native
class Data146(BrowserHarness):
    def test_mobile_default_controls_and_service_tools_are_read_only(self):
        self.page.wait_for_selector('[data-act=start]');before=native.IndexedDBMigration.records(self);local=self.page.evaluate('({...localStorage})');self.page.locator('[data-tab=settings]').click()
        for width in (360,390,412):
            self.page.set_viewport_size({'width':width,'height':844})
            for selector in ('[data-auto-ppc1]','[data-drive-action=connect]','[data-rescue-points]','[data-backup-flow=save]','[data-backup-flow=restore]'):expect(self.page.locator(selector)).to_be_visible()
            expect(self.page.locator('[data-backup-advanced]')).not_to_have_attribute('open','');expect(self.page.locator('[data-export-v4]')).to_be_hidden();expect(self.page.locator('[data-backup-size-check]')).to_be_hidden()
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
        self.page.get_by_text('Narzędzia serwisowe',exact=True).click();expect(self.page.locator('[data-technical]')).to_be_attached();self.assertEqual(native.IndexedDBMigration.records(self),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
