import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_result_panel
import test_plan_import as plan_tests
PLAN=json.loads((Path(__file__).parents[1]/'plans/PushPull-01.07.2026.json').read_text())
class WeightOptions2B(BrowserHarness):
    preview=plan_tests.PlanImport.preview
    store=plan_tests.PlanImport.store
    activate=plan_tests.PlanImport.activate
    def test_seven_options_and_descriptions_in_real_editor(self):
        self.page.wait_for_selector('[data-act=start]');self.preview(PLAN);self.store();self.activate();self.page.locator('[data-tab=training]').click();self.page.locator('[data-type="PULL A"]').click();self.start()
        self.page.locator('[data-expand="pp260701-u2-p5-ex"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');select=f.locator('[data-load-basis]')
        self.assertEqual(select.locator('option').all_text_contents(),['Nieokreślony','Jednostronnie','Sztanga','Maszyna','Obustronnie','Masa ciała +','Łącznie'])
        for value in ('per-implement','barbell','machine-indication','sled','bodyweight-extra','combined',''):
            select.select_option(value);expect(select).to_have_value(value)
            if value=='sled':expect(f.locator('[data-load-help]')).to_contain_text('bez masy sanek')
            if value=='bodyweight-extra':expect(f.locator('[data-load-help]')).to_contain_text('bez masy ciała')
