"""Independent check of the exact clock used by the v2 performance report."""
import sys
from test_browser import BrowserHarness,ROOT
from playwright.sync_api import expect
sys.path.insert(0,str(ROOT/'scripts'))
from measure_incremental_write import instrument_v2,instrument_runtime
from measure_ui_response import UI_PROBE

class IncrementalClock(BrowserHarness):
    def test_native_clock_precedes_slow_publication_and_later_completion_listener(self):
        code=instrument_v2((ROOT/'model/journal-idb.mjs').read_text())
        self.page.route('**/model/journal-idb.mjs',lambda route:route.fulfill(body=code,content_type='text/javascript'))
        runtime=instrument_runtime((ROOT/'model/journal-runtime.mjs').read_text())
        self.page.route('**/model/journal-runtime.mjs',lambda route:route.fulfill(body=runtime,content_type='text/javascript'))
        self.page.reload();self.start();self.result('31','8')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.evaluate(UI_PROBE)
        self.page.evaluate("window.__slowPublish=true;window.__writeMarks=[];__ui.begin();document.querySelector('.seriesResultForm [type=submit]').click()")
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        result=self.page.evaluate("""()=>{const mark=__writeMarks.find(m=>m.name==='strict-complete'),late=__ui.commits.at(-1);return {native:mark.at-__ui.sample.start,event:mark.eventTimeStamp-__ui.sample.start,late:late.at-__ui.sample.start,durability:mark.durability}}""")
        self.assertEqual(result['durability'],'strict');self.assertGreater(result['native'],0)
        self.assertLessEqual(result['event'],result['native']);self.assertGreaterEqual(result['late']-result['native'],55,result)
