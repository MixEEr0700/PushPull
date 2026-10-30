from test_browser import BrowserHarness
import test_indexeddb as legacy

class CompleteContract(BrowserHarness):
    def test_synthetic_all_stores_field_diff_offline_and_no_storage_mutation(self):
        self.page.wait_for_selector('[data-act=start]')
        records=legacy.IndexedDBMigration.records(self)
        self.page.evaluate("""async()=>{window.contract=await import('./model/complete-backup-contract.mjs');const {completeFixture}=await import('./tests/fixtures/complete-contract-fixture.mjs'),{previewFixture}=await import('./tests/fixtures/compact-preview-fixture.mjs');const s=previewFixture(await(await fetch('./tests/fixtures/v1.json')).json(),null,false);delete s.settings;delete s.metadata;window.input=await completeFixture(s)}""")
        before=self.page.evaluate('({...localStorage})');self.context.set_offline(True)
        result=self.page.evaluate("""async()=>{const baseline=JSON.stringify(input);const out=await contract.readCompleteContract(await contract.writeCompleteContract(input));const {equalJSON}=await import('./model/journal-protocol.mjs');const perStore=contract.COMPLETE_STORES.every(k=>equalJSON(input.indexedDB.stores[k],out.indexedDB.stores[k]));let missing=false;const bad=structuredClone(input);bad.localStorage.pop();try{await contract.validateCompleteContract(bad)}catch{missing=true}return {equal:equalJSON(out,input),perStore,unchanged:baseline===JSON.stringify(input),missing,production:contract.contractCoverage().productionComplete}}""")
        self.assertEqual(result,dict(equal=True,perStore=True,unchanged=True,missing=True,production=False));self.assertEqual(self.page.evaluate('({...localStorage})'),before);self.assertEqual(legacy.IndexedDBMigration.records(self),records)
