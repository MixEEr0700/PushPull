"""Stage E native reader / strict commands against independent full oracle."""
from test_browser import BrowserHarness,confirm_restore,open_result_panel
import test_fast_start
from playwright.sync_api import expect

class RuntimeIndex(BrowserHarness):
    prepare=test_fast_start.FastStart.prepare

    def test_incremental_finish_start_save_survive_restart_and_full_audit(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull'),before=await a.readRecords(db),original=await __fastDB.auditExport();
         let complete=0,strict=0;const transaction=IDBDatabase.prototype.transaction;
         IDBDatabase.prototype.transaction=function(...args){const tx=transaction.apply(this,args);if(tx.mode==='readwrite'&&[...tx.objectStoreNames].includes('journalState')){if(tx.durability==='strict')strict++;tx.addEventListener('complete',()=>complete++)}return tx};
         try{
          await __fastDB.finishSession({id:__fastDB.value.activeId});if(complete!==1)throw Error('early finish');
          await __fastDB.startSession({id:'incremental-new',type:(await import('./model/journal.mjs')).units(__fastDB.value)[0].id,date:'2026-10-27',startedAt:'2026-10-27T12:00:00.000Z'});if(complete!==2)throw Error('early start');
         }finally{IDBDatabase.prototype.transaction=transaction}
         const full=await __fastDB.auditExport(),after=await a.readRecords(db);db.close();
         return {complete,strict,newId:full.data.activeId,oneMore:full.data.sessions.length===original.data.sessions.length+1,entries:a.same(original.data.entries,full.data.entries),archives:a.same(original.archives,full.archives),checkpoint:a.same(before.records.journalCheckpoints,after.records.journalCheckpoints),retained:before.records.journalObjects.every(row=>after.records.journalObjects.some(v=>a.same(v,row))),partial:__fastDB.historyDeferred};
        }""")
        self.assertEqual(result['complete'],2);self.assertEqual(result['strict'],2);self.assertEqual(result['newId'],'incremental-new')
        for k in ['oneMore','entries','archives','checkpoint','retained','partial']:self.assertTrue(result[k],result)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.page.locator('[data-tab=calendar]').click();expect(self.page.locator('h1')).to_have_text('Kalendarz')
        self.assertFalse(self.alerts,self.alerts)

    def test_startup_reads_no_history_list_or_full_index_and_ages_match_full_oracle(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const reads=structuredClone(__reads),d=__fastDB.value,full=await __fastDB.auditExport(),p=await import('./model/performance.mjs');
         return {partial:__fastDB.historyDeferred,smaller:d.entries.length<full.data.entries.length,ages:d.entries.every(e=>__fastDB.changeAge(e)===p.resultChangeAge(full.data,e)),noScan:!reads.some(r=>['journalResults','journalSessions','journalSnapshots','journalIndex'].includes(r.name)&&r.op==='getAll')};
        }""")
        self.assertTrue(all(result.values()),result)

    def test_corrupt_runtime_node_fails_closed_without_repair_or_deletion(self):
        self.prepare()
        self.page.evaluate("""async()=>{const a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull');try{const b=await a.readRecords(db),n=b.records.journalIndex.find(n=>n.id===b.state.runtime.indexRoot);await a.transact(db,['journalIndex'],'readwrite',tx=>tx.objectStore('journalIndex').put({...n,value:'0'.repeat(64)}))}finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[role=alert]').first).to_contain_text('index')
        self.assertEqual(self.page.locator('[data-act=start],[data-act=finish]').count(),0)

    def test_session_abort_quota_and_stale_cas_do_not_publish_or_drop_records(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull'),before=await a.readRecords(db),value=__fastDB.value;let failures=0;
         for(const kind of ['QuotaExceededError','AbortError']){const put=IDBObjectStore.prototype.put;let fired=false;
          IDBObjectStore.prototype.put=function(...args){if(this.name==='journalSessions'&&!fired){fired=true;if(kind==='AbortError')this.transaction.abort();throw new DOMException('synthetic',kind)}return put.apply(this,args)};
          try{await __fastDB.finishSession({id:value.activeId})}catch{failures++}finally{IDBObjectStore.prototype.put=put}
          if(!fired||!a.same(before,await a.readRecords(db))||!a.same(value,__fastDB.value))throw Error('rollback oracle');
         }
         const w=await a.openWriter(db),ctx=w.sessionContext();await __fastDB.finishSession({id:value.activeId});let stale=false;try{await w.finishSession({id:value.activeId,...ctx})}catch(e){stale=/CAS/.test(e.message)}db.close();return {failures,stale};
        }""")
        self.assertEqual(result,{'failures':2,'stale':True})

    def test_global_id_collision_in_unloaded_history_and_cancellation_are_rejected(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull'),before=await a.readRecords(db),partial=__fastDB.value,full=await __fastDB.auditExport(),p=await import('./model/performance.mjs');
         const hidden=full.data.entries.find(e=>e.performance&&!partial.entries.some(v=>v.id===e.id)),entry=structuredClone(partial.entries.find(e=>e.performance));if(!hidden)throw Error('missing hidden test result');
         entry.performance.rows[0].id=hidden.performance.rows[0].id;entry.series=p.flatten(entry.performance);
         const cmd={sessionId:entry.sessionId,exerciseId:entry.exerciseId,entry,...__fastDB.resultContext(entry.sessionId,entry.exerciseId)};
         let collision=false;try{await __fastDB.saveResult(cmd)}catch(e){collision=/duplicate global/.test(e.message)}
         const w=await a.openWriter(db),c=new AbortController();c.abort();let aborted=false;try{await w.finishSession({id:w.source.data.activeId,...w.sessionContext()},{signal:c.signal})}catch(e){aborted=e.name==='AbortError'}
         const unchanged=a.same(before,await a.readRecords(db));db.close();return {collision,aborted,unchanged};
        }""")
        self.assertTrue(all(result.values()),result)

    def test_partial_bulk_mutation_requires_history_and_native_readback_tamper_aborts(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         let partialRefused=false;try{await __fastDB.commit(__fastDB.value)}catch(e){partialRefused=/wczytania historii/.test(e.message)}
         const a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull'),before=await a.readRecords(db),put=IDBObjectStore.prototype.put;let injected=false,rejected=false;
         IDBObjectStore.prototype.put=function(row,...rest){const req=put.call(this,row,...rest);if(this.name==='journalSessions'&&!injected){injected=true;put.call(this,{...row,position:999999})}return req};
         try{await __fastDB.finishSession({id:__fastDB.value.activeId})}catch(e){rejected=/readback/.test(e.message)}finally{IDBObjectStore.prototype.put=put}
         const unchanged=a.same(before,await a.readRecords(db));db.close();return {partialRefused,injected,rejected,unchanged};
        }""")
        self.assertTrue(all(result.values()),result)

    def test_observed_source_preview_keeps_result_after_incremental_session_finish(self):
        self.page.wait_for_selector('[data-act=start]')
        self.page.evaluate("""async()=>{const d=await(await fetch('./tests/fixtures/v1.json')).json(),j=await import('./model/journal.mjs');d.sessions.forEach(s=>s.status='done');d.activeId=null;d.nextType='PUSH A';d.trainingJournal=j.initialize('source-preview-test');const h=await PushPullDB.open(()=>{});try{await h.commit(d,{importing:true})}finally{h.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.page.locator('[data-expand="PUSH-A-1"]').click();open_result_panel(self.page)
        self.page.locator('[data-main=kg]').fill('27');self.page.locator('[data-main=reps]').fill('8')
        self.page.locator('.seriesResultForm [type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-type="PUSH A"]').click()
        expect(self.page.locator('.exercise-card').filter(has=self.page.locator('[data-expand="PUSH-A-1"]')).locator('.last-result')).to_have_text('8×27 kg')
        self.assertFalse(self.alerts,self.alerts)

    def test_index_installation_preserves_journal_revision_but_blocks_prepared_old_writer(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const a=await import('./model/journal-idb.mjs'),p=await import('./model/journal-protocol.mjs'),e=await import('./model/journal-runtime.mjs'),db=await a.connectV2('pushpull');
         try{const before=await a.readRecords(db),{runtime,...body}=before.state,old=await p.sealState(body);await a.transact(db,['journalState'],'readwrite',tx=>tx.objectStore('journalState').put(old));
          const w=await a.openWriter(db),entry=structuredClone(w.source.data.entries.find(e=>e.performance)),context=w.context(entry.sessionId,entry.exerciseId);
          await e.installRuntime(db,await a.readTraining(db));const after=await a.readRecords(db);let rejected=false;
          try{await w.saveResult({entry,sessionId:entry.sessionId,exerciseId:entry.exerciseId,...context})}catch(error){rejected=/root CAS/.test(error.message)}
          return {rejected,sameRevision:old.revision===after.state.revision,differentRoot:old.root!==after.state.root,primaryUnchanged:old.indexRoot===after.state.indexRoot,exactSource:a.same(await p.materialize(before),await p.materialize(after)),allObjectsKept:before.records.journalObjects.every(r=>after.records.journalObjects.some(v=>a.same(r,v)))};
         }finally{db.close()}
        }""")
        self.assertTrue(all(result.values()),result)

    def test_reused_immutable_snapshot_proof_still_checks_native_bytes_in_every_strict_cas(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{
         const a=await import('./model/journal-idb.mjs'),p=await import('./model/performance.mjs'),db=await a.connectV2('pushpull'),entry=structuredClone(__fastDB.value.entries.find(e=>e.performance));
         entry.performance.rows[0].segments[0].kg='46';entry.series=p.flatten(entry.performance);entry.kg=entry.series[0].kg;
         await __fastDB.saveResult({entry,sessionId:entry.sessionId,exerciseId:entry.exerciseId,...__fastDB.resultContext(entry.sessionId,entry.exerciseId)});
         const b=await a.readRecords(db),snapshot=b.records.journalSnapshots.find(s=>s.id===entry.journalSnapshotId),id=snapshot.fields.find(([key])=>key==='model')[1],object=b.records.journalObjects.find(r=>r.id===id);
         await a.transact(db,['journalObjects'],'readwrite',tx=>tx.objectStore('journalObjects').put({...object,json:object.json+' '}));const before=await a.readRecords(db),value=__fastDB.value;
         entry.performance.rows[0].segments[0].kg='47';entry.series=p.flatten(entry.performance);entry.kg=entry.series[0].kg;
         let rejected=false;try{await __fastDB.saveResult({entry,sessionId:entry.sessionId,exerciseId:entry.exerciseId,...__fastDB.resultContext(entry.sessionId,entry.exerciseId)})}catch(e){rejected=/CAS|object/.test(e.message)}
         const unchanged=a.same(before,await a.readRecords(db)),memory=a.same(value,__fastDB.value);db.close();return {rejected,unchanged,memory};
        }""")
        self.assertTrue(all(result.values()),result)

    def test_restore_after_missing_root_immediately_supports_incremental_session_commands(self):
        self.prepare()
        raw=self.page.evaluate("""async()=>{const source=structuredClone(await __fastDB.auditExport());source.data.sessions.forEach(s=>s.status='done');source.data.activeId=null;
         const a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull');try{await a.transact(db,['journalState'],'readwrite',tx=>tx.objectStore('journalState').delete('active'))}finally{db.close()}return JSON.stringify(source);
        }""")
        self.page.reload();expect(self.page.locator('[role=alert]').first).to_be_visible()
        self.page.locator('#importFile').set_input_files({'name':'synthetic-full-v2.json','mimeType':'application/json','buffer':raw.encode()})
        confirm_restore(self.page);expect(self.page.get_by_text('Dane zaimportowane',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click()
        self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        preserved=self.page.evaluate("""async raw=>{const expected=JSON.parse(raw),actual=await __fastDB.auditExport(),a=await import('./model/journal-idb.mjs'),db=await a.connectV2('pushpull');try{return {
         indexed:!!(await a.readRecords(db)).state.runtime,entries:a.same(actual.data.entries,expected.data.entries),
         snapshots:expected.data.trainingJournal.sessionSnapshots.every(s=>actual.data.trainingJournal.sessionSnapshots.some(v=>a.same(s,v))),
         archives:expected.archives.every(s=>actual.archives.some(v=>a.same(s,v)))
        }}finally{db.close()}}""",raw)
        self.assertTrue(all(preserved.values()),preserved)
        self.assertFalse(self.alerts,self.alerts)
