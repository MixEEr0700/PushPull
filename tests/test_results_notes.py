"""Final result/note polish. Real isolated IndexedDB, never user databases."""
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_notes,wait_for_service_worker_controller,add_drop,ROOT
from test_indexeddb import PAUSE
import test_incremental_matrix as incremental
import test_v2_training as training

class ResultsNotes(BrowserHarness):
    activate=training.V2Training.activate
    prepare=training.V2Training.prepare
    def ready(self):expect(self.page.locator('[data-act=start],[data-act=finish]').first).to_be_visible()
    open_result=training.V2Training.open_result
    fill_rows=training.V2Training.fill_rows
    save_form=training.V2Training.save_form
    expose_handle=incremental.IncrementalMatrix.expose_handle

    def note(self):
        b=self.page.locator('[data-expand="PUSH-A-1"]')
        if b.get_attribute('aria-expanded')!='true':b.click()
        open_notes(self.page);n=self.page.locator('[data-personal-note]').first
        if not n.evaluate('(e)=>e.open'):n.locator('summary').click()
        return n

    def test_adaptive_collapsed_results_actual_width_order_and_whole_drop_rows(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-5');self.fill_rows(f,'20','3')
        for i,kg in enumerate(['10','9','8']):f.locator(f'[data-row="{i}"][data-segment="1"][data-field=kg]').fill(kg)
        self.save_form(f);before=self.state();card=self.page.locator('.exercise-card').filter(has=self.page.locator('[data-expand="PUSH-A-5"]'));card.locator('[data-expand]').click()
        result=card.locator('[data-adaptive-result]');expect(result).to_be_visible()
        output=Path('/tmp/pushpull-results-notes');output.mkdir(exist_ok=True)
        for width,height in [(360,844),(390,844),(412,844),(844,390),(360,844)]:
            self.page.set_viewport_size({'width':width,'height':height})
            if width<=412:expect(result).to_have_class('last-result adaptive-result result-stacked')
            self.assertEqual(result.locator('.result-unit').all_text_contents(),['3×20 + drop 3×10 kg','3×20 + drop 3×9 kg','3×20 + drop 3×8 kg'])
            self.assertEqual(len(set(result.locator('.result-unit').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().y)'))),3 if result.evaluate("e=>e.classList.contains('result-stacked')") else 1)
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.assertTrue(result.locator('.result-unit').evaluate_all('(es)=>es.every(e=>getComputedStyle(e).whiteSpace==="nowrap"&&e.clientHeight<=parseFloat(getComputedStyle(e).lineHeight)+1)'))
            self.page.screenshot(path=str(output/f'drop-{width}.png'),full_page=True)
        # Both states use the same tokens and measure their own available width.
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            for expanded in [True,False,True,False]:
                card.locator('[data-expand]').click()
                self.assertEqual(card.locator('[data-expand]').get_attribute('aria-expanded'),str(expanded).lower())
                expect(result.locator('.result-unit')).to_have_text(['3×20 + drop 3×10 kg','3×20 + drop 3×9 kg','3×20 + drop 3×8 kg'])
                expect(result).to_have_class('last-result adaptive-result result-stacked')
                self.assertTrue(result.locator('.result-unit').evaluate_all('(es)=>es.every(e=>getComputedStyle(e).whiteSpace==="nowrap"&&e.clientHeight<=parseFloat(getComputedStyle(e).lineHeight)+1)'))
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        # A short identical drop fits; the presence of a drop must not force stacking.
        card.locator('[data-expand]').click();f=card.locator('.performanceForm')
        if not f.locator('[data-rich-details]').is_visible():f.locator('[data-rich-action=toggle]').click()
        self.fill_rows(f,'2','3');self.save_form(f);card.locator('[data-expand]').click()
        expect(result.locator('.result-unit')).to_have_count(1);expect(result).not_to_have_class('last-result adaptive-result result-stacked')
        card.locator('[data-expand]').click();expect(result.locator('.result-unit')).to_have_count(1);expect(result).not_to_have_class('last-result adaptive-result result-stacked');card.locator('[data-expand]').click()
        self.assertEqual(self.state()['entries'][:-1],before['entries'][:-1])
        # Plain mixed values fit inline with a single final kg, equal values compress.
        self.page.locator('[data-expand="PUSH-A-1"]').click();f=self.page.locator('.performanceForm');f.locator('[data-rich-action=toggle]').click();self.fill_rows(f,'20','2')
        f.locator('[data-row="1"][data-field=kg]').fill('18');f.locator('[data-row="2"][data-field=kg]').fill('10');self.save_form(f)
        self.page.locator('[data-expand="PUSH-A-1"]').click();r=self.page.locator('.exercise-card').first.locator('[data-adaptive-result]')
        expect(r).not_to_have_class('last-result adaptive-result result-stacked');self.assertEqual(r.inner_text(),'2×20 | 2×18 | 2×10 kg')
        self.page.locator('[data-expand="PUSH-A-1"]').click();expect(r).not_to_have_class('last-result adaptive-result result-stacked');self.assertEqual(r.inner_text(),'2×20 | 2×18 | 2×10 kg')
        self.page.reload();self.ready();expect(self.page.locator('.exercise-card').first.locator('[data-adaptive-result]')).to_have_text('2×20 kg | 2×18 kg | 2×10 kg')

    def test_quick_fields_keep_drop_children_and_individual_fields_through_restart_without_dialog(self):
        self.activate();f=self.open_result('PUSH A','PUSH-A-5');self.fill_rows(f,'20','10')
        f.locator('[data-row="2"][data-segment="0"][data-field=reps]').fill('9');f.locator('[data-row="0"][data-segment="1"][data-field=kg]').fill('8')
        before=self.page.evaluate("async()=> (await import('./model/performance-editor.mjs')).state('PUSH-A-5',document.querySelector('.performanceForm').dataset.session)")
        dialogs=[];self.page.on('dialog',lambda d:dialogs.append(d.message));f.locator('[data-quick=reps]').fill('12');f.locator('[data-quick=kg]').fill('25')
        self.assertEqual(dialogs,[]);self.assertEqual(f.locator('[data-segment="0"][data-field=reps]').evaluate_all('(es)=>es.map(e=>e.value)'),['12','12','9'])
        self.assertEqual(f.locator('[data-segment="1"][data-field=kg]').evaluate_all('(es)=>es.map(e=>e.value)'),['8','20','20'])
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie');self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        f.locator('[data-quick=reps]').fill('9');f.locator('[data-quick=reps]').fill('14')
        expect(f.locator('[data-row="2"][data-segment="0"][data-field=reps]')).to_have_value('9')
        self.save_form(f);entry=self.state()['entries'][-1]
        self.assertEqual([r['segments'][1] for r in entry['performance']['rows']],[r['segments'][1] for r in before['performance']['rows']])
        self.assertEqual([r['id'] for r in entry['performance']['rows']],[r['id'] for r in before['performance']['rows']])
        # Prefilled mixed history has no manual mask yet. Crossing its 9 must
        # not silently rejoin that independent series on the next keystroke.
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        f=self.open_result('PUSH A','PUSH-A-5');dialogs.clear();f.locator('[data-quick=reps]').fill('9');f.locator('[data-quick=reps]').fill('15')
        self.assertEqual(f.locator('[data-segment="0"][data-field=reps]').evaluate_all('(es)=>es.map(e=>e.value)'),['15','15','9'])
        f.locator('[data-row="0"][data-segment="0"][data-field=kg]').fill('27');f.locator('[data-quick=kg]').fill('30')
        self.assertEqual(f.locator('[data-segment="0"][data-field=kg]').evaluate_all('(es)=>es.map(e=>e.value)'),['27','30','30'])
        self.assertEqual(dialogs,[])
        for _ in range(3):f.locator('[data-rich-action=remove-set]').first.click()
        for _ in range(3):f.locator('[data-rich-action=add-set]').click()
        dialogs.clear();f.locator('[data-quick=kg]').fill('22');f.locator('[data-quick=reps]').fill('11')
        self.assertEqual(f.locator('[data-segment="0"][data-field=kg]').evaluate_all('(es)=>es.map(e=>e.value)'),['22']*3)
        self.assertEqual(f.locator('[data-segment="0"][data-field=reps]').evaluate_all('(es)=>es.map(e=>e.value)'),['11']*3)
        self.assertTrue(f.locator('[data-segment="1"][data-field=kg]').evaluate_all('(es)=>es.every(e=>e.value==="")'))
        self.assertEqual(dialogs,[])

    def test_note_delta_avoids_history_full_export_waits_for_strict_and_retains_native_rows(self):
        self.activate();self.expose_handle();self.ready();n=self.note();n.locator('textarea').fill('Durable own note Ł 😀');before=self.state()
        native_before=self.page.evaluate("""async()=>{const a=await import('./model/journal-idb.mjs'),d=await a.connectV2('pushpull');try{return (await a.readRecords(d)).records}finally{d.close()}}""")
        self.page.evaluate("""()=>{for(const key of ['ensureHistory','ensureFull','commit','export'])__appDB[key]=()=>{throw Error('Forbidden full '+key)};Object.defineProperty(__appDB,'value',{get(){throw Error('full value')}});const native=IDBDatabase.prototype.transaction;window.__nativeNotes=[];IDBDatabase.prototype.transaction=function(...a){const tx=native.apply(this,a);if(tx.mode==='readwrite'&&[...tx.objectStoreNames].includes('journalState'))tx.addEventListener('complete',()=>__nativeNotes.push(tx.durability));return tx}}""")
        self.page.evaluate(PAUSE);n.locator('[type=submit]').click();self.page.wait_for_function('window.__held===true')
        expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_have_count(0);self.assertEqual(self.page.evaluate('__nativeNotes'),[])
        self.assertEqual(self.page.evaluate('__peek().trainingJournal.model.userNotes'),before['trainingJournal']['model']['userNotes'])
        self.page.evaluate('window.__hold=false');expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible();self.assertEqual(self.page.evaluate('__nativeNotes'),['strict'])
        after=self.state();self.assertEqual(after['sessions'],before['sessions']);self.assertEqual(after['entries'],before['entries']);self.assertEqual(after['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        native_after=self.page.evaluate("""async()=>{const a=await import('./model/journal-idb.mjs'),d=await a.connectV2('pushpull');try{return (await a.readRecords(d)).records}finally{d.close()}}""")
        for key in ['journalSessions','journalResults','journalSnapshots','journalArchives','journalCheckpoints']:self.assertEqual(native_after[key],native_before[key])
        for old in native_before['journalObjects']:self.assertIn(old,native_after['journalObjects'])
        self.page.reload();self.ready();expect(self.note().locator('textarea')).to_have_value('Durable own note Ł 😀')

    def test_note_abort_and_bad_readback_preserve_draft_no_success_then_offline_retry(self):
        self.context=self.new_context(service_workers='allow');self.page=self.context.new_page();self.page.on('dialog',self.dialog);self.page.goto(self.url);wait_for_service_worker_controller(self.page)
        self.activate();n=self.note();n.locator('textarea').fill('Retry Ł 😀');before=self.state()
        for kind in ['abort','readback']:
            self.page.evaluate("""kind=>{window.__noteOldPut=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(v,...args){if(this.name==='journalMetadata'&&v.id==='journal'){window.__noteInjected=true;if(kind==='abort')this.transaction.abort();else v={...v,version:v.version+1};}return __noteOldPut.call(this,v,...args)}}""",kind)
            with self.page.expect_event('dialog'):self.page.locator('[data-personal-note] [type=submit]').click()
            self.assertTrue(self.page.evaluate('__noteInjected'));self.assertEqual(self.state(),before);expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_have_count(0)
            expect(self.page.locator('[data-personal-note] textarea')).to_have_value('Retry Ł 😀');self.page.evaluate('()=>{IDBObjectStore.prototype.put=__noteOldPut}')
        self.context.set_offline(True);self.page.reload();self.ready();n=self.note();expect(n.locator('textarea')).to_have_value('Retry Ł 😀');n.locator('[type=submit]').click();expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        self.page.reload();self.ready();expect(self.note().locator('textarea')).to_have_value('Retry Ł 😀');self.assertFalse(self.alerts[-1:].count('Notatka zapisana'))

    def test_stale_note_command_cannot_overwrite_committed_other_tab_or_plan_context(self):
        self.activate();self.expose_handle();self.ready();n=self.note();n.locator('textarea').fill('Unsaved first tab')
        other=self.context.new_page();other.on('dialog',self.dialog);other.goto(self.url);expect(other.locator('[data-act=start]')).to_be_visible()
        cmd=n.locator('form').evaluate("f=>({versionId:f.dataset.noteVersion,exerciseId:f.dataset.id,variantId:f.dataset.noteVariant,noteId:f.dataset.noteId,base:f.dataset.noteBase,revision:Number(f.dataset.noteRevision),text:'Committed other tab',recordedAt:new Date().toISOString()})")
        result=other.evaluate("""async cmd=>{const h=await PushPullDB.open(()=>{},{training:true});try{return await h.saveUserNote(cmd)}finally{h.close()}}""",cmd);self.assertEqual(result['note']['text'],'Committed other tab')
        # Existing cross-tab protection replaces stale UI with recovery. The
        # stale writer itself must reject, not wait for a now-detached button.
        expect(self.page.locator('[role=alert]')).to_be_visible()
        error=self.page.evaluate("async cmd=>{try{await __appDB.saveUserNote({...cmd,text:'forbidden overwrite'});return null}catch(e){return e.message}}",cmd)
        self.assertIn('innej karcie',error)
        expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_have_count(0)
        self.assertTrue(self.page.evaluate("()=>Object.entries(localStorage).some(([k,v])=>k.startsWith('pushpull-note-ui-v1:')&&v.includes('Unsaved first tab'))"))
        self.assertEqual(self.state()['trainingJournal']['model']['userNotes'][-1]['text'],'Committed other tab')
        self.page.reload();self.ready();n=self.note();expect(n.locator('[data-note-conflict]')).to_be_visible();expect(n.locator('textarea')).to_have_attribute('readonly','')
