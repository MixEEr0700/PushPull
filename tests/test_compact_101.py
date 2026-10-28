"""Issue101: real disposable IndexedDB, explicit sides, ad-hoc drop roundtrips."""
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,add_drop,confirm_restore,wait_for_service_worker_controller,seed_historical_editor
import test_v2_training as v2

class Compact101(BrowserHarness):
    prepare=v2.V2Training.prepare
    ready=v2.V2Training.ready
    activate=v2.V2Training.activate
    open_result=v2.V2Training.open_result
    fill_rows=v2.V2Training.fill_rows
    save_form=v2.V2Training.save_form
    history_edit=v2.V2Training.history_edit

    def memory(self):return self.page.evaluate("async()=>{const m=await import('./model/performance-editor.mjs'),f=document.querySelector('.performanceForm');return m.state(f.dataset.id,f.dataset.session)}")
    def drafts(self):return self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
    def restart(self):
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();return self.page.locator('.performanceForm')
    def optional_pair(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-6');self.fill_rows(f,'24','10')
        f.locator('.execution-choice summary').click();f.locator('[data-rich-action=sides]').click()
        return f
    def mobile_toolbar(self,f):
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            expect(f.locator('.series-add-actions>.btn')).to_have_text(['+ Dodaj serię','+ Dodaj dropset'])
            self.assertTrue(f.locator('.series-add-actions>.btn').evaluate_all('es=>{const [a,b]=es.map(e=>e.getBoundingClientRect());return Math.abs(a.width-b.width)<.1&&Math.abs(a.y-b.y)<.1&&a.height>=44&&b.height>=44}'))
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.assertFalse(f.locator('[data-rich-action=side-mode]').count())

    def test_optional_delete_all_restart_add_common_pair_and_history_without_second_multiplier(self):
        f=self.optional_pair();before=self.state();old=self.memory()['performance'];self.mobile_toolbar(f)
        for _ in range(3):f.locator('[data-rich-action=remove-set]').first.click()
        expect(f.locator('[data-compact-row]')).to_have_count(0)
        self.assertEqual(self.memory()['executionMode'],'paired')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        f=self.restart();expect(f.locator('[data-compact-row]')).to_have_count(0)
        self.assertEqual(self.memory()['executionMode'],'paired');self.assertEqual(self.state(),before)
        f.locator('[data-rich-action=add-set]').click();expect(f.locator('[data-compact-row]')).to_have_count(1)
        expect(f.locator('[data-field=kg]')).to_have_value('');expect(f.locator('[data-field=reps]')).to_have_value('')
        self.fill_rows(f,'24','10');new=self.memory()['performance'];self.assertEqual([r['side'] for r in new['rows']],['left','right'])
        self.assertTrue(all(r['id'] not in [x['id'] for x in old['rows']] for r in new['rows']))
        f=self.restart();expect(f.locator('[data-field=kg]')).to_have_count(1);self.save_form(f)
        saved=self.state();e=saved['entries'][-1];self.assertEqual(len(e['series']),2);self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in e['series']),480)
        self.assertEqual(e['performance'],new);self.assertEqual(saved['entries'][:-1],before['entries']);self.assertEqual(saved['trainingJournal'],before['trainingJournal'])
        f=self.history_edit(e['sessionId'],e['exerciseId']);expect(f.locator('[data-field=kg]')).to_have_count(1)
        self.save_form(f);self.assertEqual(self.state()['entries'][-1]['performance'],new)

    def test_drop_child_delete_all_restart_readd_and_parent_delete_all_rebuild(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-5');self.fill_rows(f,'24','10');before=self.state();original=self.memory()['performance']
        for row in [0,1,2]:f.locator(f'[data-rich-action=remove-segment][data-row="{row}"]').click()
        expect(f.locator('[data-compact-row]')).to_have_count(3);self.mobile_toolbar(f)
        f=self.restart();add_drop(f,1);expect(f.locator('[data-row="1"][data-segment="1"][data-field=kg]')).to_have_value('')
        self.assertEqual([r['segments'][0]['id'] for r in self.memory()['performance']['rows']],[r['segments'][0]['id'] for r in original['rows']])
        f.locator('[data-row="1"][data-segment="1"][data-field=kg]').fill('10');f.locator('[data-row="1"][data-segment="1"][data-field=reps]').fill('6')
        for _ in range(3):f.locator('[data-rich-action=remove-set]').first.click()
        f=self.restart();expect(f.locator('[data-rich-action=add-drop]')).to_be_disabled()
        f.locator('[data-rich-action=add-set]').click();self.assertEqual(self.memory()['performance']['rows'][0]['setId'],original['rows'][0]['setId'])
        # The prescribed drop is still known; no values are invented.
        self.assertTrue(all(s['kg']=='' and s['reps']=='' for s in self.memory()['performance']['rows'][0]['segments']))
        while f.locator('[data-rich-action=remove-segment]').count():f.locator('[data-rich-action=remove-segment]').first.click()
        add_drop(f);self.fill_rows(f,'24','10');self.save_form(f)
        e=self.state()['entries'][-1];self.assertEqual(len(e['performance']['rows']),1);self.assertEqual(len(e['series']),2)
        self.assertEqual(self.state()['entries'][:-1],before['entries']);self.assertEqual(self.state()['trainingJournal'],before['trainingJournal'])

    def test_ad_hoc_plain_and_new_series_target_draft_restart_v3_restore_and_tonnage(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-1');self.fill_rows(f,'24','10');before=self.state();original=self.memory()['performance']
        f.locator('[data-rich-action=add-drop]').click();expect(f.locator('[data-drop-target]')).to_be_visible();self.assertEqual(self.memory()['performance'],original)
        f.locator('[data-drop-target]').select_option(original['rows'][1]['id'])
        expect(f.locator('.compact-set').nth(1).locator('.compact-number')).to_have_text(['2','+1'])
        f.locator('[data-row="1"][data-segment="1"][data-field=kg]').fill('12');f.locator('[data-row="1"][data-segment="1"][data-field=reps]').fill('6')
        f.locator('[data-rich-action=add-set]').click()
        f.locator('[data-row="3"][data-field=kg]').fill('24');f.locator('[data-row="3"][data-field=reps]').fill('10')
        expect(f.locator('[data-row="1"][data-segment="1"][data-field=kg]')).to_have_value('12')
        expect(f.locator('[data-row="1"][data-segment="1"][data-field=reps]')).to_have_value('6')
        add_drop(f,3)
        expect(f.locator('[data-row="3"][data-segment="1"][data-field=kg]')).to_have_value('')
        f.locator('[data-row="3"][data-segment="1"][data-field=kg]').fill('8');f.locator('[data-row="3"][data-segment="1"][data-field=reps]').fill('5');self.mobile_toolbar(f)
        snapshot=self.memory()['performance'];self.assertEqual(snapshot['rows'][3]['setId'],None);self.assertEqual(snapshot['rows'][3]['dropOrigin'],'user')
        f=self.restart();self.assertEqual(self.memory()['performance'],snapshot);self.save_form(f)
        saved=self.state();e=saved['entries'][-1];self.assertEqual(e['performance'],snapshot);self.assertEqual(len(e['series']),6)
        self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in e['series']),1072)
        self.assertEqual(saved['entries'][:-1],before['entries']);self.assertEqual(saved['trainingJournal'],before['trainingJournal'])
        self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as dl:self.page.locator('[data-act=export]').click()
        text=Path(dl.value.path()).read_bytes();other=self.new_context(service_workers='block');page=other.new_page();page.on('dialog',lambda d:d.accept());page.goto(self.url)
        page.locator('[data-tab=settings]').click();page.locator('#importFile').set_input_files({'name':'user-drops-v3.json','mimeType':'application/json','buffer':text});confirm_restore(page)
        expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible()
        self.assertEqual(page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}'),saved)

    def test_common_lp_user_drop_offline_finish_counts_both_records_once(self):
        self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog);self.page.goto(self.url)
        wait_for_service_worker_controller(self.page);self.activate();f=self.open_result('PULL A','PULL-A-1');self.fill_rows(f,'24','10');before=self.state()
        self.context.set_offline(True);add_drop(f,0);self.fill_rows(f,'24','10');snapshot=self.memory()['performance']
        self.assertEqual([len(r['segments']) for r in snapshot['rows']],[2,2,1,1,1,1]);expect(f.locator('[data-compact-row]')).to_have_count(4)
        f=self.restart();self.assertEqual(self.memory()['performance'],snapshot)
        self.page.locator('[data-act=finish]').click();self.page.locator('[data-finish-save]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        saved=self.state();e=saved['entries'][-1];self.assertEqual(e['performance'],snapshot);self.assertEqual(len(e['series']),8)
        self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in e['series']),1920);self.assertFalse(self.drafts())
        self.assertEqual(saved['entries'][:-1],before['entries']);self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),saved)

    def test_incomplete_and_aborted_user_drop_keeps_all_draft_data_and_retry(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-1');self.fill_rows(f,'24','10');before=self.state();add_drop(f,0)
        with self.page.expect_event('dialog'):f.locator('[type=submit]').click()
        self.assertEqual(self.state(),before);self.assertTrue(self.drafts());expect(f.locator('[data-row="0"][data-segment="1"][data-field=kg]')).to_have_value('')
        self.fill_rows(f,'24','10');expected=self.memory()['performance']
        self.page.evaluate("()=>{const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v,...a){if(this.name==='journalState'&&v.id==='active'){window.injected101=true;this.transaction.abort()}return put.call(this,v,...a)}}")
        with self.page.expect_event('dialog'):f.locator('[type=submit]').click()
        self.assertTrue(self.page.evaluate('window.injected101===true'));self.assertEqual(self.state(),before);self.assertTrue(self.drafts())
        f=self.restart();self.assertEqual(self.memory()['performance'],expected);self.save_form(f)
        self.assertEqual(self.state()['entries'][-1]['performance'],expected);self.assertEqual(self.state()['entries'][:-1],before['entries'])

    def test_historical_asymmetry_survives_additional_segment_on_chosen_side(self):
        self.activate();f=self.open_result('PULL A','PULL-A-1');self.fill_rows(f,'24','10');before=self.state()
        f=seed_historical_editor(self.page,"d.performance.rows[1].segments[0].kg='21'");snapshot=self.memory()['performance'];add_drop(f,1)
        expect(f.locator('[data-row="1"][data-segment="1"][data-field=kg]')).to_have_value('')
        f.locator('[data-row="1"][data-segment="1"][data-field=kg]').fill('10');f.locator('[data-row="1"][data-segment="1"][data-field=reps]').fill('6')
        self.assertEqual(self.memory()['performance']['rows'][0],snapshot['rows'][0]);f=self.restart();self.save_form(f)
        saved=self.state()['entries'][-1];self.assertEqual(saved['performance']['rows'][0],snapshot['rows'][0]);self.assertEqual(saved['performance']['rows'][1]['segments'][0],snapshot['rows'][1]['segments'][0])
        self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in saved['series']),1470)
        self.assertEqual(self.state()['entries'][:-1],before['entries'])
