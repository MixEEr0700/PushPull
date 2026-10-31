from test_browser import BrowserHarness
import test_indexeddb as legacy
class CanonicalBackup(BrowserHarness):
    def test_isolated_roundtrip_has_no_persistent_side_effects(self):
        self.page.wait_for_selector('[data-act=start]')
        before=legacy.IndexedDBMigration.records(self);local=self.page.evaluate('({...localStorage})')
        result=self.page.evaluate("""async()=>{const m=await import('./model/canonical-backup.mjs'),f=await import('./tests/canonical-fixture.mjs');const input=f.canonicalFixture(await(await fetch('./tests/fixtures/v1.json')).json(),40);const c=m.createCanonicalBackup(input),file=await m.writeCanonicalBackup(c),out=await m.readCanonicalBackup(file);return {equal:JSON.stringify(c)===JSON.stringify(out),count:out.source.data.sessions.length};}""")
        self.assertEqual(result,dict(equal=True,count=40));self.assertEqual(legacy.IndexedDBMigration.records(self),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local)
