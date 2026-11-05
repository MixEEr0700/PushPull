from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_v2_training as t
class Repeat159(BrowserHarness):
    activate=t.V2Training.activate
    prepare=t.V2Training.prepare
    ready=t.V2Training.ready
    open_result=t.V2Training.open_result
    fill_rows=t.V2Training.fill_rows
    save_form=t.V2Training.save_form
    def finish(self):
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
    def test_repeat_convention_skip_restart_and_manual_preserved(self):
        self.activate();f=self.open_result('PULL A','PULL-A-1');f.locator('[data-load-basis]').select_option('per-implement');self.fill_rows(f,'20','8');self.save_form(f);self.finish();old=self.state();source=old['entries'][-1]
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible();sid=self.state()['activeId'];self.finish()
        repeated=next(e for e in self.state()['entries'] if e['sessionId']==sid and e['exerciseId']=='PULL-A-1');self.assertEqual(repeated['performance']['loadConvention'],source['performance']['loadConvention']);self.assertEqual([r['side'] for r in repeated['performance']['rows']],[r['side'] for r in source['performance']['rows']]);self.assertNotEqual(repeated['id'],source['id']);self.assertEqual([r['segments'][0]['kg'] for r in repeated['performance']['rows']],['20']*3)
        self.assertEqual(next(e for e in self.state()['entries'] if e['id']==source['id']),source)
        f=self.open_result('PULL A','PULL-A-1');expect(f.locator('[data-load-basis]')).to_have_value('per-implement');self.fill_rows(f,'25','9');self.save_form(f);manual=self.state()['entries'][-1];self.finish();self.assertEqual(next(e for e in self.state()['entries'] if e['id']==manual['id']),manual)
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible();sid=self.state()['activeId']
        if self.page.locator('[data-expand="PULL-A-1"]').get_attribute('aria-expanded')=='false':self.page.locator('[data-expand="PULL-A-1"]').click()
        self.page.locator('[data-skip-exercise="PULL-A-1"]').click();expect(self.page.locator('[data-skip-exercise="PULL-A-1"]')).to_have_attribute('aria-pressed','true')
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.assertIn('PULL-A-1',self.state()['sessions'][-1]['skippedExerciseIds']);self.finish();self.assertFalse(any(e['sessionId']==sid and e['exerciseId']=='PULL-A-1' for e in self.state()['entries']))
    def test_drops_and_historical_sides_retry_without_duplicate_or_rebinding(self):
        from test_browser import seed_historical_editor,LEGACY_PAIRS
        self.activate();f=self.open_result('PULL A','PULL-A-1');self.fill_rows(f,'20','8');f=seed_historical_editor(self.page,LEGACY_PAIRS+"d.performance.rows[1].segments[0].kg='21';d.performance.rows[1].dropOrigin='user';d.performance.rows[1].segments.push({id:crypto.randomUUID(),kg:'10',reps:'6'})");self.save_form(f);self.finish();source=self.state()['entries'][-1]
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible();sid=self.state()['activeId'];before=self.state()
        # A changed machine/variant identity must never receive a guessed repeat.
        count=self.page.evaluate("async d=>{const m=await import('./model/repeat-results.mjs'),j=await import('./model/journal.mjs'),s=d.sessions.find(s=>s.id===d.activeId),snap=j.snapshotFor(d,s.id),pos=snap.model.positions.find(p=>p.legacyPositionId==='PULL-A-1')??snap.model.positions[0];pos.variantId='different-machine';return m.repeatResults(d,s,j.exercisesFor(d,s)).entries.length}",before);self.assertEqual(count,0)
        self.page.evaluate("()=>{const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v,...a){if(this.name==='journalState'&&v.id==='active')this.transaction.abort();return put.call(this,v,...a)}}")
        with self.page.expect_event('dialog',predicate=lambda d:d.type=='alert'):self.page.locator('[data-act=finish]').click()
        self.assertEqual(self.state(),before)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.finish()
        entries=[e for e in self.state()['entries'] if e['sessionId']==sid];self.assertEqual(len(entries),1)
        new=entries[0];self.assertEqual([r['side'] for r in new['performance']['rows']],[r['side'] for r in source['performance']['rows']])
        self.assertEqual([[ (s['kg'],s['reps']) for s in r['segments']] for r in new['performance']['rows']],[[ (s['kg'],s['reps']) for s in r['segments']] for r in source['performance']['rows']])
        self.assertTrue(set(r['id'] for r in new['performance']['rows']).isdisjoint(r['id'] for r in source['performance']['rows']))
        self.assertEqual(next(e for e in self.state()['entries'] if e['id']==source['id']),source)
    def test_second_automatic_write_abort_then_restart_is_idempotent(self):
        from test_browser import open_result_panel
        self.activate();f=self.open_result('PULL A','PULL-A-1');self.fill_rows(f);self.save_form(f)
        self.page.locator('[data-expand="PULL-A-2"]').click();open_result_panel(self.page);f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click();self.fill_rows(f);self.save_form(f);self.finish()
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible();sid=self.state()['activeId']
        self.page.evaluate("()=>{let count=0;const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v,...a){if(this.name==='journalState'&&v.id==='active'&&++count===2)this.transaction.abort();return put.call(this,v,...a)}}")
        with self.page.expect_event('dialog',predicate=lambda d:d.type=='alert'):self.page.locator('[data-act=finish]').click()
        partial=[e for e in self.state()['entries'] if e['sessionId']==sid];self.assertEqual(len(partial),1);self.assertEqual(self.state()['activeId'],sid)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.finish();entries=[e for e in self.state()['entries'] if e['sessionId']==sid];self.assertEqual(len(entries),2);self.assertEqual(len(set(e['exerciseId'] for e in entries)),2);self.assertIn(partial[0],entries)
