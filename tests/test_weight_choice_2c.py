import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_result_panel
import test_plan_import as plans
PLAN=json.loads((Path(__file__).parents[1]/'plans/PushPull-01.07.2026.json').read_text())
class WeightChoice2C(BrowserHarness):
    preview=plans.PlanImport.preview
    store=plans.PlanImport.store
    activate=plans.PlanImport.activate
    def test_choice_survives_restart_next_session_without_changing_history(self):
        self.page.wait_for_selector('[data-act=start]');self.preview(PLAN);self.store();self.activate();self.page.locator('[data-tab=training]').click()
        self.page.locator('[data-type="PULL A"]').click();self.start();eid='pp260701-u2-p5-ex'
        self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm')
        f.locator('[data-load-basis]').select_option('per-implement');f.locator('[data-quick=kg]').fill('20');f.locator('[data-quick=reps]').fill('8');f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();before=self.state();old=before['entries'][0];snap=before['trainingJournal']['sessionSnapshots'][0]
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-type="PULL A"]').click();self.start()
        self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');expect(f.locator('[data-load-basis]')).to_have_value('per-implement')
        f.locator('[data-load-basis]').select_option('machine-indication');f.locator('[data-quick=kg]').fill('25');f.locator('[data-quick=reps]').fill('9');f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        d=self.state();self.assertEqual(next(e for e in d['entries'] if e['id']==old['id']),old);self.assertEqual(next(s for s in d['trainingJournal']['sessionSnapshots'] if s['id']==snap['id']),snap);self.assertEqual(len(d['entries']),2)
        self.assertEqual(d['entries'][1]['performance']['loadConvention']['basis'],'machine-indication')
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        final=self.state();self.assertEqual(next(e for e in final['entries'] if e['id']==old['id']),old);self.assertEqual(next(s for s in final['trainingJournal']['sessionSnapshots'] if s['id']==snap['id']),snap)
    def test_all_seven_conventions_can_be_saved_without_changing_snapshots(self):
        self.page.wait_for_selector('[data-act=start]');self.preview(PLAN);self.store();self.activate();self.page.locator('[data-tab=training]').click();self.start()
        prior=self.state()['trainingJournal']['sessionSnapshots'][0]
        for pos,basis in enumerate(('', 'per-implement','barbell','machine-indication','sled','bodyweight-extra','combined'),1):
            eid=f'pp260701-u1-p{pos}-ex';self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm')
            f.locator('[data-load-basis]').select_option(basis);f.locator('[data-quick=kg]').fill('20');f.locator('[data-quick=reps]').fill('8')
            if f.locator('[data-rich-action=toggle]').count():
                f.locator('[data-rich-action=toggle]').click()
                for field in f.locator('[data-field=kg]').all():field.fill('20')
                for field in f.locator('[data-field=reps]').all():field.fill('8')
            f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        d=self.state();self.assertEqual(len(d['entries']),7);self.assertEqual(d['trainingJournal']['sessionSnapshots'][0],prior)
        for pos,basis in enumerate((None,'per-implement','barbell','machine-indication','sled','bodyweight-extra','combined'),1):
            e=next(e for e in d['entries'] if e['exerciseId']==f'pp260701-u1-p{pos}-ex');self.assertEqual(e['performance']['loadConvention']['basis'],basis)

    def test_all_seven_ppc1_round_trip_to_clean_profile(self):
        import test_canonical_restore_ui as canonical
        import test_used_restore as used
        self.test_all_seven_conventions_can_be_saved_without_changing_snapshots()
        raw=used.UsedRestore.export(self,self.page);expected=canonical.CanonicalRestoreUI.decode(self,self.page,raw)
        ctx,p=canonical.CanonicalRestoreUI.target(self,raw)
        p.locator('[data-restore-confirm]').click();expect(p.locator('[data-restore-busy]')).to_have_count(0,timeout=120000)
        expect(p.locator('[data-restore-success]')).to_be_visible(timeout=60000);p.reload();p.wait_for_selector('[data-act=finish]',timeout=60000)
        actual=canonical.CanonicalRestoreUI.decode(self,p,used.UsedRestore.export(self,p));self.assertEqual(actual,expected);ctx.close()
