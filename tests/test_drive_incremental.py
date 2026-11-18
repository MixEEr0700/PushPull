"""Production HTTP routes, OAuth and stores; Google service is simulated."""
import json,re,uuid
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
from playwright.sync_api import Error,expect
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
        first,last=list(google.files)
        google.files[first]['createdTime']='2026-07-03T05:15:00Z'
        google.files[last]['createdTime']='2026-11-02T23:30:00Z'
        # The mock deliberately returns a legacy row with a newer date too.
        google.files['legacy-json']={'id':'legacy-json','createdTime':'2026-11-08T23:30:00Z','appProperties':{'pushpull':'sync-v1'},'text':'unread legacy backup'}
        ctx=self.new_context(service_workers='allow');google.install(ctx)
        requests=[];ctx.on('request',lambda request:requests.append(request.url))
        p=ctx.new_page();p.on('dialog',self.dialog);p.goto(self.url);p.wait_for_selector('[data-act=start]');self.page=p;self.configure()
        self.backup_flow('restore')
        p.get_by_role('button',name='Przywróć z Google Drive',exact=True).click()
        entries=p.locator('[data-ppc1-point]');expect(entries).to_have_count(2)
        expect(entries).to_have_text([re.compile(r'Najnowszy zapis.*3 listopada 2026.*00:30'),re.compile(r'3 lipca 2026.*07:15')])
        expect(p.locator('[data-ppc1-points]')).to_contain_text('Najnowszy zapis na Drive może zawierać mniej danych')
        self.assertFalse(any('alt=media' in url for url in requests))
        self.assertTrue(any('ppc1-incremental-v1' in url for url in requests))
        for width in (360,390,412):
            p.set_viewport_size({'width':width,'height':844})
            self.assertLessEqual(p.evaluate('document.documentElement.scrollWidth'),width)
        entries.first.click();expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000)
        expect(p.locator('[data-restore-preview]')).to_contain_text('Treningi: 2')
        self.assertFalse(any('legacy-json' in url for url in requests))
        p.locator('[data-restore-confirm]').click();expect(p.locator('[data-restore-success]')).to_be_visible(timeout=30000)
        p.reload();p.wait_for_selector('[data-act=start]');p.locator('[data-tab=settings]').click();self.backup_flow('save')
        with p.expect_download() as dl:p.locator('[data-canonical-export]').click()
        self.assertEqual(self.decode(Path(dl.value.path()).read_bytes()),expected)
        for width in (360,390,412):
            p.set_viewport_size({'width':width,'height':844});self.assertLessEqual(p.evaluate('document.documentElement.scrollWidth'),width)
    def test_cancel_metadata_and_selected_file_ignores_late_responses(self):
        google=IncrementalGoogle();google.install(self.context);self.page.wait_for_selector('[data-act=start]');self.configure()
        self.backup_flow('save');self.page.locator('[data-ppc1-send]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000)
        self.backup_flow('restore')
        before=self.state()
        held=[]
        def stall(route):
            held.append(route)
        metadata='https://www.googleapis.com/drive/v3/files?*'
        point='https://www.googleapis.com/drive/v3/files/*?alt=media'
        for pattern,selector in ((metadata,'[data-ppc1-list]'),(point,'[data-ppc1-point]')):
            if pattern==point:
                self.page.locator('[data-ppc1-list]').click()
                expect(self.page.locator(selector)).to_have_count(1)
            self.page.route(pattern,stall)
            with self.page.expect_request(pattern):
                self.page.locator(selector).click()
            expect(self.page.locator('[data-restore-cancel]')).to_be_visible()
            self.page.locator('[data-restore-cancel]').click()
            self.page.unroute(pattern,stall)
            route=held.pop()
            try:route.fulfill(status=500,headers={'access-control-allow-origin':'*'},body='{}')
            except Error as error:self.assertIn('Route is already handled',str(error))
            expect(self.page.locator('[data-restore-preview],[data-restore-error],[data-ppc1-point]')).to_have_count(0)
            expect(self.page.locator('[data-restore-cancelled]')).to_be_visible()
            expect(self.page.locator('[data-ppc1-list]')).to_be_enabled()
            self.assertEqual(self.state(),before)

    def test_auth_failure_keeps_finished_session_and_queue_then_restart_reconnect(self):
        google=IncrementalGoogle();google.install(self.context);self.page.wait_for_selector('[data-act=start]');self.configure();google.error=401
        self.page.locator('[data-tab=training]').click();self.start();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();expect(self.page.locator('[data-drive-reminder]')).to_be_visible(timeout=30000)
        self.assertEqual(self.state()['sessions'][-1]['status'],'done');self.assertEqual(google.posts,0)
        self.assertTrue(self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{return !!(await h.readDriveState()).ppc1Queue}finally{h.close()}}"""))
        google.error=0;self.page.locator('[data-reminder-connect]').click();expect(self.page.locator('[data-drive-reminder]')).to_have_count(0);expect(self.page.locator('[data-drive-global]')).to_contain_text('Kopia zweryfikowana',timeout=60000);self.assertEqual(google.posts,1)
        self.page.reload();self.page.wait_for_selector('[data-act=start]');expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)
    def test_offline_finish_and_offline_restart_keep_intent(self):
        from test_browser import wait_for_service_worker_controller
        self.context.close();self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog);self.page.on('pageerror',lambda e:self.errors.append(str(e)));google=IncrementalGoogle();google.install(self.context);self.page.goto(self.url);self.page.wait_for_selector('[data-act=start]');wait_for_service_worker_controller(self.page);self.configure();self.context.set_offline(True)
        self.page.locator('[data-tab=training]').click();self.start();self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state()['sessions'][-1]['status'],'done');self.assertEqual(google.posts,0);self.page.reload();self.page.wait_for_selector('[data-act=start]');self.context.set_offline(False);self.page.locator('[data-tab=settings]').click();self.backup_flow('save');self.data_section('google');self.page.locator('[data-drive-action=connect]').click();expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000);self.assertEqual(google.posts,1)
    def test_interrupted_manual_upload_resumes_same_remote_file_after_restart(self):
        google=IncrementalGoogle()
        route_response=google.route
        held=[]
        def stall_after_post(route):
            if '/upload/' not in route.request.url or held:
                return route_response(route)
            request=route.request
            boundary=request.headers['content-type'].split('boundary=')[1]
            parts=request.post_data.split('--'+boundary)
            metadata=json.loads(parts[1].split('\r\n\r\n',1)[1].strip())
            text=parts[2].split('\r\n\r\n',1)[1].rstrip('\r\n')
            google.posts+=1
            google.files[metadata['id']]={'id':metadata['id'],'appProperties':metadata['appProperties'],'text':text,'createdTime':'2026-11-18T12:00:00Z'}
            held.append(metadata['id'])
            # The remote write succeeded but its response never arrives.
        google.route=stall_after_post
        # Install routing before loading a fresh document with a test-only deadline.
        js=Path('model/google-drive.mjs').read_text().replace('timeoutMs=30000','timeoutMs=5000')
        self.page.route('**/model/google-drive.mjs',lambda r:r.fulfill(body=js,content_type='text/javascript'))
        google.install(self.context)
        self.page.reload();self.page.wait_for_selector('[data-act=start]')
        legacy_drive.ManualDriveFlow.configure(self,automatic=False)
        self.backup_flow('save')
        self.page.locator('[data-ppc1-send]').click()
        self.page.wait_for_function("""async()=>{const h=await PushPullDB.open(()=>{});try{return !!(await h.readDriveState()).accounts['mock-account']?.ppc1?.pending}finally{h.close()}}""")
        # Browser round trips let the intercepted POST reach the simulated Drive.
        deadlines=0
        while not held and deadlines<30:
            self.page.wait_for_timeout(50);deadlines+=1
        self.assertEqual(len(held),1)
        self.page.reload()
        self.page.locator('[data-tab=settings]').click()
        self.data_section('google')
        self.page.locator('[data-drive-action=connect]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=15000)
        self.assertEqual(google.posts,1)
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Ostatnia kopia zweryfikowana')
        expect(self.page.locator('[data-drive-reminder]')).to_have_count(0)

    def test_stalled_api_releases_busy_and_reminder_can_retry(self):
        google=IncrementalGoogle()
        route_response=google.route
        stalled=[]
        def stall_reservation(route):
            if route.request.url.split('?')[0].endswith('/generateIds') and not stalled:
                stalled.append(True)
                return
            route_response(route)
        google.route=stall_reservation
        js=Path('model/google-drive.mjs').read_text().replace('timeoutMs=30000','timeoutMs=500')
        self.page.route('**/model/google-drive.mjs',lambda r:r.fulfill(body=js,content_type='text/javascript'))
        google.install(self.context)
        self.page.reload();self.page.wait_for_selector('[data-act=start]');self.configure()
        self.page.locator('[data-tab=training]').click();self.start()
        self.page.locator('[data-act=finish]').click()
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        reminder=self.page.locator('[data-drive-reminder]')
        expect(reminder).to_be_visible(timeout=15000)
        expect(self.page.locator('[data-drive-global]')).to_contain_text('Przekroczono czas')
        self.assertEqual(google.posts,0)
        expect(reminder.locator('[data-reminder-connect]')).to_have_text('Ponów kopię')
        reminder.locator('[data-reminder-connect]').click()
        expect(self.page.locator('[data-drive-global]')).to_contain_text('Kopia zweryfikowana')
        expect(reminder).to_have_count(0)
        self.assertEqual(google.posts,1)
