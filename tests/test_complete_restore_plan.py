from test_browser import BrowserHarness
import test_complete_capture as live

class CompleteRestorePlan(BrowserHarness):
    def test_live_capture_file_plan_and_empty_target_observation_do_not_write(self):
        live.CompleteCapture.prepare(self)
        result=self.page.evaluate("""async()=>{const before=await dump();const file=await capture.writeCapturedCompleteContract();const planner=await import('/model/complete-backup-restore-plan.mjs');const plan=await planner.planCompleteRestore(file);window.bytes=[...new Uint8Array(await file.arrayBuffer())];return {unchanged:protocol.equalJSON(before,await dump()),exact:protocol.equalJSON(plan.evidence,input),canCommit:plan.canCommit,stores:plan.stores.length};}""")
        self.assertEqual(result,dict(unchanged=True,exact=True,canCommit=False,stores=19))
        data=self.page.evaluate('bytes')
        ctx=self.new_context(service_workers='block');page=ctx.new_page();page.goto(self.url+'tests/fixtures/v1.json')
        actual=page.evaluate("""async bytes=>{const planner=await import('/model/complete-backup-restore-plan.mjs');localStorage.setItem('other-app','untouched');const before={local:{...localStorage},db:await indexedDB.databases()};const target=await planner.inspectEmptyRestoreTarget();const plan=await planner.planCompleteRestore(new Blob([new Uint8Array(bytes)]));return {empty:target.database,reserved:target.reserved,canCommit:plan.canCommit,equal:JSON.stringify(before)===JSON.stringify({local:{...localStorage},db:await indexedDB.databases()})};}""",data)
        self.assertEqual(actual,dict(empty='absent',reserved=False,canCommit=False,equal=True))
        page.reload()
        self.assertEqual(page.evaluate('localStorage.getItem("other-app")'),'untouched')
        self.assertEqual(page.evaluate('indexedDB.databases()'),[])

    def test_existing_profile_local_keys_and_database_rows_refuse(self):
        live.CompleteCapture.prepare(self)
        self.assertIn('not empty',self.page.evaluate("""async()=>{const p=await import('/model/complete-backup-restore-plan.mjs');try{await p.inspectEmptyRestoreTarget();return 'accepted'}catch(e){return e.message}}"""))
        self.page.evaluate('localStorage.clear()')
        self.assertIn('not empty',self.page.evaluate("""async()=>{const p=await import('/model/complete-backup-restore-plan.mjs');try{await p.inspectEmptyRestoreTarget();return 'accepted'}catch(e){return e.message}}"""))

    def test_empty_nineteen_store_schema_abort_and_read_error(self):
        live.CompleteCapture.prepare(self)
        self.page.evaluate("""async()=>{localStorage.clear();await new Promise((r,j)=>{const tx=db.transaction(codec.COMPLETE_STORES,'readwrite');for(const k of codec.COMPLETE_STORES)tx.objectStore(k).clear();tx.oncomplete=r;tx.onabort=()=>j(tx.error)});}""")
        result=self.page.evaluate("""async()=>{const p=await import('/model/complete-backup-restore-plan.mjs'),before=await dump(),target=await p.inspectEmptyRestoreTarget();const c=new AbortController();c.abort();let abort;try{await p.inspectEmptyRestoreTarget({signal:c.signal})}catch(e){abort=e.name}const old=IDBObjectStore.prototype.count;IDBObjectStore.prototype.count=function(){throw new DOMException('synthetic','QuotaExceededError')};let quota;try{await p.inspectEmptyRestoreTarget()}catch(e){quota=e.name}finally{IDBObjectStore.prototype.count=old}return {target:target.database,count:Object.keys(target.counts).length,abort,quota,unchanged:protocol.equalJSON(before,await dump())};}""")
        self.assertEqual(result,dict(target='empty-schema-v2',count=19,abort='AbortError',quota='QuotaExceededError',unchanged=True))
