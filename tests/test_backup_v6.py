"""Isolated codec with synthetic evidence; never a real multi-tab collector."""
from test_browser import BrowserHarness
import shutil

class BackupV6(BrowserHarness):
    def test_offline_codec_under_128_mib_old_space_preserves_quarantined_evidence(self):
        browser=self.pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--js-flags=--max-old-space-size=128'])
        context=browser.new_context(viewport={'width':390,'height':844})
        try:
            page=context.new_page();page.goto(self.url)
            page.evaluate("""async()=>{window.codec=await import('./model/backup-v6.mjs');const old=await(await fetch('./tests/fixtures/v1.json')).json();
             const snapshot={format:'pushpull-backup',version:2,data:old,catalog:PushPullDB.parseBackup(old).catalog,archives:[{id:'synthetic',kind:'opaque',createdAt:'2026-10-24T00:00:00.000Z',raw:'x'.repeat(4*1024*1024)}]};
             const at='2026-10-24T00:00:00.000Z';window.source={history:JSON.parse((await(await import('./model/backup-v5.mjs')).exportBackupV5(snapshot,{createdAt:at})).text),createdAt:at,
              capture:{version:1,historyRevision:1,startedAt:at,completedAt:at,scope:'observed-origin',consistency:'observed-stable'},
              evidence:{format:'pushpull-draft-evidence',version:1,sources:[{source:'local-buffer',storageKey:'pushpull_workout_draft_v1:synthetic',raw:'incomplete\\ud800\\0'+ 'x'.repeat(500000)}]}};
            }""")
            context.set_offline(True)
            result=page.evaluate("""async()=>{const out=await codec.exportBackupV6(source),stage=await codec.decodeBackup(out.text);let bad=false;try{await codec.decodeBackup(out.text.slice(0,-1))}catch{bad=true}return {exact:stage.draftEvidence.sources[0].raw===source.evidence.sources[0].raw,archive:stage.history.archives[0].raw.length,status:stage.classification[0].status,coverage:stage.draftCoverage,bad,diagnostics:out.diagnostics}}""")
            self.assertTrue(result['exact']);self.assertTrue(result['bad']);self.assertEqual(result['archive'],4*1024*1024)
            self.assertEqual(result['status'],'quarantine');self.assertEqual(result['coverage'],'observed-origin')
            print(result['diagnostics'],flush=True)
        finally:context.close();browser.close()
