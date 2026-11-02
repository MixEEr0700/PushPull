from test_browser import BrowserHarness,open_result_panel
from playwright.sync_api import expect
import test_indexeddb as legacy
from pathlib import Path
import base64

class CanonicalExportUI(BrowserHarness):
    def open_export(self):
        self.page.locator('[data-tab=settings]').click();self.backup_flow('save')

    def decode(self,raw):
        return self.page.evaluate("""async b=>{const {readCanonicalBackup}=await import('./model/canonical-backup.mjs');return readCanonicalBackup(new Blob([Uint8Array.from(atob(b),c=>c.charCodeAt(0))]))}""",base64.b64encode(raw).decode())

    def test_new_training_ui_export_exact_auxiliary_no_archives_no_writes_mobile(self):
        self.page.wait_for_selector('[data-act=start]');self.start();self.result('22','9');self.save()
        self.open_export();self.page.locator('[data-backup-advanced] > summary').click()
        self.page.locator('#driveConfig').evaluate('(f)=>{f.closest("details").open=true}')
        self.page.locator('#driveConfig input').fill('synthetic-client.apps.googleusercontent.com');self.page.locator('#driveConfig button').click()
        self.page.wait_for_function("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});try{return await new Promise(r=>{const q=db.transaction('meta').objectStore('meta').get('drive-sync-v1');q.onsuccess=()=>r(q.result?.clientId==='synthetic-client.apps.googleusercontent.com')})}finally{db.close()}}""")
        self.page.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise((r,j)=>{const tx=db.transaction('meta','readwrite');tx.objectStore('meta').put({key:'canonical-preferences-v1',value:{units:'kg',unicode:'Ł😀'}});tx.objectStore('meta').put({key:'workout-draft:synthetic',id:'synthetic',token:'conflict',value:{kg:'12,',reps:''}});tx.oncomplete=r;tx.onabort=()=>j(tx.error)});db.close();localStorage.setItem('pushpull-note-ui-v1:unfinished','{raw unfinished');}""")
        expected=self.state();before=legacy.IndexedDBMigration.records(self);local=self.page.evaluate('({...localStorage})')
        self.open_export()
        for width in (360,390,412):
            self.page.set_viewport_size({'width':width,'height':844})
            expect(self.page.locator('[data-canonical-export]')).to_be_visible()
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
        with self.page.expect_download(timeout=60000) as dl:self.page.locator('[data-canonical-export]').click()
        raw=Path(dl.value.path()).read_bytes();self.assertTrue(dl.value.suggested_filename.endswith('.ppc1'))
        decoded=self.decode(raw);self.assertEqual(decoded['source']['data'],expected)
        self.assertEqual(decoded['drive']['clientId'],'synthetic-client.apps.googleusercontent.com');self.assertEqual(decoded['preferences'],{'units':'kg','unicode':'Ł😀'});self.assertEqual(len(decoded['drafts']),1);self.assertEqual(decoded['buffers'],[{'key':'pushpull-note-ui-v1:unfinished','raw':'{raw unfinished'}]);self.assertNotIn('archives',decoded['source'])
        self.assertEqual(legacy.IndexedDBMigration.records(self),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
        expect(self.page.locator('[data-backup-save-status]')).to_contain_text('Przywracanie wymaga czystej instalacji')

    def test_cancel_navigation_and_double_click_do_not_queue_or_download_late(self):
        self.page.wait_for_selector('[data-act=start]');self.open_export()
        self.page.evaluate("""()=>{const Original=Worker;window.sent=0;window.Worker=class extends Original{constructor(url,opts){super(url,opts);if(String(url).includes('canonical-export-worker')){const post=this.postMessage.bind(this);this.postMessage=value=>{window.sent++;window.releaseExport=()=>post(value)}}}}}""")
        self.page.locator('[data-canonical-export]').evaluate('(b)=>{b.click();b.click()}')
        self.page.wait_for_function('window.sent===1');downloads=[];self.page.on('download',lambda d:downloads.append(d))
        self.page.locator('[data-tab=training]').click();expect(self.page.locator('[data-act=start]')).to_be_visible(timeout=1500)
        self.page.locator('[data-tab=settings]').click();expect(self.page.locator('[data-backup-save-status]')).to_contain_text('Anulowano');self.assertFalse(downloads)

    def test_new_native_plan_snapshot_user_note_offline_worker_export(self):
        from test_browser import wait_for_service_worker_controller,open_notes
        import test_v2_training as v2
        self.context.close();self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog);self.page.goto(self.url)
        self.page.wait_for_selector('[data-act=start]');wait_for_service_worker_controller(self.page)
        self.plans('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.start()
        self.page.locator('[data-expand]').first.click();open_result_panel(self.page)
        form=self.page.locator('.performanceForm');form.locator('[data-rich-action=toggle]').click();v2.V2Training.fill_rows(self,form,'24','8');form.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        if self.page.locator('[data-expand]').first.get_attribute('aria-expanded')=='false':self.page.locator('[data-expand]').first.click()
        open_notes(self.page);note=self.page.locator('[data-personal-note]').first
        if not note.evaluate('(e)=>e.open'):note.locator('summary').click()
        note.locator('textarea').fill('Nowa notatka Ł😀');note.locator('[type=submit]').click();expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        expected=self.state();before=legacy.IndexedDBMigration.records(self);self.open_export();self.context.set_offline(True)
        with self.page.expect_download(timeout=60000) as dl:self.page.locator('[data-canonical-export]').click()
        raw=Path(dl.value.path()).read_bytes();print('NATIVE_UI_EXPORT',len(raw),self.page.locator('[data-backup-save-status]').inner_text());decoded=self.decode(raw);self.assertEqual(decoded['source']['data'],expected);self.assertEqual(len(decoded['source']['data']['trainingJournal']['sessionSnapshots']),1);self.assertEqual(decoded['source']['data']['trainingJournal']['model']['userNotes'][-1]['text'],'Nowa notatka Ł😀');self.assertEqual(legacy.IndexedDBMigration.records(self),before)

    def test_changed_auxiliary_during_encoding_refuses_without_download(self):
        import json
        self.page.wait_for_selector('[data-act=start]');self.open_export();held=[]
        self.context.route('**/canonical-test-gate',lambda route:held.append(route))
        self.page.evaluate("""()=>{const Original=Worker;window.Worker=class extends Original{constructor(url,opts){if(String(url).includes('canonical-export-worker')){const gate=new URL('./canonical-test-gate',location.href).href;const source='let early;self.onmessage=e=>early=e;const digest=crypto.subtle.digest.bind(crypto.subtle);let first=true;crypto.subtle.digest=async(...a)=>{if(first){first=false;await fetch('+JSON.stringify(gate)+')}return digest(...a)};await import('+JSON.stringify(String(url))+');if(early)self.onmessage(early);';url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));}super(url,opts)}}}""")
        downloads=[];self.page.on('download',lambda d:downloads.append(d));self.page.locator('[data-canonical-export]').click()
        for _ in range(150):
            if held:break
            self.page.wait_for_timeout(20)
        self.assertTrue(held,self.page.locator('[data-backup-save-status]').inner_text())
        self.page.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise(r=>{const tx=db.transaction('meta','readwrite');tx.objectStore('meta').put({key:'canonical-preferences-v1',value:{changed:true}});tx.oncomplete=r});db.close()}""")
        expected=legacy.IndexedDBMigration.records(self);held[0].fulfill(status=200,body='ok')
        expect(self.page.locator('[data-backup-save-status]')).to_contain_text('Nie zlecono',timeout=60000)
        self.assertFalse(downloads);self.assertEqual(legacy.IndexedDBMigration.records(self),expected)

    def test_400_and_4000_new_synthetic_histories_production_ui_worker(self):
        self.page.wait_for_selector('[data-act=start]')
        for n in (400,4000):
            self.page.goto(self.url+'tests/fixtures/v1.json')
            expected=self.page.evaluate("""async n=>{const {canonicalFixture}=await import('/tests/canonical-fixture.mjs'),p=await import('/model/journal-protocol.mjs'),{buildRuntime}=await import('/model/journal-runtime-index.mjs');const input=canonicalFixture(await(await fetch('/tests/fixtures/v1.json')).json(),n);input.preferences={snapshots:Array.from({length:n},(_,i)=>({instructions:'Synthetic '.repeat(30),version:i}))};const source={...input.source,archives:[]},bundle=await p.createProtocol(source),rt=await buildRuntime(source,{sourceRoot:bundle.state.indexRoot});const records={...bundle.records,journalObjects:[...new Map([...bundle.records.journalObjects,...rt.objects].map(r=>[r.id,r])).values()],journalIndex:[...new Map([...bundle.records.journalIndex,...rt.nodes].map(r=>[r.id,r])).values()]};records.journalState=[await p.sealState({...bundle.state,allocation:await p.allocationFor(records),runtime:rt.runtime})];const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise((r,j)=>{const tx=db.transaction([...db.objectStoreNames],'readwrite',{durability:'strict'});for(const name of db.objectStoreNames)tx.objectStore(name).clear();for(const [name,rows] of Object.entries(records))for(const row of rows)tx.objectStore(name).put(row);tx.objectStore('meta').put({key:'journal-protocol-v2',protocol:2,status:'active',epoch:bundle.state.epoch});tx.objectStore('meta').put({key:'canonical-preferences-v1',value:input.preferences});tx.oncomplete=r;tx.onabort=()=>j(tx.error)});db.close();localStorage.clear();return input;}""",n)
            self.page.goto(self.url);self.page.wait_for_selector('[data-act=start]');self.open_export()
            with self.page.expect_download(timeout=60000) as dl:self.page.locator('[data-canonical-export]').click()
            raw=Path(dl.value.path()).read_bytes();decoded=self.decode(raw)
            self.assertEqual(decoded['source'],expected['source']);self.assertEqual(decoded['preferences'],expected['preferences']);self.assertEqual(len(decoded['source']['data']['sessions']),n)
            print('SYNTHETIC_UI_EXPORT',n,len(raw),self.page.locator('[data-backup-save-status]').inner_text())

    def test_worker_read_quota_and_abort_refuse_no_mutation(self):
        self.page.wait_for_selector('[data-act=start]');self.open_export();before=legacy.IndexedDBMigration.records(self);downloads=[];self.page.on('download',lambda d:downloads.append(d))
        self.page.evaluate('()=>{window.NativeExportWorker=Worker}')
        for kind in ('QuotaExceededError','AbortError'):
            self.page.evaluate("""kind=>{window.Worker=class extends NativeExportWorker{constructor(url,opts){if(String(url).includes('canonical-export-worker')){const prefix='let early;self.onmessage=e=>early=e;const get=IDBObjectStore.prototype.get;IDBObjectStore.prototype.get=function(...a){if(this.name===\"journalState\")throw new DOMException(\"synthetic read failure\",'+JSON.stringify(kind)+');return get.apply(this,a)};await import('+JSON.stringify(String(url))+');if(early)self.onmessage(early);';url=URL.createObjectURL(new Blob([prefix],{type:'text/javascript'}));}super(url,opts)}}}""",kind)
            self.page.locator('[data-canonical-export]').click();expect(self.page.locator('[data-backup-save-status]')).to_contain_text('Nie zlecono',timeout=60000)
            expect(self.page.locator('[data-canonical-export]')).to_be_enabled();self.assertEqual(legacy.IndexedDBMigration.records(self),before)
        self.assertFalse(downloads)

    def test_invalid_existing_preferences_are_not_silently_defaulted(self):
        self.page.wait_for_selector('[data-act=start]');self.open_export()
        self.page.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise(r=>{const tx=db.transaction('meta','readwrite');tx.objectStore('meta').put({key:'canonical-preferences-v1',value:null});tx.oncomplete=r});db.close()}""")
        before=legacy.IndexedDBMigration.records(self);downloads=[];self.page.on('download',lambda d:downloads.append(d));self.page.locator('[data-canonical-export]').click()
        expect(self.page.locator('[data-backup-save-status]')).to_contain_text('Nieprawidłowe preferencje',timeout=60000)
        self.assertFalse(downloads);self.assertEqual(legacy.IndexedDBMigration.records(self),before)
