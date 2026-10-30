from test_browser import BrowserHarness
import shutil

class CompactWriter(BrowserHarness):
    def test_full_synthetic_roundtrip_offline_under_memory_cap(self):
        browser=self.pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--js-flags=--max-old-space-size=64'])
        context=browser.new_context(viewport={'width':390,'height':844})
        try:
            page=context.new_page();page.goto(self.url)
            page.evaluate("async()=>{window.codec=await import('./model/compact-backup-writer.mjs');window.transport=await import('./model/compact-backup-reader.mjs');window.fixture=await(await fetch('./tests/fixtures/v1.json')).json()}")
            context.set_offline(True)
            result=page.evaluate("""async()=>{
             const model={history:fixture,sessions:[{id:'s',results:[{side:'L',reps:10,kg:20},{side:'R',reps:9,kg:20}]}],plans:{active:'p',versions:[{id:'p'}]},snapshots:[{id:'p',notes:'original'}],settings:{custom:'\\ud800\\0😀é',draft:{kg:'12,'}},archives:[{raw:'x'.repeat(4*1024*1024),metadata:{keep:true}},{raw:null},{raw:''}]};
             const before=JSON.stringify(model),at=performance.now(),file=await codec.writeCompactModel(model),written=performance.now();
             const reader=await transport.openCompactBackup(file);let graph=0;for await(const b of reader.readObject('graph'))graph+=b.length;
             const out=await codec.readCompactModel(file);let corrupt=false;try{await codec.readCompactModel(file.slice(0,-1))}catch{corrupt=true}
             return {equal:JSON.stringify(out)===before,unchanged:JSON.stringify(model)===before,corrupt,graph,ppcBytes:file.size,jsonBytes:new Blob([before]).size,writeMs:written-at};
            }""")
            self.assertTrue(result['equal']);self.assertTrue(result['unchanged']);self.assertTrue(result['corrupt']);self.assertGreater(result['graph'],0);print(result,flush=True)
        finally:context.close();browser.close()
