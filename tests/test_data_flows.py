"""Two inline backup flows; native IndexedDB and gated file/worker/HTTP reads."""
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy
import test_drive_sync as cloud
import test_fast_start as fast

class DataFlows(BrowserHarness):
    records = legacy.IndexedDBMigration.records

    def test_b3_file_read_does_not_hold_navigation_or_publish_after_leaving(self):
        legacy.IndexedDBMigration.prepare(self)
        self.page.locator('[data-tab=settings]').click()
        # New flow opener is absent in the historical implementation used for RED.
        opener=self.page.locator('[data-backup-flow=restore]')
        if opener.count():opener.click()
        raw=self.page.request.get(self.url+'tests/fixtures/v1.json').text()
        before=self.records()
        self.page.evaluate("""()=>{const original=File.prototype.text;File.prototype.text=function(){window.__fileReading=true;return new Promise((resolve,reject)=>{window.__releaseFile=()=>original.call(this).then(resolve,reject)})}}""")
        self.page.locator('#importFile').set_input_files({'name':'test.json','mimeType':'application/json','buffer':raw.encode()})
        self.page.wait_for_function('window.__fileReading===true')
        self.page.locator('[data-tab=training]').click()
        try:
            expect(self.page.locator('[data-act=finish]')).to_be_visible(timeout=1500)
        finally:
            self.page.evaluate('__releaseFile()')
        self.page.locator('[data-tab=settings]').click()
        expect(self.page.locator('[data-restore-preview]')).to_have_count(0)
        self.assertEqual(self.records(),before)

    def test_two_inline_flows_mobile_preview_focus_confirmation_and_offline_restart(self):
        legacy.IndexedDBMigration.prepare(self)
        self.page.locator('[data-tab=settings]').click()
        before=self.records();state=self.state()
        self.context.set_offline(True)
        for width in (360,390,412):
            self.page.set_viewport_size({'width':width,'height':844})
            primary=self.page.locator('[data-primary-backups]')
            self.assertEqual(primary.locator(':scope > button').all_text_contents(),['Zapisz kopię','Przywróć kopię'])
            self.backup_flow('save')
            expect(self.page.locator('[data-backup-body=restore]')).to_be_hidden()
            expect(self.page.locator('[data-backup-body=save]')).not_to_contain_text('Anulowano podgląd')
            with self.page.expect_download() as item:self.page.locator('[data-act=export]').click()
            from pathlib import Path
            raw=Path(item.value.path()).read_bytes()
            expect(self.page.locator('[data-backup-body=save] [data-backup-save-status]')).to_contain_text('Zlecono pobranie')
            self.backup_flow('restore')
            expect(self.page.locator('[data-backup-body=save]')).to_be_hidden()
            self.page.locator('#importFile').set_input_files({'name':'copy.json','mimeType':'application/json','buffer':raw})
            preview=self.page.locator('[data-backup-body=restore] [data-restore-preview]')
            expect(preview).to_be_visible()
            expect(preview).to_be_focused()
            expect(preview).to_be_in_viewport()
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.assertEqual(self.records(),before)
            # Explicit refusal never writes or deletes the candidate.
            self.confirm=False
            self.page.locator('[data-restore-confirm]').click()
            expect(self.page.locator('[data-restore-busy]')).to_have_count(0)
            self.assertEqual(self.records(),before)
            self.confirm=True
            self.page.locator('[data-restore-cancel]').click()
            for button in primary.locator(':scope > button').all():self.assertGreaterEqual(button.bounding_box()['height'],44)
        self.context.set_offline(False)  # Harness blocks SW; the full PWA suite covers offline reload.
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual(self.state(),state)
        self.assertFalse(self.alerts,self.alerts)

    def test_cancel_preview_worker_and_new_file_ignore_late_messages(self):
        legacy.IndexedDBMigration.prepare(self);self.page.locator('[data-tab=settings]').click()
        raw=self.page.request.get(self.url+'tests/fixtures/v1.json').body()
        before=self.records()
        self.page.evaluate("""()=>{const Native=Worker;window.__previews=[];window.Worker=class extends Native{
         constructor(url,options){super(url,options);if(String(url).endsWith('/legacy-model.mjs')){const send=this.postMessage.bind(this);this.postMessage=value=>{__previews.push({worker:this,value,send})};const stop=this.terminate.bind(this);this.terminate=()=>{this.stopped=true;stop()}}}
        }}""")
        self.backup_flow('restore')
        self.page.locator('#importFile').set_input_files({'name':'one.json','mimeType':'application/json','buffer':raw})
        self.page.wait_for_function('__previews.length===1')
        expect(self.page.locator('[data-restore-busy]')).to_be_visible()
        self.page.locator('[data-restore-cancel]').click()
        self.assertTrue(self.page.evaluate('__previews[0].worker.stopped'))
        self.page.locator('#importFile').set_input_files({'name':'two.json','mimeType':'application/json','buffer':raw})
        self.page.wait_for_function('__previews.length===2')
        self.page.evaluate("""async()=>{const m=await import('./model/legacy-model.mjs'),old=__previews[0];old.worker.onmessage({data:{preview:await m.inspectFullBackup(old.value.raw,old.value.current)}});__previews[1].send(__previews[1].value)}""")
        expect(self.page.locator('[data-restore-preview]')).to_be_visible()
        self.assertEqual(self.records(),before)
        self.assertFalse(self.alerts,self.alerts)

    def test_file_error_and_revision_change_are_inline_and_never_write(self):
        legacy.IndexedDBMigration.prepare(self);self.page.locator('[data-tab=settings]').click()
        self.backup_flow('restore');before=self.records()
        self.page.locator('#importFile').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{broken'})
        expect(self.page.locator('[data-backup-body=restore] [data-restore-error]')).to_be_visible()
        expect(self.page.locator('[data-restore-preview]')).to_have_count(0)
        self.assertEqual(self.records(),before)
        raw=self.page.request.get(self.url+'tests/fixtures/v1.json').body()
        self.page.evaluate("""()=>{const original=File.prototype.text;File.prototype.text=function(){return new Promise(r=>window.__releaseFile=()=>original.call(this).then(r))}}""")
        self.page.locator('#importFile').set_input_files({'name':'old.json','mimeType':'application/json','buffer':raw})
        self.page.wait_for_function('!!window.__releaseFile')
        self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const value=d.value;value.exercises['PUSH A'][0].notes='newer isolated data';await d.commit(value)}finally{d.close()}}""")
        changed=self.records();self.page.evaluate('__releaseFile()')
        expect(self.page.locator('[data-restore-error]')).to_be_visible()
        expect(self.page.locator('[data-restore-preview]')).to_have_count(0)
        self.assertEqual(self.records(),changed)

    def test_drive_restores_directly_without_phone_download_after_explicit_confirmation(self):
        import json
        from test_browser import confirm_restore
        import test_simple_data as simple
        mock=simple.SimpleData.seed_cloud(self)
        before=self.state();downloads=[];self.page.on('download',lambda d:downloads.append(d))
        raw=json.loads(mock.files['file-0']['text'])['backup']
        expected=self.page.evaluate('raw=>PushPullDB.parseBackup(JSON.parse(raw)).data',raw)
        self.backup_flow('restore')
        self.page.locator('[data-drive-action=restore]').click()
        expect(self.page.locator('#driveCopy option')).to_have_count(2)
        self.page.locator('#driveCopy').select_option('file-0')
        self.page.locator('[data-drive-action=preview]').click()
        preview=self.page.locator('[data-backup-body=restore] [data-restore-preview]')
        expect(preview).to_be_focused(timeout=60000)
        self.assertEqual(self.state(),before);self.assertFalse(downloads)
        self.confirm=False;confirm_restore(self.page);self.assertEqual(self.state(),before)
        self.confirm=True
        self.page.locator('[data-restore-confirm]').evaluate('(b)=>{b.click();b.click()}')
        expect(self.page.locator('[data-backup-body=restore] [data-restore-success]')).to_be_visible(timeout=60000)
        self.assertEqual(self.state(),expected);self.assertFalse(downloads);self.assertEqual(mock.posts,0)
        has_preimage=self.page.evaluate("""async before=>{const d=await PushPullDB.open(()=>{});try{
         const {canonical}=await import('./model/backup-json.mjs');
         for(const key of d.backups())try{const raw=await d.readBackup(key),v=JSON.parse(raw),parsed=v.version===3?await PushPullDB.parseModelBackup(raw):PushPullDB.parseBackup(v);if(canonical(parsed.data)===canonical(before))return true}catch{}
         return false;
        }finally{d.close()}}""",before)
        self.assertTrue(has_preimage)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual(self.state(),expected);self.assertFalse(self.alerts,self.alerts)

    configure = cloud.ManualDriveFlow.configure
    prepare = fast.FastStart.prepare

    def test_file_read_errors_are_inline_and_cancelled_failure_stays_hidden(self):
        legacy.IndexedDBMigration.prepare(self);self.page.locator('[data-tab=settings]').click()
        self.backup_flow('restore');before=self.records()
        self.page.evaluate("""()=>{File.prototype.text=function(){return new Promise((r,reject)=>window.__failFile=()=>reject(Error('synthetic file read failure')))}}""")
        payload={'name':'read-error.json','mimeType':'application/json','buffer':b'{}'}
        self.page.locator('#importFile').set_input_files(payload)
        self.page.wait_for_function('!!window.__failFile')
        self.page.locator('[data-restore-cancel]').click();self.page.evaluate('__failFile()')
        expect(self.page.locator('[data-restore-preview],[data-restore-error]')).to_have_count(0)
        self.page.evaluate("()=>{File.prototype.text=()=>Promise.reject(Error('synthetic file read failure'))}")
        self.page.locator('#importFile').set_input_files(payload)
        expect(self.page.locator('[data-backup-body=restore] [data-restore-error]')).to_have_text('synthetic file read failure')
        self.assertEqual(self.records(),before);self.assertFalse(self.alerts,self.alerts)

    def test_same_turn_file_choice_and_navigation_reserve_then_cancel_before_queue(self):
        legacy.IndexedDBMigration.prepare(self);self.page.locator('[data-tab=settings]').click()
        self.backup_flow('restore');before=self.records()
        raw=self.page.request.get(self.url+'tests/fixtures/v1.json').text()
        reserved=self.page.evaluate("""raw=>{const original=Blob.prototype.arrayBuffer;window.__fileReading=false;window.__previewWorkers=0;const Native=Worker;
         window.Worker=class extends Native{constructor(url,options){super(url,options);if(String(url).endsWith('/legacy-model.mjs'))__previewWorkers++}};
         Blob.prototype.arrayBuffer=function(){__fileReading=true;return new Promise(r=>window.__releaseFile=async()=>{r(await original.call(this));window.__fileReturned=true})};
         const transfer=new DataTransfer();transfer.items.add(new File([raw],'same-turn.json',{type:'application/json'}));const input=document.querySelector('#importFile');input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));
         const reserved=__fileReading&&!!document.querySelector('[data-restore-busy]');document.querySelector('[data-tab=training]').click();return reserved;
        }""",raw)
        try:self.assertTrue(reserved,'File preview must reserve its generation before queued navigation')
        finally:
            self.page.wait_for_function('!!window.__releaseFile');self.page.evaluate('__releaseFile()')
        expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.page.wait_for_function('window.__fileReturned===true')
        self.page.locator('[data-tab=settings]').click()
        expect(self.page.locator('[data-restore-preview],[data-restore-error]')).to_have_count(0)
        self.assertEqual(self.page.evaluate('__previewWorkers'),0)
        self.assertEqual(self.records(),before)

    def test_cancel_drive_preview_ignores_late_http_error_and_keeps_inline_cancelled_state(self):
        import test_simple_data as simple
        mock=simple.SimpleData.seed_cloud(self);before=self.records();downloads=[];held=[]
        self.page.on('download',lambda item:downloads.append(item));self.backup_flow('restore')
        self.page.locator('[data-drive-action=restore]').click()
        expect(self.page.locator('#driveCopy option')).to_have_count(2)
        pattern='https://www.googleapis.com/drive/v3/files/*?alt=media'
        def hold(route):
            held.append(route);self.page.evaluate('window.__heldPreview=true')
        self.context.route(pattern,hold)
        with self.page.expect_request(pattern):self.page.locator('[data-drive-action=preview]').click()
        self.page.wait_for_function('window.__heldPreview===true')
        self.assertEqual(len(held),1)
        self.page.locator('[data-restore-cancel]').click()
        self.context.unroute(pattern)
        held.pop().fulfill(status=500,headers={'Access-Control-Allow-Origin':'*'},content_type='application/json',body='{"error":"synthetic late error"}')
        expect(self.page.locator('[data-drive-action=restore]')).to_be_enabled()
        expect(self.page.locator('[data-backup-body=restore] [data-drive-status]')).to_contain_text('Anulowano podgląd')
        expect(self.page.locator('[data-restore-preview],[data-restore-error]')).to_have_count(0)
        self.assertEqual(self.records(),before);self.assertFalse(downloads);self.assertEqual(mock.posts,0)
        self.assertFalse(self.alerts,self.alerts)
