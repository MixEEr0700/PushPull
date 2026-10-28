"""Run: python3 -m unittest discover -s tests -p 'test_*.py' -v
Uses installed Playwright + Chromium; starts its own local HTTP server.
"""
import datetime
import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import shutil
import threading
import unittest
from playwright.sync_api import sync_playwright, expect
from ci_annotations import install as install_ci_annotations
install_ci_annotations()

ROOT = Path(__file__).resolve().parents[1]
KEY = 'pushpull_skeleton_v1'
BASE = '92390b1449bd61c4c6fdc41ccf8a272e5ff914d3'

def confirm_restore(page):
    expect(page.locator('[data-restore-confirm]')).to_be_visible(timeout=60000)
    page.locator('[data-restore-confirm]').click()
    expect(page.locator('[data-restore-busy]')).to_have_count(0,timeout=120000)

def open_notes(scope):
    """Header toggle in the final polish; historical release fixtures have no toggle."""
    toggle=scope.locator('[data-note-toggle]').first
    if toggle.count() and toggle.get_attribute('aria-expanded')=='false':toggle.click()

def open_result_panel(scope):
    """Issue95 auto-opens the form; correction/history still have an opener.
    Also exercises old-release upgrade fixtures that need an explicit click.
    """
    form=scope.locator('.performanceForm,.seriesResultForm').first
    if not form.is_visible():
        scope.locator('[data-panel=result],[data-panel=historicalResult]').click()
    expect(form).to_be_visible()

class QuietServer(http.server.SimpleHTTPRequestHandler):
    upgrade_latest = False
    runtime_ref = None

    def do_GET(self):
        prefix = '/upgrade/' if self.path.startswith('/upgrade/') else '/legacy/' if self.path.startswith('/legacy/') else None
        if prefix:
            asset=self.path[len(prefix):].split('?')[0] or 'index.html'
            allowed={'index.html','app.js','storage.js','indexeddb.js','style.css','sw.js','manifest.webmanifest','icon.svg','icons/icon-192.png','icons/icon-512.png','icons/icon-maskable-512.png','model/draft-collector.mjs','model/backup-v6.mjs','model/backup-v5-preview.mjs','model/backup-v5.mjs','model/backup-v4.mjs','model/backup-v4-export.mjs','model/local-backup-v4.mjs','model/training-model.mjs','model/backup.mjs','model/backup-json.mjs','model/legacy-backup.mjs','model/legacy-model.mjs','model/v2-plan-data.mjs','model/v2-plan.mjs','model/performance.mjs','model/performance-editor.mjs','model/workout-drafts.mjs','model/journal.mjs','model/plan-overview.mjs','model/plan-import.mjs','model/google-drive.mjs','model/drive-sync.mjs','model/journal-runtime-index.mjs','model/journal-runtime.mjs','model/journal-index.mjs','model/journal-protocol.mjs','model/journal-idb.mjs','model/journal-database.mjs'}
            if asset not in allowed:
                self.send_error(404);return
            try:
                if prefix=='/legacy/' or not type(self).upgrade_latest:
                    body=subprocess.check_output(['git','show','99902a22c820d228b2e6cd3cf0fb49371b1bf3ce:'+asset],cwd=ROOT,stderr=subprocess.DEVNULL)
                else: body=subprocess.check_output(['git','show',self.runtime_ref+':'+asset],cwd=ROOT,stderr=subprocess.DEVNULL) if self.runtime_ref else (ROOT/asset).read_bytes()
            except (subprocess.CalledProcessError,FileNotFoundError):
                self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type',self.guess_type(asset))
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body);return
        # Tests of the retained v1 schema/writer run the exact pre-integration
        # release, including its hash-matched worker. Functional suites default
        # to the current v2 application; assertions are never disabled.
        asset=self.path.split('?')[0].lstrip('/') or 'index.html'
        if self.runtime_ref and asset in self.legacy_assets:
            body=subprocess.check_output(['git','show',self.runtime_ref+':'+asset],cwd=ROOT)
            self.send_response(200);self.send_header('Content-Type',self.guess_type(asset));self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        super().do_GET()

    def log_message(self, *args):
        pass

