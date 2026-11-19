"""Production PPC1 restore and automatic Drive backup across isolated profiles."""
import base64
from copy import deepcopy
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_result_panel,KEY
import test_drive_incremental as cloud
import test_indexeddb as native
import test_used_restore as used
import test_canonical_restore_ui as canonical

class TwoDevice172(BrowserHarness):
    configure=cloud.IncrementalDriveUI.configure
    encode_export=used.UsedRestore.export
    decode=canonical.CanonicalRestoreUI.decode
    records=native.IndexedDBMigration.records

    def add_completed_result(self,page,kg):
        self.page=page
        page.locator('[data-tab=training]').click()
        self.start()
        page.locator('[data-expand]').first.click();open_result_panel(page)
        form=page.locator('.performanceForm')
        form.locator('[data-quick=kg]').fill(kg)
        form.locator('[data-quick=reps]').fill('9')
        form.locator('[type=submit]').click()
        expect(page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        page.locator('[data-act=finish]').click()
        expect(page.locator('[data-act=start]')).to_be_visible()

    def upload_verified(self,page,drive,number):
        page.locator('[data-tab=settings]').click()
        self.data_section('google',page)
        old=len(drive.files)
        expect(page.locator('[data-drive-status]')).to_contain_text('Kopia zweryfikowana',timeout=60000)
        self.assertEqual(drive.posts,number,(old,drive.posts))
        return next(reversed(drive.files))

    def preview_cloud(self,page,file_id):
        page.locator('[data-tab=settings]').click()
        self.backup_flow('restore',page)
        page.locator('[data-ppc1-list]').click()
        page.locator(f'[data-ppc1-point="{file_id}"]').click()
        expect(page.locator('[data-canonical-preview]')).to_be_visible(timeout=60000)

    def configure_peer(self,context,drive):
        drive.install(context)
        page=context.new_page();page.on('dialog',self.dialog)
        page.goto(self.url);page.wait_for_selector('[data-act=start]')
        self.page=page;self.configure()
        return page

    def test_alternating_automatic_drive_backups_keep_history_anchor_and_checkpoint(self):
        drive=cloud.IncrementalGoogle();drive.install(self.context)
        native.IndexedDBMigration.prepare(self)
        pixel=self.page
        self.configure()
        self.plans('v2-owner-2026-10-22')
        pixel.locator('[data-plan-activate]').click()
        expect(pixel.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        pixel.locator('[data-tab=training]').click();pixel.locator('[data-act=finish]').click()
        expect(pixel.locator('[data-act=start]')).to_be_visible()
        first=self.upload_verified(pixel,drive,1)
        point=pixel.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{await db.ensureFull();await db.commit(db.value,{backupBefore:true});const id=db.backups().find(x=>x.startsWith('preimage:'));const f=await db.readBackup(id);const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await f.arrayBuffer())));return {id,sha}}finally{db.close()}}""")
        pixel.reload();pixel.wait_for_selector('[data-act=start]')
        # Reconnect on the same profile after its explicit restart.
        pixel.locator('[data-tab=settings]').click();self.data_section('google',pixel);pixel.locator('[data-drive-action=connect]').click()
        expect(pixel.locator('[data-drive-action=connect]')).to_be_hidden()
        samsung=self.configure_peer(self.new_context(service_workers='allow'),drive)
        expected=self.decode(pixel,self.encode_export(pixel))
        receiver,other,selected=samsung,pixel,first
        for count in range(1,5):
            self.preview_cloud(receiver,selected)
            self.assertEqual(receiver.locator('[data-restore-warning]').count(),0,(count,receiver.locator('[data-restore-comparison]').inner_text()))
            receiver.locator('[data-restore-confirm]').click()
            expect(receiver.locator('[data-restore-success]')).to_be_visible(timeout=60000)
            receiver.reload();receiver.wait_for_selector('[data-act=start]')
            self.assertEqual(self.decode(receiver,self.encode_export(receiver)),expected)
            self.assertEqual(pixel.evaluate('(k)=>localStorage.getItem(k)',KEY),native.RAW)
            self.assertIsNone(samsung.evaluate('(k)=>localStorage.getItem(k)',KEY))
            self.data_section('google',receiver)
            expect(receiver.locator('[data-auto-ppc1]')).to_be_checked()
            receiver.locator('[data-drive-action=connect]').click()
            expect(receiver.locator('[data-drive-action=connect]')).to_be_hidden()
            self.add_completed_result(receiver,str(20+count))
            selected=self.upload_verified(receiver,drive,count+1)
            expected=self.decode(receiver,self.encode_export(receiver))
            self.assertEqual(len({s['id'] for s in expected['source']['data']['sessions']}),len(expected['source']['data']['sessions']))
            receiver,other=other,receiver
        actual=pixel.evaluate("""async id=>{const db=await PushPullDB.open(()=>{});try{const f=await db.readBackup(id);return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await f.arrayBuffer())))}finally{db.close()}}""",point['id'])
        self.assertEqual(actual,point['sha'])
        self.assertEqual(len(drive.files),5)
        self.assertFalse(self.alerts,self.alerts)

    def choose_file(self,page,raw):
        page.locator('[data-tab=settings]').click();self.backup_flow('restore',page)
        page.locator('#importFile').set_input_files({'name':'sample.ppc1','mimeType':'application/octet-stream','buffer':raw})
        expect(page.locator('[data-canonical-preview]')).to_be_visible(timeout=60000)

    def test_older_and_equal_size_changed_copy_show_local_draft_and_block_by_default(self):
        self.page.wait_for_selector('[data-act=start]')
        p=self.page
        old=self.encode_export(p)
        self.add_completed_result(p,'32')
        changed_value=self.decode(p,self.encode_export(p))
        entry=changed_value['source']['data']['entries'][0]
        entry['series'][0]['kg']='55'
        entry['kg']='55'
        divergent=deepcopy(changed_value)
        other_session=divergent['source']['data']['sessions'][0]
        other_entry=divergent['source']['data']['entries'][0]
        versions=divergent['source']['catalog']['sessionVersions']
        versions['another-session']=versions.pop(other_session['id'])
        other_session['id']=other_entry['sessionId']='another-session'
        other_entry['id']='another-result'
        encode="""async value=>{const {writeCanonicalBackup}=await import('./model/canonical-backup.mjs');return Array.from(new Uint8Array(await(await writeCanonicalBackup(value)).arrayBuffer()))}"""
        changed_bytes=bytes(p.evaluate(encode,changed_value))
        divergent_bytes=bytes(p.evaluate(encode,divergent))
        p.evaluate("localStorage.setItem('pushpull-note-ui-v1:unsaved-test','niedokończona notatka')")
        before=self.records()
        for raw,warning in (
            (old,'Treningi · tylko lokalnie 1'),
            (changed_bytes,'Wyniki · tylko lokalnie 0 · tylko w kopii 0 · zmienione 1'),
            (divergent_bytes,'Treningi · tylko lokalnie 1 · tylko w kopii 1 · zmienione 0'),
        ):
            self.choose_file(p,raw)
            review=p.locator('[data-restore-comparison]')
            expect(review).to_contain_text(warning)
            expect(review).to_contain_text('Bufory edycji · tylko lokalnie 1')
            expect(p.locator('[data-restore-confirm]')).to_be_disabled()
            expect(p.locator('[data-restore-allow-loss]')).not_to_be_checked()
            p.locator('[data-restore-cancel]').click()
            self.assertEqual(self.records(),before)
            self.assertEqual(p.evaluate("localStorage.getItem('pushpull-note-ui-v1:unsaved-test')"),'niedokończona notatka')

    def test_interrupted_migrated_profile_rolls_back_without_touching_legacy_anchor(self):
        native.IndexedDBMigration.prepare(self)
        p=self.page;p.wait_for_selector('[data-act=finish]')
        before=self.encode_export(p)
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-act=finish]').click()
        expect(p.locator('[data-act=start]')).to_be_visible()
        current=self.encode_export(p)
        self.choose_file(p,before)
        p.locator('[data-restore-allow-loss]').check()
        held=canonical.CanonicalRestoreUI.gate_worker(self,p,self.context)
        p.locator('[data-restore-confirm]').click();canonical.CanonicalRestoreUI.wait_gate(self,p,held)
        p.reload();held[0].abort()
        expect(p.locator('[data-rollback-pending]')).to_be_visible()
        p.locator('[data-rollback-pending]').click();p.wait_for_selector('[data-tab=settings]')
        self.assertEqual(self.decode(p,self.encode_export(p)),self.decode(p,current))
        self.assertEqual(p.evaluate('(k)=>localStorage.getItem(k)',KEY),native.RAW)
        self.assertFalse(self.alerts,self.alerts)

    def test_restart_after_local_reservation_before_idb_claim_recovers_exact_state(self):
        native.IndexedDBMigration.prepare(self)
        p=self.page;p.wait_for_selector('[data-act=finish]')
        incoming=self.encode_export(p)
        p.locator('[data-tab=training]').click();p.locator('[data-act=finish]').click()
        expect(p.locator('[data-act=start]')).to_be_visible()
        prior=self.encode_export(p)
        self.choose_file(p,incoming);p.locator('[data-restore-allow-loss]').check()
        p.evaluate("""()=>{const Native=Worker;window.Worker=class extends Native{constructor(url,opts){super(url,opts);if(String(url).includes('canonical-restore-worker')){const send=this.postMessage.bind(this);this.postMessage=value=>{if(value.reserveOK)window.heldReserve=true;else send(value)}}}}}""")
        p.locator('[data-restore-confirm]').click();p.wait_for_function('window.heldReserve===true')
        self.assertFalse(any(row['key']=='canonical-restore-pending' for row in self.records()['meta']))
        self.assertTrue(p.evaluate("localStorage.getItem('pushpull_canonical_restore_pending')"))
        p.reload();expect(p.locator('[data-rollback-pending]')).to_be_visible()
        p.locator('[data-rollback-pending]').click();p.wait_for_selector('[data-tab=settings]')
        self.assertEqual(self.decode(p,self.encode_export(p)),self.decode(p,prior))
        self.assertEqual(p.evaluate('(k)=>localStorage.getItem(k)',KEY),native.RAW)

    def test_still_active_v1_and_changed_anchor_keep_original_data(self):
        self.page.wait_for_selector('[data-act=start]')
        blob=base64.b64encode(self.encode_export(self.page)).decode()
        context=self.new_context(service_workers='block');old=context.new_page()
        old.goto(self.url+'tests/')
        old.add_script_tag(url=self.url+'storage.js');old.add_script_tag(url=self.url+'indexeddb.js')
        unchanged=old.evaluate("""async ({raw,encoded})=>{
          localStorage.setItem('pushpull_skeleton_v1',raw);
          const old=await PushPullDB.openV1(()=>null);if(old.error)throw old.error;
          old.close();
          const {legacyEvidence,same}=await import('../model/journal-idb.mjs');
          async function read(){
           const db=await new Promise((resolve,reject)=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);});
           try{if(db.version!==1)throw Error('Expected active v1');return await legacyEvidence(db)}finally{db.close()}
          }
          const snapshot=await read();
          const {restoreCanonicalFile}=await import('../model/canonical-restore.mjs');
          const file=new Blob([Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))]);
          let error;try{await restoreCanonicalFile(file,{previewLegacyRaw:raw})}catch(e){error=e.message;}
          return {error,unchanged:same(snapshot,await read()),raw:localStorage.getItem('pushpull_skeleton_v1')};
        }""",{'raw':native.RAW,'encoded':blob})
        self.assertIn('dokończ zweryfikowaną aktualizację',unchanged['error'])
        self.assertTrue(unchanged['unchanged']);self.assertEqual(unchanged['raw'],native.RAW)
        native.IndexedDBMigration.prepare(self)
        p=self.page;self.choose_file(p,base64.b64decode(blob))
        p.locator('[data-restore-allow-loss]').check()
        before=self.records()
        p.evaluate('(key)=>localStorage.setItem(key,localStorage.getItem(key)+" ")',KEY)
        p.locator('[data-restore-confirm]').click()
        expect(p.locator('[data-restore-error]')).to_contain_text('Dane zmieniły się od podglądu',timeout=60000)
        self.assertEqual(self.records(),before)
        self.assertEqual(p.evaluate('(k)=>localStorage.getItem(k)',KEY),native.RAW+' ')
