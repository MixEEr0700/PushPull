from playwright.sync_api import expect
from test_browser import BrowserHarness

class DriveReminder156(BrowserHarness):
    def setup_reminder(self):
        self.page.goto(self.url);self.page.wait_for_selector('[data-tab=settings]')
        self.page.evaluate('''async()=>{const m=await import('./model/drive-reminder.mjs');window.clock=100000000;window.safe=true;window.calls=[];window.s={automatic:true,pending:true,backupFailed:true,busy:false};window.d={status:s,config:{connected:false},connect(){calls.push('connect');window.clickWasActive=navigator.userActivation.isActive;return window.rejectLogin?Promise.reject(Error('Okno Google zamknięte lub zablokowane. Kliknij Połącz ponownie.')):Promise.resolve().then(()=>{d.config.connected=true})},async retryCanonical(){calls.push('retry');s.pending=false;s.backupFailed=false}};window.r=m.openDriveReminder({drive:d,safe:()=>safe,now:()=>clock});await r.refresh()}''')
    def test_connect_cancel_retry_and_daily_limit(self):
        self.setup_reminder();expect(self.page.locator('[data-drive-reminder]')).to_be_visible()
        for width in (360,390,412):
            self.page.set_viewport_size({'width':width,'height':844});self.assertLessEqual(self.page.locator('[data-drive-reminder]').bounding_box()['width'],width)
        self.page.evaluate('window.rejectLogin=true');self.page.locator('[data-reminder-connect]').click()
        expect(self.page.locator('[data-reminder-status]')).to_contain_text('zablokowane')
        self.assertTrue(self.page.evaluate('clickWasActive'));self.assertEqual(self.page.evaluate('calls'),['connect'])
        self.page.evaluate('window.rejectLogin=false');self.page.locator('[data-reminder-connect]').click();expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)
        self.assertEqual(self.page.evaluate('calls'),['connect','connect','retry'])
        self.page.evaluate('s.pending=true;s.backupFailed=true;r.refresh()');expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)
        self.page.reload();self.setup_reminder();expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)
        self.page.evaluate('clock+=86400000;r.refresh()');expect(self.page.locator('[data-drive-reminder]')).to_be_visible()
        self.page.locator('[data-reminder-later]').click();self.page.evaluate('r.refresh()');expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)
    def test_safe_views_and_connected_retry(self):
        self.setup_reminder();self.page.locator('[data-reminder-later]').click()
        self.page.evaluate('clock+=86400000;safe=false;r.refresh()');expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)
        self.page.evaluate('safe=true;s.automatic=false;r.refresh()');expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)
        self.page.evaluate('s.automatic=true;s.pending=false;r.refresh()');expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)
        self.page.evaluate('s.pending=true;d.config.connected=true;r.refresh()');expect(self.page.locator('[data-reminder-connect]')).to_have_text('Ponów kopię')
        self.page.locator('[data-reminder-connect]').click();expect(self.page.locator('[data-drive-reminder]')).to_have_count(0);self.assertEqual(self.page.evaluate('calls'),['retry'])
