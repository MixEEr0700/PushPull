from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_plan_import as fixtures
import test_v2_training as training

class DeletePlan154(BrowserHarness):
    prepare=fixtures.PlanImport.prepare
    ready=fixtures.PlanImport.ready
    settings=fixtures.PlanImport.settings
    preview=fixtures.PlanImport.preview
    store=fixtures.PlanImport.store
    activate=fixtures.PlanImport.activate
    def setup_active(self):
        self.prepare();self.ready();self.preview();self.store();self.activate()
        self.settings();self.page.locator('[data-view=plans]').click()
    def test_cancel_delete_v2_backup_restart(self):
        self.setup_active();before=self.state()
        current=self.page.locator('[data-plan-row="synthetic-v3"]')
        expect(current.locator('[data-plan-delete]')).to_have_count(0)
        row=self.page.locator('[data-plan-row="v2-owner-2026-10-22"]')
        expect(row.locator('[data-select-plan] + [data-plan-delete]')).to_have_count(1)
        backups=self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.backups()}finally{d.close()}}")
        self.confirm=False;row.locator('[data-plan-delete]').click();self.assertEqual(self.state(),before)
        self.confirm=True;row.locator('[data-plan-delete]').click();expect(self.page.get_by_text('Plan usunięty',exact=True)).to_be_visible(timeout=30000)
        after=self.state();self.assertEqual(after['sessions'],before['sessions']);self.assertEqual(after['entries'],before['entries']);self.assertEqual(after['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertTrue(after['trainingJournal']['hiddenBuiltinV2']);expect(row).to_have_count(0)
        ids=self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.backups()}finally{d.close()}}")
        added=[x for x in ids if x not in backups];self.assertEqual(len(added),1)
        old=self.page.evaluate("async id=>{const d=await PushPullDB.open(()=>{});try{const raw=await d.readBackup(id);if(!(raw instanceof Blob))return (await PushPullDB.parseModelBackup(raw)).data;const r=await(await import('./model/canonical-json-transport.mjs')).readCanonicalJSON(await(await import('./model/compact-backup-reader.mjs')).openCompactBackup(raw));return (await(await import('./model/reference-preimage.mjs')).validateRescueBundle(r.bundle)).data}finally{d.close()}}",added[0]);self.assertEqual(old,before)
        self.page.reload();self.settings();self.page.locator('[data-view=plans]').click();expect(row).to_have_count(0);self.assertEqual(self.state(),after)
        self.settings();self.backup_flow('save')
        with self.page.expect_download(timeout=60000) as dl:self.page.locator('[data-canonical-export]').click()
        raw=Path(dl.value.path()).read_bytes()
        ctx=self.new_context(service_workers='allow');p=ctx.new_page();p.on('dialog',self.dialog);p.goto(self.url);p.wait_for_selector('[data-act=start]')
        p.locator('[data-tab=settings]').click();p.locator('[data-backup-flow=restore]').click()
        p.locator('#importFile').set_input_files({'name':'test.ppc1','mimeType':'application/octet-stream','buffer':raw})
        expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000)
        p.locator('[data-restore-confirm]').click();expect(p.locator('[data-restore-success]')).to_be_visible(timeout=60000)
        p.reload();p.locator('[data-tab=settings]').click();p.locator('[data-view=plans]').click()
        expect(p.locator('[data-plan-row="v2-owner-2026-10-22"]')).to_have_count(0)
    def test_history_blocks_removal(self):
        training.V2Training.activate(self)
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click();self.page.locator('[data-act=finish]').click()
        self.preview();self.store();self.activate();self.settings();self.page.locator('[data-view=plans]').click()
        before=self.state();row=self.page.locator('[data-plan-row="v2-owner-2026-10-22"]')
        with self.page.expect_event('dialog'):row.locator('[data-plan-delete]').click()
        self.assertEqual(self.state(),before);expect(row).to_be_visible()
    def test_remove_stored_unused_v2_preserves_active_plan(self):
        training.V2Training.activate(self)
        self.preview();self.store();self.activate();self.settings();self.page.locator('[data-view=plans]').click()
        before=self.state();self.assertTrue(any(v['id']=='v2-owner-2026-10-22' for v in before['trainingJournal']['model']['planVersions']))
        self.page.locator('[data-plan-row="v2-owner-2026-10-22"] [data-plan-delete]').click()
        expect(self.page.get_by_text('Plan usunięty',exact=True)).to_be_visible(timeout=30000)
        after=self.state();self.assertEqual(after['sessions'],before['sessions']);self.assertEqual(after['entries'],before['entries']);self.assertEqual(after['trainingJournal']['activePlanVersionId'],'synthetic-v3')
        self.assertFalse(any(v['id']=='v2-owner-2026-10-22' for v in after['trainingJournal']['model']['planVersions']))
        self.page.reload();self.settings();self.page.locator('[data-view=plans]').click()
        expect(self.page.locator('[data-plan-row="v2-owner-2026-10-22"]')).to_have_count(0)
