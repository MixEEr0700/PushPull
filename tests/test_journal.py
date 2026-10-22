"""The opt-in journal through the real mobile forms, calendar and JSON controls."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy

class JournalFlow(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    records=legacy.IndexedDBMigration.records

    def settings(self):
        self.page.locator('[data-tab=settings]').click()

    def enable(self):
        self.prepare();self.ready()
        self.page.locator('[data-act=finish]').click()
        self.before=self.state()
        self.settings()
        with self.page.expect_download():self.page.locator('[data-enable-journal]').click()
        expect(self.page.get_by_text('Nowy zapis włączony',exact=True)).to_be_visible()
        self.assertEqual(self.state()['entries'],self.before['entries'])
        self.assertEqual(self.state()['sessions'],self.before['sessions'])
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],[])
        self.page.locator('[data-tab=training]').click()
        self.page.locator('[data-type="PUSH A"]').click()

    def start_result(self):
        self.page.locator('[data-act=start]').click();self.ready()
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        self.page.locator('[data-panel=result]').click()
        expect(self.page.locator('[data-main=kg]')).to_have_value('')
        self.page.locator('[data-main=kg]').fill('100')
        self.page.locator('[data-main=reps]').fill('8')
        self.page.locator('[data-series-toggle]').click()
        self.page.locator('[data-series-index="1"][data-field=kg]').fill('75')
        self.page.locator('[data-series-index="1"][data-field=reps]').fill('10')
        self.page.locator('[data-series-remove="2"]').click()
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()

    def test_real_session_restart_correction_statistics_and_v3_restore(self):
        self.enable();self.start_result()
        saved=self.state();entry=saved['entries'][-1];sid=saved['activeId']
        self.assertEqual([r['kg'] for r in entry['series']],['100','75'])
        self.assertEqual(len({r['id'] for r in entry['series']}),2)
        snapshot=saved['trainingJournal']['sessionSnapshots'][0]
        self.page.locator('[data-act=finish]').click()
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url)
        self.page.locator('[data-tab=calendar]').click()
        self.page.locator(f'[data-act=openSession][data-id="{sid}"]').click()
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        self.page.locator('[data-panel=historicalResult]').click()
        self.page.locator('[data-series-toggle]').click()
        self.page.locator('[data-series-index="1"][data-field=kg]').fill('60')
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        corrected=self.state()
        self.assertEqual([r['id'] for r in corrected['entries'][-1]['series']],[r['id'] for r in entry['series']])
        self.assertEqual(corrected['trainingJournal']['sessionSnapshots'][0],snapshot)
        self.assertEqual(corrected['entries'][:-1],self.before['entries'])
        self.page.locator('[data-panel=stats]').click()
        expect(self.page.locator('.stat-tile').first).to_contain_text('1400')
        self.assertEqual(self.page.locator('.stat-table .stat-row').count(),2)
        self.settings()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_text();backup=json.loads(raw)
        self.assertEqual(backup['version'],3)
        self.assertEqual(len(backup['payload']['resultReferences']),2)
        self.assertEqual(backup['payload']['sessionSnapshots'][0],snapshot)
        before_records=self.records()
        unsupported=self.page.evaluate('''async raw=>{const b=await import('./model/backup.mjs');const d=JSON.parse(raw);d.payload.resultRecords.at(-1).data.futureField='must not be dropped';return b.exportBackup(await b.createBackup(d.payload,{createdAt:d.createdAt,metadata:d.metadata}))}''',raw)
        with self.page.expect_event('dialog') as rejected:
            self.page.locator('#importFile').set_input_files({'name':'future-v3.json','mimeType':'application/json','buffer':unsupported.encode()})
        self.assertIn('unsupported backup contents',rejected.value.message)
        self.assertEqual(self.records(),before_records)
        # A separate empty browser profile restores using the same actual UI.
        other=self.new_context(service_workers='block');page=other.new_page();page.on('dialog',lambda d:d.accept())
        page.goto(self.url);page.locator('[data-tab=settings]').click()
        page.locator('#importFile').set_input_files({'name':'full-v3.json','mimeType':'application/json','buffer':raw.encode()})
        expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible()
        restored=page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{if(d.error)throw d.error;return d.value}finally{d.close()}}')
        self.assertEqual(restored,corrected)
        page.reload();expect(page.locator('h1')).to_have_text('Trening')
        self.assertEqual(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),True)
        page.locator('[data-type="PUSH A"]').click()
        expect(page.locator('.exercise-card').first).to_contain_text('60 kg')
        page.locator('[data-act=start]').click()
        page.locator('[data-expand="PUSH-A-1"]').click()
        page.locator('[data-panel=result]').click()
        page.locator('.seriesResultForm [type=submit]').click()
        expect(page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        newer=page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value.entries.at(-1)}finally{d.close()}}')
        self.assertTrue({r['id'] for r in newer['series']}.isdisjoint({r['id'] for r in entry['series']}))
        self.assertEqual(self.local_raw(),legacy.RAW)

    def test_failed_save_retains_draft_and_retry_does_not_duplicate_session(self):
        self.enable()
        self.page.locator('[data-act=start]').click();self.ready()
        before=self.state()
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        self.page.locator('[data-panel=result]').click()
        self.page.locator('[data-main=kg]').fill('100')
        self.page.locator('[data-main=reps]').fill('8')
        self.page.evaluate("""() => {window.__put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v){if(this.name==='meta' && v.key==='training-model-v1')throw new DOMException('Journal quota','QuotaExceededError');return window.__put.call(this,v)}}""")
        with self.page.expect_event('dialog'):
            self.page.locator('.seriesResultForm [type=submit]').click()
        self.assertEqual(self.state(),before)
        self.assertTrue(any('Journal quota' in a for a in self.alerts))
        expect(self.page.locator('[data-main=kg]')).to_have_value('100')
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_have_count(0)
        self.page.evaluate('()=>{IDBObjectStore.prototype.put=window.__put}')
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        after=self.state()
        self.assertEqual(after['sessions'],before['sessions'])
        self.assertEqual(len(after['entries']),len(before['entries'])+1)
        self.assertEqual(len(after['trainingJournal']['sessionSnapshots']),1)

    def test_cancel_optin_and_snapshot_survives_changed_current_parameters(self):
        self.prepare();self.ready();self.settings();self.confirm=False
        self.page.locator('[data-enable-journal]').click()
        self.assertNotIn('trainingJournal',self.state())
        self.confirm=True
        self.enable();self.start_result();before=self.state();sid=before['activeId']
        self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const v=d.value;v.exercises['PUSH A'][0].name='Changed current machine';await d.commit(v)}finally{d.close()}}""")
        self.page.reload();self.ready()
        expect(self.page.locator('.exercise-card .name').first).to_have_text('Prostowanie ud obunóż')
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PUSH A"]').click()
        expect(self.page.locator('.exercise-card .name').first).to_have_text('Changed current machine')
        expect(self.page.locator('.exercise-card').first).to_contain_text('Brak zapisanego wyniku')

    def test_interrupted_optin_keeps_legacy_usable_and_can_be_retried(self):
        self.prepare();self.ready();self.settings()
        self.page.evaluate("""() => {window.__alert=window.alert;window.alert=text=>{window.__optinError=text};window.__put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v){if(this.name==='meta' && v.key==='training-model-v1')throw new DOMException('Optin quota','QuotaExceededError');return window.__put.call(this,v)}}""")
        with self.page.expect_download():self.page.locator('[data-enable-journal]').click()
        self.page.wait_for_function('window.__optinError?.includes("Optin quota")')
        self.assertNotIn('trainingJournal',self.state())
        self.assertIn('Optin quota',self.page.evaluate('window.__optinError'))
        self.page.evaluate('()=>{IDBObjectStore.prototype.put=window.__put;window.alert=window.__alert}')
        self.page.locator('[data-tab=training]').click()
        expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.settings()
        with self.page.expect_download():self.page.locator('[data-enable-journal]').click()
        expect(self.page.get_by_text('Nowy zapis włączony',exact=True)).to_be_visible()
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],[])

    def test_source_pair_snapshot_and_v3_roundtrip_without_v2_activation(self):
        self.enable()
        self.page.locator('[data-tab=training]').click()
        self.page.locator('[data-type="PULL B"]').click();self.page.locator('[data-act=start]').click()
        self.ready();before=self.state();snapshot=before['trainingJournal']['sessionSnapshots'][-1]
        self.assertTrue(snapshot['planVersionId'].startswith('observed:'))
        self.assertNotIn('activePlanVersionId',before['trainingJournal'])
        for eid,kg in [('PULL-B-6-SKI','23'),('PULL-B-6-SHRUGS','12')]:
            self.page.locator(f'[data-expand="{eid}"]').click();self.page.locator('[data-panel=result]').click()
            form=self.page.locator('.seriesResultForm')
            form.locator('[data-main=kg]').fill(kg);form.locator('[data-main=reps]').fill('8')
            expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
            form.locator('[type=submit]').click();expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        saved=self.state()
        self.assertEqual(saved['entries'][:-2],before['entries'])
        self.assertEqual(saved['trainingJournal']['sessionSnapshots'][-1],snapshot)
        self.assertTrue(all(e['journalSnapshotId']==snapshot['id'] and len(e['series'])==2 for e in saved['entries'][-2:]))
        self.page.reload();self.ready();self.assertEqual(self.state(),saved)
        self.settings()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_bytes();self.assertEqual(json.loads(raw)['version'],3)
        self.page.locator('#importFile').set_input_files({'name':'source-pair-v3.json','mimeType':'application/json','buffer':raw})
        self.ready();self.assertEqual(self.state(),saved)
        self.assertFalse(self.alerts,self.alerts)
