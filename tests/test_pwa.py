"""Real service workers + installability metadata + isolated artifact/HTTPS tests."""
import functools
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
        for name in ['style.css','icon.svg','icons/icon-192.png','icons/icon-512.png','icons/icon-maskable-512.png','storage.js','scripts/service-worker.template.js','PushPull_PLAN_PROJEKTU_v1.md']:
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
    def ready(self):
        expect(self.page.locator('[data-act=finish]')).to_be_visible()
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
        self.page.evaluate('async()=>{window.__pwaRegistration=await navigator.serviceWorker.getRegistration();await window.__pwaRegistration.update()}')
        # Poll a synchronous property: a Promise itself is truthy to the polling API.
        self.poll('window.__pwaRegistration.waiting?.state === "installed"')
        expected='pushpull-shell-'+json.loads((self.controller['directory']/'release.json').read_text())['release']
        self.waiting_worker=next(w for w in self.context.service_workers if w.evaluate('CACHE')==expected)
    def reopen(self):
        waiting=getattr(self,'waiting_worker',None)
        if waiting:waiting.evaluate("self.__testActivated=false;self.addEventListener('activate',()=>{self.__testActivated=true})")
        self.page.close()
        if waiting:
            deadline=time.monotonic()+10
            while not waiting.evaluate('self.__testActivated && !self.registration.waiting && self.registration.active?.state === "activated"'):
                if time.monotonic()>deadline:self.fail('Waiting worker did not activate after the final old tab closed')
                time.sleep(0.02)
            self.waiting_worker=None
        self.page=self.context.new_page();self.page.on('dialog',self.accept_dialog);self.page.goto(self.url);self.ready()

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
        expect(self.page.locator('h1')).to_have_text('Trening')
        self.assertEqual(self.snapshot()['data'],FIXTURE)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)

    def test_update_waits_for_all_tabs_and_preserves_unsaved_series_and_all_data(self):
        self.seed();self.page.goto(self.url);self.ready()
        before=self.snapshot()
        self.page.locator('[data-expand="PUSH-A-1"]').click();self.page.locator('[data-panel=result]').click()
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

    def test_issue14_upgrade_saved_skeleton_draft_and_independent_source_pair(self):
        # Real pre-fix build + persisted IDB + waiting SW; never reset app data.
        source=self.path/'issue14-old-source'
        for name in [*ASSETS,'scripts/service-worker.template.js']:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(subprocess.check_output(['git','show','cf9b765:'+name],cwd=ROOT))
        old_release=self.path/'issue14-old';build(old_release,source)
        current_release=self.controller['directory'];self.controller['directory']=old_release
        self.seed();self.page.goto(self.url);self.ready()
        self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL B"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PULL-B-6"]').click();self.page.locator('[data-panel=result]').click()
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
        self.assertEqual(self.snapshot(),pre_start)
        self.page.remove_listener('dialog',dismiss);self.page.on('dialog',self.accept_dialog)
        self.page.locator('[data-act=start]').click();self.ready()
        expect(self.page.locator('.exercise-card')).to_have_count(10)
        expect(self.page.locator('[data-expand="PULL-B-7"] .num')).to_have_text('7')
        for eid,number,kg in [('PULL-B-6-SKI','6A','20'),('PULL-B-6-SHRUGS','6B','10')]:
            button=self.page.locator(f'[data-expand="{eid}"]')
            expect(button.locator('.num')).to_have_text(number)
            expect(button).to_contain_text('Brak zapisanego wyniku')
            expect(button).to_contain_text('Tempo do uzupełnienia')
            button.click();self.page.locator('[data-panel=result]').click()
            form=self.page.locator('.seriesResultForm')
            expect(form.locator('[data-main=kg]')).to_have_value('')
            expect(form.locator('[data-main=reps]')).to_have_value('')
            form.locator('[data-main=kg]').fill(kg);form.locator('[data-main=reps]').fill('8')
            expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.locator('[data-expand="PULL-B-6-SKI"]').click();self.page.locator('[data-panel=result]').click()
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
            dest.write_bytes(subprocess.check_output(['git','show','16e131a:'+name],cwd=ROOT))
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
                    self.page.locator(f'[data-expand="{eid}"]').click();self.page.locator('[data-panel=result]').click()
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
        self.page.locator('[data-preview-v2]').click()
        with self.page.expect_download():self.page.locator('[data-activate-v2]').click()
        expect(self.page.get_by_text('V2 aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL A"]').click();self.page.locator('[data-act=start]').click()
        self.page.locator('[data-expand="PULL-A-1"]').click();self.page.locator('[data-panel=result]').click()
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
        self.page.locator('[data-expand="PULL-A-1"]').click();self.page.locator('[data-panel=result]').click()
        form=self.page.locator('.performanceForm');form.locator('[data-rich-action=toggle]').click()
        expect(form.locator('[data-row="1"][data-field=kg]')).to_have_value('25')
        form.locator('[data-row="1"][data-field=kg]').fill('20')
        form.locator('[type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.page.reload();self.ready()
        self.assertEqual(self.snapshot()['data']['entries'][-1]['performance']['rows'][1]['segments'][0]['kg'],'20')
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)

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
