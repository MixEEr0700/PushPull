"""Real service workers + installability metadata + isolated artifact/HTTPS tests."""
from test_browser import confirm_restore,open_result_panel,add_drop
import functools
from datetime import datetime, timezone
import http.server
import json
import os
from pathlib import Path
import shutil
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen, Request
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_release import ASSETS, FILES, build, generate
from serve_test import ReleaseHandler, make_server, verify_release
# Historical app bytes stay at their original ref. The current release builder
# also precaches the newly introduced, unused-by-old-app v4 support modules.
V4_ASSETS={'model/draft-collector.mjs','model/backup-v6.mjs','model/backup-v5-preview.mjs','model/backup-v5.mjs','model/backup-v4.mjs','model/backup-v4-export.mjs','model/local-backup-v4.mjs'}
V4_ASSETS.update({'model/journal-runtime-index.mjs','model/journal-runtime.mjs','model/journal-index.mjs','model/journal-protocol.mjs','model/journal-idb.mjs','model/journal-database.mjs'})
def historical_asset(ref,name):
    if name in V4_ASSETS:return (ROOT/name).read_bytes()
    return subprocess.check_output(['git','show',ref+':'+name],cwd=ROOT)

FIXTURE=json.loads((ROOT/'tests/fixtures/v1.json').read_text())
RAW=' '+json.dumps(FIXTURE,ensure_ascii=False)+'\n'
KEY='pushpull_skeleton_v1'
STAGE2='120b8547b31926705e75079c69109c06cac9f9c8'
STAGE3='adadf8f8c45af3693de559f09971759a53ea1bb0'

