"""Optional private timing observer; no app integration or collected record data."""
from playwright.sync_api import expect
from test_browser import BrowserHarness, ROOT
import test_indexeddb as legacy

PROBE=(ROOT/'scripts/pixel_write_probe.js').read_text()

class PixelWriteProbe(BrowserHarness):
    records=legacy.IndexedDBMigration.records

    def test_probe_does_not_write_or_publish_success_before_complete_and_restores_wrappers(self):
        self.start();self.result('73.1234567','9')
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        before=self.records()
        self.page.evaluate('window.__originalProbeMethods=[IDBDatabase.prototype.transaction,IDBObjectStore.prototype.put,IDBObjectStore.prototype.add,IDBObjectStore.prototype.get,crypto.subtle.digest]')
        self.page.evaluate(PROBE)
        self.assertEqual(self.records(),before)
        self.assertEqual(self.page.evaluate('PushPullWriteProbe.samples()'),[])
        self.page.evaluate(legacy.PAUSE)
        self.page.evaluate('window.__holdPut=IDBObjectStore.prototype.put')
        self.page.locator('.seriesResultForm [type=submit]').click()
        self.page.wait_for_function('window.__held===true')
        self.assertEqual(self.page.evaluate('PushPullWriteProbe.samples()'),[])
        self.page.evaluate('window.__hold=false')
        expect(self.page.locator('.seriesResultForm')).to_have_count(0)
        self.page.wait_for_function('PushPullWriteProbe.samples()[0]?.uiReadyMs!==undefined')
        samples=self.page.evaluate('PushPullWriteProbe.samples()');self.assertEqual(len(samples),1)
        sample=samples[0];self.assertEqual(sample['status'],'complete');self.assertEqual(sample['durability'],'strict')
        self.assertGreaterEqual(sample['clickToStrictCompleteMs'],sample['transactionMs'])
        self.assertGreaterEqual(sample['uiReadyMs'],sample['clickToStrictCompleteMs'])
        self.assertEqual(sample['statePuts'],1)
        self.assertEqual(set(sample)-{'kind','trigger','status','durability'}, {'preTransactionMs','transactionMs','clickToStrictCompleteMs','uiReadyMs','statePuts','modelGetMs','nativeSha'})
        self.assertTrue(sample['nativeSha']);self.assertTrue(all(set(s)=={'ms','inputBytes'} for s in sample['nativeSha']))
        self.assertTrue(self.page.evaluate("()=>{PushPullWriteProbe.stop();const methods=[IDBDatabase.prototype.transaction,IDBObjectStore.prototype.put,IDBObjectStore.prototype.add,IDBObjectStore.prototype.get,crypto.subtle.digest];return methods[0]===__originalProbeMethods[0]&&methods[1]===__holdPut&&methods[3]===__originalProbeMethods[3]&&methods[4]===__originalProbeMethods[4]&&window.PushPullWriteProbe===undefined}"))
        # PAUSE itself wraps add after installing the observer. stop() must leave
        # that later wrapper in place instead of overwriting another observer.
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual(self.state()['entries'][0]['kg'],'73.1234567')
