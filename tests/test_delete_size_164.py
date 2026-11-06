"""Reference preimages on isolated synthetic stores; never user data."""
import base64
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_v2_training as training
import test_indexeddb as native

class DeleteSize164(BrowserHarness):
    prepare=training.V2Training.prepare
    ready=training.V2Training.ready
    activate=training.V2Training.activate
    def delete(self,s):
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="'+s['date']+'"]').click()
        self.page.locator('[data-act=deleteSession][data-id="'+s['id']+'"]').click();expect(self.page.get_by_text('Trening usunięty',exact=True)).to_be_visible(timeout=30000)
    def test_repeated_deletion_large_archive_and_portable_restore(self):
        source=Path('model/journal-protocol.mjs').read_text().replace('objectBytes:128*1024*1024','objectBytes:1024*1024')
        self.page.route('**/model/journal-protocol.mjs',lambda r:r.fulfill(body=source,content_type='text/javascript'))
        self.activate()
        self.page.evaluate('''async()=>{const d=await PushPullDB.open(()=>{});try{await d.ensureFull();const data=d.value,j=await import('./model/journal.mjs'),p=await import('./model/performance.mjs');while(data.sessions.length<40){const s={id:crypto.randomUUID(),seq:Math.max(...data.sessions.map(s=>s.seq))+1,type:'PULL A',date:'2026-10-21',status:'done'};data.sessions.push(s);await j.startSession(data,s,'2026-10-21T10:00:00.000Z');for(const ex of j.exercisesFor(data,s)){const performance=p.newPerformance(ex);for(const r of performance.rows)for(const v of r.segments){v.kg='20';v.reps='8'}const series=p.flatten(performance),e={id:crypto.randomUUID(),sessionId:s.id,exerciseId:ex.id,createdAt:'2026-10-21T10:00:00.000Z',kg:series[0].kg,reps:series[0].reps,performance,series};j.recordEntry(data,e);data.entries.push(e);}}await d.commit(data,{importedArchives:[{id:'synthetic-164',kind:'before-import',createdAt:'2026-11-06T00:00:00.000Z',raw:'"\\\\'.repeat(131072)}]})}finally{d.close()}}''')
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        before=self.state();old_ids=self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.backups()}finally{d.close()}}")
        self.delete(before['sessions'][-1]);after=self.state();self.assertEqual(after['sessions'],before['sessions'][:-1]);self.assertEqual(after['entries'],[e for e in before['entries'] if e['sessionId']!=before['sessions'][-1]['id']])
        point=self.page.evaluate("async old=>{const d=await PushPullDB.open(()=>{});try{return d.backups().find(id=>!old.includes(id))}finally{d.close()}}",old_ids)
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.delete(after['sessions'][-1])
        second=self.page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.backups().at(-1)}finally{d.close()}}")
        raw=self.page.evaluate("async id=>{const d=await PushPullDB.open(()=>{});try{const f=await d.readBackup(id),a=new Uint8Array(await f.arrayBuffer());let s='';for(let i=0;i<a.length;i+=8192)s+=String.fromCharCode(...a.subarray(i,i+8192));return btoa(s)}finally{d.close()}}",second)
        ctx=self.new_context(service_workers='block');p=ctx.new_page();p.on('dialog',self.dialog);p.goto(self.url);p.wait_for_selector('[data-act=start]');p.locator('[data-tab=settings]').click();p.locator('[data-backup-flow=restore]').click();p.locator('#importFile').set_input_files({'name':'rescue.ppc1','mimeType':'application/octet-stream','buffer':base64.b64decode(raw)})
        expect(p.locator('[data-ppc1-preview]')).to_be_visible(timeout=60000);p.locator('[data-restore-confirm]').click();expect(p.get_by_text('Dane zaimportowane',exact=True)).to_be_visible(timeout=60000)
        p.reload();p.wait_for_selector('[data-tab=settings]');actual=p.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return d.value}finally{d.close()}}")
        self.assertEqual(actual,after)
        self.assertTrue(p.evaluate("async id=>{const d=await PushPullDB.open(()=>{});try{return (await d.readBackup(id)) instanceof Blob}finally{d.close()}}",point))
    def test_manifest_limit_refuses_before_persistent_write(self):
        source=Path('model/reference-preimage.mjs').read_text().replace('encodedJSON(raw,LIMITS.objectBytes)','encodedJSON(raw,globalThis.__limitReferenceTest?1000:LIMITS.objectBytes)')
        self.page.route('**/model/reference-preimage.mjs',lambda r:r.fulfill(body=source,content_type='text/javascript'))
        self.activate();before=native.IndexedDBMigration.records(self);data=self.state();self.page.evaluate('window.__limitReferenceTest=true')
        target=data['sessions'][-1];self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="'+target['date']+'"]').click()
        with self.page.expect_event('dialog',predicate=lambda d:d.type=='alert'):self.page.locator('[data-act=deleteSession][data-id="'+target['id']+'"]').click()
        self.assertIn('protocol JSON size',self.alerts[-1]);self.assertEqual(native.IndexedDBMigration.records(self),before)
    def test_abort_rolls_back_checkpoint_and_history_together(self):
        self.activate();data=self.state();target=data['sessions'][-1]
        self.page.locator('[data-tab=calendar]').click();self.page.locator('[data-day="'+target['date']+'"]').click();before=native.IndexedDBMigration.records(self)
        self.page.evaluate("()=>{const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v,...a){if(this.name==='journalState'&&v.id==='active')this.transaction.abort();return put.call(this,v,...a)}}")
        with self.page.expect_event('dialog',predicate=lambda d:d.type=='alert'):self.page.locator('[data-act=deleteSession][data-id="'+target['id']+'"]').click()
        self.assertEqual(native.IndexedDBMigration.records(self),before)
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.assertEqual(self.state(),data)
    def test_foreign_revision_refuses_without_adding_checkpoint(self):
        self.activate()
        self.page.evaluate("async()=>{window.a164=await PushPullDB.open(()=>{});await a164.ensureFull();window.rev164=a164.revision;window.next164=a164.value;const b=await PushPullDB.open(()=>{});try{await b.ensureFull();const n=b.value;n.sessions[0].date='2026-10-20';await b.commit(n)}finally{b.close()}}")
        before=native.IndexedDBMigration.records(self)
        error=self.page.evaluate("async()=>{try{await a164.commit(next164,{backupBefore:true,expectedRevision:rev164});return ''}catch(e){return e.message}finally{a164.close()}}")
        self.assertTrue(error);self.assertEqual(native.IndexedDBMigration.records(self),before)
