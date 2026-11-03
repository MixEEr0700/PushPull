from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_used_restore as profiles
import test_indexeddb as native
class Backup147(BrowserHarness):
    produce=profiles.UsedRestore.produce
    decode=profiles.UsedRestore.decode
    export=profiles.UsedRestore.export
    used=profiles.UsedRestore.used
    choose=profiles.UsedRestore.choose
    apply=profiles.UsedRestore.apply
    def test_aggregate_string_limit_is_avoided_and_rescue_rollback_remains_exact(self):
        raw,ctx,p,before=self.used();self.choose(p,raw);records=native.IndexedDBMigration.records(self,p)
        p.evaluate("""()=>{const Original=Worker;window.Worker=class extends Original{constructor(url,opts){if(String(url).includes('canonical-restore-worker')){const script='let early;onmessage=e=>early=e;const stringify=JSON.stringify;JSON.stringify=function(v,...a){if(v&&typeof v===\"object\"&&(v.records&&v.meta||v.journalState&&v.journalCheckpoints))throw new RangeError(\"Invalid string length: synthetic aggregate budget\");return stringify.call(this,v,...a)};await import('+JSON.stringify(String(url))+');if(early)onmessage(early);';url=URL.createObjectURL(new Blob([script],{type:'text/javascript'}));}super(url,opts)}}}""")
        self.apply(p);self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,raw));after=native.IndexedDBMigration.records(self,p);import json
        ref=json.loads(after['journalCheckpoints'][0]['raw']);self.assertEqual(ref['format'],'pushpull-rescue-reference');point=p.evaluate("""async id=>{const m=await import('./model/canonical-rescue.mjs');const p=await m.readRescue(id);return p.evidence.records}""",ref['id']);self.assertEqual(point,{k:records[k] for k in point})
        self.data_section('undo',p);p.locator('[data-rescue-points]').click();p.locator('[data-rescue-load]').click();expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000);self.apply(p);self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,before))
    def test_existing_legacy_rescue_proof_still_restores_original_data(self):
        raw,ctx,p,before=self.used();self.choose(p,raw);self.apply(p);self.export(p)
        p.evaluate("""async()=>{const {hashJSON}=await import('./model/journal-index.mjs');const db=await new Promise(r=>{const q=indexedDB.open('pushpull-canonical-rescue');q.onsuccess=()=>r(q.result)});const point=await new Promise(r=>{const q=db.transaction('points').objectStore('points').getAll();q.onsuccess=()=>r(q.result[0])});point.evidenceSHA=await hashJSON(point.evidence);delete point.evidenceEncoding;await new Promise((r,j)=>{const tx=db.transaction('points','readwrite');tx.objectStore('points').put(point);tx.oncomplete=r;tx.onabort=()=>j(tx.error)});db.close()}""")
        self.data_section('undo',p);p.locator('[data-rescue-points]').click();p.locator('[data-rescue-load]').click();expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000);self.apply(p);self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,before))
    def test_rescue_reference_cannot_replace_a_different_physical_snapshot(self):
        self.page.wait_for_selector('[data-act=start]')
        result=self.page.evaluate("""async()=>{const a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull');try{const before=await a.readRecords(db),other=structuredClone(before.records);other.journalState[0].revision++;let error='accepted';try{await a.replaceSource(db,{}, {expectedState:before.state,expectedRecords:other,recovery:true,indexed:true})}catch(e){error=e.message}return {error,unchanged:a.same(before.records,(await a.readRecords(db)).records)}}finally{db.close()}}""")
        self.assertIn('rescue snapshot CAS',result['error']);self.assertTrue(result['unchanged'])
