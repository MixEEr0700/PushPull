import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_result_panel
import test_plan_import as plan_tests
PLAN=json.loads((Path(__file__).parents[1]/'plans/PushPull-01.07.2026.json').read_text())
class KeyboardLP(BrowserHarness):
    preview=plan_tests.PlanImport.preview
    store=plan_tests.PlanImport.store
    activate=plan_tests.PlanImport.activate
    def test_fresh_pull_a_pair_quick_focus_type_save_restart(self):
        self.page.set_viewport_size({'width':390,'height':844});self.page.wait_for_selector('[data-act=start]');self.preview(PLAN);self.store();self.activate()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-type="PULL A"]').click();self.start()
        for pos in (5,6):
            eid=f'pp260701-u2-p{pos}-ex';self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page)
            form=self.page.locator('.performanceForm');quick=form.locator('[data-quick=kg]');expect(quick).to_be_editable();quick.focus();expect(quick).to_be_focused();quick.press_sequentially('24');expect(quick).to_be_focused()
            reps=form.locator('[data-quick=reps]');expect(reps).to_be_editable();reps.focus();reps.press_sequentially('10');expect(reps).to_be_focused()
            form.locator('[data-rich-action=toggle]').click()
            for field in form.locator('[data-field=kg]').all():expect(field).to_have_value('24')
            for field in form.locator('[data-field=reps]').all():expect(field).to_have_value('10')
            form.locator('[data-load-basis]').select_option('per-implement');form.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        d=self.state();self.assertEqual(len(d['entries']),2)
        for e in d['entries']:self.assertEqual(len(e['series']),4)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.page.locator('[data-expand="pp260701-u2-p5-ex"]').click();open_result_panel(self.page)
        form=self.page.locator('.performanceForm');expect(form.locator('[data-quick=kg]')).to_be_editable();form.locator('[data-quick=kg]').focus();expect(form.locator('[data-quick=kg]')).to_be_focused()
