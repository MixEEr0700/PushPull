"""Model CAS/readback compare full content, including raw, with real IndexedDB."""
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy
import test_v2_training as v2


class ModelComparison(BrowserHarness):
    activate=v2.V2Training.activate
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    records=legacy.IndexedDBMigration.records
    open_result=v2.V2Training.open_result
    fill_rows=v2.V2Training.fill_rows

    def result(self):
        form=self.open_result('PUSH A','PUSH-A-3');self.fill_rows(form)
        expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        return form

    def test_model_cas_rejects_changed_raw_even_with_unchanged_revision_and_digest(self):
        self.activate();form=self.result()
        self.page.evaluate("""async()=>{
          const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('pushpull');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
          try{await new Promise((resolve,reject)=>{
            const tx=db.transaction('meta','readwrite',{durability:'strict'}),store=tx.objectStore('meta'),r=store.get('training-model-v1');
            r.onsuccess=()=>{const row=r.result;row.document.payload.legacySources[0].raw+=' ';store.put(row)};
            tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error);
          })}finally{db.close()}
        }""")
        before=self.records()
        with self.page.expect_event('dialog'):form.locator('[type=submit]').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertTrue(any('Model zmienił' in message for message in self.alerts))
        self.assertEqual(self.records(),before)
        self.assertNotIn('Wynik zapisany',self.page.locator('body').inner_text())

    def test_changed_large_raw_readback_aborts_all_stores_and_preserves_draft(self):
        self.activate()
        self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{
          await db.commit(db.value,{importedArchives:[{id:'cmp-large-archive',kind:'recovery',createdAt:'2026-01-01T00:00:00.000Z',raw:'Ł😀'.repeat(128*1024)+'cmp-archive-tail'}]});
        }finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible(timeout=15000)
        form=self.result();before=self.records()
        self.page.evaluate("""()=>{
          const put=IDBObjectStore.prototype.put;
          IDBObjectStore.prototype.put=function(value,...args){
            if(this.name==='meta'&&value.key==='training-model-v1'){
              const changed=structuredClone(value),source=changed.document.payload.legacySources[0];
              if(!source.raw.includes('cmp-archive-tail'))throw Error('missing synthetic archive');
              source.raw=source.raw.replace('cmp-archive-tail','cmp-archive-taiX');
              window.__changedModelReadback=true;
              window.__unchangedModelDigest=changed.document.integrity.digest===value.document.integrity.digest;
              return put.call(this,changed,...args);
            }
            return put.call(this,value,...args);
          };
        }""")
        with self.page.expect_event('dialog'):form.locator('[type=submit]').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertTrue(self.page.evaluate('window.__changedModelReadback&&window.__unchangedModelDigest'))
        self.assertTrue(any('Model nie przeszedł' in message for message in self.alerts))
        self.assertEqual(self.records(),before)
        self.assertNotIn('Wynik zapisany',self.page.locator('body').inner_text())
