"""Real Chromium journal + real IDB; only Google OAuth/HTTP is simulated."""
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy
import test_v2_training as training

class MockGoogle:
    def __init__(self):
        self.files={};self.posts=0;self.hold=False;self.held=[];self.error=0;self.corrupt=False;self.scopes=[];self.list_files=None
    def install(self,context):
        context.route('https://accounts.google.com/gsi/client',lambda route:route.fulfill(content_type='text/javascript',body="""window.google={accounts:{oauth2:{hasGrantedAllScopes:()=>true,initTokenClient:o=>{window.__requestedScope=o.scope;return {requestAccessToken:()=>o.callback({access_token:'synthetic-google-token',expires_in:3600})}}}}};"""))
        context.route('https://www.googleapis.com/**',self.route)
    def route(self,route):
        request=route.request;url=urlsplit(request.url);query=parse_qs(url.query)
        headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,POST,OPTIONS'}
        def reply(value,status=200):route.fulfill(status=status,headers=headers,content_type='application/json',body=json.dumps(value))
        if request.method=='OPTIONS':reply({});return
        if self.error:reply({'error':'simulated'},self.error);return
        if url.path.endswith('/about'):reply({'user':{'permissionId':'mock-account','emailAddress':'tester@example.invalid'}});return
        if '/upload/' in url.path:
            self.posts+=1
            boundary=request.headers['content-type'].split('boundary=')[1]
            parts=request.post_data.split('--'+boundary)
            metadata=json.loads(parts[1].split('\r\n\r\n',1)[1].strip())
            text=parts[2].split('\r\n\r\n',1)[1].rstrip('\r\n')
            assert metadata['parents']==['appDataFolder']
            record={'id':'file-'+str(self.posts),'appProperties':metadata['appProperties'],'text':text,'createdTime':datetime.now(timezone.utc).isoformat()}
            if self.hold:self.held.append((route,record,headers));return
            self.files[record['id']]=record;reply({'id':record['id']});return
        if url.path.endswith('/files'):
            assert query['spaces']==['appDataFolder']
            reply({'files':[{k:v for k,v in f.items() if k!='text'} for f in (self.files.values() if self.list_files is None else self.list_files)]});return
        record=self.files[url.path.rsplit('/',1)[1]]
        text=record['text'].replace('Prostowanie','TAMPERED') if self.corrupt else record['text']
        route.fulfill(headers=headers,content_type='application/json',body=text)
    def release(self,error=0):
        self.hold=False
        for route,record,headers in self.held:
            if not error:self.files[record['id']]=record
            route.fulfill(status=error or 200,headers=headers,content_type='application/json',body=json.dumps({'id':record['id']} if not error else {'error':'simulated'}))
        self.held=[]

