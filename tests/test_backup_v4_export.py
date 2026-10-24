"""Real-browser B1 exports from detached synthetic sources, never production UI."""
import json
import os
import shutil
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy

SETUP="""async()=>{
 window.b1=await import('/model/backup-v4-export.mjs');window.reader=await import('/model/backup-v4.mjs');
 window.f=await import('/tests/fixtures/backup-v4-fixture.mjs');
 const old=await (await fetch('/tests/fixtures/v1.json')).json(),p=await (await fetch('/tests/fixtures/plan-v3.json')).json();
 const data=f.nativeData(old,p),oldSource={format:'pushpull-backup',version:2,data:old,catalog:PushPullDB.parseBackup(old).catalog,archives:[]};
 window.b1Source={format:'pushpull-backup',version:2,data,catalog:PushPullDB.parseBackup(data).catalog,
 archives:f.archiveFixtures(JSON.stringify(old),JSON.stringify(oldSource),await f.sourceV3(oldSource))};
}"""


class BackupV4Export(BrowserHarness):
    records=legacy.IndexedDBMigration.records

    def setUp(self):
        super().setUp();expect(self.page.locator('[data-act=start]')).to_be_visible()

    def test_native_export_offline_full_roundtrip_and_repeated_exports_keep_actual_database_unchanged(self):
        before=self.records();self.page.evaluate(SETUP);self.context.set_offline(True)
        result=self.page.evaluate("""async()=>{
         const {canonical}=await import('/model/backup-json.mjs'),before=canonical(b1Source);
         const first=await b1.exportBackupV4(b1Source,{createdAt:f.AT,metadata:{synthetic:true}}),s=await reader.decodeBackup(first.text);
         const second=await b1.exportBackupV4(first.text,{createdAt:f.AT}),third=await b1.exportBackupV4(first.text,{createdAt:f.AT});
         window.b1Text=first.text;
         return {data:canonical(s.live.data)===canonical(b1Source.data),catalog:canonical(s.live.catalog)===canonical(b1Source.catalog),
          archives:canonical(s.archives)===canonical(b1Source.archives),unchanged:before===canonical(b1Source),
          repeat:first.text===second.text&&second.text===third.text,diagnostics:first.diagnostics};
        }""")
        for key in ['data','catalog','archives','unchanged','repeat']:self.assertTrue(result[key],key)
        self.assertEqual(self.records(),before)
        # One downloadable file in the synthetic harness, not a production button.
        with self.page.expect_download() as saved:
            self.page.evaluate("""()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([b1Text],{type:'application/json'}));a.download='synthetic-v4.json';a.click();URL.revokeObjectURL(a.href)}""")
        self.assertEqual(saved.value.suggested_filename,'synthetic-v4.json')
        self.assertEqual(Path(saved.value.path()).read_text(),self.page.evaluate('b1Text'))

    def test_cancel_limits_and_compression_error_keep_previous_backup_and_database(self):
        before=self.records();self.page.evaluate(SETUP)
        result=self.page.evaluate("""async()=>{
         const valid=await b1.exportBackupV4(b1Source,{createdAt:f.AT}),original=valid.text,out=[];
         for(const limits of [{fileBytes:20},{storedBlobBytes:20}]){try{await b1.exportBackupV4(b1Source,{createdAt:f.AT,limits});out.push(false)}catch{out.push(true)}}
         const c=new AbortController(),pending=b1.exportBackupV4(b1Source,{createdAt:f.AT,signal:c.signal});queueMicrotask(()=>c.abort());
         try{await pending;out.push(false)}catch(e){out.push(e.name==='AbortError')}
         const cs=globalThis.CompressionStream;
         try{globalThis.CompressionStream=class{constructor(){throw Error('synthetic compression error')}};try{await b1.exportBackupV4(b1Source,{createdAt:f.AT});out.push(false)}catch{out.push(true)}}finally{globalThis.CompressionStream=cs}
         return {out,previous:valid.text===original,stillReadable:(await reader.decodeBackup(original)).archives.length===b1Source.archives.length};
        }""")
        self.assertTrue(all(result['out']));self.assertTrue(result['previous']);self.assertTrue(result['stillReadable']);self.assertEqual(self.records(),before)

    def test_large_export_and_self_validation_offline_under_128_mib_old_space(self):
        browser=self.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),args=['--no-sandbox','--enable-precise-memory-info','--js-flags=--max-old-space-size=128'])
        try:
            context=browser.new_context(service_workers='block');page=context.new_page();page.goto(self.url)
            expect(page.locator('[data-act=start]')).to_be_visible()
            page.evaluate("""async()=>{window.exporter=await import('/model/backup-v4-export.mjs');window.r=await import('/model/backup-v4.mjs');
             const old=await (await fetch('/tests/fixtures/v1.json')).json();window.source={format:'pushpull-backup',version:2,data:old,catalog:PushPullDB.parseBackup(old).catalog,
              archives:[{id:'large-synthetic',kind:'opaque',createdAt:'2026-10-24T12:00:00.000Z',raw:'\\"Ł😀'.repeat(1024*1024)}]};}""")
            context.set_offline(True)
            metrics=page.evaluate("""async()=>{const start=performance.now(),out=await exporter.exportBackupV4(source,{createdAt:'2026-10-24T12:00:00.000Z'}),ms=Math.round(performance.now()-start),heap=performance.memory.usedJSHeapSize;
             const stage=await r.decodeBackup(out.text);return {ms,heap,exact:stage.archives[0].raw===source.archives[0].raw,sourceUnchanged:source.archives[0].raw==='\\"Ł😀'.repeat(1024*1024),...out.diagnostics}}""")
            self.assertTrue(metrics['exact']);self.assertTrue(metrics['sourceUnchanged']);self.assertEqual(metrics['archiveRecords'],1)
            print('ISSUE58_SYNTHETIC '+json.dumps({**metrics,'oldSpaceMiB':128}),flush=True)
        finally:browser.close()