class ArtifactBuild(unittest.TestCase):
    def test_allowlist_determinism_and_worker_freshness(self):
        expected=generate()
        self.assertEqual(expected,generate())
        self.assertEqual(expected['sw.js'],(ROOT/'sw.js').read_bytes())
        self.assertEqual(set(expected),set(FILES))
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp)
            verify_release(tmp)
            self.assertEqual(build(tmp),json.loads(expected['release.json']))
            (Path(tmp)/'private-backup.json').write_text('do not overwrite')
            with self.assertRaises(ValueError):build(tmp)
            with self.assertRaises(ValueError):verify_release(tmp)
            self.assertEqual((Path(tmp)/'private-backup.json').read_text(),'do not overwrite')

    def test_rename_preserves_pwa_identity_icons_and_data_contract(self):
        old=json.loads(subprocess.check_output(['git','show',STAGE3+':manifest.webmanifest'],cwd=ROOT))
        current=json.loads((ROOT/'manifest.webmanifest').read_text())
        self.assertEqual(current['name'],'Aplikacja Treningowa')
        self.assertEqual(current['short_name'],'Aplikacja Treningowa')
        self.assertIn('Aplikacja Treningowa',current['description'])
        for field in set(old)-{'name','short_name','description'}:
            self.assertEqual(current[field],old[field],field)
        # Issue43 explicitly authorizes Compact Matrix v0.4 CSS; identity/icons remain frozen.
        for name in ['icon.svg','icons/icon-192.png','icons/icon-512.png','icons/icon-maskable-512.png','PushPull_PLAN_PROJEKTU_v1.md']:
            self.assertEqual((ROOT/name).read_bytes(),subprocess.check_output(['git','show',STAGE3+':'+name],cwd=ROOT),name)

    def test_artifact_server_refuses_modified_assets_and_source_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp)
            (Path(tmp)/'app.js').write_text('modified')
            with self.assertRaises(ValueError):verify_release(tmp)
            with self.assertRaises(ValueError):build(tmp)
        with self.assertRaises((OSError,ValueError)):verify_release(ROOT)

    def test_verified_https_headers_mime_and_no_source_or_data_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'dist';build(directory)
            cert=Path(tmp)/'test-cert.pem';key=Path(tmp)/'test-key.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',str(key),'-out',str(cert),'-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-addext','basicConstraints=critical,CA:TRUE'],check=True,capture_output=True)
            server=make_server(directory,port=0,base_path='/PushPull/')
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
            server.socket=context.wrap_socket(server.socket,server_side=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            trust=ssl.create_default_context(cafile=str(cert)) # Actual chain/hostname verification, never ignore TLS errors.
            url=f'https://localhost:{server.server_port}'
            try:
                for name in ['',*FILES]:
                    with urlopen(url+'/PushPull/'+name,context=trust) as response:
                        self.assertEqual(response.status,200)
                        self.assertIn('no-cache',response.headers['Cache-Control'])
                        self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
                        self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
                        self.assertIn('max-age=',response.headers['Strict-Transport-Security'])
                        self.assertTrue(response.read())
                with urlopen(url+'/PushPull/manifest.webmanifest',context=trust) as response:
                    self.assertEqual(response.headers.get_content_type(),'application/manifest+json')
                for path in ['/.git/config','/PushPull/.git/config','/PushPull/tests/fixtures/v1.json','/PushPull/docs/CODEX_HANDOFF.md','/PushPull/backup.json','/PushPull/%2e%2e/app.js','/other/']:
                    with self.assertRaises(HTTPError) as error:urlopen(url+path,context=trust)
                    self.assertEqual(error.exception.code,404)
                with self.assertRaises(HTTPError) as error:urlopen(Request(url+'/PushPull/',data=b'not-uploaded',method='POST'),context=trust)
                self.assertEqual(error.exception.code,405)
            finally:server.shutdown();server.server_close();thread.join()

class PWADeployment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),args=['--no-sandbox'])
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.pw.stop()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='pushpull-pwa-')
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.controller={'directory':self.path/'a','broken':None,'base':'/'}
        build(self.controller['directory'])
        controller=self.controller
        class Handler(ReleaseHandler):
            def __init__(self,*args,**kwargs):super().__init__(*args,directory=controller['directory'],base_path=controller['base'],**kwargs)
            def do_GET(self):
                if controller['broken'] and self.path.split('?')[0].endswith('/app.js'):
                    if controller['broken']=='missing':self.send_error(404);return
                    # A login page, changed file or mixed upload must not become a cached JS resource.
                    body=b'<html>unexpected login or mixed release</html>'
                    self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                super().do_GET()
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        def stop():self.server.shutdown();self.server.server_close();thread.join()
        self.addCleanup(stop)
        self.origin=f'http://127.0.0.1:{self.server.server_port}'
        self.context=self.browser.new_context(service_workers='allow',viewport={'width':390,'height':844},timezone_id='Europe/Warsaw',accept_downloads=True)
        self.addCleanup(self.context.close)
        self.page=self.context.new_page()
        self.accept_dialog=lambda d:d.accept()
        self.page.on('dialog',self.accept_dialog)
    @property
    def url(self):return self.origin+self.controller['base']
    def seed(self):
        self.page.add_init_script(f"if(localStorage.getItem('{KEY}')===null){{localStorage.setItem('{KEY}',{json.dumps(RAW)});localStorage.setItem('{KEY}_backup_test','old backup preserved')}}")
    def poll(self,expression,page=None):
        page=page or self.page
        deadline=time.monotonic()+10
        while not page.evaluate(expression):
            if time.monotonic()>deadline:self.fail('Timed out: '+expression)
            time.sleep(0.02)
    def ready(self,timeout=5000):
        expect(self.page.locator('[data-act=finish]')).to_be_visible(timeout=timeout)
        self.page.evaluate('navigator.serviceWorker.ready')
        self.poll('navigator.serviceWorker.controller !== null')
    def snapshot(self):
        return self.page.evaluate("async()=>{const db=await PushPullDB.open(()=>{throw Error('No DB')});try{if(db.error)throw db.error;return db.export()}finally{db.close()}}")
    def next_release(self,label):
        source=self.path/('source-'+label)
        for name in ASSETS:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
        template=source/'scripts/service-worker.template.js';template.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'scripts/service-worker.template.js',template)
        with (source/'app.js').open('a') as file:file.write('\n// Test release '+label+'\n')
        output=self.path/label;build(output,source);return output
    def wait_update(self):
        self.page.evaluate("""async()=>{
          const r=window.__pwaRegistration=await navigator.serviceWorker.getRegistration();
          const events=window.__pwaUpdateEvents=[];
          const observe=w=>{if(!w)return;const record=()=>events.push({state:w.state,at:performance.now()});record();w.addEventListener('statechange',record)};
          r.addEventListener('updatefound',()=>observe(r.installing),{once:true});
          observe(r.installing);await r.update();
          // A pre-deployment update job may have supplied the old script to
          // both callers. Drain that job before requesting this release.
          // Never retry a failed installer: it has lifecycle events.
          if(!r.installing&&!r.waiting&&events.length===0){
            await new Promise(resolve=>setTimeout(resolve,0));await r.update();
          }
        }""")
        # Poll a synchronous property: a Promise itself is truthy to the polling API.
        # Preserve the assertion and budget; retain lifecycle evidence on failure.
        try:self.poll('window.__pwaRegistration.waiting?.state === "installed"')
        except AssertionError as error:
            states=self.page.evaluate("""()=>{const r=window.__pwaRegistration;return {
              active:r.active?.state,installing:r.installing?.state,waiting:r.waiting?.state,
              events:window.__pwaUpdateEvents};}""")
            self.fail(str(error)+'; worker lifecycle: '+json.dumps(states))
        expected='pushpull-shell-'+json.loads((self.controller['directory']/'release.json').read_text())['release']
        self.waiting_worker=next(w for w in self.context.service_workers if w.evaluate('CACHE')==expected)
    def reopen(self,timeout=5000):
        waiting=getattr(self,'waiting_worker',None)
        if waiting:waiting.evaluate("self.__testActivated=false;self.addEventListener('activate',()=>{self.__testActivated=true})")
        self.page.close()
        if waiting:
            deadline=time.monotonic()+10
            while not waiting.evaluate('self.__testActivated && !self.registration.waiting && self.registration.active?.state === "activated"'):
                if time.monotonic()>deadline:self.fail('Waiting worker did not activate after the final old tab closed')
                time.sleep(0.02)
            self.waiting_worker=None
        self.page=self.context.new_page();self.page.on('dialog',self.accept_dialog);self.page.goto(self.url);self.ready(timeout=timeout)

    def notification_state(self,page=None):
        return (page or self.page).evaluate('''async()=>{const d=await PushPullDB.open(()=>{});try{return {backup:d.export(),drafts:await d.readDrafts(),drive:await d.readDriveState(),revision:d.revision,legacy:d.raw}}finally{d.close()}}''')

    def test_issue44_existing_main_then_waiting_release_keeps_two_tabs_native_editor_and_history(self):
        source=self.path/'notice-main-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(historical_asset('23e1cab',name))
        old_release=self.path/'notice-main';build(old_release,source)
        current=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        # Synthetic large legacy history, opaque extension, and retained Google metadata.
        self.page.evaluate('''async()=>{const d=await PushPullDB.open(()=>{});try{const v=d.value,s=v.sessions[0],e=v.entries[0];for(let n=0;n<250;n++){const id='notice-session-'+n;v.sessions.push({...s,id,seq:10+n,status:'done'});v.entries.push({...e,id:'notice-result-'+n,sessionId:id});}v.extension.notice='x'.repeat(1024*1024);await d.commit(v);const state=await d.readDriveState()??{clientId:'',enabled:false,selected:null,accounts:{},mode:'manual',deviceId:crypto.randomUUID()};state.accounts.synthetic={label:'Synthetic retained account'};await d.writeDriveState(state,state.token??null);}finally{d.close()}}''')
        self.page.reload();self.ready()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PULL-A-1"]').click();open_result_panel(self.page)
        f=self.page.locator('.performanceForm');f.locator('[data-quick=kg]').fill('40');f.locator('[data-quick=reps]').fill('9')
        f.locator('[data-rich-action=toggle]').click();f.locator('[data-rich-action=side-mode][data-row="0"]').click()
        f.locator('[data-row="1"][data-field=kg]').fill('35')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.notification_state()
        # One-time verified index installation is not an ordinary startup.
        self.controller['directory']=current;self.wait_update();self.reopen(timeout=20000)
        self.assertEqual(self.notification_state(),before)
        release=json.loads((current/'release.json').read_text())['release'][:12]
        self.page.locator('[data-tab=settings]').click();expect(self.page.locator('[data-pwa-version]')).to_have_text('Wersja aplikacji: '+release)
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-draft-resume]').click()
        f=self.page.locator('.performanceForm');expect(f.locator('[data-row="1"][data-field=kg]')).to_have_value('35')
        f.locator('[data-row="1"][data-field=kg]').focus()
        self.page.evaluate('window.__keptEditor=document.querySelector(".performanceForm");window.__keptInput=document.activeElement')
        other=self.context.new_page();other.goto(self.url);expect(other.locator('[data-act=finish]')).to_be_visible()
        before=self.notification_state()
        newer=self.next_release('notice-two-tabs');self.controller['directory']=newer;self.wait_update()
        message='Dostępna nowa wersja PushPull. Zapisz bieżące wyniki i zamknij wszystkie okna aplikacji, następnie uruchom ją ponownie.'
        for page in [self.page,other]:expect(page.locator('[data-pwa-notice]')).to_have_text(message,timeout=30000)
        self.assertTrue(self.page.evaluate('window.__keptEditor===document.querySelector(".performanceForm")&&window.__keptInput===document.activeElement'))
        self.assertEqual(self.notification_state(),before)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.close();self.page=other
        self.page.locator('[data-tab=settings]').click();expect(self.page.locator('[data-pwa-version]')).to_have_text('Wersja aplikacji: '+release)
        expect(self.page.locator('[data-pwa-notice]')).to_have_text(message)
        self.context.set_offline(True);self.reopen()
        self.assertEqual(self.notification_state(),before)
        self.page.locator('[data-tab=settings]').click()
        new_id=json.loads((newer/'release.json').read_text())['release'][:12]
        expect(self.page.locator('[data-pwa-version]')).to_have_text('Wersja aplikacji: '+new_id)
        expect(self.page.locator('[data-pwa-notice]')).to_be_hidden()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('.performanceForm [data-row="0"][data-field=kg]')).to_have_value('40')
        expect(self.page.locator('.performanceForm [data-row="1"][data-field=kg]')).to_have_value('35')

    def test_issue44_offline_bad_integrity_retry_and_independent_device_do_not_import_data(self):
        self.page.add_init_script("ServiceWorker.prototype.postMessage=()=>{throw Error('simulated unavailable identity')}")
        self.seed();self.page.goto(self.url);self.ready();before=self.notification_state()
        independent=self.browser.new_context(service_workers='allow');self.addCleanup(independent.close)
        device=independent.new_page();device.goto(self.url);expect(device.locator('[data-act=start]')).to_be_visible()
        device.evaluate('navigator.serviceWorker.ready');device.wait_for_function('()=>navigator.serviceWorker.controller!==null')
        other_before=self.notification_state(device)
        self.assertNotEqual(other_before['backup']['data'],before['backup']['data'])
        self.page.locator('[data-tab=settings]').click();self.context.set_offline(True)
        self.page.locator('[data-pwa-check]').click()
        expect(self.page.locator('[data-pwa-notice]')).to_contain_text('Nie udało się')
        expect(self.page.locator('[data-pwa-notice]')).not_to_contain_text('Dostępna nowa wersja')
        self.assertEqual(self.notification_state(),before)
        self.context.set_offline(False);newer=self.next_release('notice-retry');self.controller['directory']=newer;self.controller['broken']='mismatch'
        self.page.evaluate('''async()=>{const r=await navigator.serviceWorker.getRegistration();r.addEventListener('updatefound',()=>{window.__badWorker=r.installing})}''')
        self.page.locator('[data-pwa-check]').click();self.page.wait_for_function('()=>window.__badWorker?.state==="redundant"')
        expect(self.page.locator('[data-pwa-notice]')).to_contain_text('Nie udało się')
        self.assertEqual(self.notification_state(),before)
        self.assertTrue(self.page.evaluate('async()=>!(await navigator.serviceWorker.getRegistration()).waiting'))
        retry_workers=[];self.context.on('serviceworker',lambda worker:retry_workers.append(worker))
        self.controller['broken']=None;self.page.locator('[data-pwa-check]').click()
        expect(self.page.locator('[data-pwa-notice]')).to_contain_text('Dostępna nowa wersja',timeout=60000)
        expected='pushpull-shell-'+json.loads((newer/'release.json').read_text())['release']
        self.waiting_worker=retry_workers[-1]
        self.assertEqual(self.waiting_worker.evaluate('CACHE'),expected)
        self.context.set_offline(True)
        expect(self.page.locator('[data-pwa-notice]')).to_contain_text('Dostępna nowa wersja') # Already verified/cached, unlike an offline check.
        self.assertEqual(self.notification_state(),before);self.assertEqual(self.notification_state(device),other_before)
        self.reopen();expect(self.page.locator('[data-pwa-notice]')).to_be_hidden()
        self.assertEqual(self.notification_state(),before);self.assertEqual(self.notification_state(device),other_before)

    def test_issue48_main_update_keeps_legacy_data_draft_and_advanced_options_closed(self):
        source=self.path/'advanced-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(historical_asset('af79976',name))
        old_release=self.path/'advanced-old';build(old_release,source)
        current=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-expand="PUSH-A-1"]').click();open_result_panel(self.page)
        self.page.locator('[data-main=kg]').fill('81.25');self.page.locator('[data-main=reps]').fill('7')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.notification_state()
        self.controller['directory']=current;self.wait_update();self.reopen();self.context.set_offline(True)
        self.assertEqual(self.notification_state(),before)
        self.page.locator('[data-tab=settings]').click()
        drawer=self.page.locator('[data-backup-advanced]');expect(drawer).not_to_have_attribute('open','');drawer.locator(':scope > summary').click()
        section=self.page.locator('[data-journal-advanced]')
        expect(section.locator('summary')).to_have_text('Opcje zaawansowane')
        expect(section).not_to_have_attribute('open','');expect(section.locator('[data-enable-journal]')).to_be_hidden()
        section.locator('summary').click();expect(section.locator('[data-enable-journal]')).to_be_visible()
        self.assertEqual(self.notification_state(),before)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('[data-main=kg]')).to_have_value('81.25')
        expect(self.page.locator('[data-main=reps]')).to_have_value('7')

    def test_manifest_png_safe_zone_and_desktop_installability(self):
        self.context=self.pw.chromium.launch_persistent_context(self.path/'profile',executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
        self.addCleanup(self.context.close)
        self.page=self.context.new_page()
        self.seed();self.page.goto(self.url);self.ready()
        result=self.context.new_cdp_session(self.page).send('Page.getAppManifest')
        self.assertEqual(result['errors'],[])
        manifest=json.loads(result['data'])
        self.assertEqual(manifest['id'],'./index.html') # Matches stage-2 implicit identity.
        self.assertEqual(manifest['start_url'],'./index.html')
        self.assertEqual(manifest['scope'],'./')
        self.assertEqual(manifest['display'],'standalone')
        self.assertFalse(manifest['prefer_related_applications'])
        for name,size in [('icons/icon-192.png',192),('icons/icon-512.png',512),('icons/icon-maskable-512.png',512)]:
            body=(ROOT/name).read_bytes();self.assertEqual(body[:8],b'\x89PNG\r\n\x1a\n');self.assertEqual(struct.unpack('>II',body[16:24]),(size,size))
        icon=self.page.evaluate("""async()=>{const image=new Image();image.src='./icons/icon-maskable-512.png';await image.decode();const c=document.createElement('canvas');c.width=c.height=512;const x=c.getContext('2d');x.drawImage(image,0,0);const p=x.getImageData(0,0,512,512).data;let transparent=0,outside=0;for(let i=0;i<p.length;i+=4){if(p[i+3]!==255)transparent++;const col=(i/4)%512,row=Math.floor(i/4/512);if(p[i]>70 && Math.hypot(col+0.5-256,row+0.5-256)>512*0.4)outside++}return {transparent,outside}}""")
        self.assertEqual(icon,{'transparent':0,'outside':0})
        errors=self.context.new_cdp_session(self.page).send('Page.getInstallabilityErrors')['installabilityErrors']
        self.assertEqual(errors,[]) # Desktop diagnostic, not an Android/WebAPK installation claim.

    def test_subpath_offline_export_and_import_under_security_headers(self):
        self.controller['base']='/PushPull/'
        self.seed();self.page.goto(self.url);self.ready()
        before=self.snapshot();self.assertEqual(before['data'],FIXTURE)
        self.context.set_offline(True);self.page.reload();self.ready()
        self.assertEqual(self.snapshot(),before)
        self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_text();self.assertEqual(json.loads(raw),before)
        self.page.locator('#importFile').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':raw.encode()})
        confirm_restore(self.page)
        expect(self.page.locator('h1')).to_have_text('Trening')
        self.assertEqual(self.snapshot()['data'],FIXTURE)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)

    def test_update_after_release_switch_does_not_reuse_old_inflight_check(self):
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-expand="PUSH-A-1"]').click();open_result_panel(self.page)
        self.page.locator('[data-main=kg]').fill('77');self.page.locator('[data-main=reps]').fill('9')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.notification_state();old=self.controller['directory'];new=self.next_release('overlapping-check')
        entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        handler=self.server.RequestHandlerClass;get=handler.do_GET
        def gated_get(request):
            if request.path.split('?')[0]=='/sw.js' and request.directory==old and not entered.is_set():
                entered.set()
                if not release.wait(10):request.send_error(504);return
            return get(request)
        handler.do_GET=gated_get
        self.page.evaluate("()=>{window.__oldUpdate=navigator.serviceWorker.getRegistration().then(r=>r.update())}")
        self.assertTrue(entered.wait(3),'Old-version update must be in flight before the release switch')
        self.controller['directory']=new
        # Enqueue the explicit check before allowing the old script response.
        # The browser coalesces it with that older update job. No timing sleep.
        self.page.expose_function('__releaseOldCheck',release.set)
        self.page.evaluate("""()=>{
          const update=ServiceWorkerRegistration.prototype.update;
          window.__updateObservations=[];
          ServiceWorkerRegistration.prototype.update=function(...args){
            const result=update.apply(this,args);
            result.then(()=>__updateObservations.push({installing:!!this.installing,waiting:!!this.waiting}));
            void window.__releaseOldCheck();return result;
          };
        }""")
        self.wait_update()
        observations=self.page.evaluate('__updateObservations')
        self.assertEqual(observations[0],{'installing':False,'waiting':False})
        self.assertEqual(self.notification_state(),before)
        self.assertTrue(self.page.evaluate('!!navigator.serviceWorker.controller'))
        self.reopen();self.assertEqual(self.notification_state(),before)

    def test_update_waits_for_all_tabs_and_preserves_unsaved_series_and_all_data(self):
        self.seed();self.page.goto(self.url);self.ready()
        before=self.snapshot()
        self.page.locator('[data-expand="PUSH-A-1"]').click();open_result_panel(self.page)
        self.page.locator('[data-series-toggle]').click()
        self.page.locator('[data-series-index="1"][data-field=kg]').fill('77')
        second=self.context.new_page();second.goto(self.url);expect(second.locator('[data-act=finish]')).to_be_visible()
        second.evaluate("navigator.serviceWorker.register('./sw.js',{updateViaCache:'none'})")
        self.controller['directory']=self.next_release('b')
        self.wait_update()
        expect(self.page.locator('[data-series-index="1"][data-field=kg]')).to_have_value('77')
        self.assertEqual(self.snapshot(),before)
        second.close()
        self.assertTrue(self.page.evaluate('navigator.serviceWorker.getRegistration().then(r=>!!r.waiting)'))
        # Save user work before deliberately closing the final old client.
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        saved=self.snapshot()
        self.reopen()
        self.assertEqual(self.snapshot(),saved)
        self.assertEqual(self.snapshot()['data']['entries'][-1]['series'][1]['kg'],'77')
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)
        self.context.set_offline(True);self.reopen()
        self.assertEqual(self.snapshot(),saved)

    def test_issue40_update_preview_and_large_v3_restore_offline_keeps_local_drafts(self):
        source=self.path/'restore-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(historical_asset('8d327a7',name))
        old_release=self.path/'restore-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-expand="PUSH-A-1"]').click();open_result_panel(self.page)
        self.page.locator('[data-main=kg]').fill('81.123');self.page.locator('[data-main=reps]').fill('7')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const v=d.value;v.extension.large='x'.repeat(16*1024*1024);await d.commit(v)}finally{d.close()}}""")
        self.page.reload();self.ready()
        def value():return self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}')
        def drafts():return self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        expected=value();self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_bytes();self.assertGreater(len(raw),16*1024*1024)
        self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const v=d.value;v.exercises['PUSH A'][0].notes='newer local note protected by preimage';await d.commit(v)}finally{d.close()}}""")
        self.page.reload();self.ready();before=value();before_drafts=drafts()
        self.controller['directory']=current_release;self.wait_update()
        # This 16 MiB live fixture tests conversion integrity, not a 5 s startup
        # target. Keep its existing 90 s large-operation budget and report time.
        conversion_started=time.monotonic();self.reopen(timeout=90000);self.context.set_offline(True)
        print('Issue82 16 MiB live v1-to-v2 conversion/reopen ms:',round((time.monotonic()-conversion_started)*1000),flush=True)
        self.assertEqual(value(),before);self.assertEqual(drafts(),before_drafts)
        self.page.locator('[data-tab=settings]').click()
        for text in ['Zapisz kopię na Google Drive','Pobierz kopię na telefon','Pobierz kopię z Google Drive','Importuj kopię z telefonu']:expect(self.page.get_by_text(text,exact=True)).to_be_visible()
        drawer=self.page.locator('[data-backup-advanced]')
        expect(drawer).not_to_have_attribute('open','')
        expect(self.page.locator('[data-drive-action=restore]')).not_to_be_visible()
        drawer.locator(':scope > summary').click()
        expect(self.page.locator('[data-drive-action=restore]')).to_be_visible()
        self.page.evaluate('window.__previewTicks=0;window.__ticker=setInterval(()=>window.__previewTicks++,5)')
        self.page.locator('#importFile').set_input_files({'name':'large-v3.json','mimeType':'application/json','buffer':raw})
        expect(self.page.locator('[data-restore-preview]')).to_be_visible(timeout=90000)
        self.assertGreater(self.page.evaluate('window.__previewTicks'),5);self.page.evaluate('clearInterval(window.__ticker)')
        expect(self.page.locator('[data-restore-preview]')).to_contain_text('Zawartość danych jest różna')
        self.assertEqual(value(),before);self.assertEqual(drafts(),before_drafts)
        confirm_restore(self.page);expect(self.page.locator('[data-restore-success]')).to_contain_text('Przywrócono')
        self.assertEqual(value(),expected);self.assertEqual(drafts(),before_drafts)
        # This is an integrity test, not a 5 s startup performance assertion.
        # The 16 MiB source + preserved preimage still need full validation.
        # Use this large-file test's existing 90 s budget; report the latency.
        reopened=time.monotonic();self.reopen(timeout=90000)
        print('Issue40 restored 16 MiB fixture reopen ms:',round((time.monotonic()-reopened)*1000),flush=True)
        self.assertEqual(value(),expected);self.assertEqual(drafts(),before_drafts)
        expect(self.page.locator('[data-draft-download]')).to_have_count(1)

    def test_issue34_return_continues_version_history_and_dated_gaps_after_pwa_update(self):
        source=self.path/'return-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(historical_asset('3a92fbf',name))
        old_release=self.path/'return-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.page.clock.install(time=datetime(2026,2,1,10,tzinfo=timezone.utc))
        self.seed();self.page.goto(self.url);self.ready()
        def plans():self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        def at(month,day):self.page.clock.set_fixed_time(datetime(2026,month,day,10,tzinfo=timezone.utc))
        def value(page=None):
            return (page or self.page).evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}')
        def drafts():return self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        def form(unit,eid,day):
            self.page.locator('[data-type="'+unit+'"]').click();self.page.locator('#trainingDate').fill(day);self.page.locator('[data-act=start]').click()
            if self.page.locator('[data-expand="'+eid+'"]').get_attribute('aria-expanded')!='true':self.page.locator('[data-expand="'+eid+'"]').click()
            open_result_panel(self.page);return self.page.locator('.performanceForm')
        def save(f):
            f.locator('[type=submit]').click();expect(f).to_have_count(0);expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        def finish():self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible(timeout=60000)
        plans();self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();finish()
        for day,kg in [(2,'100'),(9,'105')]:
            at(2,day);f=form('PUSH A','PUSH-A-1',f'2026-02-{day:02d}')
            f.locator('[data-quick=kg]').fill(kg);f.locator('[data-quick=reps]').fill('10');save(f);finish()
        at(2,10);plans();self.page.locator('#planFile').set_input_files(ROOT/'tests/fixtures/plan-v3.json')
        self.page.locator('[data-plan-save]').click();expect(self.page.get_by_text('Plan zapisany bez aktywacji',exact=True)).to_be_visible()
        self.page.locator('#importedPlanId').select_option('synthetic-v3')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();at(2,11);f=form('TEST-A','TEST-1','2026-02-11')
        f.locator('[data-quick=kg]').fill('20');f.locator('[data-quick=reps]').fill('8');save(f);finish()
        at(8,1);f=form('TEST-B','TEST-5','2026-08-01');f.locator('[data-quick=kg]').fill('20');f.locator('[data-quick=reps]').fill('8')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        # Synthetic update fixture: full native definitions survive without the original imported packet.
        self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{const v=structuredClone(d.value);delete v.trainingJournal.importedPlans;await d.commit(v)}finally{d.close()}}')
        self.page.reload();self.ready();before=self.snapshot();old_drafts=drafts()
        self.controller['directory']=current_release;self.wait_update();self.reopen();self.context.set_offline(True)
        self.assertEqual(self.snapshot(),before);self.assertEqual(drafts(),old_drafts)
        plans();self.page.locator('[data-plan-switch]').click();self.page.locator('#switchPlanId').select_option('v2-owner-2026-10-22')
        confirmations=[]
        def confirm(d):confirmations.append(d.message);d.accept()
        self.page.remove_listener('dialog',self.accept_dialog);self.page.on('dialog',confirm)
        with self.page.expect_download():self.page.locator('[data-switch-activate]').click()
        # Full plan replacement retains/imports preimages; it is a bulk path,
        # separate from the result-save timing acceptance in Issue #82.
        bulk_started=time.monotonic()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible(timeout=60000)
        print('Issue82 historical plan return bulk wait ms:',round((time.monotonic()-bulk_started)*1000),flush=True)
        self.page.remove_listener('dialog',confirm);self.page.on('dialog',self.accept_dialog)
        self.assertTrue(any('statystyki tej wersji pozostają dostępne i będą kontynuowane' in text for text in confirmations))
        active=value();self.assertEqual(active['entries'],before['data']['entries']);self.assertEqual(active['sessions'],before['data']['sessions'])
        self.assertEqual(active['trainingJournal']['sessionSnapshots'],before['data']['trainingJournal']['sessionSnapshots']);self.assertEqual(drafts(),old_drafts)
        expect(self.page.locator('[data-plan-row="v2-owner-2026-10-22"] [data-plan-period]')).to_have_text(['Używany: 01.02.2026 – 10.02.2026','Używany: od 01.08.2026'])
        self.page.locator('[data-plan-switch]').click();self.page.locator('#switchPlanId').select_option('synthetic-v3')
        expect(self.page.locator('[data-switch-activate]')).to_be_enabled();self.page.locator('[data-switch-cancel]').click()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f).to_have_attribute('data-id','TEST-5');expect(f.locator('[data-row="0"][data-field=kg]')).to_have_value('20');save(f);finish()
        self.assertEqual(value()['trainingJournal']['nextUnitId'],'PUSH A')
        at(8,3);f=form('PUSH A','PUSH-A-1','2026-08-03')
        card=self.page.locator('.exercise-card').filter(has=self.page.locator('[data-expand="PUSH-A-1"]'))
        expect(card.locator('.exercise-toggle .last-result')).to_have_text('10 × 105 kg')
        f.locator('[data-quick=kg]').fill('95');f.locator('[data-quick=reps]').fill('10');save(f);finish()
        self.page.locator('[data-type="PUSH A"]').click()
        if card.locator('[data-expand]').get_attribute('aria-expanded')!='true':card.locator('[data-expand]').click()
        card.locator('[data-panel=stats]').click();plot=self.page.locator('svg[aria-label="Wykres Tonaż"]')
        expect(plot.locator('circle[fill="#42e88b"]')).to_have_count(3);expect(plot.locator('polyline')).to_have_count(2)
        self.assertEqual([len(p.get_attribute('points').split()) for p in plot.locator('polyline').all()],[2,1])
        xs=[float(x.get_attribute('cx')) for x in plot.locator('circle[fill="#42e88b"]').all()];self.assertLess(xs[1]-xs[0],20);self.assertGreater(xs[2]-xs[1],250)
        expect(plot.locator('text')).to_have_text(['2026-02-02','2026-08-03'])
        expect(self.page.locator('.stat-table .stat-row')).to_have_count(4)
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=weekly]').click()
        self.page.locator('#weeklyRange [name=from]').fill('2026-02-02');self.page.locator('#weeklyRange [name=to]').fill('2026-08-09');self.page.locator('#weeklyRange button').click()
        expect(self.page.locator('#weeklyPlan')).to_have_value('v2-owner-2026-10-22')
        self.assertEqual(self.page.locator('[data-weekly-metric=tonnage] strong').inner_text().replace('\xa0','').replace(' ',''),'9000kg')
        expect(self.page.locator('[data-weekly-metric=workouts] strong')).to_have_text('3')
        expect(self.page.locator('[data-week="2026-W15"]')).to_contain_text('0 treningów')
        expect(self.page.locator('svg[aria-label="Tygodniowo: Tonaż"] circle')).to_have_count(3)
        expect(self.page.locator('svg[aria-label="Tygodniowo: Tonaż"] polyline')).to_have_count(2)
        saved=value();self.assertEqual(saved['entries'][:len(before['data']['entries'])],before['data']['entries'])
        self.assertEqual(saved['trainingJournal']['sessionSnapshots'][:-1],before['data']['trainingJournal']['sessionSnapshots'])
        self.assertEqual(drafts(),[]);self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_bytes();other=self.browser.new_context(service_workers='block');self.addCleanup(other.close)
        page=other.new_page();page.on('dialog',lambda d:d.accept());page.goto(self.url);page.locator('[data-tab=settings]').click()
        page.locator('#importFile').set_input_files({'name':'continuous-plans.json','mimeType':'application/json','buffer':raw})
        confirm_restore(page)
        expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible(timeout=30000);self.assertEqual(value(page),saved)
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.accept_dialog);self.page.goto(self.url)
        self.page.locator('[data-type="PUSH A"]').click();expect(self.page.locator('[data-expand="PUSH-A-1"] .last-result')).to_have_text('10 × 95 kg')
        self.assertEqual(value(),saved)

    def test_issue36_change_age_after_pwa_update_edit_restore_and_offline_restart(self):
        source=self.path/'issue36-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(historical_asset('fd708b0',name))
        old_release=self.path/'issue36-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.page.clock.install(time=datetime(2026,10,23,10,tzinfo=timezone.utc))
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        def card(page=None):
            page=page or self.page
            return page.locator('.exercise-card').filter(has=page.locator('[data-expand="PULL-B-1"]'))
        def open_result(day):
            self.page.locator('[data-type="PULL B"]').click();self.page.locator('#trainingDate').fill('2026-10-'+day)
            self.page.locator('[data-act=start]').click()
            if card().locator('[data-expand]').get_attribute('aria-expanded')!='true':card().locator('[data-expand]').click()
            open_result_panel(card())
            return self.page.locator('.performanceForm')
        def save(f):
            f.locator('[type=submit]').click();expect(f).to_have_count(0)
            expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        for day in ['19','20','21']:
            f=open_result(day);f.locator('[data-quick=kg]').fill('105');f.locator('[data-quick=reps]').fill('15');save(f)
            self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        f=open_result('22');f.locator('[data-quick=kg]').fill('95');f.locator('[data-quick=reps]').fill('12')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.snapshot()
        def drafts():
            return self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        old_drafts=drafts()
        self.controller['directory']=current_release;self.wait_update();self.reopen();self.context.set_offline(True)
        expect(card().locator('.exercise-toggle .last-result')).to_have_text('L/P 15 × 105 kg')
        expect(card().locator('[data-result-change]')).to_have_text('· Ostatnia zmiana: 3 sesje temu')
        self.assertEqual(self.snapshot(),before);self.assertEqual(drafts(),old_drafts)
        self.assertEqual(card().locator('[data-result-change]').count(),1)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-row="0"][data-field=kg]')).to_have_value('95')
        expect(card().locator('[data-result-change]')).to_contain_text('3 sesje temu')
        save(f)
        expect(card().locator('.exercise-toggle .last-result')).to_have_text('L/P 12 × 95 kg')
        expect(card().locator('[data-result-change]')).to_contain_text('3 sesje temu') # In-progress session does not count.
        sid=self.snapshot()['data']['activeId']
        self.page.locator('[data-act=finish]').click();self.page.locator('[data-type="PULL B"]').click()
        expect(card().locator('[data-result-change]')).to_contain_text('1 sesję temu') # Decrease is a change, too.
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="2026-10-22"]').click()
        self.page.locator(f'[data-act=openSession][data-id="{sid}"]').click()
        expect(card().locator('[data-result-change]')).to_have_count(0) # Historical result stays unannotated.
        if card().locator('[data-expand]').get_attribute('aria-expanded')!='true':card().locator('[data-expand]').click()
        open_result_panel(card());f=self.page.locator('.performanceForm')
        f.locator('[data-quick=kg]').fill('105');f.locator('[data-quick=reps]').fill('15');save(f)
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-type="PULL B"]').click()
        expect(card().locator('[data-result-change]')).to_contain_text('4 sesje temu')
        expected=self.snapshot();self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.accept_dialog);self.page.goto(self.url)
        expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-type="PULL B"]').click()
        expect(card().locator('[data-result-change]')).to_contain_text('4 sesje temu')
        self.assertEqual(self.snapshot(),expected);self.assertEqual(drafts(),[])
        self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_bytes()
        other=self.browser.new_context(service_workers='block');self.addCleanup(other.close)
        page=other.new_page();page.on('dialog',lambda d:d.accept());page.goto(self.url);page.locator('[data-tab=settings]').click()
        page.locator('#importFile').set_input_files({'name':'change-age.json','mimeType':'application/json','buffer':raw})
        confirm_restore(page)
        expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible(timeout=30000)
        page.locator('[data-tab=training]').click();page.locator('[data-type="PULL B"]').click()
        expect(card(page).locator('.exercise-toggle .last-result')).to_have_text('L/P 15 × 105 kg')
        expect(card(page).locator('[data-result-change]')).to_contain_text('4 sesje temu')
        actual=page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}')
        self.assertEqual(actual,expected['data']);self.assertEqual(self.snapshot(),expected)

    def test_issue34_saved_plan_return_periods_draft_and_cycle_after_existing_pwa_update(self):
        source=self.path/'issue34-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(historical_asset('c40e173',name))
        old_release=self.path/'issue34-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.page.clock.install(time=datetime(2026,10,21,10,tzinfo=timezone.utc))
        self.seed();self.page.goto(self.url);self.ready()
        def plans():
            self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        def value(page=None):
            return (page or self.page).evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}')
        def drafts():
            return self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        plans();self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PULL-A-1"]').click();open_result_panel(self.page)
        f=self.page.locator('.performanceForm');f.locator('[data-quick=kg]').fill('105');f.locator('[data-quick=reps]').fill('15')
        f.locator('[type=submit]').click();expect(f).to_have_count(0)
        open_result_panel(self.page);f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click()
        f.locator('[data-rich-action=side-mode][data-row="4"]').click();f.locator('[data-row="4"][data-field=reps]').fill('12');f.locator('[data-row="5"][data-field=reps]').fill('14')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        plans();self.page.locator('#planFile').set_input_files(ROOT/'tests/fixtures/plan-v3.json')
        self.page.locator('[data-plan-save]').click();expect(self.page.get_by_text('Plan zapisany bez aktywacji',exact=True)).to_be_visible()
        before=self.snapshot();old_drafts=drafts();sid=before['data']['activeId']
        self.controller['directory']=current_release;self.wait_update();self.reopen();self.context.set_offline(True)
        self.assertEqual(self.snapshot(),before);self.assertEqual(drafts(),old_drafts)
        plans();self.page.locator('[data-plan-switch]').click();self.page.locator('#switchPlanId').select_option('synthetic-v3')
        self.assertEqual(self.page.locator('#switchPlanId option').evaluate_all('(els)=>els.map(e=>e.value)'),['','synthetic-v3'])
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.assertEqual(self.snapshot(),before);self.assertEqual(drafts(),old_drafts)
        cancel=lambda d:d.dismiss();self.page.remove_listener('dialog',self.accept_dialog);self.page.on('dialog',cancel)
        self.page.locator('[data-switch-activate]').click();self.page.remove_listener('dialog',cancel);self.page.on('dialog',self.accept_dialog)
        self.assertEqual(self.snapshot(),before)
        self.page.clock.set_fixed_time(datetime(2026,10,22,22,30,tzinfo=timezone.utc)) # 23 October in Warsaw.
        with self.page.expect_download():self.page.locator('[data-switch-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.assertEqual(value()['trainingJournal']['nextUnitId'],'TEST-A')
        self.page.clock.set_fixed_time(datetime(2026,10,25,12,tzinfo=timezone.utc))
        self.page.locator('[data-plan-switch]').click();self.page.locator('#switchPlanId').select_option('v2-owner-2026-10-22')
        self.page.locator('[data-switch-preview]').click();expect(self.page.locator('#importedPlanId')).to_have_value('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-switch-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        current=value();self.assertEqual(current['entries'],before['data']['entries']);self.assertEqual(current['sessions'],before['data']['sessions'])
        self.assertEqual(current['trainingJournal']['sessionSnapshots'],before['data']['trainingJournal']['sessionSnapshots']);self.assertEqual(drafts(),old_drafts)
        self.assertEqual(len(current['trainingJournal']['importedPlans']),1);self.assertEqual(current['trainingJournal']['model'],before['data']['trainingJournal']['model'])
        v2=self.page.locator('[data-plan-row="v2-owner-2026-10-22"]');v3=self.page.locator('[data-plan-row="synthetic-v3"]')
        expect(v2.locator('[data-plan-period]')).to_have_text(['Używany: 21.10.2026 – 23.10.2026','Używany: od 25.10.2026'])
        expect(v3.locator('[data-plan-period]')).to_have_text(['Używany: 23.10.2026 – 25.10.2026'])
        expect(v2).to_contain_text('Używany w 2 okresach');expect(self.page.locator('[data-plan-activate]')).to_have_count(0)
        self.reopen();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-row="4"][data-field=reps]')).to_have_value('12');expect(f.locator('[data-row="5"][data-field=reps]')).to_have_value('14')
        f.locator('[type=submit]').click();expect(f).to_have_count(0)
        expect(self.page.locator('.exercise-toggle .last-series-row')).to_have_text(['Seria 1: L/P 15 × 105 kg','Seria 2: L/P 15 × 105 kg','Seria 3: L 12 × 105 kg · P 14 × 105 kg'])
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible(timeout=60000)
        self.assertEqual(value()['trainingJournal']['nextUnitId'],'PUSH A') # Old PULL A must not advance this new V2 period.
        self.page.locator('[data-act=start]').click();self.ready()
        self.assertEqual(value()['sessions'][-1]['type'],'PUSH A')
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible(timeout=60000);self.assertEqual(value()['trainingJournal']['nextUnitId'],'PULL A')
        saved=value();self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_bytes();other=self.browser.new_context(service_workers='block',accept_downloads=True);self.addCleanup(other.close)
        page=other.new_page();messages=[]
        def accept_restore(d):messages.append((d.type,d.message));d.accept()
        page.on('dialog',accept_restore);page.goto(self.url);page.locator('[data-tab=settings]').click()
        page.locator('#importFile').set_input_files({'name':'full-periods.json','mimeType':'application/json','buffer':raw})
        confirm_restore(page)
        try:expect(page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible(timeout=30000)
        except AssertionError as error:self.fail(str(error)+'\nRestore dialogs: '+repr(messages))
        self.assertEqual(value(page),saved)
        page.locator('[data-tab=settings]').click();page.locator('[data-view=plans]').click()
        expect(page.locator('[data-plan-row="v2-owner-2026-10-22"] [data-plan-period]')).to_have_text(['Używany: 21.10.2026 – 23.10.2026','Używany: od 25.10.2026'])
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

    def test_issue32_compact_results_after_update_preserve_saved_history_and_asymmetric_draft(self):
        source=self.path/'issue32-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(historical_asset('084f470',name))
        old_release=self.path/'issue32-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL B"]').click();self.page.locator('[data-act=start]').click()
        card=self.page.locator('.exercise-card').filter(has=self.page.locator('[data-expand="PULL-B-1"]'))
        card.locator('[data-expand]').click();open_result_panel(self.page)
        f=self.page.locator('.performanceForm');f.locator('[data-quick=kg]').fill('105');f.locator('[data-quick=reps]').fill('15')
        f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        expect(card.locator('.exercise-toggle .last-series-row')).to_have_count(6) # Reproduces the old Android symptom.
        open_result_panel(self.page);f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click()
        f.locator('[data-rich-action=side-mode][data-row="4"]').click()
        f.locator('[data-row="4"][data-field=reps]').fill('12');f.locator('[data-row="5"][data-field=reps]').fill('14')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.snapshot();sid=before['data']['activeId']
        draft=lambda:self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        old_drafts=draft()
        # One-time v1 conversion plus index installation; all data assertions stay exact.
        self.controller['directory']=current_release;self.wait_update();self.reopen(timeout=20000);self.context.set_offline(True)
        self.assertEqual(self.snapshot(),before);self.assertEqual(draft(),old_drafts)
        card=self.page.locator('.exercise-card').filter(has=self.page.locator('[data-expand="PULL-B-1"]'))
        expect(card.locator('.exercise-toggle .last-result')).to_have_text('L/P 15 × 105 kg')
        expect(card.locator('.exercise-toggle .last-series-row')).to_have_count(0)
        self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-row="4"][data-field=reps]')).to_have_value('12');expect(f.locator('[data-row="5"][data-field=reps]')).to_have_value('14')
        f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        expected=['Seria 1: L/P 15 × 105 kg','Seria 2: L/P 15 × 105 kg','Seria 3: L 12 × 105 kg · P 14 × 105 kg']
        expect(card.locator('.exercise-toggle .last-series-row')).to_have_text(expected)
        saved=self.snapshot();self.assertEqual(saved['data']['trainingJournal']['sessionSnapshots'],before['data']['trainingJournal']['sessionSnapshots'])
        self.assertEqual(saved['data']['entries'][:-1],before['data']['entries'][:-1])
        self.assertEqual([r['id'] for r in saved['data']['entries'][-1]['performance']['rows']],[r['id'] for r in before['data']['entries'][-1]['performance']['rows']])
        self.assertEqual(draft(),[]);self.reopen();self.assertEqual(self.snapshot(),saved)
        self.page.locator('[data-tab=calendar]').click();self.page.locator(f'[data-act=openSession][data-id="{sid}"]').click()
        card=self.page.locator('.exercise-card').filter(has=self.page.locator('[data-expand="PULL-B-1"]'))
        expect(card.locator('.exercise-toggle .last-series-row')).to_have_text(expected)
        card.locator('[data-expand]').click();self.page.locator('[data-panel=stats]').click()
        expect(self.page.locator('.stat-tile').first).to_contain_text('9030')
        self.assertEqual(self.snapshot(),saved)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

    def test_issue30_update_preserves_active_plan_drafts_snapshots_and_offline_statistics(self):
        source=self.path/'issue30-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/name).read_bytes() if name=='model/plan-overview.mjs' else historical_asset('133bbd7',name))
        old_release=self.path/'issue30-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-preview-v2]').click()
        with self.page.expect_download():self.page.locator('[data-activate-v2]').click()
        expect(self.page.get_by_text('V2 aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('#trainingDate').fill('2026-10-20');self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PULL-A-1"]').click();open_result_panel(self.page)
        f=self.page.locator('.performanceForm');f.locator('[data-quick=kg]').fill('10');f.locator('[data-quick=reps]').fill('10')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.snapshot()
        drafts=self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        self.controller['directory']=current_release;self.wait_update();self.reopen();self.context.set_offline(True)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}'),drafts)
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        expect(self.page.locator('[data-current-plan]')).to_be_visible();expect(self.page.locator('[data-plan-activate]')).to_have_count(0)
        self.page.locator('[data-view=data]').click();self.page.locator('[data-view=weekly]').click()
        expect(self.page.locator('#weeklyPlan')).to_have_value('v2-owner-2026-10-22');expect(self.page.locator('[data-weekly-metric=workouts] strong')).to_have_text('0')
        self.assertEqual(self.snapshot(),before)
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-draft-resume]').click()
        self.page.locator('[data-rich-action=toggle]').click()
        expect(self.page.locator('[data-row="0"][data-field=kg]')).to_have_value('10')
        self.page.locator('.performanceForm [type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        saved=self.snapshot();self.assertEqual(saved['data']['trainingJournal']['activations'],before['data']['trainingJournal']['activations'])
        self.assertEqual(saved['data']['trainingJournal']['sessionSnapshots'],before['data']['trainingJournal']['sessionSnapshots'])
        self.page.reload();self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=weekly]').click()
        self.page.locator('#weeklyRange [name=from]').fill('2026-10-19');self.page.locator('#weeklyRange [name=to]').fill('2026-10-25');self.page.locator('#weeklyRange button').click()
        expect(self.page.locator('[data-weekly-metric=tonnage] strong')).to_have_text('600 kg')
        expect(self.page.locator('[data-weekly-metric=sets] strong')).to_have_text('6')
        self.assertEqual(self.snapshot(),saved)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

    def test_issue29_update_recovers_old_asymmetric_draft_and_active_v2_without_reactivation(self):
        source=self.path/'issue29-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/name).read_bytes() if name=='model/plan-overview.mjs' else historical_asset('3c51bc9',name))
        old_release=self.path/'issue29-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-preview-v2]').click()
        with self.page.expect_download():self.page.locator('[data-activate-v2]').click()
        expect(self.page.get_by_text('V2 aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click();self.ready()
        self.page.locator('[data-expand="PULL-A-1"]').click();open_result_panel(self.page)
        form=self.page.locator('.performanceForm');form.locator('[data-rich-action=toggle]').click()
        form.locator('[data-quick=kg]').fill('40');form.locator('[data-quick=reps]').fill('9')
        for row in [0,2,4]:form.locator(f'[data-rich-action=copy][data-row="{row}"]').click()
        form.locator('[data-row="1"][data-field=kg]').fill('35')
        expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.snapshot()
        old_draft=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return (await db.readDrafts())[0]}finally{db.close()}}')
        self.assertNotIn('sidePairs',old_draft['value'])
        self.controller['directory']=current_release;self.wait_update();self.reopen()
        self.assertEqual(self.snapshot(),before)
        self.context.set_offline(True)
        self.page.locator('[data-draft-resume]').click();form=self.page.locator('.performanceForm')
        expect(form.get_by_label('Ciężar (kg)',exact=True)).to_be_visible()
        expect(form.locator('[data-side-exception]').first).to_be_visible()
        expect(form.locator('[data-row="0"][data-field=kg]')).to_have_value('40')
        expect(form.locator('[data-row="1"][data-field=kg]')).to_have_value('35')
        form.locator('[data-row="0"][data-field=kg]').fill('41')
        expect(form.locator('[data-row="1"][data-field=kg]')).to_have_value('35')
        expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click()
        form=self.page.locator('.performanceForm');expect(form.locator('[data-row="0"][data-field=kg]')).to_have_value('41')
        form.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        saved=self.snapshot()['data'];rows=saved['entries'][-1]['performance']['rows']
        self.assertEqual([r['id'] for r in rows],[r['id'] for r in old_draft['value']['performance']['rows']])
        self.assertEqual(saved['sessions'],before['data']['sessions'])
        self.assertEqual(saved['trainingJournal']['sessionSnapshots'],before['data']['trainingJournal']['sessionSnapshots'])
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        expect(self.page.locator('[data-current-plan]')).to_be_visible()
        expect(self.page.locator('[data-plan-activate]')).to_have_count(0)
        self.assertEqual(self.snapshot()['data'],saved)

    def test_issue21_plan_import_offline_after_real_main_update_retains_history_and_draft(self):
        # Upgrade the actual pre-import main release on one origin, no clearing data.
        source=self.path/'issue21-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/name).read_bytes() if name in {'model/plan-import.mjs','model/plan-overview.mjs'} else historical_asset('ef0dec6',name))
        old=self.path/'issue21-old';build(old,source);self.controller['directory']=old
        self.seed();self.page.goto(self.url);self.ready();before=self.snapshot()
        self.page.locator('[data-expand="PUSH-A-1"]').click();open_result_panel(self.page)
        self.page.locator('[data-main=kg]').fill('63');self.page.locator('[data-main=reps]').fill('7')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.controller['directory']=self.next_release('issue21-plan-update');self.wait_update();self.reopen()
        self.assertEqual(self.snapshot(),before)
        self.context.set_offline(True)
        self.page.locator('[data-draft-resume]').click();expect(self.page.locator('[data-main=kg]')).to_have_value('63')
        self.page.locator('[data-tab=settings]').click()
        self.page.locator('[data-view=plans]').click()
        plan=(ROOT/'tests/fixtures/plan-v3.json').read_bytes()
        self.page.locator('#planFile').set_input_files({'name':'test-v3.json','mimeType':'application/json','buffer':plan})
        expect(self.page.locator('[data-plan-preview]')).to_be_visible()
        self.page.locator('[data-plan-save]').click();expect(self.page.get_by_text('Plan zapisany bez aktywacji',exact=True)).to_be_visible()
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.assertEqual(self.snapshot()['data']['sessions'],before['data']['sessions'])
        self.page.locator('[data-tab=training]').click();open_result_panel(self.page)
        expect(self.page.locator('[data-main=kg]')).to_have_value('63')
        self.page.locator('.seriesResultForm [type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.page.locator('[data-act=finish]').click();self.page.locator('[data-type="TEST-B"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="TEST-4"]').click();open_result_panel(self.page)
        f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click()
        for el in f.locator('[data-field=kg]').all():el.fill('21')
        for el in f.locator('[data-field=reps]').all():el.fill('9')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.reopen();self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('.performanceForm [data-field=kg]')).to_have_count(4)
        self.page.locator('.performanceForm [type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        saved=self.snapshot();self.reopen();self.assertEqual(self.snapshot(),saved)
        self.assertEqual(saved['data']['entries'][-1]['performance']['rows'][0]['segments'][1]['kg'],'21')

    def test_issue26_update_from_conflict_preserves_data_copies_drafts_and_disables_automation(self):
        from test_drive_sync import MockGoogle
        source=self.path/'issue26-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/name).read_bytes() if name in {'model/plan-import.mjs','model/plan-overview.mjs'} else historical_asset('e93a4a5',name))
        old_release=self.path/'issue26-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        mock=MockGoogle();mock.install(self.context)
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click()
        self.page.locator('#driveConfig input').fill('123-test.apps.googleusercontent.com')
        self.page.locator('#driveConfig button').click();self.page.locator('[data-drive-action=connect]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Zsynchronizowano')
        old_files=dict(mock.files)
        self.page.locator('[data-tab=training]').click()
        self.page.locator('[data-expand="PUSH-A-1"]').click();open_result_panel(self.page)
        self.page.locator('[data-main=kg]').fill('84.125')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.snapshot()
        meta=self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{
          const s=await db.readDriveState();const node=await (await import('./model/drive-sync.mjs')).makeNode(JSON.stringify(db.export()),[]);
          s.accounts['mock-account'].base=[crypto.randomUUID()];s.accounts['mock-account'].ackRevision=18;
          s.accounts['mock-account'].outbox={node,revision:19};s.accounts['mock-account'].resolution={id:'old-resolution'};
          await db.writeDriveState(s,s.token);return s;
        }finally{db.close()}}""")
        drafts=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')
        self.controller['directory']=current_release;self.wait_update()
        # No forced reload of the old form. Activation waits for old clients.
        expect(self.page.locator('[data-main=kg]')).to_have_value('84.125')
        count=mock.posts;self.reopen()
        self.assertEqual(self.snapshot(),before)
        current=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return {meta:await db.readDriveState(),drafts:await db.readDrafts()}}finally{db.close()}}')
        self.assertFalse(current['meta']['enabled']);self.assertEqual(current['meta']['mode'],'manual')
        self.assertEqual(current['meta']['accounts'],meta['accounts']);self.assertEqual(current['drafts'],drafts)
        self.context.set_offline(True);self.page.reload();self.ready()
        self.page.locator('[data-draft-resume]').click();expect(self.page.locator('[data-main=kg]')).to_have_value('84.125')
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        today=self.snapshot();self.assertEqual(today['data']['entries'][-1]['kg'],'84.125')
        self.context.set_offline(False);self.page.locator('[data-tab=settings]').click()
        self.page.locator('[data-drive-action=connect]').click();expect(self.page.locator('[data-drive-action=connect]')).to_be_hidden()
        self.assertEqual(mock.posts,count)
        expect(self.page.locator('[data-drive-diagnostics]')).to_have_count(0)
        self.page.locator('[data-drive-action=upload]').click()
        expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zapisana i zweryfikowana')
        self.assertEqual(mock.posts,count+1)
        for id,old in old_files.items():self.assertEqual(mock.files[id],old)
        latest=list(mock.files.values())[-1]
        parsed=self.page.evaluate('async text=>(await import("./model/drive-sync.mjs")).inspectBackup(JSON.parse(text).backup)',latest['text'])
        self.assertEqual(parsed['data'],today['data'])
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)

    def test_issue14_upgrade_saved_skeleton_draft_and_independent_source_pair(self):
        # Real pre-fix build + persisted IDB + waiting SW; never reset app data.
        source=self.path/'issue14-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/name).read_bytes() if name in {'model/plan-overview.mjs','model/plan-import.mjs','model/google-drive.mjs','model/drive-sync.mjs'} else historical_asset('cf9b765',name))
        old_release=self.path/'issue14-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL B"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PULL-B-6"]').click();open_result_panel(self.page)
        form=self.page.locator('.seriesResultForm')
        form.locator('[data-main=kg]').fill('73');form.locator('[data-main=reps]').fill('9')
        expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.snapshot();old_session=before['data']['activeId']
        self.controller['directory']=current_release;self.wait_update();self.reopen()
        self.assertEqual(self.snapshot(),before)
        expect(self.page.locator('[data-expand="PULL-B-6"]')).to_be_visible()
        expect(self.page.locator('[data-expand="PULL-B-6-SKI"]')).to_have_count(0)
        self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('[data-main=kg]')).to_have_value('73')
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        historical=self.snapshot()['data']['entries'][-1]
        self.assertEqual(historical['exerciseId'],'PULL-B-6')
        self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL B"]').click()
        # Cancel the explicit source revision; no silent persistent change.
        dismiss=lambda d:d.dismiss()
        self.page.remove_listener('dialog',self.accept_dialog);self.page.on('dialog',dismiss)
        pre_start=self.snapshot();self.page.locator('[data-act=start]').click()
        # Keep the dismiss handler installed until the deferred operation has
        # actually displayed and handled its confirmation dialog.
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertEqual(self.snapshot(),pre_start)
        self.page.remove_listener('dialog',dismiss);self.page.on('dialog',self.accept_dialog)
        self.page.locator('[data-act=start]').click();self.ready()
        expect(self.page.locator('.exercise-card')).to_have_count(10)
        expect(self.page.locator('[data-expand="PULL-B-7"] .num')).to_have_text('7')
        for eid,number,kg in [('PULL-B-6-SKI','6A','20'),('PULL-B-6-SHRUGS','6B','10')]:
            button=self.page.locator(f'[data-expand="{eid}"]')
            expect(button.locator('.num')).to_have_text(number)
            expect(button).to_contain_text('Brak zapisanego wyniku')
            expect(button).to_contain_text('2 × 8–10 | tempo do uzupełnienia | RIR do uzupełnienia')
            button.click();open_result_panel(self.page)
            form=self.page.locator('.seriesResultForm')
            expect(form.locator('[data-main=kg]')).to_have_value('')
            expect(form.locator('[data-main=reps]')).to_have_value('')
            form.locator('[data-main=kg]').fill(kg);form.locator('[data-main=reps]').fill('8')
            expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.locator('[data-expand="PULL-B-6-SKI"]').click();open_result_panel(self.page)
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        # Save A, lose the page, resume B offline with every series intact.
        self.context.set_offline(True);self.reopen()
        expect(self.page.locator('[data-draft-resume]')).to_have_count(1)
        self.page.locator('[data-draft-resume]').click()
        form=self.page.locator('.seriesResultForm')
        expect(form).to_have_attribute('data-id','PULL-B-6-SHRUGS')
        expect(form.locator('[data-main=kg]')).to_have_value('10')
        form.locator('[data-series-toggle]').click()
        expect(form.locator('[data-series-index][data-field=kg]')).to_have_count(2)
        form.locator('[type=submit]').click();expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        state=self.snapshot()['data']
        self.assertEqual(state['entries'][:-2],pre_start['data']['entries'])
        self.assertEqual(state['exercises']['PULL B'][:9],pre_start['data']['exercises']['PULL B'])
        self.assertEqual([e['exerciseId'] for e in state['entries'][-2:]],['PULL-B-6-SKI','PULL-B-6-SHRUGS'])
        self.assertTrue(all(len(e['series'])==2 for e in state['entries'][-2:]))
        for eid,total in [('PULL-B-6-SKI','320'),('PULL-B-6-SHRUGS','160')]:
            self.page.locator(f'[data-expand="{eid}"]').click();self.page.locator('[data-panel=stats]').click()
            expect(self.page.locator('.stat-tile').first).to_contain_text(total)
            self.page.locator('[data-panel=history]').click()
            expect(self.page.locator('.panel .entry')).to_have_count(1)
        self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_bytes()
        self.page.locator('#importFile').set_input_files({'name':'pair.json','mimeType':'application/json','buffer':raw})
        confirm_restore(self.page)
        self.ready();self.assertEqual(self.snapshot()['data'],state)
        self.page.locator('[data-tab=calendar]').click()
        self.page.locator(f'[data-act=openSession][data-id="{old_session}"]').click()
        expect(self.page.locator('[data-expand="PULL-B-6"]')).to_contain_text('73 kg')
        expect(self.page.locator('[data-expand="PULL-B-6-SKI"]')).to_have_count(0)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)

    def test_issue17_card_copy_after_update_preserves_saved_sessions_and_drafts(self):
        source=self.path/'issue17-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/name).read_bytes() if name in {'model/plan-overview.mjs','model/plan-import.mjs','model/google-drive.mjs','model/drive-sync.mjs'} else historical_asset('16e131a',name))
        old_release=self.path/'issue17-old';build(old_release,source)
        current_release=self.controller['directory']
        def check_cards():
            for eid,number,name in [('PULL-B-6-SKI','6A','Narciarz'),('PULL-B-6-SHRUGS','6B','Szrugsy')]:
                button=self.page.locator(f'[data-expand="{eid}"]')
                expect(button.locator('.num')).to_have_text(number)
                expect(button.locator('.name')).to_have_text(name)
                expect(button.locator('.exercise-description')).to_have_count(0)
                for text in ['PULL-B','Para A/B','Superseria','szkielet źródłowy','2 rundy']:
                    expect(button).not_to_contain_text(text)
        def drafts():
            return self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')
        for mode in ['source','observed','v2']:
            with self.subTest(mode=mode):
                self.context.close();self.context=self.browser.new_context(service_workers='allow',viewport={'width':390,'height':844},accept_downloads=True)
                self.page=self.context.new_page();self.page.on('dialog',self.accept_dialog)
                self.controller['directory']=old_release
                self.seed();self.page.goto(self.url);self.ready()
                self.page.locator('[data-act=finish]').click()
                if mode!='source':
                    self.page.locator('[data-tab=settings]').click()
                    if mode=='v2':
                        self.page.locator('[data-preview-v2]').click();button='[data-activate-v2]'
                    else:button='[data-enable-journal]'
                    with self.page.expect_download():self.page.locator(button).click()
                    self.page.locator('[data-tab=training]').click()
                self.page.locator('[data-type="PULL B"]').click();self.page.locator('[data-act=start]').click();self.ready()
                for eid,kg in [('PULL-B-6-SKI','20'),('PULL-B-6-SHRUGS','10')]:
                    self.page.locator(f'[data-expand="{eid}"]').click();open_result_panel(self.page)
                    form=self.page.locator('.performanceForm' if mode=='v2' else '.seriesResultForm')
                    if mode=='v2':
                        form.locator('[data-rich-action=toggle]').click()
                        for field,value in [('kg',kg),('reps','8')]:
                            for el in form.locator(f'input[data-field={field}]').all():el.fill(value)
                    else:
                        form.locator('[data-main=kg]').fill(kg);form.locator('[data-main=reps]').fill('8')
                    expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
                    if eid.endswith('SKI'):
                        form.locator('[type=submit]').click();expect(self.page.locator('form[data-session]')).to_have_count(0)
                before=self.snapshot();saved_drafts=drafts();sid=before['data']['activeId']
                self.controller['directory']=current_release;self.wait_update();self.reopen()
                check_cards();self.assertEqual(self.snapshot(),before);self.assertEqual(drafts(),saved_drafts)
                # Calendar uses the same labels for stored legacy and native snapshots.
                self.page.locator('[data-tab=calendar]').click()
                self.page.locator(f'[data-act=openSession][data-id="{sid}"]').click();check_cards()
                self.assertEqual(self.snapshot(),before);self.assertEqual(drafts(),saved_drafts)
                self.page.locator('[data-tab=training]').click();self.page.locator('[data-draft-resume]').click()
                form=self.page.locator('.performanceForm' if mode=='v2' else '.seriesResultForm')
                expect(form).to_have_attribute('data-id','PULL-B-6-SHRUGS')
                expect(form.locator('[data-row="0"][data-field=kg]' if mode=='v2' else '[data-main=kg]')).to_have_value('10')
                form.locator('[type=submit]').click();expect(self.page.locator('form[data-session]')).to_have_count(0)
                self.assertEqual(drafts(),[])
                self.assertEqual(self.snapshot()['data']['entries'][:-1],before['data']['entries'])
                self.page.locator('[data-act=finish]').click()
                self.page.locator('[data-type="PULL B"]').click();check_cards()
                self.page.locator('[data-act=start]').click();self.ready();check_cards()

    def failed_install(self,mode):
        self.seed();self.page.goto(self.url);self.ready()
        before=self.snapshot()
        self.controller['directory']=self.next_release('broken-'+mode);self.controller['broken']=mode
        new_cache='pushpull-shell-'+json.loads((self.controller['directory']/'release.json').read_text())['release']
        # Observe the actual installing worker becoming redundant after install failure.
        outcome=self.page.evaluate("""async()=>{const r=await navigator.serviceWorker.getRegistration();const result=new Promise(resolve=>r.addEventListener('updatefound',()=>{const w=r.installing;w.addEventListener('statechange',()=>{if(w.state==='redundant')resolve(w.state)})},{once:true}));await r.update();return result}""")
        self.assertEqual(outcome,'redundant')
        self.assertFalse(self.page.evaluate('(name)=>caches.has(name)',new_cache))
        self.context.set_offline(True);self.page.reload();self.ready()
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)
    def test_missing_asset_keeps_previous_offline_release(self):self.failed_install('missing')
    def test_hash_or_login_html_mismatch_keeps_previous_offline_release(self):self.failed_install('wrong-body')

    def test_model_bridge_offline_restart_and_worker_update(self):
        self.seed();self.page.goto(self.url);self.ready()
        self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{await db.prepareModel({ownerId:'offline-test',backupText:JSON.stringify(db.export())})}finally{db.close()}}""")
        self.reopen()
        # Drain app.js's asynchronous registration before swapping the served release.
        self.page.evaluate("navigator.serviceWorker.register('./sw.js',{updateViaCache:'none'}).then(r=>r.update())")
        before=self.snapshot()
        read="""async()=>{const db=await PushPullDB.open(()=>{});try{if(db.error)throw db.error;return JSON.parse(await db.exportModelBackup()).payload}finally{db.close()}}"""
        model=self.page.evaluate(read)
        self.controller['directory']=self.next_release('model-update')
        self.wait_update();self.reopen()
        self.context.set_offline(True);self.page.reload();self.ready()
        self.assertEqual(self.page.evaluate(read),model)
        self.assertEqual(self.snapshot(),before)

    def test_v2_results_offline_after_worker_update(self):
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click()
        self.page.locator('[data-view=plans]').click();self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PULL-A-1"]').click();open_result_panel(self.page)
        form=self.page.locator('.performanceForm');form.locator('[data-rich-action=toggle]').click()
        for el in form.locator('[data-field=kg]').all():el.fill('25')
        for el in form.locator('[data-field=reps]').all():el.fill('8')
        form.locator('[type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        before=self.snapshot()
        self.page.evaluate("navigator.serviceWorker.register('./sw.js',{updateViaCache:'none'}).then(r=>r.update())")
        self.controller['directory']=self.next_release('v2-update')
        self.wait_update();self.reopen()
        self.context.set_offline(True);self.page.reload();self.ready()
        self.assertEqual(self.snapshot(),before)
        self.page.locator('[data-expand="PULL-A-1"]').click();open_result_panel(self.page)
        form=self.page.locator('.performanceForm');form.locator('[data-rich-action=toggle]').click()
        expect(form.locator('[data-row="0"][data-field=kg]')).to_have_value('25')
        form.locator('[data-row="0"][data-field=kg]').fill('20')
        form.locator('[type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.page.reload();self.ready()
        self.assertEqual(self.snapshot()['data']['entries'][-1]['performance']['rows'][1]['segments'][0]['kg'],'20')
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)

    def test_issue99_update_from_pr98_preserves_asymmetric_draft_ids_offline_and_history(self):
        source=self.path/'issue99-pr98-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(subprocess.check_output(['git','show','42fc1010092c7adea0ad3520a493f7600d9b1bdc:'+name],cwd=ROOT))
        old_release=self.path/'issue99-pr98';build(old_release,source)
        current=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click()
        self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PULL-A-1"]').click();open_result_panel(self.page)
        f=self.page.locator('.performanceForm');f.locator('[data-quick=kg]').fill('40');f.locator('[data-quick=reps]').fill('9')
        f.locator('[data-rich-action=toggle]').click();f.locator('[data-row="1"][data-field=kg]').fill('35')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.snapshot()
        drafts=lambda:self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        old=drafts();self.assertEqual(len(old),1)
        self.controller['directory']=current;self.wait_update();self.reopen();self.context.set_offline(True)
        self.assertEqual(self.snapshot(),before);self.assertEqual(drafts(),old)
        self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-compact-row]')).to_have_count(4);expect(f.locator('[data-side-exception]')).to_have_count(1)
        expect(f.locator('[data-row="0"][data-field=kg]')).to_have_value('40');expect(f.locator('[data-row="1"][data-field=kg]')).to_have_value('35')
        expect(f.locator('[data-rich-action=side-mode]')).to_have_count(0)
        f.locator('[data-row="1"][data-field=kg]').fill('34');expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        expect(f.locator('[data-row="1"][data-field=kg]')).to_have_value('34');f.locator('[type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible();saved=self.snapshot()['data'];entry=saved['entries'][-1]
        self.assertEqual([r['id'] for r in entry['performance']['rows']],[r['id'] for r in old[0]['value']['performance']['rows']])
        self.assertEqual([r['segments'][0]['id'] for r in entry['performance']['rows']],[r['segments'][0]['id'] for r in old[0]['value']['performance']['rows']])
        self.assertEqual(sum(float(v['kg'])*int(v['reps']) for v in entry['series']),2106)
        self.assertEqual(saved['entries'][:-1],before['data']['entries']);self.assertEqual(saved['trainingJournal']['sessionSnapshots'],before['data']['trainingJournal']['sessionSnapshots'])
        self.assertFalse(drafts());self.page.reload();self.ready();self.assertEqual(self.snapshot()['data'],saved)

    def test_issue101_pr100_update_old_empty_optional_and_removed_drop_segments_remain_recoverable(self):
        source=self.path/'issue101-pr100-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(subprocess.check_output(['git','show','0a7b1ac62f75c9d3fffd3c750807ec369b065d00:'+name],cwd=ROOT))
        old_release=self.path/'issue101-pr100';build(old_release,source)
        current=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-view=plans]').click();self.page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click();self.page.locator('[data-type="PUSH A"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PUSH-A-5"]').click();f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click()
        for el in f.locator('[data-field=kg]').all():el.fill('20')
        for el in f.locator('[data-field=reps]').all():el.fill('8')
        for row in [0,1,2]:f.locator(f'[data-rich-action=remove-segment][data-row="{row}"]').click()
        self.page.locator('[data-expand="PUSH-A-6"]').click();f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click();f.locator('[data-quick=kg]').fill('24');f.locator('[data-quick=reps]').fill('10')
        f.locator('.execution-choice summary').click();f.locator('[data-rich-action=sides]').click()
        for _ in range(3):f.locator('[data-rich-action=remove-set]').first.click()
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        drafts=lambda:self.page.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return await d.readDrafts()}finally{d.close()}}')
        before=self.snapshot();old=drafts();self.assertEqual(len(old),2);self.assertTrue(all('executionMode' not in r['value'] for r in old))
        drop_before=next(r for r in old if r['exerciseId']=='PUSH-A-5')['value']['performance']
        self.controller['directory']=current;self.wait_update();self.reopen();self.context.set_offline(True)
        self.assertEqual(self.snapshot(),before);self.assertEqual(drafts(),old)
        self.page.locator('.spaced').filter(has=self.page.locator('[data-draft-resume]')).filter(has_text='PUSH-A-6').last.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        self.assertEqual(f.get_attribute('data-id'),'PUSH-A-6');expect(f.locator('[data-execution-choice]')).to_be_visible();expect(f.locator('[data-rich-action=add-set]')).to_be_disabled()
        f.locator('[data-execution-choice]').select_option('paired');f.locator('[data-rich-action=add-set]').click()
        expect(f.locator('[data-field=kg]')).to_have_count(1);f.locator('[data-field=kg]').fill('24');f.locator('[data-field=reps]').fill('10')
        f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm');self.assertEqual(f.get_attribute('data-id'),'PUSH-A-5')
        add_drop(f,0);f.locator('[data-row="0"][data-segment="1"][data-field=kg]').fill('10');f.locator('[data-row="0"][data-segment="1"][data-field=reps]').fill('6')
        self.page.locator('[data-act=finish]').click();self.page.locator('[data-finish-save]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        saved=self.snapshot()['data'];pair=next(e for e in saved['entries'] if e['sessionId']==before['data']['activeId'] and e['exerciseId']=='PUSH-A-6');drop=next(e for e in saved['entries'] if e['sessionId']==before['data']['activeId'] and e['exerciseId']=='PUSH-A-5')
        self.assertEqual([r['side'] for r in pair['performance']['rows']],['left','right']);self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in pair['series']),480)
        self.assertEqual(sum(float(s['kg'])*int(s['reps']) for s in drop['series']),540);self.assertEqual([r['segments'][0] for r in drop['performance']['rows']],[r['segments'][0] for r in drop_before['rows']])
        self.assertEqual(saved['entries'][:-2],before['data']['entries']);self.assertEqual(saved['trainingJournal']['nextUnitId'],'PULL A');self.assertEqual({**saved['trainingJournal'],'nextUnitId':before['data']['trainingJournal']['nextUnitId']},before['data']['trainingJournal']);self.assertFalse(drafts())
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.snapshot()['data'],saved)

    def test_stage2_to_stage3_worker_update_retains_database_and_backups(self):
        old=self.path/'stage2'
        for name in ['index.html','style.css','app.js','storage.js','indexeddb.js','manifest.webmanifest','icon.svg','sw.js']:
            dest=old/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(subprocess.check_output(['git','show',STAGE2+':'+name],cwd=ROOT))
        self.controller['directory']=old
        self.seed();self.page.goto(self.url);self.ready()
        before=self.snapshot()
        self.controller['directory']=self.path/'a'
        self.wait_update()
        self.assertEqual(self.snapshot(),before)
        self.reopen()
        self.assertEqual(self.snapshot(),before)
        self.context.set_offline(True);self.page.reload();self.ready()
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)

    def test_stage3_rename_update_keeps_identity_complete_backup_and_offline_name(self):
        old=self.path/'stage3'
        # Stage 3 predates the model modules; restore its actual asset set.
        for name in [*(name for name in ASSETS if not name.startswith('model/')),'sw.js']:
            dest=old/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(subprocess.check_output(['git','show',STAGE3+':'+name],cwd=ROOT))
        self.controller['directory']=old
        self.seed();self.page.goto(self.url);self.ready()
        expect(self.page).to_have_title('PushPull · Dziennik')
        before=self.snapshot()
        old_manifest=json.loads(self.context.new_cdp_session(self.page).send('Page.getAppManifest')['data'])
        self.controller['directory']=self.path/'a'
        self.wait_update()
        expect(self.page).to_have_title('PushPull · Dziennik') # No forced reload.
        self.assertEqual(self.snapshot(),before)
        self.reopen()
        expect(self.page).to_have_title('Aplikacja Treningowa')
        expect(self.page.locator('meta[name=description]')).to_have_attribute('content','Aplikacja Treningowa — kompaktowy dziennik treningowy')
        manifest=json.loads(self.context.new_cdp_session(self.page).send('Page.getAppManifest')['data'])
        self.assertEqual(manifest['name'],'Aplikacja Treningowa')
        self.assertEqual(manifest['short_name'],'Aplikacja Treningowa')
        for field in ['id','start_url','scope','icons']:
            self.assertEqual(manifest[field],old_manifest[field])
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key+"_backup_test")',KEY),'old backup preserved')
        self.context.set_offline(True);self.reopen()
        expect(self.page).to_have_title('Aplikacja Treningowa')
        self.assertEqual(self.snapshot(),before)
        self.page.locator('[data-tab=settings]').click()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        raw=Path(download.value.path()).read_text()
        self.assertEqual(json.loads(raw),before)
        self.page.locator('#importFile').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':raw.encode()})
        confirm_restore(self.page)
        expect(self.page.locator('h1')).to_have_text('Trening')
        restored=self.snapshot()
        self.assertEqual(restored['data'],before['data'])
        self.assertEqual(restored['catalog'],before['catalog'])
        self.assertGreater(len(restored['archives']),len(before['archives']))

    def test_pwa_survives_browser_process_restart_offline(self):
        profile=self.path/'persistent-profile'
        options={'executable_path':os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),'headless':True,'args':['--no-sandbox']}
        first=self.pw.chromium.launch_persistent_context(profile,**options)
        try:
            page=first.new_page()
            page.add_init_script(f"if(localStorage.getItem('{KEY}')===null)localStorage.setItem('{KEY}',{json.dumps(RAW)})")
            page.goto(self.url)
            expect(page.locator('[data-act=finish]')).to_be_visible()
            page.evaluate('navigator.serviceWorker.ready')
            self.poll('navigator.serviceWorker.controller !== null',page)
            before=page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.export()}finally{d.close()}}")
        finally:first.close()
        second=self.pw.chromium.launch_persistent_context(profile,**options)
        try:
            second.set_offline(True)
            page=second.new_page();page.goto(self.url)
            expect(page.locator('[data-act=finish]')).to_be_visible()
            after=page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.export()}finally{d.close()}}")
            self.assertEqual(before,after)
            self.assertEqual(page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)
        finally:second.close()

    def test_evicted_asset_fails_offline_then_repairs_verified_bytes_online(self):
        self.seed();self.page.goto(self.url);self.ready()
        before=self.snapshot()
        name='pushpull-shell-'+json.loads((self.controller['directory']/'release.json').read_text())['release']
        self.page.evaluate('(name)=>caches.open(name).then(c=>c.delete(new URL("app.js",location.href).href))',name)
        self.context.set_offline(True)
        self.assertEqual(self.page.evaluate('fetch("./app.js").then(r=>r.status)'),503)
        self.assertEqual(self.snapshot(),before)
        self.context.set_offline(False)
        self.page.reload();self.ready()
        self.assertEqual(self.snapshot(),before)
        self.assertTrue(self.page.evaluate('(name)=>caches.open(name).then(c=>c.match(new URL("app.js",location.href).href)).then(Boolean)',name))

    def test_protocol_v1_to_v2_update_retains_native_draft_and_old_writer_fails_closed(self):
        ref='46475114841895ad063a8eaea5054b10ef2b2094'
        source=self.path/'pre-incremental-source'
        for name in ASSETS:
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(historical_asset(ref,name))
        template=source/'scripts/service-worker.template.js';template.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'scripts/service-worker.template.js',template)
        old=self.path/'pre-incremental';build(old,source);self.controller['directory']=old
        self.seed();self.page.goto(self.url);self.ready()
        self.page.evaluate("""async()=>{
         const db=await PushPullDB.open(()=>{});try{
          await db.prepareModel({backupText:JSON.stringify(db.export()),ownerId:'pwa-protocol-owner'});
          const data=db.value,journal=await import('./model/journal.mjs'),v2=await import('./model/v2-plan.mjs');
          data.sessions.forEach(s=>s.status='done');data.activeId=null;data.trainingJournal=journal.initialize('pwa-protocol-owner');v2.activate(data,'2026-10-25T00:00:00.000Z');
          const session={id:'pwa-native-session',seq:100,type:'PUSH A',date:'2026-10-25',status:'active'};data.sessions.push(session);data.activeId=session.id;await journal.startSession(data,session,'2026-10-25T00:00:00.000Z');await db.commit(data);
         }finally{db.close()}
        }""")
        self.page.reload();self.ready();self.page.locator('[data-expand="PUSH-A-3"]').click();open_result_panel(self.page)
        self.page.locator('[data-quick=kg]').fill('23,')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.notification_state();self.assertTrue(before['drafts'])
        new=self.next_release('protocol-v2');self.controller['directory']=new;self.wait_update()
        self.assertEqual(self.notification_state(),before)
        self.reopen(timeout=20000);self.assertEqual(self.notification_state(),before)
        expect(self.page.locator('[data-draft-resume]')).to_be_visible()
        old_code=subprocess.check_output(['git','show',ref+':indexeddb.js'],cwd=ROOT,text=True)
        result=self.page.evaluate("""async code=>{
         const old=new Function(code+';return PushPullDB')(),db=await old.open(()=>{throw Error('must not initialize')});try{return {error:db.error?.name,value:db.value}}finally{db.close()}
        }""",old_code)
        self.assertEqual(result,{'error':'VersionError','value':None});self.assertEqual(self.notification_state(),before)
        self.context.set_offline(True);self.page.locator('[data-draft-resume]').click()
        # Quick-fill controls are commands and have always rendered empty after
        # restart. The unfinished values belong to the actual segment fields.
        expect(self.page.locator('[data-row="0"][data-segment="0"][data-field=kg]')).to_have_value('23,')
        self.page.locator('[data-quick=kg]').fill('23.5');self.page.locator('[data-quick=reps]').fill('8')
        self.page.locator('.performanceForm [type=submit]').click();expect(self.page.locator('.performanceForm')).to_have_count(0)
        after=self.notification_state();self.assertEqual(after['backup']['data']['sessions'],before['backup']['data']['sessions']);self.assertEqual(after['backup']['data']['trainingJournal']['sessionSnapshots'],before['backup']['data']['trainingJournal']['sessionSnapshots'])
        self.assertEqual(after['backup']['data']['entries'][:-1],before['backup']['data']['entries']);self.assertEqual(after['drafts'],[])
        self.page.reload();self.ready();self.assertEqual(self.notification_state(),after)
