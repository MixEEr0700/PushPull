"""Prepared source: full native IDB readback, caller ownership and atomic failure."""
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy
import test_v2_training as v2


class PreparedWrite(BrowserHarness):
    legacy_backend = True
    activate=v2.V2Training.activate
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready
    records=legacy.IndexedDBMigration.records
    open_result=v2.V2Training.open_result
    fill_rows=v2.V2Training.fill_rows

    def corrupted_save(self,store,method,change,message):
        self.activate();form=self.open_result('PUSH A','PUSH-A-3');self.fill_rows(form)
        expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.records()
        self.page.evaluate("""({store,method,change})=>{
          const original=IDBObjectStore.prototype[method];
          IDBObjectStore.prototype[method]=function(value,...args){
            if(this.name===store&&(store!=='meta'||value.key==='state'&&!value.verified)){
              const copy=structuredClone(value);new Function('value',change)(copy);
              window.__preparedFault=true;return original.call(this,copy,...args);
            }
            return original.call(this,value,...args);
          };
        }""",{'store':store,'method':method,'change':change})
        with self.page.expect_event('dialog'):form.locator('[type=submit]').click()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)
        self.assertTrue(self.page.evaluate('window.__preparedFault'))
        self.assertTrue(any(message in text for text in self.alerts),self.alerts)
        self.assertEqual(self.records(),before,'all source/model/archive/draft stores must roll back')
        self.assertNotIn('Wynik zapisany',self.page.locator('body').inner_text())

    def test_changed_snapshot_in_root_readback_aborts_with_unchanged_counts_and_digest(self):
        self.corrupted_save('meta','put',"value.rest.trainingJournal.sessionSnapshots[0].model.exercises[0].name+=' altered';",'odczyt kontrolny metadanych')

    def test_unknown_row_metadata_in_readback_is_not_ignored(self):
        self.corrupted_save('entries','add',"value.value.future={unexpected:['Ł😀',null]};",'Niezgodne rekordy')

    def test_commit_detaches_catalog_archives_and_source_before_await_without_losing_extensions(self):
        self.activate()
        result=self.page.evaluate("""async()=>{
          const db=await PushPullDB.open(()=>{throw Error('missing fixture')});
          try{
            const data=db.value,catalog=db.export().catalog,expectedCatalog=structuredClone(catalog);
            data.extension={future:['before','Ł😀',null]};
            const drafts=await db.readDrafts(),archives=[{id:'prepared-archive',kind:'recovery',createdAt:'2026-10-25T00:00:00.000Z',raw:'original archive'}];
            const promise=db.commit(data,{importedCatalog:catalog,importedArchives:archives});
            data.extension.future[0]='after';catalog.plans[0].label='caller mutation';archives[0].raw='changed archive';
            await promise;
            return {extension:db.value.extension,catalog:db.export().catalog,expectedCatalog,
              raw:db.export().archives.find(a=>a.id==='prepared-archive').raw,
              draftsUnchanged:JSON.stringify(drafts)===JSON.stringify(await db.readDrafts())};
          }finally{db.close()}
        }""")
        self.assertEqual(result['extension'],{'future':['before','Ł😀',None]})
        self.assertEqual(result['catalog'],result['expectedCatalog'])
        self.assertEqual(result['raw'],'original archive');self.assertTrue(result['draftsUnchanged'])
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.assertEqual(self.state()['extension'],result['extension'])
