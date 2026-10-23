"""V2 in the existing phone journal, using only synthetic history."""
from test_browser import confirm_restore
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy

class V2Training(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    records=legacy.IndexedDBMigration.records

    def activate(self):
        self.prepare();self.ready()
        self.before=self.state()
        self.plans('v2-owner-2026-10-22')
        self.assertNotIn('trainingJournal',self.state())
        self.confirm=False;self.page.locator('[data-plan-activate]').click()
        self.assertNotIn('trainingJournal',self.state())
        self.confirm=True
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        # Old in-progress session has not acquired new prescriptions.
        self.assertEqual(self.state()['sessions'],self.before['sessions'])
        self.assertEqual(self.state()['entries'],self.before['entries'])
        self.page.locator('[data-tab=training]').click()
        expect(self.page.locator('.exercise-card .name').nth(3)).to_have_text('Dipy')
        self.page.locator('[data-act=finish]').click()

    def open_result(self,type,id):
        self.page.locator('[data-type="'+type+'"]').click()
        self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="'+id+'"]').click()
        self.page.locator('[data-panel=result]').click()
        form=self.page.locator('.performanceForm').first
        form.locator('[data-rich-action=toggle]').click()
        return form

    def fill_rows(self,form,kg='20',reps='8'):
        for el in form.locator('input[data-field=kg]').all():el.fill(kg)
        for el in form.locator('input[data-field=reps]').all():el.fill(reps)

    def save_form(self,form):
        form.locator('[type=submit]').click()
        expect(self.page.locator('.performanceForm')).to_have_count(0)
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()

    def history_edit(self,sid,id):
        self.page.locator('[data-tab=calendar]').click()
        self.page.locator(f'[data-act=openSession][data-id="{sid}"]').click()
        if self.page.locator(f'[data-expand="{id}"]').get_attribute('aria-expanded')!='true':self.page.locator(f'[data-expand="{id}"]').click()
        self.page.locator('[data-panel=historicalResult]').click()
        form=self.page.locator('.performanceForm').first
        form.locator('[data-rich-action=toggle]').click()
        return form

    def test_backoff_restart_edit_notes_statistics_and_full_restore(self):
        self.activate()
        form=self.open_result('PUSH A','PUSH-A-3')
        expect(form).to_contain_text('back-off')
        self.fill_rows(form,'100','6')
        form.locator('[data-row="2"][data-field=kg]').fill('70')
        form.locator('[data-row="2"][data-field=reps]').fill('10')
        self.save_form(form)
        expect(self.page.locator('.exercise-toggle .last-series-row')).to_have_text(['Seria 1: 6 × 100 kg','Seria 2: 6 × 100 kg','Seria 3 · back-off: 10 × 70 kg'])
        saved=self.state();sid=saved['activeId'];entry=saved['entries'][-1]
        self.assertEqual(len(entry['performance']['rows']),3)
        self.page.locator('.v2NoteForm textarea').fill('Moja technika, nie instrukcja trenera')
        self.page.locator('.v2NoteForm button').click()
        expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        self.page.reload();self.ready()
        self.page.locator('[data-act=finish]').click()
        form=self.history_edit(sid,'PUSH-A-3')
        self.confirm=False;form.locator('[data-quick=kg]').fill('90')
        expect(form.locator('[data-row="2"][data-field=kg]')).to_have_value('70')
        expect(form.locator('[data-row="0"][data-field=kg]')).to_have_value('100')
        self.confirm=True
        form.locator('[data-row="2"][data-field=kg]').fill('60')
        self.save_form(form)
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],saved['trainingJournal']['sessionSnapshots'])
        self.assertEqual([r['id'] for r in self.state()['entries'][-1]['performance']['rows']],[r['id'] for r in entry['performance']['rows']])
        self.page.locator('[data-panel=stats]').click()
        expect(self.page.locator('.stat-tile').first).to_contain_text('1800')
        self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_text();backup=json.loads(raw)
        self.assertEqual(backup['version'],3)
        self.assertEqual(backup['payload']['resultRecords'][-1]['data']['segments'][0]['kg'],'60')
        expected=self.state()
        other=self.new_context(service_workers='block');page=other.new_page();page.on('dialog',lambda d:d.accept())
        page.goto(self.url);page.locator('[data-tab=settings]').click()
        page.locator('#importFile').set_input_files({'name':'v2.json','mimeType':'application/json','buffer':raw.encode()})
        confirm_restore(page)
        expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible()
        actual=page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}')
        self.assertEqual(actual,expected)
        self.assertEqual(self.state()['entries'][:-1],self.before['entries'])
        self.assertEqual(self.local_raw(),legacy.RAW)
        self.assertFalse(self.alerts,self.alerts)

    def test_drop_sides_and_two_round_group_mobile_corrections(self):
        self.activate()
        form=self.open_result('PUSH A','PUSH-A-5');self.fill_rows(form)
        form.locator('[data-rich-action=add-segment][data-row="1"]').click()
        form.locator('[data-row="1"][data-segment="2"][data-field=kg]').fill('5')
        form.locator('[data-row="1"][data-segment="2"][data-field=reps]').fill('15')
        form.locator('[data-rich-action=remove-segment][data-row="1"][data-segment="2"]').click()
        form.locator('[data-rich-action=add-segment][data-row="1"]').click()
        form.locator('[data-row="1"][data-segment="2"][data-field=kg]').fill('5')
        form.locator('[data-row="1"][data-segment="2"][data-field=reps]').fill('15')
        self.save_form(form)
        expect(self.page.locator('.exercise-toggle .last-series-row')).to_have_text(['Seria 1 · dropset: 8 × 20 kg → 8 × 20 kg','Seria 2 · dropset: 8 × 20 kg → 8 × 20 kg → 15 × 5 kg','Seria 3 · dropset: 8 × 20 kg → 8 × 20 kg'])
        drop=self.state()['entries'][-1];drop_sid=self.state()['activeId']
        self.assertEqual([len(r['segments']) for r in drop['performance']['rows']],[2,3,2])
        self.page.locator('[data-act=finish]').click()
        form=self.open_result('PULL A','PULL-A-1')
        # Quick input fills both sides; asymmetric correction requires explicit separation.
        form.locator('[data-quick=kg]').fill('40');form.locator('[data-quick=reps]').fill('9')
        expect(form.locator('[data-row="1"][data-field=kg]')).to_have_value('40')
        form.locator('[data-rich-action=side-mode][data-row="0"]').click()
        form.locator('[data-row="1"][data-field=kg]').fill('35')
        self.save_form(form)
        sides=self.state()['entries'][-1]
        self.assertEqual([r['side'] for r in sides['performance']['rows']],['left','right']*3)
        self.assertEqual(sides['series'][1]['kg'],'35')
        self.page.locator('[data-act=finish]').click()
        form=self.open_result('PULL B','PULL-B-6-SKI')
        self.fill_rows(form,'50','8');self.save_form(form)
        # A/B are independent cards with the original IDs and shared group/rundown.
        self.page.locator('[data-expand="PULL-B-6-SHRUGS"]').click()
        self.page.locator('[data-panel=result]').click()
        form=self.page.locator('.performanceForm');form.locator('[data-rich-action=toggle]').click()
        self.fill_rows(form,'15','10');self.save_form(form)
        saved=self.state();sid=saved['activeId']
        for eid,value in [('PULL-B-6-SKI','8 × 50 kg'),('PULL-B-6-SHRUGS','10 × 15 kg')]:
            expect(self.page.locator('.exercise-card').filter(has=self.page.locator(f'[data-expand="{eid}"]')).locator('.exercise-toggle .last-result')).to_have_text(value)
        pair=saved['entries'][-2:]
        self.assertEqual([e['exerciseId'] for e in pair],['PULL-B-6-SKI','PULL-B-6-SHRUGS'])
        self.assertTrue(all([r['round'] for r in e['performance']['rows']]==[1,2] for e in pair))
        self.page.reload();self.ready();self.page.locator('[data-act=finish]').click()
        form=self.history_edit(sid,'PULL-B-6-SKI');self.fill_rows(form,'45','9');self.save_form(form)
        self.page.locator('[data-panel=stats]').click()
        expect(self.page.locator('.stat-tile').nth(0)).to_contain_text('810')
        self.page.locator('[data-expand="PULL-B-6-SHRUGS"]').click()
        self.page.locator('[data-panel=stats]').click()
        expect(self.page.locator('.stat-tile').first).to_contain_text('300')
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        form=self.history_edit(drop_sid,'PUSH-A-5')
        expect(form.locator('[data-row="1"][data-segment="2"][data-field=kg]')).to_have_value('5')
        form.locator('[data-row="1"][data-segment="2"][data-field=kg]').fill('4')
        self.save_form(form)
        self.assertEqual(self.state()['entries'][-4]['performance']['rows'][1]['segments'][2]['id'],drop['performance']['rows'][1]['segments'][2]['id'])
        self.assertFalse(self.alerts,self.alerts)
        # The full copy must include sides, flexible drops and both group members.
        expected=self.state();self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_text()
        other=self.new_context(service_workers='block');page=other.new_page();page.on('dialog',lambda d:d.accept())
        page.goto(self.url);page.locator('[data-tab=settings]').click()
        page.locator('#importFile').set_input_files({'name':'all-structures.json','mimeType':'application/json','buffer':raw.encode()})
        confirm_restore(page)
        expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible()
        self.assertEqual(page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}'),expected)

    def test_incomplete_and_aborted_v2_save_keep_original_history_and_retry(self):
        self.activate();form=self.open_result('PUSH A','PUSH-A-5');before=self.state()
        # No hidden required-input failure: incomplete rows are revealed, draft retained.
        with self.page.expect_event('dialog'):form.locator('[type=submit]').click()
        self.assertEqual(self.state(),before)
        expect(form.locator('[data-rich-details]')).to_be_visible()
        self.fill_rows(form)
        self.page.evaluate("""()=>{window.__put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v){if(this.name==='meta'&&v.key==='training-model-v1')throw new DOMException('V2 quota','QuotaExceededError');return window.__put.call(this,v)}}""")
        with self.page.expect_event('dialog'):form.locator('[type=submit]').click()
        self.assertEqual(self.state(),before)
        expect(form.locator('[data-row="0"][data-segment="0"][data-field=kg]')).to_have_value('20')
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_have_count(0)
        self.page.evaluate('()=>{IDBObjectStore.prototype.put=window.__put}')
        self.save_form(form)
        self.assertEqual(len(self.state()['entries']),len(before['entries'])+1)

    def test_symmetric_sides_per_set_separation_draft_restart_rejoin_and_history(self):
        self.activate();form=self.open_result('PULL A','PULL-A-1');before=self.state()
        expect(form.get_by_label('Ciężar (kg)',exact=True)).to_be_visible()
        expect(form).not_to_contain_text('Szybki ciężar')
        form.locator('[data-quick=kg]').fill('40');form.locator('[data-quick=reps]').fill('9')
        for row in range(6):
            expect(form.locator(f'[data-row="{row}"][data-field=kg]')).to_have_value('40')
            expect(form.locator(f'[data-row="{row}"][data-field=reps]')).to_have_value('9')
        form.locator('[data-row="2"][data-field=kg]').fill('45')
        expect(form.locator('[data-row="3"][data-field=kg]')).to_have_value('45')
        form.locator('[data-row="3"][data-field=reps]').fill('10')
        expect(form.locator('[data-row="2"][data-field=reps]')).to_have_value('10')
        for row in [0,1,4,5]:expect(form.locator(f'[data-row="{row}"][data-field=kg]')).to_have_value('40')
        form.locator('[data-rich-action=side-mode][data-row="2"]').click()
        form.locator('[data-row="3"][data-field=kg]').fill('37')
        expect(form.locator('[data-row="2"][data-field=kg]')).to_have_value('45')
        # Explicit separation must survive even while both sides are still equal.
        form.locator('[data-rich-action=side-mode][data-row="0"]').click()
        self.confirm=False;form.locator('[data-quick=kg]').fill('99');self.confirm=True
        expect(form.locator('[data-row="3"][data-field=kg]')).to_have_value('37')
        expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        draft=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return (await db.readDrafts())[0]}finally{db.close()}}')
        self.assertEqual(self.state(),before)
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();form=self.page.locator('.performanceForm')
        expect(form.locator('[data-rich-action=side-mode][data-row="0"]')).to_have_attribute('aria-pressed','true')
        form.locator('[data-row="1"][data-field=kg]').fill('38')
        expect(form.locator('[data-row="0"][data-field=kg]')).to_have_value('40')
        self.confirm=False;form.locator('[data-rich-action=side-mode][data-row="0"]').click()
        expect(form.locator('[data-row="1"][data-field=kg]')).to_have_value('38')
        self.confirm=True;form.locator('[data-rich-action=side-mode][data-row="0"]').click()
        expect(form.locator('[data-row="1"][data-field=kg]')).to_have_value('40')
        form.locator('[data-row="5"][data-field=kg]').fill('41')
        expect(form.locator('[data-row="4"][data-field=kg]')).to_have_value('41')
        self.save_form(form);saved=self.state();sid=saved['activeId'];entry=saved['entries'][-1]
        self.assertEqual([r['id'] for r in entry['performance']['rows']],[r['id'] for r in draft['value']['performance']['rows']])
        form=self.history_edit(sid,'PULL-A-1')
        expect(form.locator('[data-rich-action=side-mode][data-row="2"]')).to_have_attribute('aria-pressed','true')
        expect(form.locator('[data-row="2"][data-field=kg]')).to_have_value('45')
        expect(form.locator('[data-row="3"][data-field=kg]')).to_have_value('37')
        form.locator('[data-row="3"][data-field=reps]').fill('7')
        expect(form.locator('[data-row="2"][data-field=reps]')).to_have_value('10')
        self.save_form(form);corrected=self.state()['entries'][-1]
        self.assertEqual(corrected['id'],entry['id'])
        self.assertEqual([r['id'] for r in corrected['performance']['rows']],[r['id'] for r in entry['performance']['rows']])
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in corrected['series']),2167)
        self.page.locator('[data-panel=stats]').click()
        self.assertIn('2167',self.page.locator('.stat-tile').first.inner_text().replace('\xa0','').replace(' ',''))
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'));self.assertFalse(self.alerts,self.alerts)
