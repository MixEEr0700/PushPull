"""Issue #82 B: native transactions, never an in-memory IndexedDB substitute."""
from test_browser import BrowserHarness

SETUP=r"""async ({native=true,convert=true}={})=>{
 const api=await import('./model/journal-idb.mjs'),codec=await import('./model/journal-protocol.mjs');
 const live=await PushPullDB.open(()=>{throw Error('missing fixture')});
 if(live.error)throw live.error;
 try{
  if(native){
   const {nativeData,AT}=await import('./tests/fixtures/backup-v4-fixture.mjs'),old=await (await fetch('./tests/fixtures/v1.json')).json(),packet=await (await fetch('./tests/fixtures/plan-v3.json')).json();
   const data=nativeData(old,packet),catalog=PushPullDB.parseBackup(data).catalog;
   const source={format:'pushpull-backup',version:2,data,catalog,archives:[{id:'opaque',kind:'recovery',createdAt:AT,raw:'Ł😀\\"\n'.repeat(262144)}]};
   const {createLegacyModelFromSource}=await import('./model/legacy-model.mjs');
   await live.importModelBackup(JSON.stringify(await createLegacyModelFromSource(source,{ownerId:data.trainingJournal.model.ownerId,createdAt:AT})));
  }else{
   const old=await (await fetch('./tests/fixtures/v1.json')).json(),parsed=PushPullDB.parseBackup(old);
   await live.commit(parsed.data,{importing:true,importedCatalog:parsed.catalog});
  }
  const capture=await new Promise((ok,no)=>{const r=indexedDB.open('pushpull',1);r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});
  const name='issue82-b-'+crypto.randomUUID(),evidence=await api.legacyEvidence(capture),source=live.export();capture.close();
  const opening=indexedDB.open(name,1);opening.onupgradeneeded=()=>{for(const s of api.LEGACY_STORES)opening.result.createObjectStore(s,{keyPath:s==='meta'?'key':'id'})};
  const oldDb=await api.request(opening);await api.transact(oldDb,api.LEGACY_STORES,'readwrite',tx=>{for(const s of api.LEGACY_STORES)for(const r of evidence[s])tx.objectStore(s).add(r)});oldDb.close();
  window.__v2={api,codec,name,evidence,source};__v2.db=await api.connectV2(name);if(convert)__v2.writer=await api.convertV1(__v2.db,source,evidence,{ownerId:source.data.trainingJournal?.model.ownerId});
  window.__command=(weight='33')=>{
   const w=__v2.writer,old=w.source.data.entries.find(e=>native?!!e.performance:true),entry=structuredClone(old);
   if(entry.performance){entry.performance.rows[0].segments[0].kg=weight;entry.series=entry.performance.rows.flatMap(r=>r.segments.map(s=>({...s,parentId:r.id,side:r.side})));entry.kg=entry.series[0].kg;}
   else {entry.kg=weight;if(entry.series?.length)entry.series[0].kg=weight;}
   entry.correctedAt='2026-10-25T10:00:00.000Z';entry.future={unicode:'Ł😀\ud800',retained:[null,false]};
   return {sessionId:entry.sessionId,exerciseId:entry.exerciseId,entry,...w.context(entry.sessionId,entry.exerciseId)};
  };
  return {name,revision:__v2.writer?.state.revision??null};
 }finally{live.close()}
}"""

