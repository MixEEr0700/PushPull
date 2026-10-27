"""Step C only: real IndexedDB, existing fixture/harness, no new infrastructure."""
import json
import subprocess
from playwright.sync_api import expect
from test_browser import BrowserHarness, ROOT,open_result_panel
import test_indexeddb as legacy_tests

KEY='training-model-v1'
HOLD="""() => {
 const add=IDBObjectStore.prototype.add;
 IDBObjectStore.prototype.add=function(value){
   const result=add.call(this,value);
   if(this.name==='meta' && value.key==='training-model-v1'){
     window.__held=true;window.__hold=true;
     const store=this;
     function keep(){if(window.__hold){const r=store.get('pause');r.onsuccess=keep}}
     keep();
   }
   return result;
 };
}"""

class ModelMigration(BrowserHarness):
    legacy_backend = True
    prepare=legacy_tests.IndexedDBMigration.prepare
    ready=legacy_tests.IndexedDBMigration.ready
    records=legacy_tests.IndexedDBMigration.records

    def migrate(self):
        return self.page.evaluate("""async()=>{
          const db=await PushPullDB.open(()=>{throw Error('No DB')});
          try {if(db.error)throw db.error;return await db.prepareModel({ownerId:'test-owner',backupText:JSON.stringify(db.export())})}
          finally {db.close()}
        }""")

    def model(self):
        return self.page.evaluate("""async()=>{
          const db=await PushPullDB.open(()=>{throw Error('No DB')});
          try {if(db.error)throw db.error;return {payload:db.model,backup:await db.exportModelBackup()}}
          finally {db.close()}
        }""")

    def test_complete_history_original_stores_retry_and_v3_roundtrip(self):
        self.prepare();self.ready();before=self.records()
        self.assertFalse(any(x['key']==KEY for x in before['meta'])) # no automatic migration
        document=self.migrate();after=self.records()
        for table in ['plans','planVersions','exercises','sessions','entries','sets','notes','changes']:
            self.assertEqual(after[table],before[table],table)
        self.assertEqual(next(x for x in after['meta'] if x['key']=='state'),before['meta'][0])
        self.assertEqual(self.local_raw(),legacy_tests.RAW)
        p=document['payload']
        self.assertEqual([x['data'] for x in p['sessionRecords']],legacy_tests.FIXTURE['sessions'])
        self.assertEqual([x['data'] for x in p['resultRecords']],legacy_tests.FIXTURE['entries'])
        self.assertEqual(p['model']['planVersions'],[])
        self.assertEqual(p['sessionSnapshots'],[])
        self.assertEqual(p['resultReferences'],[])
        self.assertTrue(all(x['snapshotId'] is None for x in p['sessionRecords']))
        self.assertEqual({x['id'] for x in p['model']['exercises']},{x['id'] for plan in legacy_tests.FIXTURE['exercises'].values() for x in plan})
        self.assertEqual([x['text'] for x in p['model']['userNotes']],[x['notes'] for plan in legacy_tests.FIXTURE['exercises'].values() for x in plan])
        self.page.reload();self.ready();self.migrate()
        self.assertEqual(self.records(),after) # retry adds neither records nor backups
        copy=self.model()
        self.assertEqual(json.loads(copy['backup'])['payload']['resultRecords'],p['resultRecords'])
        self.assertTrue(self.page.evaluate("""async raw=>{const b=await import('./model/backup.mjs');const result=await b.restoreBackup(await b.previewBackup(raw));return await b.exportBackup(result.restored)===raw}""",copy['backup']))
        archived=json.loads(json.loads(copy['backup'])['payload']['legacySources'][0]['raw'])['archives']
        self.assertTrue(any(x['kind']=='before-model-migration' for x in archived))

    def test_abort_quota_corrupt_readback_and_bad_backup_leave_database_unchanged(self):
        faults=["this.transaction.abort()", "throw new DOMException('Brak miejsca','QuotaExceededError')", "value={...value,revision:999}"]
        for fault in faults:
            with self.subTest(fault=fault):
                self.prepare();self.ready();before=self.records()
                message=self.page.evaluate("""async fault=>{
                  const db=await PushPullDB.open(()=>{throw Error('No DB')});const add=IDBObjectStore.prototype.add;
                  IDBObjectStore.prototype.add=new Function('add',`return function(value){if(this.name==='meta' && value.key==='training-model-v1'){${fault}}return add.call(this,value)}`)(add);
                  try{await db.prepareModel({ownerId:'test-owner',backupText:JSON.stringify(db.export())});return null}
                  catch(e){return e.message}finally{IDBObjectStore.prototype.add=add;db.close()}
                }""",fault)
                self.assertTrue(message);self.assertEqual(self.records(),before)
                self.assertEqual(self.local_raw(),legacy_tests.RAW)
                self.migrate() # retry succeeds from the original records
        self.prepare();self.ready();before=self.records()
        self.assertTrue(self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{await db.prepareModel({ownerId:'test-owner',backupText:'{}'});return false}catch{return true}finally{db.close()}}"""))
        self.assertEqual(self.records(),before)

    def test_close_mid_transaction_rolls_back_and_retry_waits_for_completion(self):
        self.prepare();self.ready();before=self.records()
        self.page.evaluate(HOLD)
        self.page.evaluate("""() => {window.__migrationDone=false;window.__bridge=PushPullDB.open(()=>{throw Error('No DB')}).then(async db=>{try{await db.prepareModel({ownerId:'test-owner',backupText:JSON.stringify(db.export())});window.__migrationDone=true}finally{db.close()}})}""")
        self.page.wait_for_function('window.__held===true')
        self.assertFalse(self.page.evaluate('window.__migrationDone'))
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url);self.ready()
        self.assertEqual(self.records(),before)
        self.migrate();self.page.reload();self.ready()
        self.assertEqual(self.state(),legacy_tests.FIXTURE)

    def test_existing_mobile_save_updates_both_representations_and_failure_is_atomic(self):
        self.prepare();self.ready();self.migrate();self.page.reload();self.ready()
        before=self.records()
        self.page.evaluate("""() => {window.__put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v){if(this.name==='meta' && v.key==='training-model-v1')throw new DOMException('Model quota','QuotaExceededError');return window.__put.call(this,v)}}""")
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        open_result_panel(self.page)
        self.page.locator('[data-main=kg]').fill('110')
        self.page.locator('[data-main=reps]').fill('10')
        # Draft persistence is independent of the approved source/model transaction.
        expect(self.page.locator('[data-draft-status]')).to_have_text('Szkic zapisany lokalnie · wynik niezatwierdzony')
        before=self.records()
        # The form is already visible before submit; wait for the actual async failure.
        with self.page.expect_event('dialog'):
            self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.locator('.seriesResultForm')).to_be_visible()
        self.assertEqual(self.records(),before)
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_have_count(0)
        self.assertTrue(any('Model quota' in text for text in self.alerts))
        self.page.evaluate('() => {IDBObjectStore.prototype.put=window.__put}')
        self.page.locator('.seriesResultForm [type=submit]').click()
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        current=self.state();copy=self.model()
        self.assertEqual([x['data'] for x in copy['payload']['resultRecords']],current['entries'])
        self.assertEqual(current['entries'][-1]['kg'],'110')
        self.assertEqual(self.local_raw(),legacy_tests.RAW)
        self.page.reload();self.ready()
        self.assertEqual(self.state(),current)

    def test_empty_history_and_import_keep_bridge_in_sync_and_preimage_is_v3(self):
        self.prepare(None)
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.migrate()
        self.assertEqual(self.model()['payload']['resultRecords'],[])
        self.page.evaluate("""async original=>{
          const db=await PushPullDB.open(()=>{});try{const parsed=PushPullDB.parseBackup(original);await db.commit(parsed.data,{importing:true,importedCatalog:parsed.catalog,importedArchives:parsed.archives})}finally{db.close()}
        }""",legacy_tests.FIXTURE)
        copy=self.model();self.assertEqual([x['data'] for x in copy['payload']['resultRecords']],legacy_tests.FIXTURE['entries'])
        preimages=[x for x in self.records()['backups'] if x['kind']=='before-import']
        self.assertEqual(json.loads(preimages[-1]['raw'])['version'],3)

    def test_pre_migration_tab_cannot_overwrite_model_and_old_writer_is_detected(self):
        self.prepare();self.ready()
        self.page.evaluate('async()=>{window.__stale=await PushPullDB.open(()=>{})}')
        self.migrate()
        self.assertTrue(self.page.evaluate('async()=>{try{await window.__stale.commit(window.__stale.value);return false}catch{return true}finally{window.__stale.close()}}'))
        old=subprocess.check_output(['git','show','e6235acb2deca97fe932e833b156a3fdf01da7b8:indexeddb.js'],cwd=ROOT,text=True)
        self.page.evaluate("""async code=>{const previous=new Function(code+';return PushPullDB')();const db=await previous.open(()=>{});try{const next=db.value;next.entries[0].future='old-writer';await db.commit(next)}finally{db.close()}}""",old)
        result=self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{return {error:db.error?.message,value:db.value,recovery:db.recovery()}}finally{db.close()}}""")
        self.assertIn('revision mismatch',result['error'])
        self.assertIsNone(result['value'])
        self.assertTrue(result['recovery']['modelState'])
        self.assertEqual(self.local_raw(),legacy_tests.RAW)
