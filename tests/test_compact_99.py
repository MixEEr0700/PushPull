"""Issue99 real isolated IndexedDB and compact editor. Synthetic evidence only."""
from playwright.sync_api import expect
from test_browser import BrowserHarness,seed_historical_editor,wait_for_service_worker_controller
import test_v2_training as v2
import test_plan_import as plans_fixture

class Compact99(BrowserHarness):
    activate=v2.V2Training.activate
    prepare=v2.V2Training.prepare
    ready=v2.V2Training.ready
    open_result=v2.V2Training.open_result
    save_form=v2.V2Training.save_form
    history_edit=v2.V2Training.history_edit
    fill_rows=v2.V2Training.fill_rows

    def memory(self):
        return self.page.evaluate("async()=>{const m=await import('./model/performance-editor.mjs'),f=document.querySelector('.performanceForm');return m.state(f.dataset.id,f.dataset.session)}")
    def saved_drafts(self):
        return self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
    def restart(self):
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();return self.page.locator('.performanceForm')

    def test_common_lp_mobile_three_two_one_zero_add_restart_save_history_tonnage(self):
        self.activate();f=self.open_result('PULL A','PULL-A-1');before=self.state()
        f.locator('[data-quick=kg]').fill('24');f.locator('[data-quick=reps]').fill('10')
        original=self.memory()['performance']
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            expect(f.locator('[data-compact-row]')).to_have_count(3)
            expect(f.locator('[data-field=kg]')).to_have_count(3)
            self.assertFalse(any(t in f.inner_text() for t in ['Seria 1 (L/P)','Wspólna edycja','Rozdziel','Scal L/P','tempo','RIR','back-off']))
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.assertTrue(f.locator('[data-compact-row] .btn').evaluate_all('es=>es.every(e=>e.getBoundingClientRect().height>=44&&e.getBoundingClientRect().width>=44)'))
        self.assertEqual(self.memory()['performance'],original);self.assertEqual(self.state(),before)
        f.locator('[data-row="2"][data-field=kg]').fill('25')
        rows=self.memory()['performance']['rows'];self.assertEqual([r['segments'][0]['kg'] for r in rows],['24','24','25','25','24','24'])
        f.locator('[data-rich-action=remove-set]').first.click();expect(f.locator('[data-compact-row]')).to_have_count(2)
        self.assertEqual([r['id'] for r in self.memory()['performance']['rows']],[r['id'] for r in original['rows'][2:]])
        f.locator('[data-rich-action=remove-set]').last.click();expect(f.locator('[data-compact-row]')).to_have_count(1)
        f.locator('[data-rich-action=remove-set]').click();expect(f.locator('[data-compact-row]')).to_have_count(0)
        f=self.restart();expect(f.locator('[data-compact-row]')).to_have_count(0)
        with self.page.expect_event('dialog'):f.locator('[type=submit]').click()
        self.assertIn('Brak serii',self.alerts[-1]);self.assertEqual(self.state(),before)
        f.locator('[data-rich-action=add-set]').click();expect(f.locator('[data-compact-row]')).to_have_count(1)
        expect(f.locator('[data-field=kg]')).to_have_value('');expect(f.locator('[data-field=reps]')).to_have_value('')
        self.fill_rows(f,'24','10');self.save_form(f)
        entry=self.state()['entries'][-1];self.assertEqual(len(entry['series']),2)
        self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in entry['series']),480)
        self.page.reload();self.ready();self.assertEqual(self.state()['entries'][-1],entry)
        f=self.history_edit(entry['sessionId'],'PULL-A-1');expect(f.locator('[data-compact-row]')).to_have_count(1)
        self.save_form(f);corrected=self.state()['entries'][-1];self.assertEqual(corrected['performance'],entry['performance']);self.assertEqual(corrected['id'],entry['id'])
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])

    def test_drop_order_ids_one_two_three_segments_and_no_history_mutation(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-5');self.fill_rows(f,'20','8');before=self.state();original=self.memory()['performance']
        expect(f.locator('[data-compact-row]')).to_have_count(6)
        f.locator('[data-rich-action=add-segment][data-row="0"]').click();expect(f.locator('[data-compact-row]')).to_have_count(7)
        expect(f.locator('[data-row="0"][data-segment="2"][data-field=kg]')).to_have_value('')
        f.locator('[data-row="0"][data-segment="2"][data-field=kg]').fill('5');f.locator('[data-row="0"][data-segment="2"][data-field=reps]').fill('12')
        expect(f.locator('.compact-set').first.locator('.compact-number')).to_have_text(['1','+1','+2'])
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.assertTrue(f.locator('[data-compact-row] .btn,input[data-field]').evaluate_all('es=>es.every(e=>e.getBoundingClientRect().height>=44)'))
        f=self.restart();self.assertEqual(self.memory()['performance']['rows'][0]['segments'][:2],original['rows'][0]['segments'])
        f.locator('[data-rich-action=remove-segment][data-row="0"][data-segment="1"]').click()
        expect(f.locator('.compact-set').first.locator('.compact-number')).to_have_text(['1','+1'])
        self.assertEqual(self.memory()['performance']['rows'][0]['segments'][1]['kg'],'5')
        f.locator('[data-rich-action=remove-segment][data-row="0"][data-segment="1"]').click()
        expect(f.locator('.compact-set').first.locator('.compact-number')).to_have_text(['1'])
        self.save_form(f);entry=self.state()['entries'][-1];self.assertEqual([len(r['segments']) for r in entry['performance']['rows']],[1,2,2])
        self.assertEqual(self.state()['entries'][:-1],before['entries'])
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])

    def test_historical_asymmetry_unfinished_fields_exception_cancel_confirm_and_restart(self):
        self.activate();f=self.open_result('PULL A','PULL-A-1');self.fill_rows(f,'24','10');before=self.state()
        f=seed_historical_editor(self.page,"d.performance.rows[1].segments[0].kg='21';d.sidePairs.forEach(p=>p.linked=true)")
        expect(f.locator('[data-side-exception]')).to_have_count(1);expect(f.locator('[data-side-caption]')).to_have_text('L: 10 × 24 kg | P: 10 × 21 kg')
        expect(f.locator('[data-quick=kg]')).to_have_attribute('readonly','')
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        f.locator('[data-row="1"][data-field=kg]').fill('21,')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        f=self.restart();expect(f.locator('[data-row="1"][data-field=kg]')).to_have_value('21,')
        f.locator('[data-row="1"][data-field=kg]').fill('21')
        original=self.memory()['performance'];self.confirm=False;f.locator('[data-rich-action=merge-left][data-row="0"]').click()
        self.assertEqual(self.memory()['performance'],original);self.assertEqual(self.state(),before)
        self.confirm=True;f.locator('[data-rich-action=merge-right][data-row="0"]').click()
        expect(f.locator('[data-side-exception]')).to_have_count(0);expect(f.locator('[data-compact-row]')).to_have_count(3)
        self.assertEqual([r['id'] for r in self.memory()['performance']['rows']],[r['id'] for r in original['rows']])
        self.assertEqual([r['segments'][0]['id'] for r in self.memory()['performance']['rows']],[r['segments'][0]['id'] for r in original['rows']])
        f=self.restart();expect(f.locator('[data-field=kg]')).to_have_count(3);self.save_form(f)
        entry=self.state()['entries'][-1];self.assertEqual([r['segments'][0]['kg'] for r in entry['performance']['rows']],['21','21','24','24','24','24'])
        self.assertEqual(self.state()['entries'][:-1],before['entries'])

    def test_three_verified_pairs_1440_offline_finish_and_restart(self):
        self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url);wait_for_service_worker_controller(self.page);self.activate();f=self.open_result('PULL A','PULL-A-1')
        self.context.set_offline(True);self.fill_rows(f,'24','10');expected=self.memory()['performance']
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.locator('[data-act=finish]').click();self.page.locator('[data-finish-save]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        saved=self.state();entry=saved['entries'][-1];self.assertEqual(entry['performance'],expected)
        self.assertEqual(len(entry['series']),6);self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in entry['series']),1440)
        self.assertFalse(self.saved_drafts());self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),saved)
        self.assertFalse(self.alerts,self.alerts)

    def test_legacy_delete_last_and_restart_never_recreates_deleted_series(self):
        self.prepare();self.ready();self.page.locator('[data-expand="PUSH-A-1"]').click()
        f=self.page.locator('.seriesResultForm');f.locator('[data-series-toggle]').click();before=self.state()
        while f.locator('[data-series-remove]').count():f.locator('[data-series-remove]').first.click()
        expect(f.locator('[data-compact-row]')).to_have_count(0)
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.seriesResultForm')
        expect(f.locator('[data-compact-row]')).to_have_count(0);self.assertEqual(self.state(),before)
        f.locator('[data-series-add]').click();expect(f.locator('[data-compact-row]')).to_have_count(1)
        expect(f.locator('[data-field=kg]')).to_have_value('');expect(f.locator('[data-field=reps]')).to_have_value('')
        f.locator('[data-field=kg]').fill('24');f.locator('[data-field=reps]').fill('10');f.locator('[type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        entry=next(e for e in self.state()['entries'] if e['sessionId']==before['activeId'] and e['exerciseId']=='PUSH-A-1')
        self.assertEqual(len(entry['series']),1);self.assertEqual(entry['series'][0]['kg'],'24')
        self.assertEqual(self.state()['sessions'],before['sessions'])
        self.assertEqual([e for e in self.state()['entries'] if e['id']!=entry['id']],[e for e in before['entries'] if e['id']!=entry['id']])

class Compact99Conventions(BrowserHarness):
    prepare=plans_fixture.PlanImport.prepare
    ready=plans_fixture.PlanImport.ready
    preview=plans_fixture.PlanImport.preview
    store=plans_fixture.PlanImport.store
    activate=plans_fixture.PlanImport.activate
    form=plans_fixture.PlanImport.form
    save=plans_fixture.PlanImport.save

    def test_combined_convention_retains_explicit_side_records_and_never_reinterprets_weight(self):
        import copy
        p=copy.deepcopy(plans_fixture.PLAN);position=p['positions'][0];position['sideMode']='required';position['loadConvention']['basis']='combined'
        next(v for v in p['variants'] if v['id']==position['variantId'])['laterality']='unilateral'
        for target in p['sets']:
            if target['positionId']==position['id']:target['side']='each'
        self.prepare();self.ready();self.preview(p);self.store();self.activate()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="TEST-A"]').click();self.page.locator('[data-act=start]').click();f=self.form('TEST-1');before=self.state()
        expect(f.locator('[data-common-pair]')).to_have_count(0);expect(f.locator('[data-side-exception]')).to_have_count(2)
        expect(f.locator('[data-quick=kg]')).to_have_attribute('readonly','')
        expect(f.locator('[data-rich-action=merge-left]')).to_have_count(0)
        for x in f.locator('[data-field=kg]').all():x.fill('24')
        for x in f.locator('[data-field=reps]').all():x.fill('10')
        self.save(f);saved=self.state();e=saved['entries'][-1]
        self.assertEqual(e['performance']['loadConvention']['basis'],'combined')
        self.assertEqual(len(e['series']),4);self.assertEqual([r['side'] for r in e['performance']['rows']],['left','right']*2)
        # Existing semantics: sum actual recorded values once, never an extra ×2.
        self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in e['series']),960)
        self.page.reload();self.ready();self.assertEqual(self.state(),saved)
        self.assertEqual(saved['entries'][:-1],before['entries']);self.assertEqual(saved['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
