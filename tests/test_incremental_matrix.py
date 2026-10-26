"""Current Matrix + protocol 2, real browser storage and strict transactions."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,ROOT,confirm_restore
from test_indexeddb import PAUSE
from test_indexeddb import RAW,FIXTURE
import test_v2_training as v2

class IncrementalMatrix(BrowserHarness):
    activate=v2.V2Training.activate
    prepare=v2.V2Training.prepare
    ready=v2.V2Training.ready
    open_result=v2.V2Training.open_result
    fill_rows=v2.V2Training.fill_rows

    def test_two_first_open_clients_read_current_protocol_after_one_upgrades_during_the_other_preparation(self):
        self.page.goto(self.url+'tests/')
        self.page.evaluate("""async raw=>{await new Promise((ok,no)=>{const r=indexedDB.deleteDatabase('pushpull');r.onsuccess=ok;r.onerror=()=>no(r.error)});localStorage.clear();localStorage.setItem('pushpull_skeleton_v1',raw)}""",RAW)
        first=self.context.new_page();first.on('dialog',self.dialog)
        first.add_init_script("""(()=>{const digest=crypto.subtle.digest.bind(crypto.subtle);let held=false;crypto.subtle.digest=async(...args)=>{if(!held){held=true;window.__heldDigest=true;await new Promise(resolve=>window.__releaseDigest=resolve)}return digest(...args)}})()""")
        first.goto(self.url);first.wait_for_function('window.__heldDigest===true')
        second=self.context.new_page();second.on('dialog',self.dialog);second.goto(self.url)
        expect(second.locator('[data-act=finish]')).to_be_visible()
        first.evaluate('window.__releaseDigest()');expect(first.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual(first.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}'),FIXTURE)
        self.assertEqual(second.evaluate('async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}'),FIXTURE)

    def expose_handle(self):
        code=(ROOT/'app.js').read_text().replace('const database=await PushPullDB.open(fresh);','const database=await PushPullDB.open(fresh);window.__appDB=database;').replace('let data=database.value||fresh();','let data=database.value||fresh();window.__peek=()=>data;')
        self.page.route('**/app.js',lambda route:route.fulfill(body=code,content_type='text/javascript'))
        self.page.reload()

    def test_real_result_uses_small_ack_without_full_value_or_export_and_waits_for_strict_complete(self):
        self.expose_handle();self.start();self.result('22,5','9')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.evaluate("""()=>{
         window.__beforeRevision=__appDB.revision;
         for(const key of ['value','export','model'])Object.defineProperty(__appDB,key,{get(){throw Error('full '+key+' on result path')}});
         const transaction=IDBDatabase.prototype.transaction;window.__native=[];
         IDBDatabase.prototype.transaction=function(...args){const tx=transaction.apply(this,args);if(tx.mode==='readwrite'&&[...tx.objectStoreNames].includes('journalResults'))tx.addEventListener('complete',()=>__native.push({at:performance.now(),durability:tx.durability}));return tx};
        }""")
        self.page.evaluate(PAUSE);self.page.locator('.seriesResultForm [type=submit]').click()
        self.page.wait_for_function('window.__held===true')
        self.assertEqual(self.page.evaluate('__peek().entries.length'),0)
        self.assertEqual(self.page.evaluate('__native'),[])
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_have_count(0)
        self.page.evaluate('window.__hold=false')
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        self.assertEqual(self.page.evaluate('__appDB.revision===__beforeRevision+1'),True)
        self.assertEqual(self.page.evaluate('__peek().entries[0].kg'),'22.5')
        self.assertEqual(self.page.evaluate('__native.length'),1)
        self.assertEqual(self.page.evaluate('__native[0].durability'),'strict')
        self.assertFalse(self.alerts,self.alerts)
        self.page.reload();self.assertEqual(self.state()['entries'][0]['reps'],'9')

    def test_native_snapshot_models_are_shared_frozen_but_current_plan_and_editor_are_detached(self):
        self.activate();form=self.open_result('PUSH A','PUSH-A-3');self.fill_rows(form)
        form.locator('[type=submit]').click();expect(form).to_have_count(0)
        result=self.page.evaluate("""async()=>{
         const db=await PushPullDB.open(()=>{});try{
          const value=db.value,snapshot=value.trainingJournal.sessionSnapshots.at(-1),original=snapshot.model.exercises[0].name;
          const blocked=!Reflect.set(snapshot.model.exercises[0],'name','must not change');
          value.trainingJournal.model.exercises[0].name='editable current plan';value.entries.at(-1).kg='caller edit';
          const actual=db.value;
          return {blocked,currentDetached:snapshot.model.exercises[0].name===original,entryDetached:actual.entries.at(-1).kg==='20',frozen:Object.isFrozen(snapshot.model)&&Object.isFrozen(snapshot.model.exercises[0])};
         }finally{db.close()}
        }""")
        self.assertEqual(result,dict.fromkeys(['blocked','currentDetached','entryDetached','frozen'],True))

    def test_confirmed_restore_can_quarantine_corrupt_v2_records_without_losing_preimage(self):
        self.start();self.result('24','8');self.save();before=self.state()
        backup=self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return JSON.stringify(d.export())}finally{d.close()}}")
        self.page.goto(self.url+'tests/')
        self.page.evaluate("""async()=>{
         const {connectV2,transact,request}=await import('../model/journal-idb.mjs'),db=await connectV2('pushpull');
         try{await transact(db,['journalResults','journalObjects'],'readwrite',async tx=>{
          const row=(await request(tx.objectStore('journalResults').getAll()))[0],object=await request(tx.objectStore('journalObjects').get(row.ref));object.json+=' ';tx.objectStore('journalObjects').put(object);
         })}finally{db.close()}
        }""")
        self.page.goto(self.url);expect(self.page.locator('[role=alert]')).to_be_visible()
        with self.page.expect_download() as download:self.page.locator('[data-recovery-current]').click()
        recovery=json.loads(Path(download.value.path()).read_text());self.assertEqual(recovery['version'],2)
        corrupt=recovery['records']['journalObjects']
        self.page.locator('#importFile').set_input_files({'name':'restore.json','mimeType':'application/json','buffer':backup.encode()})
        confirm_restore(self.page)
        expect(self.page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible()
        self.assertEqual(self.state(),before)
        result=self.page.evaluate("""async()=>{
         const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull');try{
          const rows=await api.readRecords(db),cp=rows.records.journalCheckpoints.find(r=>r.protocol===2),writer=await api.openWriter(db);
          return {objects:JSON.parse(cp.raw).journalObjects,archives:writer.source.archives.some(a=>a.kind==='before-import'&&JSON.parse(a.raw).version===2)};
         }finally{db.close()}
        }""")
        self.assertEqual(result['objects'],corrupt);self.assertTrue(result['archives'])
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.assertEqual(self.state(),before)

    def test_export_audits_opaque_archives_and_old_checkpoint_is_not_updated_after_result(self):
        self.start();self.result('28','7');self.save()
        result=self.page.evaluate("""async()=>{
         const api=await import('./model/journal-idb.mjs'),db=await api.connectV2('pushpull'),handle=await PushPullDB.open(()=>{});try{
          const rows=await api.readRecords(db),old=await api.legacyEvidence(db),original=rows.records.journalCheckpoints.find(r=>r.protocol===1).evidence;
          const fixed=x=>({...x,meta:x.meta.filter(r=>['state','training-model-v1'].includes(r.key))});
          const checkpointUnchanged=JSON.stringify(fixed(old))===JSON.stringify(fixed(original));
          await handle.commit(handle.value,{importedArchives:[{id:'audit-raw',kind:'opaque',createdAt:'2026-10-25T00:00:00.000Z',raw:'Ł😀'.repeat(1024)}]});
          const archive=(await api.readRecords(db)).records.journalArchives.find(r=>r.id==='audit-raw');
          await api.transact(db,['journalObjects'],'readwrite',async tx=>{const row=await api.request(tx.objectStore('journalObjects').get(archive.ref));row.json+=' ';tx.objectStore('journalObjects').put(row)});
          let rejected=false;try{await handle.auditExport()}catch{rejected=true}
          return {checkpointUnchanged,rejected};
         }finally{db.close();handle.close()}
        }""")
        self.assertEqual(result,{'checkpointUnchanged':True,'rejected':True})
