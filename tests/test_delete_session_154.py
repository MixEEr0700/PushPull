from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_v2_training as training

class DeleteSession154(BrowserHarness):
    activate=training.V2Training.activate
    prepare=training.V2Training.prepare
    ready=training.V2Training.ready
    plans=training.V2Training.plans
    open_result=training.V2Training.open_result
    fill_rows=training.V2Training.fill_rows
    save_form=training.V2Training.save_form
    def test_cancel_delete_restore_and_restart(self):
        self.activate()
        form=self.open_result('PULL A','PULL-A-1');self.fill_rows(form);self.save_form(form)
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        before=self.state();target=before['sessions'][-1];snap=before['trainingJournal']['sessionSnapshots'][-1]
        old_backups=self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.backups()}finally{d.close()}}")
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="'+target['date']+'"]').click()
        button=self.page.locator('[data-act=deleteSession][data-id="'+target['id']+'"]')
        self.confirm=False;button.click();self.assertEqual(self.state(),before)
        self.confirm=True;button.click();expect(self.page.get_by_text('Trening usunięty',exact=True)).to_be_visible(timeout=30000)
        after=self.state();self.assertEqual(after['sessions'],before['sessions'][:-1]);self.assertEqual(after['entries'],[e for e in before['entries'] if e['sessionId']!=target['id']]);self.assertFalse(any(s['id']==snap['id'] for s in after['trainingJournal']['sessionSnapshots']))
        self.assertEqual(after['trainingJournal']['activePlanVersionId'],before['trainingJournal']['activePlanVersionId'])
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),after)
        catalog=self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.catalog}finally{d.close()}}")
        self.assertNotIn(target['id'],catalog['sessionVersions'])
        self.assertEqual(after['trainingJournal']['nextUnitId'],'PUSH A')
        archives=self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return await d.backups()}finally{d.close()}}")
        new_ids=[x for x in archives if x not in old_backups];self.assertEqual(len(new_ids),1)
        recovered=self.page.evaluate("async id=>{const d=await PushPullDB.open(()=>{});try{const raw=await d.readBackup(id);if(!(raw instanceof Blob))return (await PushPullDB.parseModelBackup(raw)).data;const r=await(await import('./model/canonical-json-transport.mjs')).readCanonicalJSON(await(await import('./model/compact-backup-reader.mjs')).openCompactBackup(raw));return (await(await import('./model/reference-preimage.mjs')).validateRescueBundle(r.bundle)).data}finally{d.close()}}",new_ids[0]);self.assertEqual(recovered,before)
        self.assertFalse(self.alerts,self.alerts)

    def test_abort_and_delete_older_session_preserves_rotation(self):
        self.activate()
        for kind,eid in [('PULL A','PULL-A-1'),('PUSH B','PUSH-B-1')]:
            form=self.open_result(kind,eid);self.fill_rows(form);self.save_form(form)
            self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        before=self.state();target=before['sessions'][-2];latest=before['sessions'][-1]
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="'+target['date']+'"]').click()
        button=self.page.locator('[data-act=deleteSession][data-id="'+target['id']+'"]')
        self.page.evaluate("()=>{const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v,...a){if(this.name==='journalState'&&v.id==='active')this.transaction.abort();return put.call(this,v,...a)}}")
        with self.page.expect_event('dialog'):button.click()
        self.assertEqual(self.state(),before)
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="'+target['date']+'"]').click()
        self.page.locator('[data-act=deleteSession][data-id="'+target['id']+'"]').click();expect(self.page.get_by_text('Trening usunięty',exact=True)).to_be_visible(timeout=30000)
        after=self.state();self.assertIn(latest,after['sessions']);self.assertEqual(after['trainingJournal']['nextUnitId'],before['trainingJournal']['nextUnitId'])
        self.assertEqual([e for e in after['entries'] if e['sessionId']==latest['id']],[e for e in before['entries'] if e['sessionId']==latest['id']])
