"""The benchmark must timestamp native complete before Promise publication work."""
import sys
from playwright.sync_api import expect
from test_browser import BrowserHarness,ROOT
sys.path.insert(0,str(ROOT/'scripts'))
from measure_durable_write import instrument
from measure_ui_response import UI_PROBE


class DurableTiming(BrowserHarness):
    def test_native_complete_clock_excludes_work_resumed_before_later_listeners(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.evaluate(UI_PROBE)
        code=instrument('indexeddb.js',(ROOT/'indexeddb.js').read_text(),False)
        target='      if(importing){'
        self.assertEqual(code.count(target),1)
        code=code.replace(target,"      const until=performance.now()+60;while(performance.now()<until){};\n"+target)
        result=self.page.evaluate('async()=>{'+code+"""
          const db=await PushPullDB.open(()=>{throw Error('missing fixture')});
          try{
            window.__writeMarks=[];__ui.begin();await db.commit(db.value);
            await new Promise(resolve=>setTimeout(resolve,0));
            const marker=__writeMarks.find(m=>m.name==='strict-complete');
            const late=__ui.commits.filter(c=>c.at>=__ui.sample.start).at(-1);
            return {native:marker.at-__ui.sample.start,event:marker.eventTimeStamp-__ui.sample.start,
              later:late.at-__ui.sample.start,durability:marker.durability};
          }finally{db.close()}
        }""")
        self.assertEqual(result['durability'],'strict')
        self.assertGreater(result['native'],0)
        self.assertLessEqual(result['event'],result['native'])
        self.assertGreaterEqual(result['later']-result['native'],55,result)
