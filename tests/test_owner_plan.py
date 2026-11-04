import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_notes,open_result_panel
import test_plan_import as plan_tests
PLAN=json.loads((Path(__file__).parents[1]/'plans/PushPull-01.07.2026.json').read_text())
class OwnerPlan(BrowserHarness):
    preview=plan_tests.PlanImport.preview
    store=plan_tests.PlanImport.store
    activate=plan_tests.PlanImport.activate
    def test_empty_profile_import_notes_sets_and_restart(self):
        self.page.wait_for_selector('[data-act=start]');self.preview(PLAN);self.store();self.activate()
        d=self.state();self.assertEqual(d['sessions'],[]);self.assertEqual(d['entries'],[])
        self.assertEqual(len(d['trainingJournal']['model']['positions']),35)
        self.page.locator('[data-tab=training]').click();self.start()
        eid='pp260701-u1-p3-ex';self.page.locator('[data-expand="'+eid+'"]').click();open_notes(self.page)
        note=self.page.locator('[data-personal-note]').first
        if not note.evaluate('(e)=>e.open'):note.locator('summary').click()
        expect(note.locator('textarea')).to_have_value(PLAN['initialUserNotes'][0]['text'])
        note.locator('textarea').fill('Moja zmieniona notatka');note.locator('textarea').blur();note.locator('[type=submit]').click()
        expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        self.page.wait_for_function("async()=>{const d=await PushPullDB.open(()=>{});try{return d.value.trainingJournal.model.userNotes.some(n=>n.text==='Moja zmieniona notatka')}finally{d.close()}}")
        open_result_panel(self.page);form=self.page.locator('.performanceForm')
        expect(form.locator('[data-quick=kg]')).to_have_value('')
        if not form.locator('[data-rich-details]').is_visible():form.locator('[data-rich-action=toggle]').click()
        for field in form.locator('[data-field=kg]').all():expect(field).to_have_value('')
        self.assertGreaterEqual(form.locator('[data-field=kg]').count(),3)
        form.locator('[data-field=kg]').first.fill('21');form.locator('[data-field=reps]').first.fill('6')
        self.page.locator('[data-tab=settings]').click();self.page.reload();self.page.wait_for_selector('[data-act=finish]')
        d=self.state();self.assertEqual(d['entries'],[]);self.assertTrue(any(n['text']=='Moja zmieniona notatka' for n in d['trainingJournal']['model']['userNotes']))
