"""Unified plans + real local workouts; all plans/data synthetic, Google simulated."""
from test_browser import add_drop,confirm_restore,open_result_panel,seed_historical_editor
from pathlib import Path
import json
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_v2_training as training
import test_plan_import as imports
import test_indexeddb as legacy

class PlanOverview(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    settings=imports.PlanImport.settings
    preview=imports.PlanImport.preview
    store=imports.PlanImport.store
    activate_plan=imports.PlanImport.activate
    form=imports.PlanImport.form
    fill=imports.PlanImport.fill
    save=imports.PlanImport.save

    def weekly(self,plan=None):
        self.settings();self.page.locator('[data-view=weekly]').click()
        if plan:self.page.locator('#weeklyPlan').select_option(plan)
        self.page.locator('#weeklyRange [name=from]').fill('2026-10-05')
        self.page.locator('#weeklyRange [name=to]').fill('2026-10-25')
        self.page.locator('#weeklyRange button').click()

    def metric(self,key,value):
        self.assertEqual(self.page.locator(f'[data-weekly-metric="{key}"] strong').inner_text().replace('\xa0','').replace(' ',''),value)

    def test_plan_filter_week_gap_date_and_result_correction_preserve_snapshots(self):
        training.V2Training.activate(self)
        self.page.locator('#trainingDate').fill('2026-10-19')
        f=training.V2Training.open_result(self,'PULL A','PULL-A-1')
        f.locator('[data-quick=kg]').fill('10');f.locator('[data-quick=reps]').fill('10');training.V2Training.save_form(self,f)
        v2=self.state();sid=v2['activeId'];self.page.locator('[data-act=finish]').click()
        self.preview();self.store();stored=self.state()
        self.assertEqual(stored['trainingJournal']['activePlanVersionId'],'v2-owner-2026-10-22')
        self.activate_plan();self.page.locator('[data-tab=training]').click()
        self.page.locator('#trainingDate').fill('2026-10-20');self.page.locator('[data-type="TEST-B"]').click();self.page.locator('[data-act=start]').click()
        for eid in ['TEST-4','TEST-5']:
            f=self.form(eid);self.fill(f);self.save(f)
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();before=self.state()
        self.weekly();expect(self.page.locator('#weeklyPlan')).to_have_value('synthetic-v3')
        self.metric('tonnage','1280kg');self.metric('sets','7');self.metric('reps','64');self.metric('workouts','1')
        expect(self.page.locator('[data-week="2026-W42"]')).to_contain_text('0 treningów')
        expect(self.page.locator('[data-week="2026-W43"]')).to_contain_text('Częściowy tydzień')
        self.page.locator('#weeklyPlan').select_option('v2-owner-2026-10-22');self.metric('tonnage','600kg');self.metric('sets','6')
        self.assertEqual(self.state(),before)
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="2026-10-19"]').click()
        self.page.locator(f'[data-act=openSession][data-id="{sid}"]').click()
        self.page.locator('#historicalDate [name=date]').fill('2026-10-12');self.page.locator('#historicalDate button').click()
        expect(self.page.get_by_text('Data zmieniona',exact=True)).to_be_visible()
        self.page.locator('[data-expand="PULL-A-1"]').click();open_result_panel(self.page)
        f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click()
        # Recover the old independently edited shape before correcting one side;
        # the ordinary equal-pair control now correctly changes both sides.
        f=seed_historical_editor(self.page,"d.performance.rows[0].segments[0].kg='9'")
        f.locator('[data-row="0"][data-field=kg]').fill('5');self.save(f)
        self.weekly('v2-owner-2026-10-22');self.metric('tonnage','550kg')
        expect(self.page.locator('[data-week="2026-W42"]')).to_contain_text('550')
        self.page.locator('[data-weekly-metric=workouts]').click();expect(self.page.locator('[data-week="2026-W42"]')).to_contain_text('1 treningów')
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'));self.assertFalse(self.alerts,self.alerts)

    def test_versions_read_only_draft_restart_exercise_filter_and_json(self):
        self.prepare();self.ready()
        self.preview();self.store();self.activate_plan();self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="TEST-B"]').click();self.page.locator('[data-act=start]').click()
        f=self.form('TEST-5');self.fill(f);self.save(f)
        f=self.form('TEST-4');self.fill(f);add_drop(f,0);self.fill(f)
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.state();self.preview(imports.v4());self.store();self.activate_plan()
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertEqual(self.state()['entries'],before['entries'])
        active=self.state();self.weekly();self.metric('workouts','0') # Approved results in unfinished session are excluded.
        self.plans();expect(self.page.locator('[data-plan-row="synthetic-v3"]')).to_be_visible()
        expect(self.page.locator('[data-plan-row="synthetic-v4"]')).to_be_visible()
        self.page.locator('#importedPlanId').select_option('synthetic-v4');expect(self.page.locator('[data-plan-activate]')).to_have_count(0)
        self.assertEqual(self.state(),active)
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click()
        f=self.page.locator('.performanceForm');expect(f.locator('[data-row="0"][data-segment="2"][data-field=kg]')).to_have_value('20');self.save(f)
        self.page.locator('[data-act=finish]').click();self.page.locator('[data-type="TEST-B"]').click();self.page.locator('[data-act=start]').click()
        f=self.form('TEST-5')
        for x in f.locator('[data-field=kg]').all():x.fill('30')
        for x in f.locator('[data-field=reps]').all():x.fill('6')
        self.save(f);self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="TEST-B"]').click()
        if self.page.locator('[data-expand="TEST-5"]').get_attribute('aria-expanded')!='true':self.page.locator('[data-expand="TEST-5"]').click()
        self.page.locator('[data-panel=stats]').click();expect(self.page.locator('[data-exercise-plan]')).to_be_visible()
        self.page.locator('[data-exercise-plan]').select_option('synthetic-v3')
        self.assertIn('640',self.page.locator('.stat-tile').first.inner_text().replace('\xa0',''))
        self.page.locator('[data-exercise-plan]').select_option('synthetic-v4')
        self.assertIn('720',self.page.locator('.stat-tile').first.inner_text().replace('\xa0',''))
        self.page.locator('[data-exercise-plan]').select_option('');self.page.locator('[data-panel=history]').click()
        expect(self.page.locator('.panel .entry')).to_have_count(2)
        saved=self.state();self.settings()
        self.backup_flow('save')
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_text()
        self.assertEqual(self.page.evaluate('async t=>(await PushPullDB.parseModelBackup(t)).data',raw),saved)
        other=self.new_context(service_workers='block');page=other.new_page();page.on('dialog',lambda d:d.accept());page.goto(self.url)
        page.locator('[data-tab=settings]').click();page.locator('#importFile').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':raw.encode()})
        confirm_restore(page)
        expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible(timeout=30000)
        page.locator('[data-tab=settings]').click();page.locator('[data-view=weekly]').click();expect(page.locator('#weeklyPlan')).to_have_value('synthetic-v4')
        self.assertEqual(page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return db.value}finally{db.close()}}'),saved)
        self.assertFalse(self.alerts,self.alerts)

    def test_complete_snapshot_only_plan_can_be_reactivated_without_import_or_changing_drafts(self):
        packet=json.loads(json.dumps(imports.PLAN).replace('"TEST-A"','"PUSH A"').replace('"TEST-B"','"PULL A"'))
        self.prepare();self.ready();self.preview(packet);self.store();self.activate_plan()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-act=start]').click();f=self.form('TEST-1');self.fill(f)
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.plans('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        # Only the synthetic fixture loses its redundant registry/packet, not its full snapshot.
        self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const v=structuredClone(d.value),j=v.trainingJournal,s=j.sessionSnapshots.find(s=>s.planVersionId==='synthetic-v3');delete j.importedPlans;for(const k of ['exercises','variants','planVersions','positions','sets','drops','groups','coachInstructions'])j.model[k]=j.model[k].filter(x=>!s.model[k].some(y=>y.id===x.id));await d.commit(v)}finally{d.close()}}""")
        self.page.reload();self.ready();before=self.state()
        drafts=self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        self.plans();self.page.locator('[data-plan-switch]').click();self.page.locator('#switchPlanId').select_option('synthetic-v3')
        self.page.locator('[data-switch-preview]').click();expect(self.page.locator('[data-selected-plan]')).to_contain_text('Test Narciarz')
        self.confirm=False;self.page.locator('[data-switch-activate]').click();self.assertEqual(self.state(),before)
        self.confirm=True
        with self.page.expect_download():self.page.locator('[data-switch-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        after=self.state();self.assertEqual(after['trainingJournal']['activePlanVersionId'],'synthetic-v3')
        self.assertEqual(after['trainingJournal']['nextUnitId'],'PUSH A');self.assertNotIn('importedPlans',after['trainingJournal'])
        for key in ['sessions','entries','activeId']:self.assertEqual(after[key],before[key])
        self.assertEqual(after['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertEqual(self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}'),drafts)
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('.performanceForm [data-row="0"][data-field=kg]')).to_have_value('20')
        self.assertFalse(self.alerts,self.alerts)

    def test_unknown_activation_dates_use_only_verified_training_dates_and_never_backfill(self):
        training.V2Training.activate(self)
        self.page.locator('#trainingDate').fill('2026-10-19');self.page.locator('[data-act=start]').click()
        expect(self.page.locator('[data-act=finish]')).to_be_visible();sid=self.state()['activeId']
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{const v=d.value;v.trainingJournal.activations=[];await d.commit(v)}finally{d.close()}}")
        self.page.reload();self.plans();before=self.state()
        row=self.page.locator('[data-plan-row="v2-owner-2026-10-22"]')
        expect(row.locator('[data-plan-period]')).to_have_text('Okres aktywacji nieustalony; treningi od 19.10.2026 do 19.10.2026')
        expect(self.page.locator('[data-plan-row="@unassigned"] [data-plan-period]')).to_have_text('Brak wiarygodnych dat')
        self.assertEqual(self.state(),before)
        self.page.locator('[data-plan-switch]').click();expect(self.page.locator('[data-plan-switcher]')).to_contain_text('Brak innych gotowych do aktywacji wersji planu')
        self.assertEqual(self.state(),before)
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="2026-10-19"]').click()
        self.page.locator(f'[data-act=openSession][data-id="{sid}"]').click()
        self.page.locator('#historicalDate [name=date]').fill('2026-10-12');self.page.locator('#historicalDate button').click()
        expect(self.page.get_by_text('Data zmieniona',exact=True)).to_be_visible();self.plans()
        expect(row.locator('[data-plan-period]')).to_have_text('Okres aktywacji nieustalony; treningi od 12.10.2026 do 12.10.2026')
        self.assertEqual(self.state()['trainingJournal']['activations'],[])
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
