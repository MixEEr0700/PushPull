"""Synthetic limits only; no production storage modifications."""
from test_browser import BrowserHarness

class V4LimitDiagnosis(BrowserHarness):
    def test_actual_limit_and_reduced_memory_preflight(self):
        for constrained in [False,True]:
            browser=self.browser
            if constrained:
                browser=self.pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--js-flags=--max-old-space-size=128'])
            context=browser.new_context(viewport={'width':390,'height':844})
            try:
                page=context.new_page();page.goto(self.url)
                page.evaluate("""async()=>{window.probe=await import('./tests/v4-limit-probe.mjs');const data=await(await fetch('./tests/fixtures/v1.json')).json();window.synthetic={format:'pushpull-backup',version:2,data,catalog:PushPullDB.parseBackup(data).catalog,archives:[]}}""")
                context.set_offline(True)
                result=page.evaluate("""async small=>probe.probe(synthetic,small?1024*1024:64*1024*1024,small?{decodedBlobBytes:1024*1024}:{})""",constrained)
                self.assertEqual([x['stage'] for x in result],['live','archive','nested-archive'])
                print({'oldSpaceMiB':128 if constrained else None,'results':result},flush=True)
            finally:
                context.close()
                if constrained:browser.close()