class BrowserHarness(unittest.TestCase):
    legacy_backend = False
    mock_clock = True
    @classmethod
    def setUpClass(cls):
        handler=QuietServer
        if cls.legacy_backend:
            import runpy
            ref='6002889'
            assets=runpy.run_path(str(ROOT/'scripts/build_release.py'))['ASSETS']
            # The v2 modules are isolated test modules, unused by that release.
            assets={*assets,'sw.js'}-{'model/journal-runtime-index.mjs','model/journal-runtime.mjs','model/journal-index.mjs','model/journal-protocol.mjs','model/journal-idb.mjs','model/journal-database.mjs'}
            handler=type('V1CompatibilityServer',(QuietServer,),{'runtime_ref':ref,'legacy_assets':assets})
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(handler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'), args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def new_context(self, **options):
        options.setdefault('viewport', {'width':390,'height':844})
        context = self.browser.new_context(timezone_id='Europe/Warsaw', **options)
        self.addCleanup(context.close)
        return context

    def setUp(self):
        self.context = self.new_context(service_workers='block')
        self.page = self.context.new_page()
        self.alerts = []
        self.confirm = True
        self.page.on('dialog', self.dialog)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        if self.mock_clock:
            self.page.clock.install(time=datetime.datetime(2026, 10, 21, 10, 0, tzinfo=datetime.timezone.utc))
        self.page.goto(self.url)

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def dialog(self, dialog):
        if dialog.type == 'alert':
            self.alerts.append(dialog.message)
            dialog.accept()
        elif self.confirm:
            dialog.accept()
        else:
            dialog.dismiss()

    def plans(self,version=None):
        self.page.locator('[data-tab=settings]').click()
        self.page.locator('[data-view=plans]').click()
        if version:self.page.locator('#importedPlanId').select_option(version)

    def state(self):
        return self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{throw Error('Missing database')});try{return db.value}finally{db.close()}}""")

    def raw(self):
        value=self.state()
        return json.dumps(value, ensure_ascii=False, sort_keys=True) if value is not None else None

    def local_raw(self):
        return self.page.evaluate('(key)=>localStorage.getItem(key)',KEY)

    def reset_legacy(self, raw):
        self.page.goto(self.url+'tests/')
        self.page.evaluate("""async p=>{await new Promise((resolve,reject)=>{const r=indexedDB.deleteDatabase('pushpull');r.onsuccess=resolve;r.onerror=()=>reject(r.error)});localStorage.clear();if(p!==null)localStorage.setItem('pushpull_skeleton_v1',p)}""",raw)
        self.page.goto(self.url)

    def start(self, date='2026-10-21'):
        self.page.locator('#trainingDate').fill(date)
        self.page.locator('[data-act=start]').click()
        expect(self.page.locator('[data-act=finish]')).to_be_visible()

    def result(self, kg='100', reps='10'):
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        open_result_panel(self.page)
        self.page.locator('[data-main=kg]').fill(kg)
        self.page.locator('[data-main=reps]').fill(reps)

    def save(self):
        self.page.locator('.seriesResultForm [type=submit]').click()
        # Wait for the real asynchronous IDB commit, including cold CI runners.
        expect(self.page.locator('.seriesResultForm')).to_have_count(0,timeout=15000)

    def import_data(self, content):
        self.page.locator('#importFile').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':content.encode()})
        self.page.wait_for_function("document.querySelector('[data-restore-preview],[data-restore-error]')",timeout=60000)
        if self.page.locator('[data-restore-confirm]').count():confirm_restore(self.page)

    def advanced_data(self,page=None):
        p=page or self.page
        drawer=p.locator('[data-backup-advanced]')
        if drawer.count() and not drawer.evaluate('(e)=>e.open'):
            drawer.locator(':scope > summary').click()
        if drawer.count():expect(drawer).to_have_attribute('open','')

    def settings(self):
        self.page.locator('[data-tab=settings]').click()

class BrowserRegression(BrowserHarness):
    def test_full_rotation_and_manual_choice(self):
        for current, next_type in [('PUSH A','PULL A'),('PULL A','PUSH B'),('PUSH B','PULL B'),('PULL B','PUSH A')]:
            self.start()
            self.assertEqual(self.state()['sessions'][-1]['type'], current)
            self.page.locator('[data-act=finish]').click()
            expect(self.page.locator('[data-act=start]')).to_be_visible()
            self.assertEqual(self.state()['nextType'], next_type)
        self.page.locator('[data-type="PUSH B"]').click()
        self.start()
        self.assertEqual(self.state()['sessions'][-1]['type'], 'PUSH B')

    def test_series_tonnage_history_notes_and_reload(self):
        self.start()
        self.result()
        self.page.locator('[data-series-toggle]').click()
        self.page.locator('[data-series-remove="2"]').click()
        self.page.locator('[data-series-index="1"][data-field=kg]').fill('80')
        self.page.locator('[data-series-index="1"][data-field=reps]').fill('8')
        self.assertEqual(self.page.locator('.series-total strong').inner_text().replace('\xa0','').replace(' ',''), '1640kg')
        self.save()
        self.assertEqual(len(self.state()['entries'][0]['series']), 2)
        open_notes(self.page);self.page.locator('[data-personal-note] > summary').click()
        self.page.locator('#notesForm textarea').fill('Łopatki stabilnie')
        self.page.locator('#notesForm [type=submit]').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.page.locator('[data-panel=stats]').click()
        expect(self.page.locator('.stat-tile.selected strong')).to_contain_text('640')
        for metric in ['weight','reps','pace','tonnage']:
            self.page.locator(f'[data-metric={metric}]').click()
            expect(self.page.locator('.stat-chart')).to_be_visible()
            expect(self.page.locator('.stat-table')).to_be_visible()
        self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-tab=calendar]').click()
        self.page.locator('[data-act=openSession]').click()
        if self.page.locator('[data-expand="PUSH-A-1"]').get_attribute('aria-expanded') == 'false':
            self.page.locator('[data-expand="PUSH-A-1"]').click()
        open_result_panel(self.page)
        self.page.locator('[data-series-toggle]').click()
        self.page.locator('[data-series-index="1"][data-field=kg]').fill('85')
        self.save()
        self.page.locator('#historicalDate [name=date]').fill('2026-10-20')
        self.page.locator('#historicalDate button').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        saved=self.state()
        self.assertEqual(len(saved['entries']),1)
        self.assertEqual(saved['nextType'],'PULL A')
        self.assertEqual(saved['sessions'][0]['date'],'2026-10-20')
        self.assertEqual(saved['entries'][0]['series'][1]['kg'],'85')
        self.page.reload()
        self.assertEqual(self.state(),saved)
        self.assertEqual(saved['exercises']['PUSH A'][0]['notes'],'Łopatki stabilnie')
        self.page.locator('[data-tab=calendar]').click()
        self.assertIn('mark', self.page.locator('[data-day="2026-10-20"]').get_attribute('class').split())

    def test_calendar_navigation_in_warsaw(self):
        self.page.locator('[data-tab=calendar]').click()
        self.page.locator('[data-act=nextMonth]').click()
        expect(self.page.locator('.row.between.card strong')).to_have_text('listopad 2026')
        self.page.locator('[data-act=prevMonth]').click()
        expect(self.page.locator('.row.between.card strong')).to_have_text('październik 2026')
        self.page.locator('[data-act=prevMonth]').click()
        expect(self.page.locator('.row.between.card strong')).to_have_text('wrzesień 2026')

    def test_export_import_cancel_backup_restore_and_invalid_file(self):
        self.start(); self.result(); self.save()
        original=self.raw()
        self.settings()
        with self.page.expect_download() as download:
            self.page.locator('[data-act=export]').click()
        exported=Path(download.value.path()).read_text()
        self.assertEqual(json.loads(exported)['data'],json.loads(original))
        replacement=json.loads(exported)
        replacement['data']['exercises']['PUSH A'][0]['notes']='Importowane'
        self.confirm=False
        self.import_data(json.dumps(replacement))
        self.assertEqual(self.state(),json.loads(original))
        self.assertEqual(self.page.evaluate('localStorage.length'),1)
        self.confirm=True
        self.import_data(json.dumps(replacement))
        self.settings()
        expect(self.page.locator('#backupKey option')).to_have_count(1)
        with self.page.expect_download() as backup:
            self.advanced_data();self.page.locator('[data-backup-export]').click()
        backup_raw=Path(backup.value.path()).read_text()
        self.assertEqual(json.loads(backup_raw)['data'],json.loads(original))
        self.import_data(backup_raw)
        self.assertEqual(self.state(),json.loads(original))
        self.settings()
        for content in ['{broken','null',json.dumps({'version':2}),json.dumps({**replacement,'data':{**replacement['data'],'activeId':'missing'}})]:
            before=self.raw()
            self.import_data(content)
            self.assertEqual(self.raw(),before)
        self.assertEqual(len(self.alerts),4)

    def test_corrupt_and_unsupported_boot_recovery_download_and_import(self):
        self.start()
        good=self.raw()
        for bad in ['{bad',json.dumps({'version':2}),'null','']:
            self.reset_legacy(bad)
            expect(self.page.locator('[role=alert]')).to_be_visible()
            expect(self.page.locator('[data-act=start]')).to_have_count(0)
            self.assertEqual(self.local_raw(),bad)
            with self.page.expect_download() as download:
                self.page.locator('[data-recovery-export]').click()
            self.assertEqual(Path(download.value.path()).read_text(),bad)
            self.import_data(good)
            self.assertEqual(self.state(),json.loads(good))
            backups=self.page.evaluate("async()=>{const db=await PushPullDB.open(()=>{});try{return await Promise.all(db.backups().map(id=>db.readBackup(id)))}finally{db.close()}}")
            self.assertIn(bad,backups)

    def test_quota_failure_rolls_back_ui_and_memory(self):
        self.page.evaluate("() => {const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(v){if(this.name==='journalSessions')throw new DOMException('Pełna pamięć','QuotaExceededError');return add.call(this,v)}}")
        self.page.locator('[data-act=start]').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        expect(self.page.locator('[data-act=finish]')).to_have_count(0)
        self.assertEqual(self.state()['sessions'],[])
        self.assertIn('Operacja przerwana',self.alerts[0])
        self.page.reload()
        self.start()
        self.assertEqual(len(self.state()['sessions']),1)

    def test_import_backup_failure_keeps_active_session_and_drafts(self):
        self.start(); self.result()
        self.page.locator('[data-main=kg]').fill('120')
        original=self.raw()
        self.settings()
        self.page.evaluate("() => {const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(v){if(this.name==='journalArchives')throw new DOMException('Pełna pamięć','QuotaExceededError');return add.call(this,v)}}")
        self.import_data(original)
        self.assertEqual(self.state(),json.loads(original))
        self.assertIn('Operacja przerwana',self.alerts[0])
        self.page.locator('[data-tab=training]').click()
        open_result_panel(self.page)
        expect(self.page.locator('[data-main=kg]')).to_have_value('120')

    def test_storage_access_denied_is_not_a_new_database(self):
        self.context.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('Odmowa','SecurityError')}})")
        self.page.reload()
        expect(self.page.locator('[role=alert]')).to_be_visible()
        expect(self.page.locator('[data-act=start]')).to_have_count(0)

    def test_issue44_update_failure_during_save_click_does_not_move_submit_target(self):
        self.page.add_init_script("navigator.serviceWorker.register=()=>new Promise((_,reject)=>{window.__rejectPwa=reject})")
        self.page.reload();self.start();self.result()
        self.page.locator('[data-series-toggle]').click()
        self.page.locator('[data-series-index="1"][data-field=kg]').fill('80')
        self.page.wait_for_function('()=>typeof window.__rejectPwa==="function"')
        button=self.page.locator('.seriesResultForm [type=submit]')
        button.evaluate("button=>button.addEventListener('mousedown',()=>window.__rejectPwa(Error('synthetic update failure')),{once:true})")
        self.save()
        self.assertEqual(len(self.state()['entries']),1)
        self.assertEqual(self.state()['entries'][0]['series'][1]['kg'],'80')
        self.assertFalse(self.alerts,self.alerts)

    def test_copied_custom_series_require_confirmation(self):
        self.start();self.result()
        self.page.locator('[data-series-toggle]').click()
        self.page.locator('[data-series-index="1"][data-field=kg]').fill('80')
        self.save()
        self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PUSH A"]').click()
        self.start()
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        open_result_panel(self.page)
        self.confirm=False
        self.page.locator('[data-main=kg]').fill('110')
        expect(self.page.locator('[data-main=kg]')).to_have_value('100')
        self.page.locator('[data-series-toggle]').click()
        expect(self.page.locator('[data-series-index="1"][data-field=kg]')).to_have_value('80')

    def test_other_tab_change_blocks_stale_edit(self):
        self.start()
        other=self.context.new_page()
        other.goto(self.url)
        other.evaluate('(key)=>localStorage.setItem(key,"external-change")',KEY)
        expect(self.page.locator('[role=alert]')).to_be_visible()
        self.assertEqual(self.local_raw(),'external-change')
        self.assertEqual(len(self.state()['sessions']),1)

    def test_mobile_compact_matrix_visual_contract(self):
        # Issue43 replaces v0.3 pixel equality with the approved v0.4 contract.
        # Functional assertions elsewhere remain unchanged.
        from pathlib import Path
        output=Path('/tmp/pushpull-compact-review');output.mkdir(exist_ok=True)
        for width,height in [(360,800),(390,844),(412,915)]:
            self.page.set_viewport_size({'width':width,'height':height})
            self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
            self.assertEqual(self.page.evaluate('getComputedStyle(document.body).backgroundColor'),'rgb(0, 0, 0)')
            card=self.page.locator('.exercise-card').first
            self.assertEqual(card.evaluate('(e)=>getComputedStyle(e).backgroundColor'),'rgb(17, 17, 17)')
            expect(card.locator('.detail').first).to_be_visible()
            self.assertGreaterEqual(card.locator('[data-expand]').bounding_box()['height'],44)
            before=self.state();card.locator('[data-expand]').click()
            expect(card.locator('.detail').first).to_be_visible()
            expect(card.locator('[data-personal-note] textarea')).not_to_be_visible()
            open_notes(card);card.locator('[data-personal-note] > summary').click()
            expect(card.locator('[data-personal-note] textarea')).to_be_visible()
            self.assertEqual(self.state(),before)
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.page.screenshot(path=str(output/(str(width)+'-expanded.png')),full_page=True)
            self.page.locator('[data-tab=calendar]').click();expect(self.page.locator('h1')).to_have_text('Kalendarz')
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

    def test_offline_reload_and_new_cache_does_not_serve_old_app(self):
        context=self.new_context(service_workers='allow')
        page=context.new_page()
        page.goto(self.url)
        page.evaluate("caches.open('pushpull-v2').then(c=>c.put('./app.js',new Response('throw Error(\"OLD APP\")'))) ")
        page.evaluate('navigator.serviceWorker.ready')
        page.wait_for_function('navigator.serviceWorker.controller !== null')
        page.locator('[data-act=start]').click()
        expect(page.locator('[data-act=finish]')).to_be_visible()
        before=page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});const v=d.value;d.close();return v}")
        context.set_offline(True)
        page.reload()
        expect(page.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual(page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});const v=d.value;d.close();return v}"),before)

if __name__=='__main__':
    unittest.main()
