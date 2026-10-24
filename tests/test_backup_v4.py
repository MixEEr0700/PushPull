"""Isolated staging only: no production v4 import, storage or Google changes."""
import json
import os
import shutil
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy


SETUP="""async()=>{
 window.v4=await import('/model/backup-v4.mjs');window.fixtures=await import('/tests/fixtures/backup-v4-fixture.mjs');
 const old=await (await fetch('/tests/fixtures/v1.json')).json(),packet=await (await fetch('/tests/fixtures/plan-v3.json')).json();
 const data=fixtures.nativeData(old,packet),source={format:'pushpull-backup',version:2,data,catalog:PushPullDB.parseBackup(data).catalog,archives:[]};
 const live=await fixtures.sourceV3(source),v1=JSON.stringify(old),v2=JSON.stringify({format:'pushpull-backup',version:2,data:old,catalog:PushPullDB.parseBackup(old).catalog,archives:[]});
 window.archives=fixtures.archiveFixtures(v1,v2,live);window.packet=await fixtures.encodeFixture(live,archives);
 window.text=JSON.stringify(window.packet);window.expected=data;
 return {bytes:new TextEncoder().encode(text).length,sessions:data.sessions.length,results:data.entries.length,snapshots:data.trainingJournal.sessionSnapshots.length};
}"""


