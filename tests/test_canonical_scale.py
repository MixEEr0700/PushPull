from test_browser import BrowserHarness
import test_indexeddb as legacy
class CanonicalScale(BrowserHarness):
    def test_6000_sessions_offline_exact_roundtrip_no_persistent_writes(self):
        self.page.wait_for_selector('[data-act=start]')
        before=legacy.IndexedDBMigration.records(self);local=self.page.evaluate('({...localStorage})')
        self.page.evaluate("""async()=>{window.codec=await import('./model/canonical-backup.mjs');const f=await import('./tests/canonical-fixture.mjs');const input=f.canonicalFixture(await(await fetch('./tests/fixtures/v1.json')).json(),6000);input.preferences.snapshots=Array.from({length:6000},(_,i)=>({instructions:'Synthetic'.repeat(10),version:i}));window.synthetic=codec.createCanonicalBackup(input)}""")
        self.context.set_offline(True)
        self.assertTrue(self.page.evaluate("""async()=>{const out=await codec.readCanonicalBackup(await codec.writeCanonicalBackup(synthetic));return JSON.stringify(out)===JSON.stringify(synthetic)}"""))
        self.assertEqual(legacy.IndexedDBMigration.records(self),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