class JournalWriter(BrowserHarness):
    def prepare_writer(self,native=True,convert=True):
        self.page.wait_for_selector('[data-act=start]')
        return self.page.evaluate(SETUP,{'native':native,'convert':convert})

    def test_plain_bridge_conversion_retains_original_owner_without_native_journal(self):
        self.prepare_writer(native=False,convert=False)
        result=self.page.evaluate("""async()=>{
         const {api,db,source,evidence}=__v2,{createLegacyModelFromSource}=await import('./model/legacy-model.mjs'),captured=structuredClone(evidence);
         const document=await createLegacyModelFromSource(source,{ownerId:'original-owner',createdAt:'2026-10-25T00:00:00.000Z'});
         const row={key:'training-model-v1',revision:captured.meta.find(r=>r.key==='state').revision,document};captured.meta.push(row);
         await api.transact(db,['meta'],'readwrite',tx=>tx.objectStore('meta').add(row));
         const writer=await api.convertV1(db,source,captured);return {ownerId:writer.state.ownerId,enabled:writer.state.modelEnabled,journal:!!writer.source.data.trainingJournal};
        }""")
        self.assertEqual(result,{'ownerId':'original-owner','enabled':True,'journal':False})

    def test_retained_record_and_byte_limits_refuse_before_transaction_and_leave_restart_readable(self):
        self.prepare_writer()
        result=self.page.evaluate("""async()=>{
         const {api,codec,db}=__v2,bundle=await api.readRecords(db);await api.openWriter(db,{bundle});
         const budget=codec.protocolBudget(bundle),before=JSON.stringify(bundle);let rejected=0,writes=0;
         for(const limits of [{records:budget.records},{totalBytes:budget.bytes}]){
          const limited=await api.openWriter(db,{bundle,limits}),transaction=db.transaction.bind(db);
          db.transaction=(...args)=>{if(args[1]==='readwrite')writes++;return transaction(...args)};
          try{await limited.saveResult(__command())}catch(e){if(/protocol (total size|record count)/.test(e.message))rejected++;else throw e}finally{db.transaction=transaction}
         }
         const stored=await api.readRecords(db),reopened=await api.openWriter(db);return {rejected,writes,unchanged:JSON.stringify(stored)===before,readable:JSON.stringify(reopened.source)===JSON.stringify(__v2.writer.source)};
        }""")
        self.assertEqual(result,{'rejected':2,'writes':0,'unchanged':True,'readable':True})

    def test_missing_or_resealed_checkpoint_cannot_pass_with_the_same_root(self):
        self.prepare_writer()
        result=self.page.evaluate("""async()=>{
         const {api,db,writer}=__v2,before=await api.readRecords(db),checkpoint=before.records.journalCheckpoints[0];let rejected=0;
         await api.transact(db,['journalCheckpoints'],'readwrite',tx=>tx.objectStore('journalCheckpoints').delete(checkpoint.id));
         try{await api.openWriter(db)}catch{rejected++}
         const changed={...structuredClone(checkpoint),unknown:'metadata changed with source and evidence SHA intact'};
         await api.transact(db,['journalCheckpoints'],'readwrite',tx=>tx.objectStore('journalCheckpoints').put(changed));
         try{await writer.audit()}catch{rejected++}
         const unchangedRoot=JSON.stringify((await api.readRecords(db)).state)===JSON.stringify(before.state);
         await api.transact(db,['journalCheckpoints'],'readwrite',tx=>tx.objectStore('journalCheckpoints').put(checkpoint));
         return {rejected,unchangedRoot,recovered:JSON.stringify(await writer.audit())===JSON.stringify(writer.source)};
        }""")
        self.assertEqual(result,{'rejected':2,'unchangedRoot':True,'recovered':True})

    def test_orphan_v2_records_or_formerly_active_marker_never_replay_v1(self):
        self.prepare_writer(native=False,convert=False)
        result=self.page.evaluate("""async()=>{
         const {api,codec,db,source,evidence}=__v2,row=await codec.objectRecord({value:'unreferenced data must survive'});let rejected=0;
         await api.transact(db,['journalObjects'],'readwrite',tx=>tx.objectStore('journalObjects').add(row));
         const before=JSON.stringify(await api.readRecords(db));try{await api.convertV1(db,source,evidence)}catch(e){if(e.message.includes('stores not empty'))rejected++}
         const kept=JSON.stringify(await api.readRecords(db))===before;
         await api.transact(db,['journalObjects','meta'],'readwrite',tx=>{tx.objectStore('journalObjects').delete(row.id);tx.objectStore('meta').put({key:api.MARKER,protocol:2,status:'active',epoch:'lost-root'})});
         try{await api.convertV1(db,source,evidence)}catch(e){if(e.message.includes('pending marker'))rejected++}
         return {rejected,kept,notReplayed:!(await api.readRecords(db)).state};
        }""")
        self.assertEqual(result,{'rejected':2,'kept':True,'notReplayed':True})

    def test_native_correction_strict_complete_restart_unknown_fields_and_unchanged_v1_checkpoint(self):
        self.prepare_writer()
        result=self.page.evaluate(r"""async()=>{
         const {db,api,writer,evidence}=__v2,command=__command(),before=structuredClone(writer.source);
         let complete=false,durability;const transaction=db.transaction.bind(db);
         db.transaction=(...args)=>{const tx=transaction(...args);if(args[1]==='readwrite')tx.addEventListener('complete',()=>{complete=true;durability=tx.durability});return tx};
         const ack=await writer.saveResult(command);const publishedAfterComplete=complete;
         before.data.entries[before.data.entries.findIndex(e=>e.id===command.entry.id)]=command.entry;
         const read=await writer.audit(),old=await api.legacyEvidence(db),checkpoint=(await api.readRecords(db)).records.journalCheckpoints[0];
         const noMarker=x=>({...x,meta:x.meta.filter(r=>r.key!==api.MARKER)});
         db.close();const restart=await api.connectV2(__v2.name),reopened=await api.openWriter(restart);restart.close();
         return {publishedAfterComplete,durability,ackRevision:ack.revision,identical:JSON.stringify(read)===JSON.stringify(before),restart:JSON.stringify(reopened.source)===JSON.stringify(before),v1:JSON.stringify(noMarker(old))===JSON.stringify(evidence),checkpoint:JSON.stringify(checkpoint.evidence)===JSON.stringify(evidence)};
        }""")
        self.assertTrue(result['publishedAfterComplete']);self.assertEqual(result['durability'],'strict')
        for key in ['identical','restart','v1','checkpoint']:self.assertTrue(result[key],result)

    def test_two_clients_and_wrong_epoch_revision_entry_or_snapshot_fail_cas(self):
        self.prepare_writer()
        result=self.page.evaluate("""async()=>{
         const {api,db,writer}=__v2,second=await api.openWriter(db),cmd=__command();let rejected=0;
         for(const field of ['expectedEpoch','expectedRevision','expectedEntryHash','snapshotHash']){
          try{await writer.saveResult({...cmd,[field]:field==='expectedRevision'?cmd[field]+1:'wrong'})}catch{rejected++}
         }
         await writer.saveResult(cmd);try{await second.saveResult(cmd)}catch{rejected++}
         return {rejected,revision:writer.state.revision===cmd.expectedRevision+1,audit:JSON.stringify(await writer.audit())===JSON.stringify(writer.source)};
        }""")
        self.assertEqual(result,{'rejected':5,'revision':True,'audit':True})

    def test_page_close_during_result_transaction_rolls_back_and_restart_can_retry(self):
        self.prepare_writer()
        before=self.page.evaluate('JSON.stringify(__v2.writer.source)')
        name=self.page.evaluate('__v2.name')
        self.page.evaluate("""()=>{
         const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...args){
          const result=put.apply(this,args);if(this.name==='journalResults'){
           window.__held=true;const store=this.transaction.objectStore('meta');
           function keep(){const r=store.get('hold-result');r.onsuccess=keep}keep();
          }return result;
         };
         window.__finished=false;__v2.writer.saveResult(__command()).then(()=>{window.__finished=true});
        }""")
        self.page.wait_for_function('window.__held===true')
        self.assertFalse(self.page.evaluate('__finished'))
        self.page.close();self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url)
        result=self.page.evaluate("""async name=>{const api=await import('./model/journal-idb.mjs'),db=await api.connectV2(name);try{const w=await api.openWriter(db);return JSON.stringify(w.source)}finally{db.close()}}""",name)
        self.assertEqual(result,before)

    def test_blocked_upgrade_waits_for_old_connection_and_upgrade_abort_keeps_v1(self):
        self.prepare_writer(native=False)
        result=self.page.evaluate("""async()=>{
         const {api,evidence}=__v2,name='blocked-'+crypto.randomUUID(),r=indexedDB.open(name,1);
         r.onupgradeneeded=()=>{for(const s of api.LEGACY_STORES)r.result.createObjectStore(s,{keyPath:s==='meta'?'key':'id'})};
         const old=await api.request(r);await api.transact(old,api.LEGACY_STORES,'readwrite',tx=>{for(const s of api.LEGACY_STORES)for(const row of evidence[s])tx.objectStore(s).add(row)});
         let blocked=false;try{await api.connectV2(name)}catch(e){blocked=e.message.includes('Zamknij')}
         const kept=JSON.stringify(await api.legacyEvidence(old))===JSON.stringify(evidence);old.close();
         const next=await api.connectV2(name),pending=await api.readRecords(next);next.close();
         const second='upgrade-abort-'+crypto.randomUUID(),opening=indexedDB.open(second,1);opening.onupgradeneeded=()=>opening.result.createObjectStore('meta',{keyPath:'key'});const v1=await api.request(opening);v1.close();
         const create=IDBDatabase.prototype.createObjectStore;IDBDatabase.prototype.createObjectStore=function(...args){if(args[0]==='journalResults')throw new DOMException('upgrade quota','QuotaExceededError');return create.apply(this,args)};
         let aborted=false;try{await api.connectV2(second)}catch(e){aborted=e.name==='QuotaExceededError'}finally{IDBDatabase.prototype.createObjectStore=create}
         const untouched=await api.request(indexedDB.open(second,1)),rolledBack=untouched.version===1&&untouched.objectStoreNames.length===1;untouched.close();
         return {blocked,kept,pending:!pending.state,aborted,rolledBack};
        }""")
        self.assertEqual(result,dict.fromkeys(['blocked','kept','pending','aborted','rolledBack'],True))

    def test_result_row_and_unknown_values_are_fully_validated_and_detached_before_await(self):
        self.prepare_writer()
        result=self.page.evaluate("""async()=>{
         const w=__v2.writer,original=__command();let rejected=0;
         for(const change of [e=>e.kg='999',e=>e.journalVariantId='missing',e=>e.performance.rows[0].segments[0].kg='NaN',e=>e.future.value=Infinity,e=>e.performance.rows[0].segments[0].reps='0']){
          const cmd=structuredClone(original);change(cmd.entry);try{await w.saveResult(cmd)}catch{rejected++}
         }
         const pending=w.saveResult(original);original.entry.future.unicode='mutated';original.entry.performance.rows[0].segments[0].kg='0';
         const ack=await pending;return {rejected,unicodePrefix:ack.entry.future.unicode.slice(0,-1),unicodeLastUnit:ack.entry.future.unicode.charCodeAt(3),kg:ack.entry.kg};
        }""")
        self.assertEqual(result,{'rejected':5,'unicodePrefix':'Ł😀','unicodeLastUnit':0xd800,'kg':'33'})

    def test_new_legacy_result_and_repeated_correction_preserve_order_without_reading_archives(self):
        self.prepare_writer(native=False)
        result=self.page.evaluate("""async()=>{
         const {writer}=__v2,d=writer.source.data,s=d.sessions[0],ex=d.exercises[s.type].find(ex=>!d.entries.some(e=>e.sessionId===s.id&&e.exerciseId===ex.id));
         const entry={id:'new-incremental',sessionId:s.id,exerciseId:ex.id,kg:'20',reps:'8',series:null,createdAt:'2026-10-25T00:00:00.000Z',unknown:{kept:true}},before=d.entries.length;
         const get=IDBObjectStore.prototype.get,getAll=IDBObjectStore.prototype.getAll,archiveIds=new Set((await __v2.api.readRecords(__v2.db)).records.journalArchives.map(r=>r.ref));
         IDBObjectStore.prototype.get=function(id){if(this.name==='journalArchives'||this.name==='journalObjects'&&archiveIds.has(id))throw Error('unexpected archive read');return get.call(this,id)};
         IDBObjectStore.prototype.getAll=function(...args){if(this.name==='journalArchives'||this.name==='journalObjects')throw Error('unexpected bulk read');return getAll.apply(this,args)};
         try{
          await writer.saveResult({sessionId:s.id,exerciseId:ex.id,entry,...writer.context(s.id,ex.id)});
          entry.kg='21';await writer.saveResult({sessionId:s.id,exerciseId:ex.id,entry,...writer.context(s.id,ex.id)});
         }finally{IDBObjectStore.prototype.get=get;IDBObjectStore.prototype.getAll=getAll}
         const source=await writer.audit();return {count:source.data.entries.length===before+1,last:source.data.entries.at(-1).kg,unknown:source.data.entries.at(-1).unknown.kept};
        }""")
        self.assertEqual(result,{'count':True,'last':'21','unknown':True})

    def test_conversion_rejects_unbound_source_or_a_changed_v1_checkpoint_and_can_retry_latest_evidence(self):
        self.prepare_writer(native=False,convert=False)
        result=self.page.evaluate("""async()=>{
         const {api,db,source,evidence}=__v2;let rejected=0;
         const wrong=structuredClone(source);wrong.data.entries=[];
         try{await api.convertV1(db,wrong,evidence)}catch{rejected++}
         // A source edit before conversion is detectable even without revision change.
         await api.transact(db,['meta'],'readwrite',tx=>tx.objectStore('meta').put({key:'workout-draft:unanswered-tab',token:'newer',raw:'unfinished Ł😀'}));
         try{await api.convertV1(db,source,evidence)}catch{rejected++}
         const pending=await api.readRecords(db),latest=await api.legacyEvidence(db),writer=await api.convertV1(db,source,latest);
         return {rejected,pending:!pending.state,kept:latest.meta.some(r=>r.token==='newer'),identical:JSON.stringify(await writer.audit())===JSON.stringify(source)};
        }""")
        self.assertEqual(result,{'rejected':2,'pending':True,'kept':True,'identical':True})

    def test_abort_during_preparation_or_transaction_and_global_row_id_collision_do_not_publish(self):
        self.prepare_writer()
        result=self.page.evaluate("""async()=>{
         const {api,db,writer}=__v2,before=JSON.stringify(await api.readRecords(db));let rejected=0;
         const collision=__command(),other=writer.source.data.entries.find(e=>e.id!==collision.entry.id&&e.performance);
         collision.entry.performance.rows[0].id=other.performance.rows[0].id;
         collision.entry.series=collision.entry.performance.rows.flatMap(r=>r.segments.map(s=>({...s,parentId:r.id,side:r.side})));
         try{await writer.saveResult(collision)}catch{rejected++}
         const c=new AbortController(),digest=crypto.subtle.digest.bind(crypto.subtle);crypto.subtle.digest=async(...args)=>{const value=await digest(...args);c.abort();return value};
         try{await writer.saveResult(__command(),{signal:c.signal})}catch{rejected++}finally{crypto.subtle.digest=digest}
         const abort=new AbortController(),put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...args){if(this.name==='journalResults')abort.abort();return put.apply(this,args)};
         try{await writer.saveResult(__command(),{signal:abort.signal})}catch{rejected++}finally{IDBObjectStore.prototype.put=put}
         return {rejected,unchanged:JSON.stringify(await api.readRecords(db))===before};
        }""")
        self.assertEqual(result,{'rejected':3,'unchanged':True})

    def test_quota_abort_and_tampered_readback_roll_back_every_store_and_memory(self):
        self.prepare_writer()
        result=self.page.evaluate("""async()=>{
         const {api,db,writer}=__v2,before=JSON.stringify(await api.readRecords(db)),source=JSON.stringify(writer.source),cases=[['journalObjects','add','quota'],['journalIndex','add','abort'],['journalResults','put','tamper'],['journalState','put','tamper'],['journalResults','put','undefined']];let rejected=0;
         for(const [store,method,kind] of cases){
          const fn=IDBObjectStore.prototype[method];IDBObjectStore.prototype[method]=function(row,...args){if(this.name===store){if(kind==='quota')throw new DOMException('full','QuotaExceededError');if(kind==='abort'){this.transaction.abort();throw new DOMException('stop','AbortError')}row={...row,future:kind==='undefined'?undefined:'tampered'};}return fn.call(this,row,...args)};
          try{await writer.saveResult(__command())}catch{rejected++}finally{IDBObjectStore.prototype[method]=fn}
          if(JSON.stringify(await api.readRecords(db))!==before||JSON.stringify(writer.source)!==source)throw Error('partial publication');
         }
         const c=new AbortController();c.abort();try{await writer.saveResult(__command(),{signal:c.signal})}catch{rejected++}
         return rejected;
        }""")
        self.assertEqual(result,6)

    def test_required_object_tamper_is_rejected_but_untouched_archive_is_audited_on_full_read(self):
        self.prepare_writer()
        result=self.page.evaluate("""async()=>{
         const {api,db,writer}=__v2,row=(await api.readRecords(db)).records.journalSessions.find(r=>r.id===__command().sessionId),obj=await api.transact(db,['journalObjects'],'readonly',tx=>api.request(tx.objectStore('journalObjects').get(row.ref)));
         await api.transact(db,['journalObjects'],'readwrite',tx=>tx.objectStore('journalObjects').put({...obj,json:obj.json+' '}));
         let rejected=false;try{await writer.saveResult(__command())}catch{rejected=true}
         await api.transact(db,['journalObjects'],'readwrite',tx=>tx.objectStore('journalObjects').put(obj));
         const archive=(await api.readRecords(db)).records.journalArchives[0],blob=await api.transact(db,['journalObjects'],'readonly',tx=>api.request(tx.objectStore('journalObjects').get(archive.ref)));
         await api.transact(db,['journalObjects'],'readwrite',tx=>tx.objectStore('journalObjects').put({...blob,json:blob.json+' '}));
         await writer.saveResult(__command());let auditRejected=false;try{await writer.audit()}catch{auditRejected=true}
         return {rejected,auditRejected};
        }""")
        self.assertEqual(result,{'rejected':True,'auditRejected':True})

    def test_incomplete_conversion_keeps_checkpoint_and_resumes_without_overwriting_v1(self):
        self.prepare_writer(native=False)
        result=self.page.evaluate("""async()=>{
         const {api,evidence,source}=__v2,name='issue82-pending-'+crypto.randomUUID(),r=indexedDB.open(name,1);
         r.onupgradeneeded=()=>{for(const s of api.LEGACY_STORES)r.result.createObjectStore(s,{keyPath:s==='meta'?'key':'id'})};
         let db=await api.request(r);await api.transact(db,api.LEGACY_STORES,'readwrite',tx=>{for(const s of api.LEGACY_STORES)for(const row of evidence[s])tx.objectStore(s).add(row)});db.close();db=await api.connectV2(name);
         const put=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(value,...args){if(this.name==='journalState')throw new DOMException('full','QuotaExceededError');return put.call(this,value,...args)};
         let rejected=false;try{await api.convertV1(db,source,evidence)}catch{rejected=true}finally{IDBObjectStore.prototype.add=put}
         const pending=await api.readRecords(db),old=await api.legacyEvidence(db);db.close();db=await api.connectV2(name);const writer=await api.convertV1(db,source,evidence);db.close();
         let oldVersionRejected=false;try{await api.request(indexedDB.open(name,1))}catch(e){oldVersionRejected=e.name==='VersionError'}
         return {rejected,pending:!pending.state&&pending.records.journalObjects.length===0,old:JSON.stringify(old.meta.filter(r=>r.key!==api.MARKER))===JSON.stringify(evidence.meta),resumed:JSON.stringify(writer.source)===JSON.stringify(source),oldVersionRejected};
        }""")
        self.assertEqual(result,dict.fromkeys(['rejected','pending','old','resumed','oldVersionRejected'],True))
