from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_v2_training as t
class CalendarRotation165(BrowserHarness):
    prepare=t.V2Training.prepare
    ready=t.V2Training.ready
    activate=t.V2Training.activate
    def done(self,kind,date):
        self.page.locator('#trainingDate').fill(date);self.page.locator('[data-type="'+kind+'"]').click();self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.suggested(kind);expect(self.page.locator('[data-type="'+kind+'"]')).to_be_disabled()
        sid=self.state()['activeId'];self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();return sid
    def suggested(self,kind):expect(self.page.locator('[data-type="'+kind+'"]').first).to_have_class('current')
    def test_calendar_order_date_edit_delete_manual_and_restart(self):
        self.activate();latest=self.done('PULL A','2026-10-21');self.suggested('PUSH B');older=self.done('PUSH B','2026-10-19');self.suggested('PUSH B')
        manual=self.done('PUSH A','2026-10-20');self.suggested('PUSH B');before=self.state()
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.suggested('PUSH B')
        result=self.page.evaluate("async()=>{const j=await import('./model/journal.mjs'),d=await PushPullDB.open(()=>{},{training:true});try{const deferred=d.historyDeferred,fast=j.nextType(d.value),full=j.nextType((await d.auditExport()).data);return {deferred,fast,full}}finally{d.close()}}")
        self.assertEqual(result,{'deferred':True,'fast':'PUSH B','full':'PUSH B'})
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="2026-10-19"]').click();self.page.locator('[data-act=openSession][data-id="'+older+'"]').click()
        self.page.locator('#historicalDate input').fill('2026-10-22');self.page.locator('#historicalDate button').click();expect(self.page.get_by_text('Data zmieniona',exact=True)).to_be_visible();self.page.locator('[data-tab=training]').click();self.suggested('PULL B')
        for sid,date in [(older,'2026-10-22'),(manual,'2026-10-20')]:
            self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="'+date+'"]').click();self.page.locator('[data-act=deleteSession][data-id="'+sid+'"]').click();expect(self.page.get_by_text('Trening usunięty',exact=True)).to_be_visible();self.page.locator('[data-tab=training]').click();self.suggested('PUSH B')
        after=self.state();self.assertEqual(next(s for s in after['sessions'] if s['id']==latest),next(s for s in before['sessions'] if s['id']==latest))

    def test_custom_plan_cycle_offline_restart_ignores_legacy_sessions(self):
        import test_plan_import as plans
        from test_browser import wait_for_service_worker_controller
        self.context.close();self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.prepare();self.ready();wait_for_service_worker_controller(self.page)
        plans.PlanImport.preview(self);plans.PlanImport.store(self);plans.PlanImport.activate(self)
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();self.suggested('TEST-A')
        self.done('TEST-A','2026-10-21');self.suggested('TEST-B');self.done('TEST-B','2026-10-19');self.suggested('TEST-B')
        before=self.state();self.context.set_offline(True);self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.suggested('TEST-B');self.assertEqual(self.state(),before)
