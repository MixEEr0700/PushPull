"""Real browser stores, synthetic records only; no production backup UI."""
from test_browser import BrowserHarness

class CompleteCapture(BrowserHarness):
    def prepare(self, large=False):
        self.page.wait_for_selector('[data-act=start]')
        self.page.goto(self.url+'tests/fixtures/v1.json')
        self.page.evaluate("""async large=>{
          window.capture=await import('/model/complete-backup-capture.mjs');
          window.codec=await import('/model/complete-backup-contract.mjs');
          window.protocol=await import('/model/journal-protocol.mjs');
          const {completeFixture}=await import('/tests/fixtures/complete-contract-fixture.mjs'),{previewFixture}=await import('/tests/fixtures/compact-preview-fixture.mjs');
          const s=previewFixture(await(await fetch('/tests/fixtures/v1.json')).json(),await(await fetch('/tests/fixtures/plan-test-3x5.json')).json(),true);delete s.settings;delete s.metadata;
          if(large)s.archives[0].raw='Ł😀'.repeat(300000);window.input=await completeFixture(s);for(const k of codec.COMPLETE_STORES)input.indexedDB.stores[k].sort((a,b)=>{const p=k==='meta'?'key':'id';return a[p]<b[p]?-1:a[p]>b[p]?1:0});input.localStorage.sort((a,b)=>a.key<b.key?-1:1);input.capture.localKeys=input.localStorage.map(r=>r.key);
          window.db=await new Promise((resolve,reject)=>{const r=indexedDB.open('pushpull',2);r.onupgradeneeded=()=>{for(const k of codec.COMPLETE_STORES)if(!r.result.objectStoreNames.contains(k))r.result.createObjectStore(k,{keyPath:k==='meta'?'key':'id'});};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
          await new Promise((resolve,reject)=>{const tx=db.transaction(codec.COMPLETE_STORES,'readwrite',{durability:'strict'});for(const k of codec.COMPLETE_STORES){tx.objectStore(k).clear();for(const r of input.indexedDB.stores[k])tx.objectStore(k).put(r);}tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error);});
          localStorage.clear();for(const r of input.localStorage)localStorage.setItem(r.key,r.raw);localStorage.setItem('other-app','do not capture');
          window.dump=async()=>{const stores={};await new Promise((resolve,reject)=>{const tx=db.transaction(codec.COMPLETE_STORES,'readonly');for(const k of codec.COMPLETE_STORES){const r=tx.objectStore(k).getAll();r.onsuccess=()=>stores[k]=r.result;}tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error);});return {stores,local:{...localStorage}};};
          window.holdDigest=()=>{const original=crypto.subtle.digest.bind(crypto.subtle);let release;window.gate=new Promise(r=>release=r);window.releaseDigest=()=>{crypto.subtle.digest=original;release();};let first=true;crypto.subtle.digest=async(...args)=>{if(first){first=false;window.reached=true;await gate;}return original(...args);};};
        }""",large)

    def test_all_real_stores_roundtrip_offline_and_unchanged(self):
        self.prepare()
        self.context.set_offline(True)
        result=self.page.evaluate("""async()=>{const before=await dump();const out=await capture.captureCompleteContract();const decoded=await codec.readCompleteContract(await capture.writeCapturedCompleteContract());return {stores:codec.COMPLETE_STORES.length,equal:protocol.equalJSON(out,input),wire:protocol.equalJSON(decoded,out),unchanged:protocol.equalJSON(await dump(),before),unrelated:out.localStorage.some(r=>r.key==='other-app')};}""")
        self.assertEqual(result,dict(stores=19,equal=True,wire=True,unchanged=True,unrelated=False))

    def test_other_tab_metadata_change_without_root_change_refuses(self):
        self.prepare()
        self.page.evaluate("""()=>{holdDigest();window.pending=capture.captureCompleteContract().then(()=> 'accepted',e=>e.message);}""")
        self.page.wait_for_function('window.reached===true')
        other=self.context.new_page();other.goto(self.url+'tests/fixtures/v1.json')
        other.evaluate("""async()=>{const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise((resolve,reject)=>{const tx=db.transaction('meta','readwrite');tx.objectStore('meta').put({key:'workout-draft:new',text:'unsaved conflict'});tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error)});db.close();}""")
        self.page.evaluate('releaseDigest()')
        self.assertIn('changed',self.page.evaluate('pending'))
        other.close()

    def test_local_storage_other_tab_aba_refuses(self):
        self.prepare();self.page.evaluate("""()=>{holdDigest();window.pending=capture.captureCompleteContract().then(()=> 'accepted',e=>e.message);}""")
        self.page.wait_for_function('window.reached===true')
        other=self.context.new_page();other.goto(self.url+'tests/fixtures/v1.json')
        other.evaluate("""()=>{const k='pushpull_skeleton_v1',v=localStorage.getItem(k);localStorage.setItem(k,'temporary');localStorage.setItem(k,v);}""")
        self.page.wait_for_timeout(30);self.page.evaluate('releaseDigest()')
        self.assertIn('changed',self.page.evaluate('pending'));other.close()

    def test_same_context_local_change_abort_and_limits_leave_data_unchanged(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{const before=await dump(),errors=[];for(const limits of [{records:1},{bytes:1},{nodes:1},{depth:1}]){try{await capture.captureCompleteContract({limits});errors.push('accepted')}catch(e){errors.push(e.message)}}const c=new AbortController();c.abort();try{await capture.captureCompleteContract({signal:c.signal})}catch(e){errors.push(e.name)}return {errors,unchanged:protocol.equalJSON(before,await dump())};}""")
        self.assertTrue(result['unchanged']);self.assertEqual(len(result['errors']),5)
        for value in result['errors'][:4]:self.assertIn('limit' if 'budget' not in value else 'budget',value)
        self.assertEqual(result['errors'][-1],'AbortError')
        self.page.evaluate("""()=>{holdDigest();window.pending=capture.captureCompleteContract().then(()=> 'accepted',e=>e.message);}""")
        self.page.wait_for_function('window.reached===true')
        self.page.evaluate("""()=>{localStorage.setItem('pushpull-note-ui-v1:later','new value');releaseDigest();}""")
        self.assertIn('changed',self.page.evaluate('pending'))

    def test_midflight_abort_and_transaction_failure_refuse(self):
        self.prepare()
        self.page.evaluate("""()=>{holdDigest();window.c=new AbortController();window.pending=capture.captureCompleteContract({signal:c.signal}).then(()=> 'accepted',e=>e.name);}""")
        self.page.wait_for_function('window.reached===true');self.page.evaluate('c.abort();releaseDigest()')
        self.assertEqual(self.page.evaluate('pending'),'AbortError')
        result=self.page.evaluate("""async()=>{const before=await dump();const original=IDBDatabase.prototype.transaction;IDBDatabase.prototype.transaction=function(...args){const tx=original.apply(this,args);if(args[1]==='readonly')queueMicrotask(()=>tx.abort());return tx;};let failed=false;try{await capture.captureCompleteContract()}catch{failed=true}finally{IDBDatabase.prototype.transaction=original}return {failed,unchanged:protocol.equalJSON(before,await dump())};}""")
        self.assertEqual(result,dict(failed=True,unchanged=True))

    def test_missing_store_and_unknown_application_key_refuse(self):
        self.prepare()
        self.assertIn('unclassified',self.page.evaluate("""async()=>{localStorage.setItem('pushpull_future','unknown');try{await capture.captureCompleteContract();return 'accepted'}catch(e){return e.message}finally{localStorage.removeItem('pushpull_future')}}"""))
        result=self.page.evaluate("""async()=>{db.close();await new Promise((r,j)=>{const q=indexedDB.deleteDatabase('pushpull');q.onsuccess=r;q.onerror=()=>j(q.error)});let error;try{await capture.captureCompleteContract()}catch(e){error=e.message}const absent=!(await indexedDB.databases()).some(d=>d.name==='pushpull');return {error,absent};}""")
        self.assertTrue(result['absent']);self.assertIn('unavailable',result['error'])

    def test_large_archive_capture_restart_and_readonly_transaction_modes(self):
        self.prepare(large=True)
        result=self.page.evaluate("""async()=>{const before=await dump(),modes=[],original=IDBDatabase.prototype.transaction;IDBDatabase.prototype.transaction=function(...args){modes.push({names:[...args[0]],mode:args[1]});return original.apply(this,args);};let out;try{out=await capture.captureCompleteContract()}finally{IDBDatabase.prototype.transaction=original}window.saved=out;return {equal:protocol.equalJSON(out,input),unchanged:protocol.equalJSON(before,await dump()),modes};}""")
        self.assertTrue(result['equal']);self.assertTrue(result['unchanged'])
        self.assertEqual(len(result['modes']),2)
        for tx in result['modes']:
            self.assertEqual(tx['mode'],'readonly');self.assertEqual(len(tx['names']),19)
        expected=self.page.evaluate('saved')
        self.page.reload()
        actual=self.page.evaluate("""async()=>{const {captureCompleteContract}=await import('/model/complete-backup-capture.mjs');return captureCompleteContract()}""")
        self.assertEqual(actual,expected)

    def test_read_access_failures_time_budget_and_corruption_refuse(self):
        self.prepare()
        result=self.page.evaluate("""async()=>{const before=await dump(),errors=[];for(const name of ['QuotaExceededError','SecurityError']){try{await capture.captureCompleteContract({storage:{get length(){throw new DOMException('synthetic read failure',name)}}})}catch(e){errors.push(e.name)}}const original=performance.now.bind(performance);let ticks=0;performance.now=()=>++ticks*100;try{await capture.captureCompleteContract({limits:{ms:1}})}catch(e){errors.push(e.message)}finally{performance.now=original}return {errors,unchanged:protocol.equalJSON(before,await dump())};}""")
        self.assertTrue(result['unchanged']);self.assertEqual(result['errors'][:2],['QuotaExceededError','SecurityError']);self.assertIn('time limit',result['errors'][2])
        self.page.evaluate("""async()=>{await new Promise((resolve,reject)=>{const tx=db.transaction('journalObjects','readwrite');const r=tx.objectStore('journalObjects').openCursor();r.onsuccess=()=>{const c=r.result;if(c)c.update({...c.value,json:'corrupted'})};tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error)});}""")
        self.assertNotEqual(self.page.evaluate("""async()=>{try{await capture.captureCompleteContract();return 'accepted'}catch(e){return e.message}}"""),'accepted')

    def test_missing_one_of_nineteen_stores_refuses(self):
        self.prepare()
        self.assertIn('schema',self.page.evaluate("""async()=>{db.close();await new Promise((r,j)=>{const q=indexedDB.deleteDatabase('pushpull');q.onsuccess=r;q.onerror=()=>j(q.error)});const partial=await new Promise((r,j)=>{const q=indexedDB.open('pushpull',2);q.onupgradeneeded=()=>{for(const k of codec.COMPLETE_STORES)if(k!=='notes')q.result.createObjectStore(k,{keyPath:k==='meta'?'key':'id'})};q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error)});partial.close();try{await capture.captureCompleteContract();return 'accepted'}catch(e){return e.message}}"""))

    def test_epoch_revision_change_during_validation_refuses(self):
        self.prepare()
        self.page.evaluate("""()=>{holdDigest();window.pending=capture.captureCompleteContract().then(()=> 'accepted',e=>e.message);}""")
        self.page.wait_for_function('window.reached===true')
        self.page.evaluate("""async()=>{await new Promise((resolve,reject)=>{const tx=db.transaction('journalState','readwrite');const r=tx.objectStore('journalState').get('active');r.onsuccess=()=>tx.objectStore('journalState').put({...r.result,epoch:'concurrent-epoch',revision:r.result.revision+1});tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error)});releaseDigest();}""")
        self.assertIn('changed',self.page.evaluate('pending'))
