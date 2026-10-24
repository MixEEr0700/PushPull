"""Isolated v5 reader/writer, offline, synthetic data and bounded renderer."""
from test_browser import BrowserHarness
import shutil

class BackupV5(BrowserHarness):
    def test_chunks_offline_under_128_mib_old_space(self):
        browser=self.pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--js-flags=--max-old-space-size=128'])
        context=browser.new_context(viewport={'width':390,'height':844})
        try:
            page=context.new_page();page.goto(self.url)
            page.evaluate("""async()=>{window.v5=await import('./model/backup-v5.mjs');const data=await(await fetch('./tests/fixtures/v1.json')).json();window.s={format:'pushpull-backup',version:2,data,catalog:PushPullDB.parseBackup(data).catalog,archives:[{id:'synthetic',kind:'opaque',createdAt:'2026-10-24T00:00:00.000Z',raw:'x'.repeat(4*1024*1024)+'\\ud800'}]}}""")
            context.set_offline(True)
            result=page.evaluate("""async()=>{const options={createdAt:'2026-10-24T00:00:00.000Z'},out=await v5.exportBackupV5(s,options),stage=await v5.decodeBackup(out.text);let incomplete=false;try{await v5.decodeBackup(out.text.slice(0,-8))}catch{incomplete=true}return {exact:stage.archives[0].raw===s.archives[0].raw,incomplete,...out.diagnostics}}""")
            self.assertTrue(result['exact']);self.assertTrue(result['incomplete']);self.assertGreater(result['fragments'],1)
            print(result,flush=True)
        finally:context.close();browser.close()
