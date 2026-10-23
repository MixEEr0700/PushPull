"""Synthetic data-only V3/V4 through the existing mobile UI; no owner plan."""
from test_browser import confirm_restore
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy

PLAN=json.loads((Path(__file__).parent/'fixtures/plan-v3.json').read_text())
def v4():
    p=json.loads(json.dumps(PLAN).replace('synthetic-v3','synthetic-v4').replace('v3-position','v4-position').replace('v3-group','v4-group').replace('v3-global','v4-global'))
    p['planVersion']['number']=4;p['planVersion']['label']='TEST V4'
    for c,pos,old in zip(p['continuity'],p['positions'],PLAN['positions']):
        c.update(relation='same-variant',previousExerciseId=pos['exerciseId'],previousVariantId=pos['variantId'],previousPositionId=old['id'])
    p['sets'][0]['reps']={'min':4,'max':6}
    return p

class PlanImport(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    records=legacy.IndexedDBMigration.records

    def settings(self):self.page.locator('[data-tab=settings]').click()
    def preview(self,p=PLAN):
        self.plans();self.page.locator('#planFile').set_input_files({'name':'synthetic.json','mimeType':'application/json','buffer':json.dumps(p).encode()})
        expect(self.page.locator('[data-plan-preview]')).to_be_visible()
    def store(self):
        self.page.locator('[data-plan-save]').click();expect(self.page.get_by_text('Plan zapisany bez aktywacji',exact=True)).to_be_visible()
    def activate(self):
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
    def form(self,id):
        self.page.locator(f'[data-expand="{id}"]').click();self.page.locator('[data-panel=result]').click()
        f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click();return f
    def fill(self,f):
        for x in f.locator('[data-field=kg]').all():x.fill('20')
        for x in f.locator('[data-field=reps]').all():x.fill('8')
    def save(self,f):
        f.locator('[type=submit]').click();expect(f).to_have_count(0) # An old success toast is not confirmation of this transaction.
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()

    def test_import_preview_cancel_failure_future_only_activation_and_old_draft(self):
        self.prepare();self.ready();before=self.state()
        # Existing legacy draft must survive preview/import/activation.
        self.page.locator('[data-expand="PUSH-A-1"]').click();self.page.locator('[data-panel=result]').click()
        self.page.locator('[data-main=kg]').fill('61');self.page.locator('[data-main=reps]').fill('7')
        self.page.wait_for_function("document.querySelector('[data-draft-status]')?.textContent.includes('Szkic zapisany')")
        self.preview();self.assertEqual(self.state(),before)
        self.page.locator('[data-plan-cancel]').click();expect(self.page.locator('[data-plan-preview]')).to_have_count(0)
        self.preview();self.store();saved=self.state();self.assertNotIn('activePlanVersionId',saved['trainingJournal'])
        self.assertEqual(saved['sessions'],before['sessions']);self.assertEqual(saved['entries'],before['entries'])
        self.confirm=False;self.page.locator('[data-plan-activate]').click();self.assertEqual(self.state(),saved)
        self.confirm=True;self.activate();self.page.locator('[data-tab=training]').click()
        self.assertEqual(self.state()['sessions'],before['sessions'])
        if self.page.locator('[data-expand="PUSH-A-1"]').get_attribute('aria-expanded')!='true':self.page.locator('[data-expand="PUSH-A-1"]').click()
        self.page.locator('[data-panel=result]').click()
        expect(self.page.locator('[data-main=kg]')).to_have_value('61')
        self.page.locator('.seriesResultForm [type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-type="TEST-A"]')).to_be_visible()
        self.page.locator('[data-act=start]').click();expect(self.page.locator('.exercise-card .num')).to_have_text(['1A','1B','1C'])
        for id in ['TEST-1','TEST-2','TEST-3']:
            f=self.form(id);self.fill(f);self.save(f)
        old=self.state();snapshot=old['trainingJournal']['sessionSnapshots'][-1]
        self.preview(v4());expect(self.page.locator('[data-plan-preview]')).to_contain_text('Zmienione parametry / kontekst')
        self.store();self.page.locator('#importedPlanId').select_option('synthetic-v4');self.activate()
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'][-1],snapshot)
        self.assertEqual(self.state()['entries'],old['entries'])
        self.page.locator('[data-tab=training]').click();self.page.reload()
        expect(self.page.locator('.exercise-card').first).to_contain_text('8–10')
        self.page.locator('[data-act=finish]').click();self.page.locator('[data-act=start]').click()
        expect(self.page.locator('.exercise-card').first).to_contain_text('4–6')
        expect(self.page.locator('.exercise-card .last-result').first).to_have_text('Brak zapisanego wyniku') # V4 has no own result yet; never borrow V3's result.
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.assertEqual(self.local_raw(),legacy.RAW)

    def test_issue36_imported_cards_count_each_exercise_independently_without_writes(self):
        self.prepare();self.ready();self.preview();self.store();self.activate()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        def card(eid):return self.page.locator('.exercise-card').filter(has=self.page.locator(f'[data-expand="{eid}"]'))
        for _ in range(2):
            self.page.locator('[data-type="TEST-A"]').click();self.page.locator('[data-act=start]').click()
            for eid in ['TEST-1','TEST-2']:
                f=self.form(eid);self.fill(f);self.save(f)
            self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-type="TEST-A"]').click()
        for eid in ['TEST-1','TEST-2']:expect(card(eid).locator('[data-result-change]')).to_contain_text('2 sesje temu')
        expect(card('TEST-3').locator('[data-result-change]')).to_have_count(0)
        before=self.records();self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-type="TEST-A"]').click()
        self.assertEqual(self.records(),before)
        self.page.locator('[data-act=start]').click();f=self.form('TEST-1');self.fill(f)
        f.locator('[data-row="0"][data-field=kg]').fill('10');self.save(f)
        expect(card('TEST-1').locator('[data-result-change]')).to_contain_text('2 sesje temu')
        self.page.locator('[data-act=finish]').click();self.page.locator('[data-type="TEST-A"]').click()
        expect(card('TEST-1').locator('[data-result-change]')).to_contain_text('1 sesję temu')
        expect(card('TEST-2').locator('[data-result-change]')).to_contain_text('2 sesje temu')
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

    def test_invalid_file_and_atomic_failed_import_leave_history_and_plan_intact(self):
        self.prepare();self.ready();self.plans();before=self.records()
        bad=json.loads(json.dumps(PLAN));bad['sets'][0]['positionId']='missing'
        self.page.locator('#planFile').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':json.dumps(bad).encode()})
        expect(self.page.locator('[data-plan-error]')).to_be_visible();self.assertEqual(self.records(),before)
        self.preview()
        self.page.evaluate("""()=>{window.__put=IDBObjectStore.prototype.put;window.__add=IDBObjectStore.prototype.add;for(const key of ['put','add']){const original=IDBObjectStore.prototype[key];IDBObjectStore.prototype[key]=function(v){if(this.name==='exercises'&&v.id==='TEST-1')this.transaction.abort();return original.call(this,v)}}}""")
        self.page.locator('[data-plan-save]').click();expect(self.page.locator('[data-plan-save]')).to_be_visible()
        self.assertEqual(self.state()['sessions'],legacy.FIXTURE['sessions']);self.assertNotIn('trainingJournal',self.state())
        self.page.evaluate('()=>{IDBObjectStore.prototype.put=window.__put;IDBObjectStore.prototype.add=window.__add}')
        self.store();self.assertEqual(len(self.state()['trainingJournal']['importedPlans']),1)

    def test_native_sets_restart_edit_full_backup_restore_and_independent_group_drafts(self):
        self.prepare();self.ready();self.preview();self.store();self.activate()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="TEST-B"]').click();self.page.locator('[data-act=start]').click()
        f=self.form('TEST-4');self.fill(f);f.locator('[data-rich-action=add-segment]').click();self.fill(f)
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.reload();self.page.locator('[data-draft-resume]').first.click()
        expect(self.page.locator('.performanceForm input[data-field=kg]')).to_have_count(5)
        self.page.locator('.performanceForm [type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        f=self.form('TEST-5');self.fill(f);self.save(f)
        state=self.state();sid=state['activeId'];self.assertEqual(len(state['entries'][-1]['performance']['rows']),4)
        snapshot=state['trainingJournal']['sessionSnapshots'][-1]
        self.page.locator('[data-panel=stats]').click();expect(self.page.locator('.stat-table')).to_contain_text('640')
        self.page.locator('[data-tab=calendar]').click();self.page.locator(f'[data-act=openSession][data-id="{sid}"]').click()
        self.page.locator('[data-expand="TEST-4"]').click();self.page.locator('[data-panel=historicalResult]').click()
        f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click();f.locator('[data-row="0"][data-segment="2"][data-field=kg]').fill('11');self.save(f)
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'][-1],snapshot)
        state=self.state()
        self.assertEqual(len(state['entries'][-2]['performance']['rows'][0]['segments']),3)
        self.settings()
        with self.page.expect_download() as d:self.page.locator('[data-act=export]').click()
        raw=Path(d.value.path()).read_bytes();backup=json.loads(raw);self.assertEqual(backup['version'],3)
        other=self.new_context(service_workers='block');page=other.new_page();page.on('dialog',lambda d:d.accept());page.goto(self.url)
        page.locator('[data-tab=settings]').click();page.locator('#importFile').set_input_files({'name':'full.json','mimeType':'application/json','buffer':raw})
        confirm_restore(page)
        expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible()
        actual=page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return db.value}finally{db.close()}}');self.assertEqual(actual,state)
        page.reload();expect(page.locator('[data-act=finish]')).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="TEST-A"]').click();self.page.locator('[data-act=start]').click()
        f=self.form('TEST-1');self.fill(f)
        self.page.locator('[data-expand="TEST-2"]').click();self.page.locator('[data-panel=result]').click();self.page.locator('[data-rich-action=toggle]').click();self.fill(self.page.locator('.performanceForm'))
        self.page.locator('[data-expand="TEST-1"]').click();self.page.locator('[data-panel=result]').click();self.save(self.page.locator('.performanceForm'))
        self.page.reload();expect(self.page.locator('[data-draft-resume]')).to_have_count(1)
        self.page.locator('[data-draft-resume]').click();expect(self.page.locator('.performanceForm')).to_have_attribute('data-id','TEST-2')
        self.assertEqual(self.local_raw(),legacy.RAW)

    def test_import_keeps_active_v2_until_confirmation_and_manual_drive_preserves_full_history(self):
        import test_v2_training as training
        from test_drive_sync import MockGoogle,ManualDriveFlow
        mock=MockGoogle();mock.install(self.context)
        training.V2Training.activate(self)
        form=training.V2Training.open_result(self,'PUSH A','PUSH-A-1')
        training.V2Training.fill_rows(self,form,'22.25','9');training.V2Training.save_form(self,form)
        self.page.locator('[data-panel=result]').click()
        self.page.locator('[data-quick=kg]').fill('45.5')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.state()
        drafts=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')
        ManualDriveFlow.configure(self)
        self.preview();self.store();saved=self.state()
        self.assertEqual(saved['trainingJournal']['activePlanVersionId'],before['trainingJournal']['activePlanVersionId'])
        self.assertEqual(saved['trainingJournal'].get('activations'),before['trainingJournal'].get('activations'))
        self.assertEqual(saved['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertEqual(saved['sessions'],before['sessions']);self.assertEqual(saved['entries'],before['entries'])
        self.confirm=False;self.page.locator('[data-plan-activate]').click();self.assertEqual(self.state(),saved)
        self.assertEqual(mock.posts,0) # Preview/store/cancel never trigger cloud uploads.
        self.settings();ManualDriveFlow.upload(self)
        self.assertEqual(mock.posts,1)
        self.confirm=True;self.plans('synthetic-v3');self.activate()
        self.assertEqual(mock.posts,1) # Explicit plan activation remains local too.
        self.settings()
        with self.page.expect_request('https://www.googleapis.com/upload/**'):
            self.page.locator('[data-drive-action=upload]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zapisana i zweryfikowana')
        self.assertEqual(mock.posts,2)
        current=self.state()
        ManualDriveFlow.restore_preview(self,list(mock.files)[-1])
        backup=json.loads(list(mock.files.values())[-1]['text'])['backup']
        self.assertEqual(self.state(),current) # Preview never restores automatically.
        self.page.locator('[data-restore-cancel]').click()
        self.assertEqual(self.page.evaluate('async text=>(await PushPullDB.parseModelBackup(text)).data',backup),current)
        self.assertEqual(current['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertEqual(current['entries'],before['entries']);self.assertEqual(current['sessions'],before['sessions'])
        self.assertEqual(self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}'),drafts)
        self.page.reload();self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('.performanceForm [data-row="0"][data-field=kg]')).to_have_value('45.5')
        self.assertEqual(self.state()['activeId'],before['activeId'])
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertFalse(self.alerts,self.alerts)

    def test_optional_side_split_preserves_values_and_ids_for_drop_and_backoff(self):
        p=json.loads(json.dumps(PLAN));p['positions'][3]['sideMode']='optional'
        next(v for v in p['variants'] if v['id']==p['positions'][3]['variantId'])['laterality']='unilateral'
        self.prepare();self.ready();self.preview(p);self.store();self.activate()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="TEST-B"]').click();self.page.locator('[data-act=start]').click()
        f=self.form('TEST-4');self.fill(f)
        original=self.page.evaluate('async()=> (await import("./model/performance-editor.mjs")).state("TEST-4",document.querySelector(".performanceForm").dataset.session).performance')
        self.confirm=False;f.locator('[data-rich-action=sides]').click();self.confirm=True
        self.assertEqual(f.locator('[data-rich-action=side-mode]').count(),0)
        f.locator('[data-rich-action=sides]').click()
        for row in range(6):expect(f.locator(f'[data-row="{row}"][data-segment="0"][data-field=kg]')).to_have_value('20')
        f.locator('[data-rich-action=add-segment][data-row="0"]').click()
        expect(f.locator('[data-row="3"][data-segment="2"][data-field=kg]')).to_be_visible()
        f.locator('[data-row="0"][data-segment="2"][data-field=kg]').fill('5')
        f.locator('[data-row="0"][data-segment="2"][data-field=reps]').fill('15')
        expect(f.locator('[data-row="3"][data-segment="2"][data-field=kg]')).to_have_value('5')
        f.locator('[data-row="2"][data-field=kg]').fill('12')
        expect(f.locator('[data-row="5"][data-field=kg]')).to_have_value('12')
        expect(f.locator('[data-row="1"][data-field=kg]')).to_have_value('20')
        f.locator('[data-rich-action=side-mode][data-row="0"]').click()
        f.locator('[data-rich-action=remove-segment][data-row="0"][data-segment="2"]').click()
        expect(f.locator('[data-row="3"][data-segment="2"][data-field=kg]')).to_have_value('5')
        self.save(f);entry=self.state()['entries'][-1];rows=entry['performance']['rows']
        self.assertEqual([len(r['segments']) for r in rows],[2,1,1,3,1,1])
        for old,new in zip(original['rows'],rows[:3]):
            self.assertEqual(old['id'],new['id']);self.assertEqual(old['setId'],new['setId'])
            self.assertEqual([s['id'] for s in old['segments']],[s['id'] for s in new['segments']])
        self.assertEqual(len({r['id'] for r in rows}),6)
        self.assertEqual(len({s['id'] for r in rows for s in r['segments']}),9)
        self.assertFalse(self.alerts,self.alerts)
