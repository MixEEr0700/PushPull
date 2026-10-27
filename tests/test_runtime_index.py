"""Stage E native reader / strict commands against independent full oracle."""
from test_browser import BrowserHarness
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