class DriveSyncFlow(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    activate=training.V2Training.activate
    open_result=training.V2Training.open_result
    fill_rows=training.V2Training.fill_rows
    save_form=training.V2Training.save_form

    def configure(self):
        self.page.locator('[data-tab=settings]').click()
        self.page.locator('#driveConfig input').fill('123-test.apps.googleusercontent.com')
        self.page.locator('#driveConfig button').click()
        self.page.locator('[data-drive-action=connect]').click()

    def synced(self):
        expect(self.page.locator('[data-drive-status]').first).to_contain_text('Zsynchronizowano',timeout=10000)

    def reopen(self):
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.url);self.ready()

    def test_local_save_before_google_offline_restart_retry_and_independent_ab(self):
        self.context.close();self.context=self.new_context(service_workers='allow')
        self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        mock=MockGoogle();mock.install(self.context);self.activate();self.configure();self.synced()
        self.page.evaluate('navigator.serviceWorker.ready')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.assertEqual(self.page.evaluate('window.__requestedScope'),'https://www.googleapis.com/auth/drive.appdata')
        self.page.locator('[data-tab=training]').click()
        form=self.open_result('PULL B','PULL-B-6-SKI');self.synced();self.fill_rows(form,'20','8')
        self.page.locator('[data-expand="PULL-B-6-SHRUGS"]').click();self.page.locator('[data-panel=result]').click()
        form_b=self.page.locator('.performanceForm');form_b.locator('[data-rich-action=toggle]').click()
        self.fill_rows(form_b,'13.125','10')
        expect(form_b.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        count=mock.posts;self.assertTrue(all('13.125' not in f['text'] for f in mock.files.values()))
        self.page.locator('[data-expand="PULL-B-6-SKI"]').click();self.page.locator('[data-panel=result]').click()
        mock.hold=True
        with self.page.expect_request('https://www.googleapis.com/upload/**'):
            self.save_form(self.page.locator('.performanceForm'))
            self.page.wait_for_function("document.querySelector('[data-drive-status]').textContent.includes('Oczekuje')")
            # Google is still waiting, but the official result is already committed.
            saved=self.state();self.assertEqual(saved['entries'][-1]['exerciseId'],'PULL-B-6-SKI')
            self.assertEqual(len(saved['entries'][-1]['performance']['rows']),2)
            expect(self.page.locator('[data-expand="PULL-B-6-SKI"] .name')).to_have_text('Narciarz')
        self.assertGreater(mock.posts,count);self.assertTrue(mock.held)
        mock.release(500)
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Błąd')
        self.context.set_offline(True);self.reopen()
        expect(self.page.locator('[data-draft-resume]')).to_have_count(1)
        self.page.locator('[data-draft-resume]').click()
        form=self.page.locator('.performanceForm');expect(form).to_have_attribute('data-id','PULL-B-6-SHRUGS')
        expect(form.locator('[data-row="0"][data-field=kg]')).to_have_value('13.125')
        self.save_form(form);self.page.locator('[data-act=finish]').click()
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        offline=self.state();self.assertEqual(offline['sessions'][-1]['status'],'done')
        self.context.set_offline(False)
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-drive-action=connect]').click();self.synced()
        self.assertEqual(self.state(),offline)
        self.assertEqual(len(offline['entries']),len(saved['entries'])+1)
        self.page.locator('[data-drive-action=list]').click()
        expect(self.page.locator('#driveCopy option')).to_have_count(len(mock.files))
        self.page.locator('[data-drive-action=preview]').click()
        expect(self.page.get_by_text('Podgląd kopii',exact=True)).to_be_visible()
        with self.page.expect_download() as download:self.page.locator('[data-drive-action=download]').click()
        from pathlib import Path
        backup=Path(download.value.path()).read_text()
        restored=self.page.evaluate('async text=>(await PushPullDB.parseModelBackup(text)).data',backup)
        self.assertEqual(restored,offline)
        meta=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDriveState()}finally{db.close()}}')
        self.assertNotIn('synthetic-google-token',json.dumps(meta))
        self.assertFalse(self.alerts,self.alerts)

    def test_new_phone_preview_conflict_corruption_and_confirmed_restore_preserves_preimage(self):
        mock=MockGoogle();mock.install(self.context);self.activate();self.configure();self.synced()
        self.page.locator('[data-tab=training]').click();form=self.open_result('PULL B','PULL-B-6-SKI')
        self.fill_rows(form,'37','9');self.save_form(form);self.synced();cloud=self.state()
        # A different browser profile represents a new phone with its own data.
        self.context.close();self.context=self.new_context(service_workers='block');mock.install(self.context)
        self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.prepare();self.ready();local=self.state();self.configure()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Konflikt')
        self.assertEqual(self.state(),local) # Connecting never replaces local history.
        self.page.locator('[data-drive-action=list]').click()
        expect(self.page.locator('#driveCopy')).to_be_visible()
        mock.corrupt=True;self.page.locator('[data-drive-action=preview]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('integralności')
        self.assertEqual(self.state(),local);mock.corrupt=False
        self.page.locator('[data-drive-action=preview]').click()
        expect(self.page.get_by_text('Podgląd kopii',exact=True)).to_be_visible()
        self.confirm=False;self.page.locator('[data-drive-action=restore]').click();self.assertEqual(self.state(),local)
        self.confirm=True;self.page.locator('[data-drive-action=restore]').click()
        self.ready();self.synced();self.assertEqual(self.state(),cloud)
        copies=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await Promise.all(db.backups().map(id=>db.readBackup(id)))}finally{db.close()}}')
        self.assertTrue(any(json.loads(raw).get('data')==local for raw in copies if raw))
        expect(self.page.locator('[data-expand="PULL-B-6-SKI"] .name')).to_have_text('Narciarz')
        self.assertFalse(self.alerts,self.alerts)

    def test_keep_local_upload_readback_with_stale_listing_preserves_phone_and_other_device(self):
        # Two actual browser profiles, real IDB/OAuth adapter, simulated Google
        # file search lagging behind POST and direct GET by returned file ID.
        mock=MockGoogle();mock.install(self.context);self.activate();self.configure();self.synced()
        roots=list(mock.files.values())
        self.page.locator('[data-tab=training]').click();form=self.open_result('PULL B','PULL-B-6-SKI')
        self.fill_rows(form,'39','9');self.save_form(form);self.synced();pc=self.state()
        old_files=dict(mock.files)
        self.context.close();self.context=self.new_context(service_workers='block');mock.install(self.context)
        self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.prepare();self.ready()
        self.page.locator('[data-expand="PUSH-A-1"]').click();self.page.locator('[data-panel=result]').click()
        f=self.page.locator('.seriesResultForm');f.locator('[data-main=kg]').fill('81');f.locator('[data-main=reps]').fill('8')
        f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        # A separate unfinished result must survive cloud conflict resolution.
        self.page.locator('[data-panel=result]').click();f=self.page.locator('.seriesResultForm')
        f.locator('[data-main=kg]').fill('83')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        local=self.state();self.configure()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Konflikt')
        self.page.locator('[data-drive-action=list]').click();expect(self.page.locator('#driveCopy')).to_be_visible()
        # keepLocal revalidates the fresh list; subsequent workers see only the
        # old root. Google accepts the new file, whose direct GET is available.
        mock.hold=True
        with self.page.expect_request('https://www.googleapis.com/upload/**'):
            self.page.locator('[data-drive-action=keep]').click()
        expect(self.page.locator('[data-drive-diagnostics]')).to_contain_text('"resolution":true')
        mock.list_files=roots;self.assertTrue(mock.held);mock.release()
        self.page.locator('[data-drive-action=retry]').click();self.synced()
        self.assertEqual(self.state(),local)
        for id,old in old_files.items():self.assertEqual(mock.files[id],old)
        self.assertEqual(len(mock.files),len(old_files)+1)
        newest=list(mock.files.values())[-1]
        parsed=self.page.evaluate('async text=>(await import("./model/drive-sync.mjs")).inspectBackup(JSON.parse(text).backup)',newest['text'])
        self.assertEqual(parsed['data'],local)
        self.assertNotEqual(local,pc) # No implicit merge or cloud restore.
        self.assertEqual(len(self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')),1)
        # The normal list eventually catches up. New workout changes still sync.
        mock.list_files=None
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('[data-main=kg]')).to_have_value('83')
        self.page.locator('.seriesResultForm [type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible();self.synced()
        self.assertEqual(self.state()['entries'][-1]['kg'],'83')
        self.assertFalse(self.alerts,self.alerts)

    def test_expired_google_token_does_not_block_legacy_save_or_duplicate_results(self):
        mock=MockGoogle();mock.install(self.context);self.prepare();self.ready();self.configure();self.synced()
        before=self.state();mock.error=401
        self.page.locator('[data-tab=training]').click()
        self.page.locator('[data-expand="PUSH-A-1"]').click();self.page.locator('[data-panel=result]').click()
        form=self.page.locator('.seriesResultForm')
        form.locator('[data-main=kg]').fill('77');form.locator('[data-main=reps]').fill('9')
        form.locator('[type=submit]').click();expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Autoryzacja Google wygasła')
        saved=self.state();self.assertEqual(len(saved['entries']),len(before['entries']))
        self.assertEqual(saved['entries'][-1]['id'],before['entries'][-1]['id'])
        self.assertEqual(saved['entries'][-1]['kg'],'77')
        mock.error=0;self.page.locator('[data-tab=settings]').click()
        self.page.locator('[data-drive-action=connect]').click();self.synced()
        self.assertEqual(self.state(),saved)
        self.page.locator('[data-drive-action=list]').click()
        expect(self.page.locator('#driveCopy')).to_be_visible()
        self.page.locator('[data-drive-action=preview]').click()
        expect(self.page.get_by_text('Podgląd kopii',exact=True)).to_be_visible()
        self.assertFalse(self.alerts,self.alerts)
