"""Synthetic bounded reproduction; production limits and data are untouched."""
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_v2_training as training
import test_indexeddb as native

class DeleteSize164(BrowserHarness):
    prepare=training.V2Training.prepare
    ready=training.V2Training.ready
    activate=training.V2Training.activate
    def test_preimage_object_limit_refuses_before_any_persistent_write(self):
        source=Path('model/journal-protocol.mjs').read_text().replace('objectBytes:128*1024*1024','objectBytes:1024*1024')
        self.page.route('**/model/journal-protocol.mjs',lambda r:r.fulfill(body=source,content_type='text/javascript'))
        self.activate()
        self.page.evaluate('''async()=>{const d=await PushPullDB.open(()=>{});try{await d.ensureFull();await d.commit(d.value,{importedArchives:[{id:'synthetic-164',kind:'before-import',createdAt:'2026-11-06T00:00:00.000Z',raw:'"\\\\'.repeat(131072)}]})}finally{d.close()}}''')
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        before=native.IndexedDBMigration.records(self);data=self.state();target=data['sessions'][-1]
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="'+target['date']+'"]').click()
        with self.page.expect_event('dialog',predicate=lambda d:d.type=='alert'):
            self.page.locator('[data-act=deleteSession][data-id="'+target['id']+'"]').click()
        self.assertIn('protocol JSON size',self.alerts[-1]);self.assertEqual(native.IndexedDBMigration.records(self),before)
        self.assertEqual(self.state(),data)
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),data)
