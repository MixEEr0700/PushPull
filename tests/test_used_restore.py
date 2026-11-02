"""In-place canonical replacement + real rollback; isolated browser stores only."""
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_canonical_restore_ui as old
import test_indexeddb as native

class UsedRestore(BrowserHarness):
    produce=old.CanonicalRestoreUI.produce
    decode=old.CanonicalRestoreUI.decode
    def export(self,p):
        p.locator('[data-tab=settings]').click()
        if p.locator('[data-backup-flow=save]').get_attribute('aria-expanded')=='false':p.locator('[data-backup-flow=save]').click()
        with p.expect_download(timeout=60000) as d:p.locator('[data-canonical-export]').click()
        return Path(d.value.path()).read_bytes()
    def used(self):
        raw=self.produce();ctx=self.new_context(service_workers='allow');p=ctx.new_page();p.on('dialog',self.dialog);p.goto(self.url);p.wait_for_selector('[data-act=start]')
        # Different native training history; all writes through the actual UI.
        p.locator('[data-act=start]').click();p.locator('[data-act=finish]').click();p.wait_for_selector('[data-act=start]');p.locator('[data-act=start]').click();p.locator('[data-act=finish]').click();p.wait_for_selector('[data-act=start]')
        p.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise((r,j)=>{const tx=db.transaction('meta','readwrite'),m=tx.objectStore('meta'),q=m.get('drive-sync-v1');q.onsuccess=()=>m.put({...q.result,key:'drive-sync-v1',clientId:'',deviceId:'old-device',token:'old-token',autoPPC1:true,ppc1Queue:'old-intent',selected:'old-account',accounts:{'old-account':{ppc1:{pending:{fileId:'old-upload',packet:{old:'evidence'}}}}}});m.put({key:'canonical-preferences-v1',value:{units:'kg',own:'Ł😀'}});tx.oncomplete=r;tx.onabort=()=>j(tx.error)});db.close();localStorage.setItem('pushpull-note-ui-v1:old-buffer','unfinished old note')}""")
        before=self.export(p);return raw,ctx,p,before
    def choose(self,p,raw):
        if p.locator('[data-backup-flow=restore]').get_attribute('aria-expanded')=='false':p.locator('[data-backup-flow=restore]').click()
        p.locator('#importFile').set_input_files({'name':'selected.ppc1','mimeType':'application/octet-stream','buffer':raw});expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000)
    def apply(self,p):
        p.locator('[data-restore-confirm]').click();expect(p.locator('[data-restore-success]')).to_be_visible(timeout=60000);p.reload();p.wait_for_selector('[data-tab=settings]')
    def test_used_profile_exact_replacement_cancel_and_actual_rollback(self):
        raw,ctx,p,before=self.used();original=native.IndexedDBMigration.records(self,p);self.choose(p,raw)
        self.confirm=False
        with p.expect_event('dialog'):p.locator('[data-restore-confirm]').click()
        expect(p.locator('[data-restore-busy]')).to_have_count(0);self.confirm=True;self.assertEqual(native.IndexedDBMigration.records(self,p),original)
        self.apply(p);self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,raw));p.locator('[data-backup-advanced] > summary').click();p.locator('[data-rescue-points]').click();expect(p.locator('[data-rescue-load]')).to_have_count(1);p.locator('[data-rescue-load]').click();expect(p.locator('[data-canonical-preview]')).to_be_visible(timeout=60000);self.apply(p)
        self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,before));records=native.IndexedDBMigration.records(self,p);self.assertNotEqual(original['journalState'][0]['epoch'],records['journalState'][0]['epoch']);drive=next(r for r in records['meta'] if r['key']=='drive-sync-v1');self.assertEqual(drive['accounts'],{});self.assertNotIn('ppc1Queue',drive)
    def test_partial_local_write_restart_then_pending_rollback_recovers_every_value(self):
        raw,ctx,p,before=self.used();self.choose(p,raw)
        p.evaluate("""()=>{const set=Storage.prototype.setItem;let n=0;Storage.prototype.setItem=function(k,v){if((k.startsWith('pushpull-note-ui-v1:')||k.startsWith('pushpull_workout_draft_v1:'))&&++n===3)throw new DOMException('quota','QuotaExceededError');return set.call(this,k,v)}}""")
        p.locator('[data-restore-confirm]').click();expect(p.locator('[data-rollback-pending]')).to_be_visible(timeout=60000);p.reload();expect(p.locator('[data-rollback-pending]')).to_be_visible();p.evaluate("""()=>{window.__nativeOpen=IDBFactory.prototype.open;IDBFactory.prototype.open=function(name,...rest){if(name==='pushpull')throw Error('synthetic native DB unavailable');return window.__nativeOpen.call(this,name,...rest)}}""")
        with p.expect_download(timeout=60000) as d:p.locator('[data-pending-download]').click()
        self.assertEqual(self.decode(p,Path(d.value.path()).read_bytes()),self.decode(self.page,before));p.evaluate('()=>{IDBFactory.prototype.open=window.__nativeOpen}');p.locator('[data-rollback-pending]').click();p.wait_for_selector('[data-tab=settings]',timeout=60000);p.reload();p.wait_for_selector('[data-tab=settings]');self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,before))
    def test_used_profile_can_restore_cloud_point_then_rollback_without_uploading_old_queue(self):
        import test_drive_incremental as cloud
        import test_drive_sync as legacy_drive
        google=cloud.IncrementalGoogle();google.install(self.context);self.page.wait_for_selector('[data-act=start]');legacy_drive.ManualDriveFlow.configure(self,automatic=True);self.page.locator('[data-tab=training]').click();self.start();self.result('22','9');self.save();self.page.locator('[data-act=finish]').click();self.page.wait_for_selector('[data-act=start]');self.page.locator('[data-tab=settings]').click();self.backup_flow('save');expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000);first=self.export(self.page)
        self.page.locator('[data-tab=training]').click();self.start();self.page.locator('[data-act=finish]').click();self.page.wait_for_selector('[data-act=start]');self.page.locator('[data-tab=settings]').click();self.backup_flow('save');expect(self.page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000);before=self.export(self.page);self.assertEqual(google.posts,2)
        self.backup_flow('restore');self.page.locator('[data-ppc1-list]').click();expect(self.page.locator('[data-ppc1-point]')).to_have_count(2);self.page.locator('[data-ppc1-point="'+next(iter(google.files))+'"]').click();expect(self.page.locator('[data-canonical-preview]')).to_be_visible(timeout=60000);self.apply(self.page);self.assertEqual(self.decode(self.page,self.export(self.page)),self.decode(self.page,first))
        self.page.locator('[data-backup-advanced] > summary').click();self.page.locator('[data-rescue-points]').click();self.page.locator('[data-rescue-load]').click();expect(self.page.locator('[data-canonical-preview]')).to_be_visible(timeout=60000);self.apply(self.page);self.assertEqual(self.decode(self.page,self.export(self.page)),self.decode(self.page,before));self.assertEqual(google.posts,2)
    def test_rescue_quota_refuses_before_any_source_write(self):
        raw,ctx,p,before=self.used();self.choose(p,raw);original=native.IndexedDBMigration.records(self,p);local=p.evaluate('({...localStorage})')
        p.evaluate("""()=>{const Original=Worker;window.Worker=class extends Original{constructor(url,opts){if(String(url).includes('canonical-restore-worker')){const code='let early;onmessage=e=>early=e;const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(...a){if(this.name===\"points\")throw new DOMException(\"synthetic rescue quota\",\"QuotaExceededError\");return add.apply(this,a)};await import('+JSON.stringify(String(url))+');if(early)onmessage(early)';url=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));}super(url,opts)}}}""")
        p.locator('[data-restore-confirm]').click();expect(p.locator('[data-restore-error]')).to_contain_text('quota',timeout=60000);self.assertEqual(native.IndexedDBMigration.records(self,p),original);self.assertEqual(p.evaluate('({...localStorage})'),local)
    gate_worker=old.CanonicalRestoreUI.gate_worker
    wait_gate=old.CanonicalRestoreUI.wait_gate
    def test_two_cards_and_crash_after_claim_then_rollback(self):
        raw,ctx,p,before=self.used();self.choose(p,raw);other=ctx.new_page();other.on('dialog',self.dialog);other.goto(self.url);other.wait_for_selector('[data-act=start]');held=self.gate_worker(p,ctx);p.locator('[data-restore-confirm]').click();self.wait_gate(p,held);claimed=native.IndexedDBMigration.records(self,p);other.locator('[data-act=start]').click();expect(other.locator('[data-rollback-pending]')).to_be_visible();self.assertEqual(native.IndexedDBMigration.records(self,p),claimed)
        # Even the old Drive metadata API is fenced, not just journal writers.
        error=p.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{const s=await h.readDriveState();await h.writeDriveState(s,s.token);return 'accepted'}catch(e){return e.message}finally{h.close()}}""");self.assertIn('pending',error);self.assertEqual(native.IndexedDBMigration.records(self,p),claimed)
        p.reload();expect(p.locator('[data-rollback-pending]')).to_be_visible();held[0].abort();p.locator('[data-rollback-pending]').click();p.wait_for_selector('[data-tab=settings]',timeout=60000);self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,before))
    def test_journal_abort_rolls_back_native_write_and_recovery_restores_original(self):
        raw,ctx,p,before=self.used();self.choose(p,raw);original=native.IndexedDBMigration.records(self,p)
        p.evaluate("""()=>{const Original=Worker;window.Worker=class extends Original{constructor(url,opts){if(String(url).includes('canonical-restore-worker')){const code='let early;onmessage=e=>early=e;const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...a){if(this.name===\"journalState\"){this.transaction.abort();throw new DOMException(\"synthetic abort\",\"AbortError\")}return put.apply(this,a)};await import('+JSON.stringify(String(url))+');if(early)onmessage(early)';url=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));}super(url,opts)}}}""")
        p.locator('[data-restore-confirm]').click();expect(p.locator('[data-rollback-pending]')).to_be_visible(timeout=60000);self.assertEqual(native.IndexedDBMigration.records(self,p)['journalSessions'],original['journalSessions']);p.reload();p.locator('[data-rollback-pending]').click();p.wait_for_selector('[data-tab=settings]',timeout=60000);self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,before))
    def test_change_after_preview_refuses_without_overwriting_newer_revision(self):
        raw,ctx,p,before=self.used();self.choose(p,raw);other=ctx.new_page();other.on('dialog',self.dialog);other.goto(self.url);other.wait_for_selector('[data-act=start]');other.locator('[data-act=start]').click();other.wait_for_selector('[data-act=finish]');newer=native.IndexedDBMigration.records(self,p)
        if p.locator('[data-restore-confirm]').count():
            p.locator('[data-restore-confirm]').click();expect(p.locator('[data-restore-error]')).to_be_visible(timeout=60000)
        self.assertEqual(native.IndexedDBMigration.records(self,p),newer);self.assertIsNone(p.evaluate('localStorage.getItem("pushpull_canonical_restore_pending")'))
    def test_missing_or_corrupt_drive_delta_never_touches_used_profile(self):
        import json
        import test_drive_incremental as cloud
        import test_drive_sync as legacy_drive
        google=cloud.IncrementalGoogle();google.install(self.context);p=self.page;p.wait_for_selector('[data-act=start]');legacy_drive.ManualDriveFlow.configure(self,automatic=True)
        for _ in range(2):
            p.locator('[data-tab=training]').click();self.start();p.locator('[data-act=finish]').click();p.wait_for_selector('[data-act=start]');p.locator('[data-tab=settings]').click();self.backup_flow('save');expect(p.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000)
        base,tip=list(google.files);saved=google.files.pop(base);before=native.IndexedDBMigration.records(self);local=p.evaluate('({...localStorage})');self.backup_flow('restore');p.locator('[data-ppc1-list]').click();p.locator('[data-ppc1-point="'+tip+'"]').click();expect(p.locator('[data-restore-error]')).to_be_visible(timeout=60000);self.assertEqual(native.IndexedDBMigration.records(self),before);self.assertEqual(p.evaluate('({...localStorage})'),local)
        google.files[base]=saved;packet=json.loads(google.files[tip]['text']);packet['root']='corrupted';google.files[tip]['text']=json.dumps(packet);p.locator('[data-ppc1-list]').click();p.locator('[data-ppc1-point="'+tip+'"]').click();expect(p.locator('[data-restore-error]')).to_be_visible(timeout=60000);self.assertEqual(native.IndexedDBMigration.records(self),before)
    def test_corrupt_rescue_file_or_evidence_never_activates(self):
        raw,ctx,p,before=self.used();self.choose(p,raw);self.apply(p);self.export(p);p.locator('[data-backup-advanced] > summary').click();p.locator('[data-rescue-points]').click();expect(p.locator('[data-rescue-load]')).to_have_count(1);current=native.IndexedDBMigration.records(self,p);local=p.evaluate('({...localStorage})')
        for kind in ('file','evidence'):
            p.evaluate("""async kind=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull-canonical-rescue');q.onsuccess=()=>r(q.result)});await new Promise((r,j)=>{const tx=db.transaction('points','readwrite'),s=tx.objectStore('points'),q=s.getAll();q.onsuccess=()=>{window.__originalRescue??=structuredClone(q.result[0]);const p=structuredClone(window.__originalRescue);if(kind==='file')p.file=new Blob([p.file,new Uint8Array([0])]);else p.evidence.meta.push({key:'tampered',value:1});s.put(p)};tx.oncomplete=r;tx.onabort=()=>j(tx.error)});db.close();document.querySelectorAll('.toast').forEach(n=>n.remove())}""",kind)
            p.locator('[data-rescue-load]').click();expect(p.locator('.toast')).to_contain_text('weryfikacji',timeout=60000);self.assertEqual(native.IndexedDBMigration.records(self,p),current);self.assertEqual(p.evaluate('({...localStorage})'),local)
    def test_semantically_unrestorable_draft_refuses_before_source_or_rescue_write(self):
        raw,ctx,p,before=self.used();value=self.decode(self.page,raw);value['drafts'][0]['value']['key']='wrong-native-key'
        encoded=p.evaluate("""async value=>{const {writeCanonicalBackup}=await import('./model/canonical-backup.mjs');const f=await writeCanonicalBackup(value);return Array.from(new Uint8Array(await f.arrayBuffer()))}""",value)
        original=native.IndexedDBMigration.records(self,p);local=p.evaluate('({...localStorage})');self.backup_flow('restore',p);p.locator('#importFile').set_input_files({'name':'bad-draft.ppc1','mimeType':'application/octet-stream','buffer':bytes(encoded)});expect(p.locator('[data-restore-error]')).to_be_visible(timeout=60000);self.assertEqual(native.IndexedDBMigration.records(self,p),original);self.assertEqual(p.evaluate('({...localStorage})'),local);self.assertEqual(p.evaluate("async()=>(await(await import('./model/canonical-rescue.mjs')).listRescues()).length"),0)
    def test_final_local_activation_failure_uses_verified_point_after_restart(self):
        raw,ctx,p,before=self.used();self.choose(p,raw)
        p.evaluate("""()=>{const remove=Storage.prototype.removeItem;Storage.prototype.removeItem=function(key){if(key==='pushpull_canonical_restore_pending')throw Error('synthetic final activation failure');return remove.call(this,key)}}""")
        p.locator('[data-restore-confirm]').click();expect(p.locator('[data-rollback-pending]')).to_be_visible(timeout=60000);self.assertFalse(any(r['key']=='canonical-restore-pending' for r in native.IndexedDBMigration.records(self,p)['meta']));p.reload();p.locator('[data-rollback-pending]').click();p.wait_for_selector('[data-tab=settings]',timeout=60000);self.assertEqual(self.decode(p,self.export(p)),self.decode(self.page,before))
    def test_foreign_root_after_claim_is_not_silently_erased_by_recovery(self):
        raw,ctx,p,before=self.used();self.choose(p,raw);held=self.gate_worker(p,ctx);p.locator('[data-restore-confirm]').click();self.wait_gate(p,held);p.reload();held[0].abort()
        p.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise((r,j)=>{const tx=db.transaction('journalState','readwrite'),s=tx.objectStore('journalState'),q=s.get('active');q.onsuccess=()=>s.put({...q.result,revision:q.result.revision+1});tx.oncomplete=r;tx.onabort=()=>j(tx.error)});db.close()}""")
        changed=native.IndexedDBMigration.records(self,p);p.locator('[data-rollback-pending]').click();expect(p.locator('[data-pending-detail]')).to_contain_text('Zmieniono root',timeout=60000);self.assertEqual(native.IndexedDBMigration.records(self,p),changed)
