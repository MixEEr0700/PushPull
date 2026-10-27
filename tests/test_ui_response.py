"""Real IndexedDB completion/error boundaries for immediate training feedback."""
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as idb


class TrainingResponse(BrowserHarness):
    def ready(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible()

    def hold(self):
        self.page.evaluate(idb.PAUSE)

    def held(self):
        self.page.wait_for_function('window.__held===true')
        expect(self.page.locator('[data-training-pending]')).to_be_visible()
        self.assertTrue(self.page.locator('#app').evaluate('(e)=>e.inert'))
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

    def release(self):
        self.page.evaluate('window.__hold=false')
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertFalse(self.page.locator('#app').evaluate('(e)=>e.inert'))

    def drafts(self):
        return self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}""")

    def test_start_feedback_precedes_commit_and_double_click_cannot_queue_navigation(self):
        self.ready();self.hold()
        self.page.evaluate("""()=>{const b=document.querySelector('[data-act=start]');b.click();b.dispatchEvent(new MouseEvent('click',{bubbles:true}));document.querySelector('[data-tab=calendar]').click()}""")
        self.held()
        expect(self.page.locator('[data-training-pending]')).to_contain_text('Rozpoczynanie')
        expect(self.page.locator('[data-act=finish]')).to_have_count(0)
        expect(self.page.locator('[data-act=prevMonth]')).to_have_count(0)
        # A readonly history transaction would wait behind this writer. Release
        # and abort scenarios inspect stored state after that boundary instead.
        self.release()
        expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual(len(self.state()['sessions']),1)
        expect(self.page.locator('[data-act=prevMonth]')).to_have_count(0)

    def test_result_waits_for_complete_preserves_draft_until_success_and_keeps_one_entry(self):
        self.start();self.result('22,5','9')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        drafts=self.drafts();self.hold()
        self.page.evaluate("""()=>{const f=document.querySelector('.seriesResultForm');f.requestSubmit();f.requestSubmit();document.querySelector('[data-tab=settings]').click()}""")
        self.held()
        expect(self.page.locator('[data-training-pending]')).to_contain_text('Zapisywanie')
        expect(self.page.locator('.seriesResultForm')).to_be_visible()
        self.assertNotIn('Wynik zapisany',self.page.locator('body').inner_text())
        self.release()
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        entries=self.state()['entries'];self.assertEqual(len(entries),1)
        self.assertEqual(entries[0]['kg'],'22.5');self.assertEqual(entries[0]['reps'],'9')
        self.assertTrue(drafts);self.assertEqual(self.drafts(),[])

    def test_aborted_result_unlocks_and_retains_approved_history_and_draft_after_restart(self):
        self.start();self.result('23,','')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        incomplete=self.drafts()
        self.page.reload()
        expect(self.page.locator('[data-draft-resume]')).to_be_visible()
        self.assertEqual(self.drafts(),incomplete)
        self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('[data-main=kg]')).to_have_value('23,')
        expect(self.page.locator('[data-main=reps]')).to_have_value('')
        self.page.locator('[data-main=kg]').fill('23.5');self.page.locator('[data-main=reps]').fill('8')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.state();drafts=self.drafts();self.hold()
        self.page.locator('.seriesResultForm [type=submit]').click();self.held()
        self.page.evaluate('window.__hold=false;window.__transaction.abort()')
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertFalse(self.page.locator('#app').evaluate('(e)=>e.inert'))
        self.assertTrue(self.alerts)
        self.assertEqual(self.state(),before);self.assertEqual(self.drafts(),drafts)
        self.page.reload();expect(self.page.locator('[data-draft-resume]')).to_be_visible()
        self.assertEqual(self.state(),before);self.assertEqual(self.drafts(),drafts)

    def test_quota_failure_removes_pending_feedback_and_does_not_claim_success(self):
        self.ready();before=self.state()
        self.page.evaluate("""()=>{const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v,...args){if(this.name==='journalState'&&v.id==='active')throw new DOMException('Synthetic quota','QuotaExceededError');return put.call(this,v,...args)}}""")
        self.page.locator('[data-act=start]').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        expect(self.page.locator('[data-act=start]')).to_be_enabled()
        self.assertEqual(self.state(),before)
        self.assertTrue(any('Synthetic quota' in a for a in self.alerts))
        self.assertFalse(self.page.locator('#app').evaluate('(e)=>e.inert'))

    def test_closing_page_during_held_commit_recovers_draft_without_partial_result(self):
        self.start();self.result('26,5','6')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.state();drafts=self.drafts();self.hold()
        self.page.locator('.seriesResultForm [type=submit]').click();self.held()
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url)
        expect(self.page.locator('[data-draft-resume]')).to_be_visible()
        self.assertEqual(self.state(),before);self.assertEqual(self.drafts(),drafts)
        self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('[data-main=kg]')).to_have_value('26,5')
        expect(self.page.locator('[data-main=reps]')).to_have_value('6')
        self.assertFalse(self.page.locator('#app').evaluate('(e)=>e.inert'))

    def test_cancel_and_validation_error_unlock_the_original_controls(self):
        self.start();self.confirm=False
        self.page.locator('[data-act=finish]').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        expect(self.page.locator('[data-act=finish]')).to_be_enabled()
        self.assertEqual(self.state()['sessions'][0]['status'],'active')
        self.result('invalid','8')
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        expect(self.page.locator('.seriesResultForm [type=submit]')).to_be_enabled()
        self.assertEqual(self.state()['entries'],[])
        self.assertFalse(self.page.locator('#app').evaluate('(e)=>e.inert'))

    def test_hidden_document_does_not_wait_forever_for_animation_frames(self):
        self.ready()
        self.page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});window.requestAnimationFrame=()=>0")
        self.page.evaluate("document.querySelector('[data-act=start]').click()")
        expect(self.page.locator('[data-act=finish]')).to_be_visible()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertEqual(len(self.state()['sessions']),1)

    def test_suspended_frames_have_a_bounded_fallback(self):
        self.ready()
        self.page.evaluate("window.requestAnimationFrame=()=>0;document.querySelector('[data-act=start]').click()")
        expect(self.page.locator('[data-act=finish]')).to_be_visible()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertEqual(len(self.state()['sessions']),1)

    def test_other_tab_wins_cas_while_feedback_is_visible_without_losing_drafts(self):
        self.start();self.result('24','8')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.state();drafts=self.drafts()
        other=self.context.new_page();other.on('dialog',lambda d:d.accept());other.goto(self.url)
        expect(other.locator('[data-act=finish]')).to_be_visible()
        # Pause hashing before the history transaction, allowing a genuine
        # competing commit. No fake DB or weakened CAS is involved.
        self.page.evaluate("""()=>{const digest=window.__originalDigest=crypto.subtle.digest.bind(crypto.subtle);crypto.subtle.digest=async(...args)=>{window.__digestHeld=true;await new Promise(resolve=>window.__releaseDigest=resolve);return digest(...args)}}""")
        self.page.evaluate("document.querySelector('.seriesResultForm').requestSubmit()")
        self.page.wait_for_function('window.__digestHeld===true')
        expect(self.page.locator('[data-training-pending]')).to_be_visible()
        other.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const value=d.value;value.exercises['PUSH A'][0].notes='synthetic other tab';await d.commit(value)}finally{d.close()}}""")
        self.page.evaluate('crypto.subtle.digest=window.__originalDigest;window.__releaseDigest()')
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertFalse(self.page.locator('#app').evaluate('(e)=>e.inert'))
        self.assertTrue(self.alerts)
        before['exercises']['PUSH A'][0]['notes']='synthetic other tab'
        self.assertEqual(self.state(),before);self.assertEqual(self.drafts(),drafts)

    def test_pending_feedback_and_real_writes_work_in_offline_pwa(self):
        context=self.new_context(service_workers='allow')
        self.page=context.new_page();self.page.on('dialog',self.dialog);self.page.goto(self.url)
        self.ready();self.page.evaluate('navigator.serviceWorker.ready')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        context.set_offline(True);self.page.reload();self.ready()
        self.start();self.result('25','7');self.hold()
        self.page.locator('.seriesResultForm [type=submit]').click();self.held()
        self.release();expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        self.assertEqual(self.state()['entries'][0]['kg'],'25')
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual(self.state()['entries'][0]['reps'],'7')
