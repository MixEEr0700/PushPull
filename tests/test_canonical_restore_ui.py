from test_browser import BrowserHarness,wait_for_service_worker_controller,open_result_panel
from playwright.sync_api import expect
from pathlib import Path
import test_indexeddb as legacy
import test_v2_training as v2
import base64,time

class CanonicalRestoreUI(BrowserHarness):
    def decode(self,page,raw):
        return page.evaluate("""async raw=>{const m=await import('./model/canonical-backup.mjs');return m.readCanonicalBackup(new Blob([Uint8Array.from(atob(raw),c=>c.charCodeAt(0))]))}""",base64.b64encode(raw).decode())
    def produce(self):
        self.page.wait_for_selector('[data-act=start]');self.plans('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible();self.page.locator('[data-tab=training]').click();self.start()
        self.page.locator('[data-expand]').first.click();open_result_panel(self.page);form=self.page.locator('.performanceForm');form.locator('[data-rich-action=toggle]').click();v2.V2Training.fill_rows(self,form,'24','8');form.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        from test_browser import open_notes
        if self.page.locator('[data-expand]').first.get_attribute('aria-expanded')=='false':self.page.locator('[data-expand]').first.click()
        open_notes(self.page);note=self.page.locator('[data-personal-note]').first
        if not note.evaluate('(e)=>e.open'):note.locator('summary').click()
        note.locator('textarea').fill('Restore user note Ł😀');note.locator('[type=submit]').click();expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        self.page.locator('[data-expand]').nth(1).click();open_result_panel(self.page);form=self.page.locator('.performanceForm');form.locator('[data-rich-action=toggle]').click();v2.V2Training.fill_rows(self,form,'25','7');expect(form.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});let conflict;await new Promise((r,j)=>{const tx=db.transaction('meta','readwrite'),store=tx.objectStore('meta'),q=store.getAll();q.onsuccess=()=>{const draft=q.result.find(v=>v.key.startsWith('workout-draft:'));if(!draft)throw Error('Missing real draft');const other=structuredClone(draft);other.id+='-conflict';other.key='workout-draft:'+other.id;other.token=crypto.randomUUID();store.add(other);conflict=structuredClone(draft);conflict.token=crypto.randomUUID();store.put({key:'canonical-preferences-v1',value:{units:'kg',nested:{unicode:'Ł😀',enabled:true}}})};tx.oncomplete=r;tx.onabort=()=>j(tx.error)});db.close();localStorage.setItem('pushpull_workout_draft_v1:'+conflict.id+':'+conflict.token,JSON.stringify(conflict));localStorage.setItem('pushpull-note-ui-v1:synthetic','{unfinished');}""")
        self.page.locator('[data-tab=settings]').click();self.backup_flow('save')
        self.page.locator('[data-backup-advanced] > summary').click();self.page.locator('#driveConfig').evaluate('(f)=>{f.closest("details").open=true}');self.page.locator('#driveConfig input').fill('restore-test.apps.googleusercontent.com');self.page.locator('#driveConfig button').click()
        self.page.wait_for_function("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});try{return await new Promise(r=>{const q=db.transaction('meta').objectStore('meta').get('drive-sync-v1');q.onsuccess=()=>r(q.result?.clientId==='restore-test.apps.googleusercontent.com')})}finally{db.close()}}""")
        self.page.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise(r=>{const tx=db.transaction('meta','readwrite'),s=tx.objectStore('meta'),q=s.get('drive-sync-v1');q.onsuccess=()=>s.put({...q.result,selected:'source-test',accounts:{'source-test':{heads:['synthetic-head'],outbox:['synthetic-pending']}}});tx.oncomplete=r});db.close()}""")
        with self.page.expect_download(timeout=60000) as dl:self.page.locator('[data-canonical-export]').click()
        return Path(dl.value.path()).read_bytes()
    def target(self,raw):
        ctx=self.new_context(service_workers='allow');p=ctx.new_page();p.on('dialog',self.dialog);p.goto(self.url);p.wait_for_selector('[data-act=start]');wait_for_service_worker_controller(p)
        p.locator('[data-tab=settings]').click();p.locator('[data-backup-flow=restore]').click();self.assertIn('.ppc1.txt',p.locator('#importFile').get_attribute('accept'));p.locator('#importFile').set_input_files({'name':'new.ppc1.txt','mimeType':'text/plain','buffer':raw});expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000)
        return ctx,p
    def test_real_export_import_restart_and_all_canonical_values(self):
        raw=self.produce();expected=self.decode(self.page,raw);sourceRecords=legacy.IndexedDBMigration.records(self);ctx,p=self.target(raw)
        for width in (360,390,412):
            p.set_viewport_size({'width':width,'height':844});self.assertLessEqual(p.evaluate('document.documentElement.scrollWidth'),width)
        ctx.set_offline(True);started=time.perf_counter()
        p.locator('[data-restore-confirm]').click()
        try:expect(p.locator('[data-restore-success]')).to_be_visible(timeout=20000)
        except Exception:
            print('RESTORE_ERROR',p.locator('#app').inner_text());raise
        elapsed=time.perf_counter()-started;notice=p.locator('[data-restore-success]').inner_text();p.reload();p.wait_for_selector('[data-act=finish]');p.locator('[data-tab=settings]').click();p.locator('[data-backup-flow=save]').click()
        with p.expect_download(timeout=60000) as dl:p.locator('[data-canonical-export]').click()
        out=Path(dl.value.path()).read_bytes();self.assertEqual(self.decode(p,out),expected)
        targetRecords=legacy.IndexedDBMigration.records(self,p);sourceState=sourceRecords['journalState'][0];targetState=targetRecords['journalState'][0];self.assertNotEqual(sourceState['epoch'],targetState['epoch']);self.assertNotEqual(sourceState['root'],targetState['root'])
        sourceDrive=next(r for r in sourceRecords['meta'] if r['key']=='drive-sync-v1');targetDrive=next(r for r in targetRecords['meta'] if r['key']=='drive-sync-v1');self.assertTrue(sourceDrive['accounts']);self.assertNotEqual(sourceDrive['deviceId'],targetDrive['deviceId']);self.assertNotEqual(sourceDrive['token'],targetDrive['token']);self.assertEqual(targetDrive['accounts'],{});self.assertIsNone(targetDrive['selected'])
        self.assertEqual(len(expected['drafts']),2);self.assertEqual(len(expected['source']['data']['trainingJournal']['sessionSnapshots']),1);p.locator('[data-tab=training]').click();expect(p.locator('[data-draft-resume]').first).to_be_enabled();p.locator('[data-draft-resume]').first.click();expect(p.locator('.performanceForm')).to_be_visible();expect(p.locator('.performanceForm input[data-field=kg]').first).to_have_value('25');print('CANONICAL_RESTORED',len(expected['source']['data']['sessions']),len(expected['source']['data']['entries']),len(expected['drafts']),len(expected['buffers']),len(raw),round(elapsed,3),notice)

    def test_preview_cancel_corrupt_and_nonempty_target_never_overwrite(self):
        raw=self.produce();ctx,p=self.target(raw);before=legacy.IndexedDBMigration.records(self,p)
        self.confirm=False
        with p.expect_event('dialog'):p.locator('[data-restore-confirm]').click()
        expect(p.locator('[data-restore-busy]')).to_have_count(0);self.confirm=True
        self.assertEqual(legacy.IndexedDBMigration.records(self,p),before);self.assertIsNone(p.evaluate('localStorage.getItem("pushpull_canonical_restore_pending")'))
        p.locator('#importFile').set_input_files({'name':'bad.ppc1','mimeType':'application/octet-stream','buffer':raw[:-1]});expect(p.locator('[data-restore-error]')).to_be_visible(timeout=60000);self.assertEqual(legacy.IndexedDBMigration.records(self,p),before)
        p.locator('[data-tab=training]').click();p.locator('[data-act=start]').click();expect(p.locator('[data-act=finish]')).to_be_visible();p.locator('[data-tab=settings]').click()
        if p.locator('[data-backup-flow=restore]').get_attribute('aria-expanded')=='false':p.locator('[data-backup-flow=restore]').click()
        p.locator('#importFile').set_input_files({'name':'new.ppc1','mimeType':'application/octet-stream','buffer':raw});expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000)
        before=legacy.IndexedDBMigration.records(self,p);p.locator('[data-restore-confirm]').click();expect(p.locator('[data-restore-error]')).to_contain_text('czystym profilem',timeout=60000)
        self.assertEqual(legacy.IndexedDBMigration.records(self,p),before);self.assertIsNone(p.evaluate('localStorage.getItem("pushpull_canonical_restore_pending")'))

    def test_local_quota_failure_pending_gate_survives_restart_and_blocks_other_writers(self):
        raw=self.produce();ctx,p=self.target(raw)
        p.evaluate("""()=>{const put=Storage.prototype.setItem;let count=0;Storage.prototype.setItem=function(k,v){if(k.startsWith('pushpull-note-ui-v1:')||k.startsWith('pushpull_workout_draft_v1:'))if(++count===3)throw new DOMException('synthetic quota','QuotaExceededError');return put.call(this,k,v)}}""")
        p.locator('[data-restore-confirm]').click();expect(p.get_by_role('heading',name='Przywracanie nie zostało zakończone')).to_be_visible(timeout=60000);self.assertEqual(p.locator('[data-restore-success]').count(),0)
        saved=legacy.IndexedDBMigration.records(self,p);self.assertTrue(any(r['key']=='canonical-restore-pending' for r in saved['meta']));self.assertTrue(p.evaluate('!!localStorage.getItem("pushpull_canonical_restore_pending")'))
        p.reload();expect(p.get_by_role('heading',name='Przywracanie nie zostało zakończone')).to_be_visible();self.assertEqual(legacy.IndexedDBMigration.records(self,p),saved)
        error=p.evaluate("""async()=>{const {transact}=await import('./model/journal-idb.mjs');const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});try{await transact(db,['meta'],'readwrite',tx=>tx.objectStore('meta').put({key:'intruder'}));return 'accepted'}catch(e){return e.message}finally{db.close()}}""");self.assertIn('pending',error)
        other=ctx.new_page();other.goto(self.url);expect(other.get_by_role('heading',name='Przywracanie nie zostało zakończone')).to_be_visible();self.assertEqual(other.locator('[data-act=start],[data-act=finish]').count(),0);self.assertEqual(legacy.IndexedDBMigration.records(self,p),saved)

    def gate_worker(self,p,ctx):
        held=[];ctx.route('**/restore-test-gate',lambda route:held.append(route))
        p.evaluate("""()=>{const Native=Worker;window.Worker=class extends Native{constructor(url,opts){if(String(url).includes('canonical-restore-worker')){const gate=new URL('./restore-test-gate',location.href).href;const source='let early;self.onmessage=e=>early=e;let armed=false,once=true;const send=self.postMessage.bind(self),digest=crypto.subtle.digest.bind(crypto.subtle);self.postMessage=v=>{if(v.claimed)armed=true;send(v)};crypto.subtle.digest=async(...a)=>{if(armed&&once){once=false;await fetch('+JSON.stringify(gate)+')}return digest(...a)};await import('+JSON.stringify(String(url))+');if(early)self.onmessage(early);';url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));}super(url,opts)}}}""")
        return held
    def wait_gate(self,p,held):
        deadline=time.monotonic()+20
        while not held and time.monotonic()<deadline:p.wait_for_timeout(20)
        self.assertTrue(held)

    def test_crash_after_claim_blocks_boot_and_new_clean_profile_can_retry(self):
        raw=self.produce();ctx,p=self.target(raw);held=self.gate_worker(p,ctx);p.locator('[data-restore-confirm]').click();self.wait_gate(p,held)
        p.reload();expect(p.get_by_role('heading',name='Przywracanie nie zostało zakończone')).to_be_visible();self.assertEqual(p.locator('[data-act=finish]').count(),0)
        ctx2,p2=self.target(raw);p2.locator('[data-restore-confirm]').click();expect(p2.locator('[data-restore-success]')).to_be_visible(timeout=60000)
        p2.reload();p2.wait_for_selector('[data-act=finish]');p2.locator('[data-tab=settings]').click();p2.locator('[data-backup-flow=save]').click()
        with p2.expect_download(timeout=60000) as dl:p2.locator('[data-canonical-export]').click()
        self.assertEqual(self.decode(p2,Path(dl.value.path()).read_bytes()),self.decode(self.page,raw))

    def test_already_open_card_cannot_write_while_pending_and_reloads_complete_data(self):
        raw=self.produce();ctx,p=self.target(raw);other=ctx.new_page();other.on('dialog',self.dialog);other.goto(self.url);other.wait_for_selector('[data-act=start]')
        held=self.gate_worker(p,ctx);p.locator('[data-restore-confirm]').click();self.wait_gate(p,held)
        before=legacy.IndexedDBMigration.records(self,p);other.locator('[data-act=start]').click();expect(other.get_by_role('heading',name='Przywracanie nie zostało zakończone')).to_be_visible();self.assertEqual(legacy.IndexedDBMigration.records(self,p),before)
        held[0].fulfill(status=200,body='ok');expect(p.locator('[data-restore-success]')).to_be_visible(timeout=60000)
        other.reload();expect(other.locator('[data-act=finish]')).to_be_visible(timeout=30000)

    def test_transaction_quota_and_abort_keep_pending_without_partial_journal(self):
        raw=self.produce()
        for kind in ('QuotaExceededError','AbortError'):
            ctx,p=self.target(raw)
            p.evaluate("""kind=>{const Native=Worker;window.Worker=class extends Native{constructor(url,opts){if(String(url).includes('canonical-restore-worker')){const source='let early;self.onmessage=e=>early=e;const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...a){if(this.name===\"journalState\"){if('+JSON.stringify(kind)+ '===\"AbortError\")this.transaction.abort();throw new DOMException(\"synthetic write failure\",'+JSON.stringify(kind)+')}return put.apply(this,a)};await import('+JSON.stringify(String(url))+');if(early)self.onmessage(early);';url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));}super(url,opts)}}}""",kind)
            p.locator('[data-restore-confirm]').click();expect(p.get_by_role('heading',name='Przywracanie nie zostało zakończone')).to_be_visible(timeout=60000)
            records=legacy.IndexedDBMigration.records(self,p);self.assertEqual(len(records['journalSessions']),0);self.assertEqual(len(records['journalResults']),0);self.assertTrue(any(r['key']=='canonical-restore-pending' for r in records['meta']))
            p.reload();expect(p.get_by_role('heading',name='Przywracanie nie zostało zakończone')).to_be_visible();self.assertEqual(legacy.IndexedDBMigration.records(self,p),records)

    def test_foreign_change_before_claim_cas_is_preserved(self):
        raw=self.produce();ctx,p=self.target(raw)
        p.evaluate("""()=>{const Native=Worker;window.Worker=class extends Native{constructor(url,opts){super(url,opts);if(String(url).includes('canonical-restore-worker')){const send=this.postMessage.bind(this);this.postMessage=v=>{if(Object.hasOwn(v,'reserveOK')){window.reservedRestore=true;window.releaseReserve=()=>send(v)}else send(v)}}}}}""")
        p.locator('[data-restore-confirm]').click();p.wait_for_function('window.reservedRestore===true')
        p.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise(r=>{const tx=db.transaction('meta','readwrite');tx.objectStore('meta').put({key:'canonical-preferences-v1',value:{foreign:true}});tx.oncomplete=r});db.close()}""")
        foreign=legacy.IndexedDBMigration.records(self,p);p.evaluate('releaseReserve()');expect(p.locator('[data-restore-error]')).to_contain_text('metadane',timeout=60000)
        self.assertEqual(legacy.IndexedDBMigration.records(self,p),foreign);self.assertIsNone(p.evaluate('localStorage.getItem("pushpull_canonical_restore_pending")'))