class BackupV4(BrowserHarness):
    records=legacy.IndexedDBMigration.records

    def setUp(self):
        super().setUp()
        expect(self.page.locator('[data-act=start]')).to_be_visible()

    def test_complete_staging_roundtrip_offline_never_touches_current_database(self):
        before=self.records();stats=self.page.evaluate(SETUP)
        self.assertEqual(stats['snapshots'],6)
        self.context.set_offline(True)
        result=self.page.evaluate("""async()=>{
         const {canonical}=await import('/model/backup-json.mjs'),stage=await v4.decodeBackup(text);
         const again=await fixtures.encodeFixture(stage.live.raw,stage.archives);
         return {data:canonical(stage.live.data)===canonical(expected),archives:canonical(stage.archives)===canonical(archives),
          active:stage.live.data.trainingJournal.activePlanVersionId,roundtrip:JSON.stringify(again)===text,
          lone:stage.archives[8].raw.charCodeAt(4),frozen:Object.isFrozen(stage.live.data.trainingJournal)};
        }""")
        self.assertTrue(result['data']);self.assertTrue(result['archives']);self.assertTrue(result['roundtrip']);self.assertTrue(result['frozen'])
        self.assertEqual(result['active'],'synthetic-v3');self.assertEqual(result['lone'],0xd800)
        self.assertEqual(self.records(),before)

    def test_rejections_and_cancellation_leave_database_and_prior_stage_unchanged(self):
        before=self.records();self.page.evaluate(SETUP)
        result=self.page.evaluate("""async()=>{
         const original=await v4.decodeBackup(text),before=JSON.stringify(original),out=[];
         const bad=structuredClone(packet);bad.blobs.at(-1).storedSha256='0'.repeat(64);await fixtures.seal(bad);
         const bomb=await fixtures.blob('x'.repeat(2*1024*1024));bomb.decodedBytes=128;
         const b=await fixtures.encodeFixture(original.live.raw,[{id:'bomb',kind:'opaque',createdAt:fixtures.AT,raw:'unused'}]);
         b.blobs[1]=bomb;b.archives[0].blobId=bomb.id;await fixtures.seal(b);
         const c=new AbortController();c.abort();
         for(const [raw,options] of [[JSON.stringify(bad),{}],[text.slice(0,-1),{}],[JSON.stringify(b),{}],[text,{limits:{totalDecodedBytes:1}}],[text,{signal:c.signal}]]){
          try{await v4.decodeBackup(raw,options);out.push(false)}catch{out.push(true)}
         }
         return {out,unchanged:before===JSON.stringify(original)};
        }""")
        self.assertTrue(all(result['out']));self.assertTrue(result['unchanged']);self.assertEqual(self.records(),before)

    def test_current_app_cleanly_rejects_v4_without_restore_or_local_changes(self):
        before=self.records();self.page.evaluate(SETUP);text=self.page.evaluate('text')
        self.page.locator('[data-tab=settings]').click()
        self.page.locator('#importFile').set_input_files({'name':'synthetic-v4.json','mimeType':'application/json','buffer':text.encode()})
        expect(self.page.locator('[data-restore-error]')).to_contain_text('wersja')
        expect(self.page.locator('[data-restore-confirm]')).to_have_count(0)
        self.assertEqual(self.records(),before)

    def test_large_opaque_blob_under_128_mib_old_space_and_size_comparison(self):
        # Build outside the capped renderer; only a small compressed container is
        # transferred to it. The source and archive are exclusively synthetic.
        values=self.page.evaluate("""async()=>{
         const f=await import('/tests/fixtures/backup-v4-fixture.mjs'),old=await (await fetch('/tests/fixtures/v1.json')).json();
         const archive={id:'large',kind:'opaque',createdAt:f.AT,raw:'\\"Ł😀'.repeat(1024*1024)};
         const start=performance.now(),source={format:'pushpull-backup',version:2,data:old,catalog:PushPullDB.parseBackup(old).catalog,archives:[]};
         const live=await f.sourceV3(source),d=await f.encodeFixture(live,[archive]);
         const v3=await f.sourceV3({...source,archives:[archive]});
         const oldStart=performance.now(),oldStage=await (await import('/model/legacy-model.mjs')).parseModelBackup(v3);
         if(oldStage.archives[0].raw!==archive.raw)throw Error('old raw mismatch');
         const oldDecodeMs=Math.round(performance.now()-oldStart);
         const {canonical}=await import('/model/backup-json.mjs');
         const liveDigest=await f.hash(new TextEncoder().encode(canonical({data:oldStage.data,catalog:oldStage.catalog,model:oldStage.document.payload.model})));
         return {text:JSON.stringify(d),liveDigest,rawCodeUnits:archive.raw.length,oldV3Bytes:new TextEncoder().encode(v3).length,oldDecodeMs,
          v4Bytes:new TextEncoder().encode(JSON.stringify(d)).length,buildMs:Math.round(performance.now()-start)};
        }""")
        cdp=self.context.new_cdp_session(self.page)
        values['oldHeapAfterBuildAndRead']=cdp.send('Runtime.getHeapUsage')['usedSize'];cdp.detach()
        browser=self.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),args=['--no-sandbox','--enable-precise-memory-info','--js-flags=--max-old-space-size=128'])
        try:
            context=browser.new_context(service_workers='block');page=context.new_page();page.goto(self.url+'tests/')
            page.evaluate("async()=>{window.reader=await import('/model/backup-v4.mjs')}")
            context.set_offline(True)
            metrics=page.evaluate("""async text=>{const start=performance.now(),stage=await reader.decodeBackup(text),decodedMs=Math.round(performance.now()-start),heap=performance.memory.usedJSHeapSize;
             const {canonical}=await import('/model/backup-json.mjs');
             const liveDigest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical({data:stage.live.data,catalog:stage.live.catalog,model:stage.live.document.payload.model})))),b=>b.toString(16).padStart(2,'0')).join('');return {
             rawCodeUnits:stage.archives[0].raw.length,exact:stage.archives[0].raw==='\\"Ł😀'.repeat(1024*1024),
             decodedMs,heap,liveDigest}}""",values.pop('text'))
            self.assertTrue(metrics['exact']);self.assertEqual(metrics['rawCodeUnits'],values['rawCodeUnits'])
            self.assertEqual(metrics.pop('liveDigest'),values.pop('liveDigest'))
            self.assertLess(values['v4Bytes'],values['oldV3Bytes']//10)
            print('ISSUE56_SYNTHETIC '+json.dumps({**values,**metrics,'oldSpaceMiB':128}),flush=True)
        finally:browser.close()
