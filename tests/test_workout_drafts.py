"""Four real recovery flows in existing mobile UI; no production data."""
import json
import os
import signal
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_result_panel
import test_v2_training as v2tests
import test_indexeddb as legacy

class WorkoutDrafts(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    activate=v2tests.V2Training.activate
    open_result=v2tests.V2Training.open_result
    fill_rows=v2tests.V2Training.fill_rows
    save_form=v2tests.V2Training.save_form

    def drafts(self):
        return self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}")

    def persisted(self,form):
        expect(form.locator('[data-draft-status]')).to_have_text('Szkic zapisany lokalnie · wynik niezatwierdzony')

    def reopen(self):
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.url);self.ready()

    def resume(self,eid):
        # Each recovery row includes its exercise identity; choose that one.
        self.page.locator('.spaced').filter(has=self.page.locator('[data-draft-resume]')).filter(has_text=eid).last.locator('[data-draft-resume]').click()
        return self.page.locator(f'.performanceForm[data-id="{eid}"]')

    def test_series_close_reopen_conflict_and_explicit_discard(self):
        self.activate();form=self.open_result('PUSH A','PUSH-A-3');before=self.state()
        self.assertTrue(self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{try{await d.removeDraft({key:'state',id:'not-a-draft',token:null});return false}catch(e){return e.message.includes('klucz szkicu')}}finally{d.close()}}"""))
        self.fill_rows(form,'100','6')
        form.locator('[data-row="2"][data-field=kg]').fill('70')
        form.locator('[data-row="2"][data-field=reps]').fill('10');self.persisted(form)
        draft=self.drafts()[0]
        self.assertEqual(self.state(),before) # No official entry/tonnage/history update.
        self.reopen();form=self.resume('PUSH-A-3')
        expect(form.locator('[data-row="2"][data-field=kg]')).to_have_value('70')
        self.save_form(form)
        self.assertEqual(self.state()['entries'][-1]['performance']['rows'],draft['value']['performance']['rows'])
        self.assertEqual(self.drafts(),[])
        # A stale draft after a newer approved result is preserved, never applied.
        self.page.evaluate("""async record=>{const d=await PushPullDB.open(()=>{});try{await d.writeDraft(record,null)}finally{d.close()}}""",draft)
        self.page.reload();self.ready()
        expect(self.page.locator('[data-draft-resume]')).to_have_count(0)
        expect(self.page.get_by_text('Konflikt lub inna sesja/wersja/wynik. Nie zastosowano szkicu.')).to_be_visible()
        with self.page.expect_download():self.page.locator('[data-draft-download]').click()
        self.confirm=False;self.page.locator('[data-draft-discard]').click();self.assertEqual(len(self.drafts()),1)
        self.confirm=True;self.page.locator('[data-draft-discard]').click()
        expect(self.page.locator('[data-draft-discard]')).to_have_count(0)
        self.assertEqual(self.drafts(),[])
        self.page.locator('[data-act=finish]').click()
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.assertEqual(self.state()['entries'][:-1],before['entries'])

    def test_drop_and_left_right_survive_renderer_crash_and_reload(self):
        self.activate();form=self.open_result('PUSH A','PUSH-A-5');self.fill_rows(form)
        form.locator('[data-rich-action=add-segment][data-row="1"]').click()
        form.locator('[data-row="1"][data-segment="2"][data-field=kg]').fill('5')
        form.locator('[data-row="1"][data-segment="2"][data-field=reps]').fill('15');self.persisted(form)
        drop=self.drafts()[0]
        # Kill renderer rather than dispatching pagehide/unload; emulate OS process loss.
        with self.page.expect_event('crash',timeout=5000):
            cdp=self.browser.new_browser_cdp_session()
            processes=cdp.send('SystemInfo.getProcessInfo')['processInfo']
            for process in processes:
                if process['type']=='renderer':os.kill(int(process['id']),signal.SIGKILL)
            cdp.detach()
        self.reopen();form=self.resume('PUSH-A-5')
        expect(form.locator('[data-row="1"][data-segment="2"][data-field=kg]')).to_have_value('5')
        self.save_form(form);self.page.locator('[data-act=finish]').click()
        form=self.open_result('PULL A','PULL-A-1')
        form.locator('[data-quick=kg]').fill('40');form.locator('[data-quick=reps]').fill('9')
        form.locator('[data-row="1"][data-field=kg]').fill('35');self.persisted(form)
        sides=self.drafts()[0]
        self.page.reload();self.ready();form=self.resume('PULL-A-1')
        expect(form.locator('[data-row="1"][data-field=kg]')).to_have_value('35')
        self.save_form(form)
        self.assertEqual(self.state()['entries'][-1]['performance']['rows'],sides['value']['performance']['rows'])
        self.assertEqual(self.state()['entries'][-2]['performance']['rows'],drop['value']['performance']['rows'])
        self.assertEqual(self.drafts(),[])

    def test_superset_A_saved_B_recovers_independently_offline(self):
        self.page.close();self.context=self.new_context(service_workers='allow')
        self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.url)
        self.activate();form=self.open_result('PULL B','PULL-B-6-SKI');self.fill_rows(form,'50','8');self.persisted(form)
        expect(self.page.locator('[data-expand="PULL-B-6-SKI"] .name')).to_have_text('Narciarz')
        self.page.locator('[data-expand="PULL-B-6-SHRUGS"]').click();open_result_panel(self.page)
        form_b=self.page.locator('.performanceForm');form_b.locator('[data-rich-action=toggle]').click()
        self.fill_rows(form_b,'15','10');self.persisted(form_b)
        b=next(r for r in self.drafts() if r['exerciseId']=='PULL-B-6-SHRUGS')
        self.page.locator('[data-expand="PULL-B-6-SKI"]').click();open_result_panel(self.page)
        self.save_form(self.page.locator('.performanceForm'))
        self.assertEqual([d['exerciseId'] for d in self.drafts()],['PULL-B-6-SHRUGS'])
        self.page.evaluate('navigator.serviceWorker.ready')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.context.set_offline(True)
        self.reopen();form=self.resume('PULL-B-6-SHRUGS')
        self.assertEqual(self.state()['entries'][-1]['exerciseId'],'PULL-B-6-SKI')
        self.save_form(form)
        self.assertEqual(self.state()['entries'][-1]['performance']['rows'],b['value']['performance']['rows'])
        self.assertEqual(self.drafts(),[])
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

    def test_failed_approved_save_keeps_draft_and_retry_has_no_duplicates(self):
        self.activate();form=self.open_result('PUSH A','PUSH-A-3');self.fill_rows(form,'80','8');self.persisted(form)
        draft=self.drafts()[0];before=self.state()
        self.page.evaluate("""()=>{window.__put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v){if(this.name==='journalState'&&v.id==='active')throw new DOMException('Draft result quota','QuotaExceededError');return window.__put.call(this,v)}}""")
        with self.page.expect_event('dialog'):form.locator('[type=submit]').click()
        self.assertEqual(self.state(),before);self.assertEqual(self.drafts(),[draft])
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_have_count(0)
        # A later edit cannot reach IDB either: the synchronous buffer must recover it.
        self.page.evaluate("""()=>{IDBObjectStore.prototype.put=function(v){if(this.name==='meta'&&v.key.startsWith('workout-draft:'))throw new DOMException('Draft quota','QuotaExceededError');return window.__put.call(this,v)}}""")
        form=self.page.locator('.performanceForm')
        form.locator('[data-row="0"][data-field=kg]').fill('75')
        form.locator('[data-row="0"][data-field=reps]').fill('9')
        expect(form.locator('[data-draft-status]')).to_contain_text('buforze odzyskiwania')
        buffered=self.page.evaluate("()=>Object.keys(localStorage).filter(k=>k.startsWith('pushpull_workout_draft_v1:')).map(k=>JSON.parse(localStorage.getItem(k))).sort((a,b)=>b.sequence-a.sequence)[0]")
        self.reopen();form=self.resume('PUSH-A-3')
        expect(form.locator('[data-row="0"][data-field=kg]')).to_have_value('75')
        self.save_form(form)
        self.assertEqual(len(self.state()['entries']),len(before['entries'])+1)
        self.assertEqual(self.state()['entries'][-1]['performance']['rows'],buffered['value']['performance']['rows'])
        self.assertEqual(self.drafts(),[])
