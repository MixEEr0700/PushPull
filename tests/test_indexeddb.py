"""Real-browser migration/transaction fault tests; no fake IndexedDB."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness, KEY, ROOT, QuietServer

OWNER='pushpull_indexeddb_owner'
FIXTURE=json.loads((ROOT/'tests/fixtures/v1.json').read_text())
RAW='  '+json.dumps(FIXTURE,ensure_ascii=False)+'\n'

# Keep a real transaction alive until explicitly released or the page is closed.
# Requests still execute, but transaction.oncomplete cannot occur during the loop.
PAUSE="""() => {
 for(const method of ['add','put']){const original=IDBObjectStore.prototype[method];
 IDBObjectStore.prototype[method]=function(value,...args){
   const result=original.call(this,value,...args);
   if(['sessions','journalSessions','journalResults','journalState'].includes(this.name) && !window.__held){
     window.__held=true;window.__hold=true;window.__transaction=this.transaction;
     const store=this.transaction.objectStore('meta');
     function keep(){if(window.__hold){const r=store.get('pause');r.onsuccess=keep}}
     keep();
   }
   return result;
 };}
}"""

class IndexedDBMigration(BrowserHarness):
    legacy_backend = True
    def prepare(self, raw=RAW, script=None, backups=None):
        self.page.goto(self.url+'tests/')
        self.page.evaluate("""async raw=>{await new Promise((resolve,reject)=>{const r=indexedDB.deleteDatabase('pushpull');r.onsuccess=resolve;r.onerror=()=>reject(r.error)});localStorage.clear();if(raw!==null)localStorage.setItem('pushpull_skeleton_v1',raw)}""",raw)
        if backups:self.page.evaluate('(copies)=>{for(const [k,v] of Object.entries(copies))localStorage.setItem(k,v)}',backups)
        if script:self.page.add_init_script('('+script+')()')
        self.page.goto(self.url)

    def records(self, page=None):
        return (page or self.page).evaluate("""async()=>{
          const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('pushpull');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
          try{return await new Promise((resolve,reject)=>{const tx=db.transaction([...db.objectStoreNames]);const result={};for(const name of db.objectStoreNames){const r=tx.objectStore(name).getAll();r.onsuccess=()=>result[name]=r.result}tx.oncomplete=()=>resolve(result);tx.onabort=()=>reject(tx.error)})}finally{db.close()}
        }""")

    def ready(self):
        expect(self.page.locator('[data-act=finish]')).to_be_visible()

    def test_empty_database_is_verified_without_creating_legacy_data(self):
        self.prepare(None)
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        records=self.records()
        self.assertEqual(records['sessions'],[])
        self.assertEqual(records['sets'],[])
        self.assertEqual(len(records['exercises']),34)
        self.assertTrue(records['meta'][0]['verified'])
        self.assertTrue(records['meta'][0]['migration']['complete'])
        self.assertIsNone(self.local_raw())

    def test_v1_migration_preserves_every_record_and_original_byte_for_byte(self):
        self.prepare()
        self.ready()
        self.assertEqual(self.state(),FIXTURE)
        self.assertEqual(self.local_raw(),RAW)
        records=self.records()
        self.assertEqual(len(records['sessions']),5)
        self.assertEqual(len(records['entries']),5)
        self.assertEqual(len(records['sets']),8)
        self.assertEqual({x['id'] for x in records['exercises']},{ex['id'] for plan in FIXTURE['exercises'].values() for ex in plan})
        self.assertEqual({x['id'] for x in records['sessions']},{x['id'] for x in FIXTURE['sessions']})
        self.assertEqual(records['backups'][0]['raw'],RAW)
        self.assertEqual(len(records['planVersions']),4)
        self.assertTrue(all(x['planVersion']['provenance']=='legacy-current-only' for x in records['sessions']))
        self.assertTrue(all('tonnage' not in x['value'] for x in records['sets']))
        self.page.reload();self.ready()
        self.assertEqual(self.state(),FIXTURE)
        self.assertEqual(len(self.records()['backups']),1)

    def test_transaction_abort_halfway_and_retry(self):
        script="""() => {const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(value){const r=add.call(this,value);if(this.name==='sets')this.transaction.abort();return r}}"""
        self.prepare(script=script)
        expect(self.page.locator('[role=alert]')).to_be_visible()
        records=self.records()
        self.assertTrue(all(not rows for rows in records.values()))
        self.assertEqual(self.local_raw(),RAW)
        self.assertIsNone(self.page.evaluate('(key)=>localStorage.getItem(key)',OWNER))
        # New page has no injected fault; retry from the untouched source.
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url);self.ready()
        self.assertEqual(self.state(),FIXTURE)

    def test_quota_during_migration_aborts_without_partial_history(self):
        script="""() => {const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(v){if(this.name==='sets')throw new DOMException('Brak miejsca','QuotaExceededError');return add.call(this,v)}}"""
        self.prepare(script=script)
        expect(self.page.locator('[role=alert]')).to_contain_text('Brak miejsca')
        self.assertEqual(self.local_raw(),RAW)
        self.assertTrue(all(not rows for rows in self.records().values()))
        expect(self.page.locator('[data-act=start]')).to_have_count(0)

    def test_readback_verification_failure_aborts_migration(self):
        script="""() => {const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(v){return add.call(this,this.name==='sets'?{...v,value:{kg:'0',reps:'1'}}:v)}}"""
        self.prepare(script=script)
        expect(self.page.locator('[role=alert]')).to_contain_text('Niezgodne rekordy')
        self.assertTrue(all(not rows for rows in self.records().values()))
        self.assertEqual(self.local_raw(),RAW)

    def test_closing_page_aborts_pending_migration_and_reopens_safely(self):
        self.prepare(script=PAUSE)
        self.page.wait_for_function('window.__held === true')
        expect(self.page.locator('[data-act=finish]')).to_have_count(0)
        self.page.close()
        self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url+'tests/')
        self.assertTrue(all(not rows for rows in self.records().values()))
        self.page.goto(self.url);self.ready()
        self.assertEqual(self.state(),FIXTURE)

    def test_success_waits_for_transaction_complete(self):
        self.prepare();self.ready()
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        self.page.locator('[data-panel=result]').click()
        self.page.locator('[data-main=kg]').fill('110')
        self.page.locator('[data-main=reps]').fill('10')
        self.page.evaluate(PAUSE)
        self.page.locator('.seriesResultForm [type=submit]').click()
        self.page.wait_for_function('window.__held === true')
        expect(self.page.locator('.seriesResultForm')).to_be_visible()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_have_count(0)
        self.page.evaluate('window.__hold=false')
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.assertEqual(self.state()['entries'][-1]['kg'],'110')

    def test_two_tabs_concurrent_migration_and_serialized_writes(self):
        self.prepare(script=PAUSE)
        self.page.wait_for_function('window.__held === true')
        other=self.context.new_page();other.on('dialog',self.dialog)
        other.goto(self.url)
        self.page.evaluate('window.__hold=false')
        self.ready()
        expect(other.locator('[data-act=finish]')).to_be_visible()
        # Two backends loaded at the same revision: only one may commit.
        results=other.evaluate("""async()=>{
          const a=await PushPullDB.open(()=>{}),b=await PushPullDB.open(()=>{});
          const x=a.value,y=b.value;x.exercises['PUSH A'][0].notes='A';y.exercises['PUSH A'][0].notes='B';
          const result=await Promise.allSettled([a.commit(x),b.commit(y)]);a.close();b.close();
          return result.map(r=>r.status);
        }""")
        self.assertEqual(sorted(results),['fulfilled','rejected'])
        expect(self.page.locator('[role=alert]')).to_be_visible()
        self.assertEqual(len(self.state()['sessions']),5)
        self.assertEqual(self.local_raw(),RAW)

    def test_full_backup_restores_versions_notes_sets_and_metadata(self):
        self.prepare();self.ready();self.settings()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        backup=Path(download.value.path()).read_text()
        value=json.loads(backup)
        self.assertEqual(value['data'],FIXTURE)
        self.assertEqual(value['format'],'pushpull-backup')
        self.assertEqual(len(value['catalog']['planVersions']),4)
        # Create an additional archived version without changing any training parameter.
        # It represents a previously recorded plan with the same IDs, different provenance.
        archived=json.loads(json.dumps(value['catalog']['planVersions'][0]))
        archived['id']='archived-v0';archived['provenance']='recorded'
        value['catalog']['planVersions'].append(archived)
        self.import_data(json.dumps(value));self.settings()
        with self.page.expect_download() as second:self.page.locator('[data-act=export]').click()
        restored=json.loads(Path(second.value.path()).read_text())
        self.assertEqual(restored['data'],value['data'])
        self.assertEqual(restored['catalog'],value['catalog'])
        self.assertTrue(all(x in restored['archives'] for x in value['archives']))
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url);self.ready()
        self.assertEqual(self.state(),FIXTURE)
        self.assertEqual(len(self.records()['planVersions']),5)
        self.assertEqual(self.local_raw(),RAW)

    def test_old_application_conflict_preserves_and_exports_both_histories(self):
        self.prepare();self.ready()
        self.page.locator('[data-act=finish]').click()
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        before=self.state()
        old=self.context.new_page();old.goto(self.url+'legacy/')
        old.locator('[data-expand="PUSH-A-1"]').click()
        old.locator('#notesForm textarea').fill('Zapis starej aplikacji')
        old.locator('#notesForm button').click()
        edited=json.loads(self.local_raw())
        expect(self.page.locator('[role=alert]')).to_be_visible()
        self.assertEqual(self.state(),before)
        self.page.reload()
        expect(self.page.locator('[role=alert]')).to_be_visible()
        with self.page.expect_download() as current:self.page.locator('[data-recovery-current]').click()
        full=Path(current.value.path()).read_text()
        self.assertEqual(json.loads(full)['data'],before)
        with self.page.expect_download() as legacy:self.page.locator('[data-recovery-export]').click()
        self.assertEqual(json.loads(Path(legacy.value.path()).read_text()),edited)
        self.import_data(full)
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.assertEqual(self.state(),before)
        self.assertEqual(json.loads(self.local_raw()),edited)
        self.assertTrue(any(x['kind']=='legacy-conflict' for x in self.records()['backups']))

    def test_missing_indexeddb_after_migration_does_not_replay_old_history(self):
        self.prepare();self.ready()
        self.page.goto(self.url+'tests/')
        self.page.evaluate("""async()=>{await new Promise(resolve=>{const r=indexedDB.deleteDatabase('pushpull');r.onsuccess=resolve})}""")
        self.page.goto(self.url)
        expect(self.page.locator('[role=alert]')).to_contain_text('Brak wcześniej używanej bazy')
        expect(self.page.locator('[data-act=start]')).to_have_count(0)
        self.import_data(RAW);self.ready()
        self.assertEqual(self.state(),FIXTURE)

    def test_corrupt_indexeddb_blocks_and_can_be_backed_up_before_restore(self):
        self.prepare();self.ready()
        self.page.goto(self.url+'tests/')
        self.page.evaluate("""async()=>{const db=await new Promise(resolve=>{const r=indexedDB.open('pushpull');r.onsuccess=()=>resolve(r.result)});await new Promise(resolve=>{const tx=db.transaction('sets','readwrite');tx.objectStore('sets').delete(JSON.stringify(['entry-1',0]));tx.oncomplete=resolve});db.close()}""")
        self.page.goto(self.url)
        expect(self.page.locator('[role=alert]')).to_be_visible()
        with self.page.expect_download() as dump:self.page.locator('[data-recovery-current]').click()
        self.assertEqual(json.loads(Path(dump.value.path()).read_text())['format'],'pushpull-idb-recovery')
        self.import_data(RAW);self.ready()
        self.assertEqual(self.state(),FIXTURE)
        self.assertTrue(any(json.loads(x['raw']).get('format')=='pushpull-idb-recovery' for x in self.records()['backups'] if x['kind']=='before-import'))

    def test_real_service_worker_update_failed_migration_retry_and_offline(self):
        context=self.new_context(service_workers='allow')
        page=context.new_page();page.on('dialog',lambda d:d.accept())
        self.addCleanup(setattr,QuietServer,'upgrade_latest',False)
        QuietServer.upgrade_latest=False
        page.goto(self.url+'tests/')
        page.evaluate('(raw)=>localStorage.setItem("pushpull_skeleton_v1",raw)',RAW)
        page.goto(self.url+'upgrade/')
        expect(page.locator('[data-act=finish]')).to_be_visible()
        page.evaluate('navigator.serviceWorker.ready')
        page.wait_for_function('navigator.serviceWorker.controller !== null')
        QuietServer.upgrade_latest=True
        page.evaluate('async()=>{window.__registration=await navigator.serviceWorker.ready;await window.__registration.update()}')
        page.wait_for_function('window.__registration.waiting?.state === "installed"')
        page.close()
        page=context.new_page();page.on('dialog',lambda d:d.accept())
        page.goto(self.url+'tests/')
        page.evaluate('(url)=>navigator.serviceWorker.getRegistration(url).then(r=>window.__registration=r)',self.url+'upgrade/')
        page.wait_for_function('window.__registration.active?.state === "activated" && !window.__registration.waiting')
        page.add_init_script("""if(!sessionStorage.getItem('fail-migration-once')){sessionStorage.setItem('fail-migration-once','1');const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(v){if(this.name==='sets')throw new DOMException('Brak miejsca','QuotaExceededError');return add.call(this,v)}}""")
        page.goto(self.url+'upgrade/')
        expect(page.locator('[role=alert]')).to_contain_text('Brak miejsca')
        self.assertEqual(page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)
        self.assertTrue(all(not rows for rows in self.records(page).values()))
        context.set_offline(True)
        page.reload()
        expect(page.locator('[data-act=finish]')).to_be_visible()
        current=page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}")
        self.assertEqual(current,FIXTURE)
        self.assertEqual(page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)

    def test_existing_legacy_backups_are_preserved_and_exported(self):
        key=KEY+'_backup_existing'
        copy='{previous-invalid-original'
        self.prepare(backups={key:copy});self.ready()
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',key),copy)
        records=self.records()
        self.assertTrue(any(b['raw']==copy and b['id']==key for b in records['backups']))
        self.settings()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        full=json.loads(Path(download.value.path()).read_text())
        self.assertTrue(any(b['raw']==copy for b in full['archives']))

    def test_full_backup_invalid_catalog_and_archives_leave_history_intact(self):
        self.prepare();self.ready();self.settings()
        with self.page.expect_download() as download:self.page.locator('[data-act=export]').click()
        backup=json.loads(Path(download.value.path()).read_text())
        original=self.state()
        invalid=[]
        value=json.loads(json.dumps(backup));value['version']=3;invalid.append(value)
        value=json.loads(json.dumps(backup));value['catalog']['plans'][0]['currentVersion']='missing';invalid.append(value)
        value=json.loads(json.dumps(backup));value['catalog']['sessionVersions']['session-1']['versionId']='missing';invalid.append(value)
        value=json.loads(json.dumps(backup));value['catalog']['planVersions'][0]['exercises'][0]['sets']=0;invalid.append(value)
        value=json.loads(json.dumps(backup));value['archives'][0]['raw']=123;invalid.append(value)
        value=json.loads(json.dumps(backup));value['catalog']['unexpected']='do not silently discard';invalid.append(value)
        for value in invalid:
            self.import_data(json.dumps(value))
            self.assertEqual(self.state(),original)
        self.assertEqual(len(self.alerts),len(invalid))
        self.assertEqual(self.local_raw(),RAW)
        # v1 permitted arbitrary extension fields. Its version, rather than an
        # extension named 'format', must determine legacy compatibility.
        extended={**FIXTURE,'format':'pushpull-backup'}
        self.import_data(json.dumps(extended))
        self.assertEqual(self.state(),extended)
        self.assertEqual(self.local_raw(),RAW)

    def test_actual_browser_process_close_and_reopen_persistent_profile(self):
        executable=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        with tempfile.TemporaryDirectory(prefix='pushpull-profile-') as profile:
            first=self.pw.chromium.launch_persistent_context(profile,executable_path=executable,headless=True,args=['--no-sandbox'],service_workers='block')
            try:
                page=first.new_page();page.goto(self.url+'tests/')
                page.evaluate('(raw)=>localStorage.setItem("pushpull_skeleton_v1",raw)',RAW)
                page.goto(self.url)
                expect(page.locator('[data-act=finish]')).to_be_visible()
            finally:first.close()
            second=self.pw.chromium.launch_persistent_context(profile,executable_path=executable,headless=True,args=['--no-sandbox'],service_workers='block')
            try:
                page=second.new_page();page.goto(self.url)
                expect(page.locator('[data-act=finish]')).to_be_visible()
                current=page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}")
                self.assertEqual(current,FIXTURE)
                self.assertEqual(page.evaluate('(key)=>localStorage.getItem(key)',KEY),RAW)
            finally:second.close()

    def test_abort_after_requests_succeed_has_no_success_message(self):
        self.prepare();self.ready()
        before=self.state()
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        self.page.locator('[data-panel=result]').click()
        self.page.locator('[data-main=kg]').fill('110')
        self.page.evaluate(PAUSE)
        self.page.locator('.seriesResultForm [type=submit]').click()
        self.page.wait_for_function('window.__held === true')
        self.page.evaluate('window.__hold=false;window.__transaction.abort()')
        expect(self.page.locator('.seriesResultForm')).to_be_visible()
        self.page.wait_for_function('document.querySelector(".seriesResultForm [data-main=kg]")?.value === "110"')
        self.assertEqual(self.state(),before)
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_have_count(0)
        self.assertTrue(self.alerts)

    def test_simultaneous_commits_in_one_backend_compare_captured_revision(self):
        self.prepare();self.ready()
        results=self.page.evaluate("""async()=>{
          const db=await PushPullDB.open(()=>{}),a=db.value,b=db.value;
          a.exercises['PUSH A'][0].notes='pierwszy';b.exercises['PUSH A'][0].notes='drugi';
          try{return (await Promise.allSettled([db.commit(a),db.commit(b)])).map(r=>r.status)}finally{db.close()}
        }""")
        self.assertEqual(sorted(results),['fulfilled','rejected'])
        self.assertEqual(len(self.state()['sessions']),5)
