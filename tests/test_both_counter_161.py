from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_v2_training as training

class BothCounter161(BrowserHarness):
    prepare=training.V2Training.prepare
    ready=training.V2Training.ready
    activate=training.V2Training.activate
    open_result=training.V2Training.open_result
    fill_rows=training.V2Training.fill_rows
    save_form=training.V2Training.save_form
    def test_legacy_null_descriptor_is_recomputed_read_only_on_restart(self):
        source=Path('model/journal-runtime-index.mjs').read_text().replace('measurement:comparison(data,entry,{legacyIndex:true})','measurement:null')
        self.page.route('**/model/journal-runtime-index.mjs',lambda route:route.fulfill(body=source,content_type='text/javascript'))
        self.activate();f=self.open_result('PULL A','PULL-A-1');self.fill_rows(f,'45','13');self.save_form(f)
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        before=self.state();self.page.unroute('**/model/journal-runtime-index.mjs')
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-type="PULL A"]').click()
        card=self.page.locator('.exercise-card').filter(has=self.page.locator('[data-expand="PULL-A-1"]'))
        expect(card.locator('[data-result-change]')).to_contain_text('1 sesję temu');self.assertEqual(self.state(),before)
