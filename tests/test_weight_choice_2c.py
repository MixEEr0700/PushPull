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
    def test_fixed_machine_to_barbell_is_explicit_and_snapshots_are_immutable(self):
        import copy
        p=copy.deepcopy(PLAN);pos=next(x for x in p['positions'] if x['id']=='pp260701-u2-p5-pos');pos['loadConvention']['basis']='machine-indication'
        self.page.wait_for_selector('[data-act=start]');self.preview(p);self.store();self.activate();self.page.locator('[data-tab=training]').click();self.page.locator('[data-type="PULL A"]').click();self.start()
        eid=pos['exerciseId'];self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');expect(f.locator('[data-load-basis]')).to_have_value('machine-indication')
        f.locator('[data-quick=kg]').fill('20');f.locator('[data-quick=reps]').fill('8');f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        first=self.state();old=first['entries'][0];snapshot=first['trainingJournal']['sessionSnapshots'][0]
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-type="PULL A"]').click();self.start();self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');f.locator('[data-load-basis]').select_option('barbell');f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        changed=self.state();self.assertEqual(next(e for e in changed['entries'] if e['id']==old['id']),old);self.assertEqual(next(s for s in changed['trainingJournal']['sessionSnapshots'] if s['id']==snapshot['id']),snapshot);new=next(e for e in changed['entries'] if e['id']!=old['id']);self.assertEqual(new['performance']['loadConvention']['basis'],'barbell');self.assertTrue(new['performance']['conventionExplicit'])
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-type="PULL A"]').click();self.start();self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page);expect(self.page.locator('[data-load-basis]')).to_have_value('barbell')
    def test_reused_exercise_identity_keeps_latest_convention_per_position_after_restart(self):
        import copy
        p=copy.deepcopy(PLAN);a=next(x for x in p['positions'] if x['id']=='pp260701-u1-p1-pos');b=next(x for x in p['positions'] if x['id']=='pp260701-u3-p1-pos');oldex,oldvar=b['exerciseId'],b['variantId'];b['exerciseId']=a['exerciseId'];b['variantId']=a['variantId'];p['exercises']=[x for x in p['exercises'] if x['id']!=oldex];p['variants']=[x for x in p['variants'] if x['id']!=oldvar]
        self.page.wait_for_selector('[data-act=start]');self.preview(p);self.store();self.activate();self.page.locator('[data-tab=training]').click();eid=a['exerciseId']
        def workout(unit,basis,kg):
            self.page.locator('[data-type="'+unit+'"]').click();self.start();self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');f.locator('[data-load-basis]').select_option(basis);f.locator('[data-quick=kg]').fill(kg);f.locator('[data-quick=reps]').fill('8');f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        workout('PUSH A','per-implement','20');workout('PUSH B','barbell','25');workout('PUSH B','per-implement','30')
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-type="PUSH A"]').click();self.start();self.page.locator('[data-expand="'+eid+'"]').click();open_result_panel(self.page);expect(self.page.locator('.performanceForm [data-load-basis]')).to_have_value('per-implement')
        self.assertEqual(len(self.state()['entries']),3)
        self.page.locator('[data-panel=history][data-id="'+eid+'"]').click();history=self.page.locator('.panel .entry');expect(history).to_have_count(1);expect(history.first).to_contain_text('20')
