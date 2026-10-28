"""Isolated real IndexedDB: pairs, finish orchestration, failure/restart and offline."""
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_notes,wait_for_service_worker_controller,seed_historical_editor
import test_v2_training as v2

class FinishPairs(BrowserHarness):
    activate=v2.V2Training.activate
    prepare=v2.V2Training.prepare
    ready=v2.V2Training.ready
    fill_rows=v2.V2Training.fill_rows
    open_result=v2.V2Training.open_result
    save_form=v2.V2Training.save_form
    history_edit=v2.V2Training.history_edit

    def drafts(self):return self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')
    def finish_panel(self):
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-finish-panel]')).to_be_visible()
    def fill(self,f):f.locator('[data-quick=kg]').fill('40');f.locator('[data-quick=reps]').fill('10');expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')

    def test_pairs_remove_first_last_add_independent_merge_and_restart_at_mobile_widths(self):
        self.activate();f=self.open_result('PULL A','PULL-A-1')
        self.page.evaluate("()=>{const c=window.confirm;window.confirm=m=>{(window.quickPrompts??=[]).push(m);return c(m)}}")
        self.fill(f);self.assertEqual(self.page.evaluate('window.quickPrompts||[]'),[])
        before=self.state();original=[r['id'] for r in self.drafts()[0]['value']['performance']['rows']]
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            expect(f.locator('[data-side-pair]')).to_have_count(3)
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        f.locator('[data-rich-action=remove-set]').first.click();expect(f.locator('[data-side-pair]')).to_have_count(2)
        self.assertEqual([r['id'] for r in self.drafts()[0]['value']['performance']['rows']],original[2:])
        f.locator('[data-rich-action=remove-set]').first.click();expect(f.locator('[data-side-pair]')).to_have_count(1)
        f.locator('[data-rich-action=remove-set]').first.click();expect(f.locator('[data-side-pair]')).to_have_count(0)
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-side-pair]')).to_have_count(0)
        f.locator('[data-rich-action=add-set]').click();expect(f.locator('[data-side-pair]')).to_have_count(1)
        self.fill(f);f=seed_historical_editor(self.page,"d.performance.rows[1].segments[0].kg='35'")
        expect(f.locator('[data-row="0"][data-field=kg]')).to_have_value('40')
        expect(f.locator('[data-side-exception]')).to_be_visible()
        self.confirm=False;f.locator('[data-rich-action=merge-right]').click()
        expect(f.locator('[data-row="0"][data-field=kg]')).to_have_value('40')
        self.confirm=True;f.locator('[data-rich-action=merge-right]').click()
        expect(f.locator('[data-common-pair=true][data-field=kg]')).to_have_value('35')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-common-pair=true][data-field=kg]')).to_have_value('35')
        self.assertEqual(len(self.drafts()[0]['value']['performance']['rows']),2)
        expect(f.locator('[data-row="0"][data-field=kg]')).to_have_value('35')
        snapshot=self.drafts()[0]['value']['performance'];self.assertEqual(self.state(),before)
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-side-pair]')).to_have_count(1);self.save_form(f)
        entry=self.state()['entries'][-1];self.assertEqual(entry['performance'],snapshot)
        self.assertEqual(len(entry['series']),2);self.assertEqual([r['side'] for r in entry['performance']['rows']],['left','right'])
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])

    def test_finish_complete_drafts_preserves_history_and_notes_without_heading(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-1');self.fill(f)
        open_notes(self.page);expect(self.page.locator('.exercise-notes h3')).to_have_count(0)
        expect(self.page.locator('[data-personal-note] summary')).to_have_text('＋')
        expect(self.page.locator('[data-personal-note] textarea')).not_to_be_visible()
        self.page.locator('[data-expand="PUSH-A-2"]').click();f=self.page.locator('.performanceForm');self.fill(f)
        before=self.state();drafts=self.drafts();self.assertEqual(len(drafts),2)
        self.finish_panel();self.page.locator('[data-finish-save]').dblclick()
        expect(self.page.get_by_text('Trening zakończony',exact=True)).to_be_visible();expect(self.page.locator('[data-act=start]')).to_be_visible()
        after=self.state();self.assertEqual(after['entries'][:-2],before['entries']);self.assertEqual(after['exercises'],before['exercises'])
        self.assertEqual(after['trainingJournal']['model'],before['trainingJournal']['model']);self.assertFalse(self.drafts())
        self.assertEqual(after['activeId'],None);self.assertEqual(len(after['entries']),len(before['entries'])+2)
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),after)

    def test_incomplete_conflicting_and_explicit_discard_never_finish_silently(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-1');f.locator('[data-quick=kg]').fill('40')
        before=self.state();self.finish_panel();expect(self.page.locator('[data-finish-panel]')).to_contain_text('Seria 1')
        expect(self.page.locator('[data-finish-save]')).to_have_count(0);self.assertEqual(self.state(),before)
        self.confirm=False;self.page.locator('[data-finish-discard]').click();self.assertEqual(self.state(),before);self.assertTrue(self.drafts())
        self.page.locator('[data-finish-back]').click();f=self.page.locator('.performanceForm');f.locator('[data-quick=reps]').fill('10')
        other=self.context.new_page();other.on('dialog',self.dialog);other.goto(self.url)
        other.locator('[data-expand="PUSH-A-1"]').click();other.locator('[data-draft-resume]').count() # recovery is explicit; new edit is an independent branch
        other.locator('[data-quick=kg]').fill('50');other.locator('[data-quick=reps]').fill('9');expect(other.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.finish_panel();expect(self.page.locator('[data-finish-panel]')).to_contain_text('Kilka wersji szkicu')
        self.assertEqual(self.state(),before);self.assertEqual(len(self.drafts()),2)
        other.close();self.confirm=True;self.page.locator('[data-finish-discard]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.assertEqual(self.state()['entries'],before['entries']);self.assertFalse(self.drafts())

    def test_abort_second_result_retains_all_drafts_and_restart_retry_is_idempotent(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-1');self.fill(f)
        self.page.locator('[data-expand="PUSH-A-2"]').click();self.fill(self.page.locator('.performanceForm'))
        before=self.state();drafts=self.drafts();self.finish_panel()
        self.page.evaluate('''id=>{window.failResultId=id;for(const method of ['add','put']){const original=IDBObjectStore.prototype[method];IDBObjectStore.prototype[method]=function(v,...rest){if(this.name==='journalResults'&&v.id===window.failResultId){window.failedSecond=true;this.transaction.abort();}return original.call(this,v,...rest)}}}''','draft-result-'+next(d['id'] for d in drafts if d['exerciseId']=='PUSH-A-2'))
        self.page.locator('[data-finish-save]').click();expect(self.page.locator('[data-finish-panel] [role=alert]')).to_be_visible()
        self.assertTrue(self.page.evaluate('window.failedSecond===true'));self.assertEqual(len(self.drafts()),2);self.assertEqual(self.state()['activeId'],before['activeId'])
        self.assertEqual(len(self.state()['entries']),len(before['entries'])+1)
        self.page.reload();self.ready();self.finish_panel();self.page.locator('[data-finish-save]').click()
        expect(self.page.locator('[data-act=start]')).to_be_visible();after=self.state()
        self.assertEqual(len(after['entries']),len(before['entries'])+2);self.assertEqual(after['entries'][:-2],before['entries']);self.assertFalse(self.drafts())

    def test_large_equal_rows_after_individual_editor_add_and_offline_finish(self):
        self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url);wait_for_service_worker_controller(self.page);self.activate();f=self.open_result('PUSH A','PUSH-A-1');self.fill(f)
        for _ in range(5):f.locator('[data-rich-action=add-set]').click()
        self.fill(f);self.save_form(f);expect(self.page.locator('.exercise-card').first.locator('.last-result')).to_contain_text('10 × 40 kg')
        self.assertEqual(len(self.state()['entries'][-1]['performance']['rows']),8)
        self.page.reload();self.ready();expect(self.page.locator('.exercise-card').first.locator('.last-result')).to_contain_text('10 × 40 kg')
        self.context.set_offline(True);self.page.locator('[data-expand="PUSH-A-2"]').click();self.fill(self.page.locator('.performanceForm'))
        self.finish_panel();self.page.locator('[data-finish-save]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();after=self.state()
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),after)

    def test_existing_odd_layout_is_retained_and_missing_side_added_only_explicitly(self):
        self.activate();f=self.open_result('PULL A','PULL-A-1');self.fill(f)
        original=self.page.evaluate("""async()=>{const m=await import('./model/performance-editor.mjs'),f=document.querySelector('.performanceForm'),d=m.state(f.dataset.id,f.dataset.session);d.performance.rows.pop();d.sidePairs=[];m.restore(f.dataset.id,f.dataset.session,d);return d.performance.rows}""")
        self.page.locator('[data-expand="PULL-A-1"]').click();self.page.locator('[data-expand="PULL-A-1"]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-missing-side]')).to_have_count(1)
        self.assertEqual(self.page.evaluate("async()=>{const m=await import('./model/performance-editor.mjs'),f=document.querySelector('.performanceForm');return m.state(f.dataset.id,f.dataset.session).performance.rows}"),original)
        f.locator('[data-rich-action=missing-side]').click();expect(f.locator('[data-row="5"][data-field=kg]')).to_have_value('')
        f.locator('[data-row="5"][data-field=kg]').fill('35');f.locator('[data-row="5"][data-field=reps]').fill('9')
        self.save_form(f);rows=self.state()['entries'][-1]['performance']['rows'];self.assertEqual(rows[:5],original);self.assertEqual(rows[5]['side'],'right')
        self.assertEqual(rows[5]['segments'][0]['kg'],'35')

    def test_quota_and_session_abort_retain_drafts_until_successful_retry(self):
        for mode in ['quota','session-abort']:
            with self.subTest(mode=mode):
                self.activate();f=self.open_result('PUSH A','PUSH-A-1');self.fill(f);before=self.state();self.finish_panel()
                self.page.evaluate("""mode=>{for(const key of ['add','put']){const old=IDBObjectStore.prototype[key];IDBObjectStore.prototype[key]=function(v,...a){if(mode==='quota'&&this.name==='journalObjects'){window.injectedFailure=true;throw new DOMException('synthetic quota','QuotaExceededError')}if(mode==='session-abort'&&this.name==='journalSessions'){window.injectedFailure=true;this.transaction.abort()}return old.call(this,v,...a)}}}""",mode)
                self.page.locator('[data-finish-save]').click();expect(self.page.locator('[data-finish-panel] [role=alert]')).to_be_visible()
                self.assertTrue(self.page.evaluate('window.injectedFailure===true'));self.assertEqual(len(self.drafts()),1)
                self.assertEqual(self.state()['activeId'],before['activeId']);self.assertEqual(len(self.state()['entries']),len(before['entries'])+(mode=='session-abort'))
                self.page.reload();self.ready();self.finish_panel();self.page.locator('[data-finish-save]').click()
                expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertFalse(self.drafts())
                self.assertEqual(len(self.state()['entries']),len(before['entries'])+1)

    def test_legacy_editor_memory_survives_failed_draft_storage_and_explicit_finish(self):
        self.start();before=self.state()
        self.page.evaluate("""()=>{window.oldSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.startsWith('pushpull_workout_draft_v1:'))throw new DOMException('buffer quota','QuotaExceededError');return oldSet.call(this,k,v)};const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v,...a){if(this.name==='meta'&&v.key?.startsWith('workout-draft:'))throw new DOMException('draft quota','QuotaExceededError');return put.call(this,v,...a)}}""")
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        f=self.page.locator('.seriesResultForm');f.locator('[data-main=kg]').fill('25');f.locator('[data-main=reps]').fill('8')
        expect(f.locator('[data-draft-status]')).to_contain_text('Nie utrwalono szkicu')
        self.finish_panel();self.page.locator('[data-finish-save]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        after=self.state();self.assertEqual(len(after['entries']),1);self.assertEqual(after['entries'][0]['kg'],'25')
        self.assertEqual(len(after['entries'][0]['series']),3);self.assertEqual(after['exercises'],before['exercises']);self.assertFalse(self.drafts())
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),after)
