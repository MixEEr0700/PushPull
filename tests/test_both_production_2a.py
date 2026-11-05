import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_result_panel,add_drop
import test_plan_import as plan_tests
PLAN=json.loads((Path(__file__).parents[1]/'plans/PushPull-01.07.2026.json').read_text())
class BothProduction(BrowserHarness):
    preview=plan_tests.PlanImport.preview
    store=plan_tests.PlanImport.store
    activate=plan_tests.PlanImport.activate
    def test_production_both_add_drop_save_restart_and_tonnage(self):
        self.page.wait_for_selector('[data-act=start]');self.preview(PLAN);self.store();self.activate();self.page.locator('[data-tab=training]').click();self.page.locator('[data-type="PULL A"]').click();self.start()
        self.page.locator('[data-expand="pp260701-u2-p5-ex"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm')
        f.locator('[data-load-basis]').select_option('per-implement');f.locator('[data-quick=kg]').fill('20');f.locator('[data-quick=reps]').fill('8');f.locator('[data-rich-action=toggle]').click()
        expect(f.locator('[data-compact-set]')).to_have_count(2);expect(f.locator('[data-side-exception]')).to_have_count(0)
        f.locator('[data-rich-action=add-set]').click();expect(f.locator('[data-compact-set]')).to_have_count(3)
        f.locator('[data-rich-action=remove-set]').last.click();expect(f.locator('[data-compact-set]')).to_have_count(2)
        f.locator('[data-rich-action=add-set]').click()
        while f.locator('[data-rich-action=remove-set]').count():f.locator('[data-rich-action=remove-set]').first.click()
        expect(f.locator('[data-compact-set]')).to_have_count(0)
        for _ in range(3):f.locator('[data-rich-action=add-set]').click()
        expect(f.locator('[data-compact-set]')).to_have_count(3);add_drop(f,0)
        f.locator('[data-rich-action=remove-segment]').first.click();add_drop(f,0)
        for el in f.locator('[data-field=kg]').all():el.fill('20')
        for el in f.locator('[data-field=reps]').all():el.fill('8')
        f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        before=self.state();e=before['entries'][0];self.assertEqual(len(e['performance']['rows']),3);self.assertEqual({r['side'] for r in e['performance']['rows']},{'both'});self.assertEqual(len(e['series']),4)
        total=self.page.evaluate("async()=>{const db=await PushPullDB.open(()=>{});try{const {entryTotals}=await import('./model/plan-overview.mjs');return entryTotals(db.value,db.value.entries[0])}finally{db.close()}}")
        self.assertEqual(total['tonnage'],1280)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.assertEqual(self.state()['entries'],before['entries'])
        self.page.locator('[data-expand="pp260701-u2-p5-ex"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click();expect(f.locator('[data-compact-set]')).to_have_count(3);expect(f.locator('[data-side-exception]')).to_have_count(0)
    def test_historical_asymmetric_records_survive_edit_and_restart(self):
        from test_browser import seed_historical_editor
        self.page.wait_for_selector('[data-act=start]');self.preview(PLAN);self.store();self.activate();self.page.locator('[data-tab=training]').click();self.page.locator('[data-type="PULL A"]').click();self.start()
        self.page.locator('[data-expand="pp260701-u2-p5-ex"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');f.locator('[data-load-basis]').select_option('per-implement')
        f=seed_historical_editor(self.page,"d.performance.rows=d.performance.rows.flatMap((r,i)=>['left','right'].map(side=>({...structuredClone(r),id:crypto.randomUUID(),side,segments:r.segments.map(s=>({...s,id:crypto.randomUUID(),kg:side==='left'?'20':'21',reps:'8'}))})));d.executionMode='paired';d.sidePairs=[]")
        expect(f.locator('[data-side-exception]')).to_have_count(2);expect(f.locator('[data-quick=kg]')).not_to_be_editable()
        f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible();original=self.state()['entries'][0]
        self.assertEqual([r['side'] for r in original['performance']['rows']],['left','right','left','right'])
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.assertEqual(self.state()['entries'][0],original)
        self.page.locator('[data-expand="pp260701-u2-p5-ex"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click();expect(f.locator('[data-side-exception]')).to_have_count(2)
        f.locator('[data-row="1"][data-field=kg]').fill('22');f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible();changed=self.state()['entries'][0]
        self.assertEqual(changed['performance']['rows'][0],original['performance']['rows'][0]);self.assertEqual(changed['performance']['rows'][1]['segments'][0]['kg'],'22');self.assertEqual(len(changed['performance']['rows']),4)
