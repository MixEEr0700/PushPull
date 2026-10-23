"""Real Chromium journal + real IDB; only Google OAuth/HTTP is simulated."""
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs
from pathlib import Path
import subprocess
from playwright.sync_api import expect
from test_browser import BrowserHarness, confirm_restore
import test_plan_import as imports
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

class ManualDriveFlow(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    activate=training.V2Training.activate
    open_result=training.V2Training.open_result
    fill_rows=training.V2Training.fill_rows
    save_form=training.V2Training.save_form

    def configure(self):
        self.page.locator('[data-tab=settings]').click()
        self.page.get_by_text('Opcje zaawansowane Google',exact=True).click()
        self.page.locator('#driveConfig input').fill('123-test.apps.googleusercontent.com')
        self.page.locator('#driveConfig button').click()
        self.page.locator('[data-drive-action=connect]').click()
        expect(self.page.locator('[data-drive-action=connect]')).to_be_hidden()

    def upload(self):
        self.page.locator('[data-drive-action=upload]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zapisana i zweryfikowana')

    def restore_preview(self,file_id=None):
        self.page.locator('[data-drive-action=restore]').click()
        expect(self.page.locator('#driveCopy')).to_be_visible()
        if file_id:self.page.locator('#driveCopy').select_option(file_id)
        self.page.locator('[data-drive-action=preview]').click()
        expect(self.page.locator('[data-restore-preview]')).to_be_visible(timeout=60000)

    def drafts(self):
        return self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')

    def reopen(self):
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.url);self.ready()

    def test_manual_backup_only_local_ab_save_drafts_offline_restart_and_full_download(self):
        self.context.close();self.context=self.new_context(service_workers='allow')
        self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        mock=MockGoogle();mock.install(self.context);self.activate();self.configure()
        self.assertEqual(mock.posts,0)
        expect(self.page.locator('[data-drive-diagnostics]')).to_have_count(0)
        expect(self.page.get_by_text('Zachowaj lokalne jako nową wersję',exact=True)).to_have_count(0)
        self.page.evaluate('navigator.serviceWorker.ready')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.assertEqual(self.page.evaluate('window.__requestedScope'),'https://www.googleapis.com/auth/drive.appdata')
        self.page.locator('[data-tab=training]').click()
        form=self.open_result('PULL B','PULL-B-6-SKI');self.fill_rows(form,'20','8')
        self.page.locator('[data-expand="PULL-B-6-SHRUGS"]').click();self.page.locator('[data-panel=result]').click()
        form_b=self.page.locator('.performanceForm');form_b.locator('[data-rich-action=toggle]').click()
        self.fill_rows(form_b,'13.125','10')
        expect(form_b.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.locator('[data-expand="PULL-B-6-SKI"]').click();self.page.locator('[data-panel=result]').click()
        self.save_form(self.page.locator('.performanceForm'));saved=self.state()
        self.assertEqual(saved['entries'][-1]['exerciseId'],'PULL-B-6-SKI')
        self.assertEqual(mock.posts,0)
        self.page.locator('[data-tab=settings]').click();mock.hold=True
        with self.page.expect_request('https://www.googleapis.com/upload/**'):
            self.page.locator('[data-drive-action=upload]').click()
        expect(self.page.locator('[data-drive-status]')).not_to_contain_text('zweryfikowana')
        self.assertTrue(mock.held);self.assertNotIn('13.125',mock.held[0][1]['text'])
        # Cloud waiting never prevents local navigation or draft recovery.
        self.page.locator('[data-tab=training]').click()
        expect(self.page.locator('[data-draft-resume]')).to_have_count(1)
        mock.release(500);self.context.set_offline(True);self.reopen()
        self.page.locator('[data-draft-resume]').click()
        form=self.page.locator('.performanceForm');expect(form).to_have_attribute('data-id','PULL-B-6-SHRUGS')
        expect(form.locator('[data-row="0"][data-field=kg]')).to_have_value('13.125')
        self.save_form(form);self.page.locator('[data-act=finish]').click()
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        offline=self.state();self.assertEqual(offline['sessions'][-1]['status'],'done')
        self.context.set_offline(False);self.page.evaluate("window.dispatchEvent(new Event('online'));document.dispatchEvent(new Event('visibilitychange'))")
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-drive-action=connect]').click()
        expect(self.page.locator('[data-drive-action=connect]')).to_be_hidden();self.assertEqual(mock.posts,1)
        self.upload();self.assertEqual(mock.posts,2);self.assertEqual(self.state(),offline)
        self.restore_preview();backup=json.loads(list(mock.files.values())[-1]['text'])['backup'];restored=self.page.evaluate('async text=>(await PushPullDB.parseModelBackup(text)).data',backup)
        self.assertEqual(restored,offline)
        self.assertEqual(len(offline['entries']),len(saved['entries'])+1)
        self.page.locator('[data-restore-cancel]').click()
        with self.page.expect_download() as local:self.page.locator('[data-act=export]').click()
        self.assertEqual(self.page.evaluate('async text=>(await PushPullDB.parseModelBackup(text)).data',Path(local.value.path()).read_text()),offline)
        self.assertFalse(self.alerts,self.alerts)

    def test_two_profiles_restore_v2_and_test_from_drive_preserves_preimage_drafts_and_offline(self):
        mock=MockGoogle();mock.install(self.context);self.activate()
        f=self.open_result('PUSH A','PUSH-A-1');self.fill_rows(f,'100','5');self.save_form(f)
        self.page.locator('[data-act=finish]').click()
        plan=json.loads((Path(__file__).parent/'fixtures/plan-test-3x5.json').read_text())
        imports.PlanImport.preview(self,plan);imports.PlanImport.store(self);imports.PlanImport.activate(self)
        self.page.locator('[data-tab=training]').click();f=self.open_result('TEST','TEST-1');self.fill_rows(f,'20','5');self.save_form(f)
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        cloud=self.state();self.configure();self.upload();self.assertEqual(mock.posts,1);files=dict(mock.files)
        def metrics(page):return page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const m=await import('./model/plan-overview.mjs');return Object.fromEntries(d.value.trainingJournal.model.planVersions.map(p=>[p.id,m.weeklyStats(d.value,p.id,{from:'2026-10-01',to:'2026-10-31',today:'2026-11-01',catalog:d.export().catalog})]))}finally{d.close()}}""")
        expected_metrics=metrics(self.page)
        expected_catalog=self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.export().catalog}finally{d.close()}}')
        # A second independent storage partition starts with V2 only.
        self.context=self.new_context(service_workers='allow');mock.install(self.context)
        self.page=self.context.new_page();self.page.on('dialog',self.dialog);self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.url);self.activate();f=self.open_result('PUSH A','PUSH-A-1');self.fill_rows(f,'81.123','7')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        local=self.state();drafts=self.drafts();self.configure();self.assertEqual(mock.posts,1)
        mock.corrupt=True;self.page.locator('[data-drive-action=restore]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Nie znaleziono prawidłowej kopii')
        self.assertEqual(self.state(),local);self.assertEqual(self.drafts(),drafts);mock.corrupt=False
        self.restore_preview();preview=self.page.locator('[data-restore-preview]')
        for text in ['Na tym urządzeniu','W wybranej kopii','TEST 3×5','ZASTĄPI','nie scala','Szkice']:expect(preview).to_contain_text(text)
        self.assertEqual(self.state(),local);self.assertEqual(self.drafts(),drafts)
        self.page.locator('[data-restore-cancel]').click();self.assertEqual(self.state(),local)
        self.restore_preview();self.confirm=False;confirm_restore(self.page);self.assertEqual(self.state(),local)
        before_keys=self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.backups()}finally{d.close()}}')
        self.confirm=True;confirm_restore(self.page)
        expect(self.page.locator('[data-restore-success]')).to_contain_text('TEST 3×5')
        self.assertEqual(self.state(),cloud);self.assertEqual(self.drafts(),drafts);self.assertEqual(metrics(self.page),expected_metrics)
        self.assertEqual(self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.export().catalog}finally{d.close()}}'),expected_catalog)
        preimage=self.page.evaluate("""async({before,local})=>{const d=await PushPullDB.open(()=>{});try{for(const key of d.backups().filter(k=>!before.includes(k))){try{const raw=await d.readBackup(key),parsed=await(await import('./model/drive-sync.mjs')).inspectBackup(raw);const {canonical}=await import('./model/backup-json.mjs');if(canonical(parsed.data)===canonical(local))return true;}catch{}}return false;}finally{d.close()}}""",{'before':before_keys,'local':local})
        self.assertTrue(preimage);self.assertEqual(mock.files,files);self.assertEqual(mock.posts,1)
        expect(self.page.locator('[data-draft-download]')).to_have_count(1)
        expect(self.page.locator('[data-draft-resume]')).to_have_count(0) # B's snapshot is not silently applied to A.
        self.page.evaluate('navigator.serviceWorker.ready');self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.context.set_offline(True);self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog);self.page.goto(self.url)
        expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),cloud);self.assertEqual(self.drafts(),drafts)
        self.assertEqual(metrics(self.page),expected_metrics);self.assertEqual(mock.posts,1);self.assertFalse(self.alerts,self.alerts)

    def test_restore_preview_rejects_newer_commit_from_another_tab(self):
        self.page.add_init_script('window.BroadcastChannel=undefined');self.activate();self.settings=lambda:self.page.locator('[data-tab=settings]').click();self.settings()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_bytes()
        self.page.locator('#importFile').set_input_files({'name':'old.json','mimeType':'application/json','buffer':raw})
        expect(self.page.locator('[data-restore-preview]')).to_be_visible(timeout=60000)
        newer=self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const v=d.value;v.exercises['PUSH A'][0].notes='newer data in another tab';await d.commit(v);return d.value;}finally{d.close()}}""")
        confirm_restore(self.page);self.assertEqual(self.state(),newer)
        expect(self.page.locator('[data-restore-error]')).to_contain_text('innej karcie')
        expect(self.page.locator('[data-restore-success]')).to_have_count(0)
        self.assertTrue(self.alerts)
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-tab=settings]').click()
        self.page.locator('#importFile').set_input_files({'name':'old.json','mimeType':'application/json','buffer':raw})
        expect(self.page.locator('[data-restore-preview]')).to_be_visible(timeout=60000)
        self.page.evaluate("localStorage.setItem('pushpull_skeleton_v1',localStorage.getItem('pushpull_skeleton_v1')+' ')")
        confirm_restore(self.page);self.assertEqual(self.state(),newer)
        expect(self.page.locator('[data-restore-error]')).to_contain_text('od podglądu')

    def test_post_commit_readback_failure_never_reports_success_and_keeps_preimage(self):
        self.prepare();self.ready();self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        candidate=json.loads(Path(download.value.path()).read_text());before=self.state()
        candidate['data']['exercises']['PUSH A'][0]['notes']='restored value'
        self.page.locator('#importFile').set_input_files({'name':'restored.json','mimeType':'application/json','buffer':json.dumps(candidate).encode()})
        expect(self.page.locator('[data-restore-preview]')).to_be_visible(timeout=60000)
        self.page.evaluate("""()=>{const original=IDBDatabase.prototype.transaction;window.__originalTransaction=original;IDBDatabase.prototype.transaction=function(names,mode,...rest){if(mode==='readonly'&&window.__restoreCompleted)throw Error('simulated readback failure');const tx=original.call(this,names,mode,...rest);if(mode==='readwrite')tx.addEventListener('complete',()=>window.__restoreCompleted=true);return tx;}}""")
        confirm_restore(self.page)
        expect(self.page.locator('[data-restore-success]')).to_have_count(0)
        expect(self.page.locator('h1')).to_have_text('Dane wymagają odzyskania')
        expect(self.page.locator('#backupKey')).to_be_visible()
        self.page.evaluate('()=>{IDBDatabase.prototype.transaction=window.__originalTransaction}')
        self.assertEqual(self.state(),candidate['data']) # Commit happened; failed post-read is never called success.
        self.assertTrue(self.alerts)
        preimages=self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await Promise.all(d.backups().map(k=>d.readBackup(k)))}finally{d.close()}}')
        self.assertTrue(any(json.loads(raw).get('data')==before for raw in preimages if raw))

    def test_upgrade_legacy_conflict_and_running_legacy_worker_never_sends_old_outbox(self):
        mock=MockGoogle();mock.install(self.context);self.prepare();self.ready()
        # Keep actual old implementation running with real IDB in this page;
        # updating metadata must disable its work, including stale UI configure.
        old=subprocess.check_output(['git','show','e93a4a5:model/drive-sync.mjs'],cwd=Path(__file__).resolve().parents[1]).decode()
        self.page.evaluate('''async source=>{
          const db=await PushPullDB.open(()=>{}),t=(await import('./model/google-drive.mjs')).createGoogleDrive();
          const s=await db.readDriveState()??{accounts:{}};s.enabled=true;s.mode='sync';s.selected='mock-account';s.clientId='123-test.apps.googleusercontent.com';
          const node=await (await import('./model/drive-sync.mjs')).makeNode(JSON.stringify(db.export()),[]);
          s.accounts={'mock-account':{base:[crypto.randomUUID()],ackRevision:18,outbox:{node,revision:19},resolution:{id:'yesterday'},failures:4}};
          await db.writeDriveState(s,s.token??null);window.__archive=structuredClone(s.accounts);
          source=source.replaceAll("from './", "from '"+new URL('./model/',location.href).href);
          const m=await import(URL.createObjectURL(new Blob([source],{type:'text/javascript'})));
          window.__old=await m.openDriveSync({database:db,transport:t,auto:false});
          await window.__old.connect();
          window.__manual=await (await import('./model/drive-sync.mjs')).openDriveBackup({database:db,transport:(await import('./model/google-drive.mjs')).createGoogleDrive()});
          await window.__old.retryNow();await window.__old.configure('123-test.apps.googleusercontent.com');await window.__old.connect();await window.__old.retryNow();
        }''',old)
        self.assertEqual(mock.posts,0)
        meta=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDriveState()}finally{db.close()}}')
        self.assertFalse(meta['enabled']);self.assertEqual(meta['mode'],'manual')
        self.assertEqual(meta['accounts']['mock-account']['outbox'],self.page.evaluate('window.__archive["mock-account"].outbox'))
        self.reopen();self.page.locator('[data-tab=settings]').click();self.page.locator('[data-drive-action=connect]').click()
        expect(self.page.locator('[data-drive-action=connect]')).to_be_hidden()
        before=self.state();self.upload();self.assertEqual(mock.posts,1)
        raw=next(iter(mock.files.values()))['text'];parsed=self.page.evaluate('async text=>(await import("./model/drive-sync.mjs")).inspectBackup(JSON.parse(text).backup)',raw)
        self.assertEqual(parsed['data'],before);self.assertEqual(self.state(),before)
        self.assertFalse(self.alerts,self.alerts)

    def test_expired_auth_manual_retry_does_not_block_local_result_or_duplicate_series(self):
        mock=MockGoogle();mock.install(self.context);self.prepare();self.ready();self.configure();self.upload()
        before=self.state();mock.error=401;self.page.locator('[data-drive-action=upload]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Autoryzacja Google wygasła')
        expect(self.page.locator('[data-drive-action=connect]')).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-expand="PUSH-A-1"]').click();self.page.locator('[data-panel=result]').click()
        form=self.page.locator('.seriesResultForm');form.locator('[data-main=kg]').fill('77');form.locator('[data-main=reps]').fill('9')
        form.locator('[type=submit]').click();expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        saved=self.state();self.assertEqual(len(saved['entries']),len(before['entries']));self.assertEqual(saved['entries'][-1]['id'],before['entries'][-1]['id'])
        mock.error=0;self.page.locator('[data-tab=settings]').click();self.page.locator('[data-drive-action=connect]').click()
        expect(self.page.locator('[data-drive-action=connect]')).to_be_hidden();count=mock.posts;self.upload()
        self.assertEqual(mock.posts,count+1);self.assertEqual(self.state(),saved);self.assertFalse(self.alerts,self.alerts)
