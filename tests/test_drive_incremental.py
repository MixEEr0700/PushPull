"""Production HTTP routes, OAuth and stores; Google service is simulated."""
import json,uuid
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_drive_sync as legacy_drive
import test_canonical_export_ui as canonical_ui

class IncrementalGoogle(legacy_drive.MockGoogle):
    def route(self,route):
        request=route.request;url=urlsplit(request.url)
        headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,POST,OPTIONS'}
        if request.method=='OPTIONS':return route.fulfill(headers=headers,body='{}')
        if self.error:return route.fulfill(status=self.error,headers=headers,body='{}')
        if url.path.endswith('/generateIds'):return route.fulfill(headers=headers,content_type='application/json',body=json.dumps({'ids':[str(uuid.uuid4())]}))
        if '/upload/' in url.path:
            self.posts+=1;boundary=request.headers['content-type'].split('boundary=')[1];parts=request.post_data.split('--'+boundary);meta=json.loads(parts[1].split('\r\n\r\n',1)[1].strip());text=parts[2].split('\r\n\r\n',1)[1].rstrip('\r\n');key=meta['id'];self.files[key]={'id':key,'appProperties':meta['appProperties'],'text':text,'createdTime':'2026-11-02T12:00:00Z'}
            return route.fulfill(headers=headers,content_type='application/json',body=json.dumps({'id':key}))
        if '/files/' in url.path and url.path.rsplit('/',1)[1] not in self.files:return route.fulfill(status=404,headers=headers,body='{}')
        return super().route(route)

class IncrementalDriveUI(BrowserHarness):
    def configure(self):legacy_drive.ManualDriveFlow.configure(self,automatic=True)
    decode=canonical_ui.CanonicalExportUI.decode
    def test_finish_full_delta_cloud_restore_restart_exact(self):
        google=IncrementalGoogle();google.install(self.context);self.page.wait_for_selector('[data-act=start]');self.configure()
        self.page.locator('[data-tab=training]').click();self.start();self.result('22','9');self.save();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-tab=settings]').click();self.backup_flow('save');expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000);self.assertEqual(google.posts,1)
        self.page.locator('[data-tab=training]').click();self.start();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-tab=settings]').click();self.backup_flow('save');expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000);self.assertEqual(google.posts,2)
        print('DRIVE_PPC1_BYTES',*[len(f['text'].encode()) for f in google.files.values()]);points=[json.loads(f['text']) for f in google.files.values()];self.assertEqual([p['generation'] for p in points],[0,1]);self.assertLess(len(json.dumps(points[1])),len(json.dumps(points[0])))
        with self.page.expect_download() as dl:self.page.locator('[data-canonical-export]').click()
        expected=self.decode(Path(dl.value.path()).read_bytes())
        ctx=self.new_context(service_workers='allow');google.install(ctx);p=ctx.new_page();p.on('dialog',self.dialog);p.goto(self.url);p.wait_for_selector('[data-act=start]');self.page=p;self.configure();self.backup_flow('restore');p.locator('[data-ppc1-list]').click();expect(p.locator('[data-ppc1-point]')).to_have_count(2);last=list(google.files)[-1];p.locator('[data-ppc1-point="'+last+'"]').click();expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000);p.locator('[data-restore-confirm]').click();expect(p.locator('[data-restore-success]')).to_be_visible(timeout=30000);p.reload();p.wait_for_selector('[data-act=start]');p.locator('[data-tab=settings]').click();self.backup_flow('save')
        with p.expect_download() as dl:p.locator('[data-canonical-export]').click()
        self.assertEqual(self.decode(Path(dl.value.path()).read_bytes()),expected)
        for width in (360,390,412):
            p.set_viewport_size({'width':width,'height':844});self.assertLessEqual(p.evaluate('document.documentElement.scrollWidth'),width)
    def test_auth_failure_keeps_finished_session_and_queue_then_restart_reconnect(self):
        google=IncrementalGoogle();google.install(self.context);self.page.wait_for_selector('[data-act=start]');self.configure();google.error=401
        self.page.locator('[data-tab=training]').click();self.start();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-tab=settings]').click();self.backup_flow('save');expect(self.page.locator('[data-drive-status]')).to_contain_text('Wymagane logowanie',timeout=30000)
        self.assertEqual(self.state()['sessions'][-1]['status'],'done');self.assertEqual(google.posts,0)
        self.assertTrue(self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{return !!(await h.readDriveState()).ppc1Queue}finally{h.close()}}"""))
        google.error=0;self.page.reload();self.page.wait_for_selector('[data-act=start]');self.page.locator('[data-tab=settings]').click();self.backup_flow('save');self.page.locator('[data-drive-action=connect]').click();expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000);self.assertEqual(google.posts,1)
    def test_offline_finish_and_offline_restart_keep_intent(self):
        from test_browser import wait_for_service_worker_controller
        self.context.close();self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog);self.page.on('pageerror',lambda e:self.errors.append(str(e)));google=IncrementalGoogle();google.install(self.context);self.page.goto(self.url);self.page.wait_for_selector('[data-act=start]');wait_for_service_worker_controller(self.page);self.configure();self.context.set_offline(True)
        self.page.locator('[data-tab=training]').click();self.start();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state()['sessions'][-1]['status'],'done');self.assertEqual(google.posts,0);self.page.reload();self.page.wait_for_selector('[data-act=start]');self.context.set_offline(False);self.page.locator('[data-tab=settings]').click();self.backup_flow('save');self.page.locator('[data-drive-action=connect]').click();expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000);self.assertEqual(google.posts,1)
