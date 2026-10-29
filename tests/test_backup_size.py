"""Readonly native IDB inventory. No real Drive, account or user database."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,wait_for_service_worker_controller
import test_fast_start as fast
import test_indexeddb as legacy


class BackupSize(BrowserHarness):
    prepare = fast.FastStart.prepare
    records = legacy.IndexedDBMigration.records

    def panel(self):
        self.page.locator('[data-tab=settings]').click()
        self.advanced_data()
        return self.page.locator('[data-backup-size]')

    def report(self):
        panel = self.panel()
        panel.locator('[data-backup-size-check]').click()
        expect(panel.locator('[data-backup-size-report]')).to_be_visible(timeout=120000)
        with self.page.expect_download() as pending:
            panel.locator('[data-backup-size-report-download]').click()
        return json.loads(Path(pending.value.path()).read_text())

    def gate(self):
        self.page.evaluate("""()=>{const Native=Worker;window.Worker=class extends Native{
          constructor(...args){super(...args);window.__sizeWorker=this;}
          postMessage(value){window.__releaseSize=()=>super.postMessage(value);}
        }}""")
        panel = self.panel()
        panel.locator('[data-backup-size-check]').click()
        self.page.wait_for_function('typeof window.__releaseSize==="function"')
        return panel

    def test_exact_anonymous_offline_report_preserves_all_records_and_navigation_widths(self):
        self.context.close();self.context=self.new_context(service_workers='allow')
        self.page=self.context.new_page();self.page.on('dialog',self.dialog)
        self.page.goto(self.url);self.prepare();wait_for_service_worker_controller(self.page)
        # Strong oracles can allocate full JSON in tests; production never does.
        oracle=self.page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const source=await d.auditExport();return {compact:new TextEncoder().encode(JSON.stringify(source)).length,pretty:new TextEncoder().encode(JSON.stringify(source,null,2)).length,counts:[source.data.sessions.length,source.data.entries.length,source.data.trainingJournal.sessionSnapshots.length,source.archives.length]};}finally{d.close()}}""")
        self.page.evaluate('window.__network=[]')
        self.context.route('https://www.googleapis.com/**',lambda r:(self.page.evaluate('__network.push(true)'),r.abort()))
        before=self.records();local_before=self.page.evaluate('({...localStorage})')
        self.context.set_offline(True)
        report=self.report()
        self.assertEqual(report['sourceBytes']['total'],oracle['compact'])
        self.assertEqual(report['representationBytes']['sourcePretty'],oracle['pretty'])
        self.assertEqual([report['counts'][k] for k in ['sessions','results','snapshots','archives']],oracle['counts'])
        self.assertEqual(sum(v for k,v in report['sourceBytes'].items() if k!='total'),report['sourceBytes']['total'])
        self.assertLess(len(json.dumps(report)),8192)
        def numeric(value):
            if isinstance(value,dict):return all(numeric(v) for v in value.values())
            return type(value) is int and value>=0
        self.assertTrue(numeric(report))
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.assertEqual(self.records(),before);self.assertEqual(self.page.evaluate('({...localStorage})'),local_before)
        self.assertEqual(self.page.evaluate('__network'),[])
        self.assertFalse(self.alerts,self.alerts)

    def test_cancel_late_worker_and_new_operation_never_publish_cancelled_results(self):
        self.prepare();before=self.records();panel=self.gate()
        panel.locator('[data-backup-size-cancel]').click()
        expect(panel).to_contain_text('Anulowano pomiar')
        self.page.evaluate('__releaseSize()')
        self.page.locator('[data-tab=training]').click()
        self.panel();expect(panel.locator('[data-backup-size-report]')).to_have_count(0)
        self.assertEqual(self.records(),before)
        self.page.evaluate('()=>{window.Worker=Object.getPrototypeOf(Worker)}')
        self.assertGreater(self.report()['sourceBytes']['total'],0)
        self.assertEqual(self.records(),before)

    def test_changed_revision_and_worker_error_publish_no_partial_or_private_result(self):
        self.prepare();panel=self.gate()
        self.page.evaluate("""async()=>{await __fastDB.ensureHistory();const d=__fastDB.value;d.diagnosticSentinel='test-only';await __fastDB.commit(d)}""")
        before=self.records();self.page.evaluate('__releaseSize()')
        expect(panel).to_contain_text('Dane zmieniły się',timeout=120000)
        expect(panel.locator('[data-backup-size-report]')).to_have_count(0)
        self.assertEqual(self.records(),before)
        self.page.evaluate("()=>{window.Worker=class{constructor(){throw Error('PRIVATE secret token')}}}")
        panel.locator('[data-backup-size-check]').click()
        expect(panel).to_contain_text('Nie można wykonać pełnego pomiaru')
        expect(panel).not_to_contain_text('PRIVATE')
        expect(panel.locator('[data-backup-size-report]')).to_have_count(0)
        self.assertEqual(self.records(),before)

    def fingerprint(self):
        return self.page.evaluate("""async()=>{const db=await new Promise((resolve,reject)=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});
          try{const records=await new Promise((resolve,reject)=>{const tx=db.transaction([...db.objectStoreNames],'readonly'),out={};for(const name of db.objectStoreNames){const q=tx.objectStore(name).getAll();q.onsuccess=()=>out[name]=q.result}tx.oncomplete=()=>resolve(out);tx.onabort=()=>reject(tx.error)});
          const hash=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
          const out={};for(const [store,rows] of Object.entries(records)){out[store]=[];for(const row of rows)out[store].push(store==='journalObjects'?{id:row.id,bytes:row.bytes,hash:await hash(row.json)}:await hash(JSON.stringify(row)));}return out;
          }finally{db.close()}}""")

    def test_large_escaped_archive_keeps_navigation_responsive_without_full_json(self):
        self.prepare()
        self.page.evaluate("""async()=>{await __fastDB.ensureFull();const d=__fastDB.value;await __fastDB.commit(d,{importing:true,importedArchives:[{id:'large-size-only',kind:'opaque',createdAt:'2026-10-24T12:00:00.000Z',raw:'\"\\\\\\n'.repeat(9*1024*1024)}]})}""")
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        before=self.fingerprint()
        self.context.new_cdp_session(self.page).send('Emulation.setCPUThrottlingRate',{'rate':4})
        self.page.evaluate("""()=>{for(const k of ['ensureFull','ensureHistory','auditExport','exportModelBackup','export'])__fastDB[k]=()=>{throw Error('Full exporter forbidden')};window.__sizeLongTasks=[];window.__sizeObserver=new PerformanceObserver(l=>__sizeLongTasks.push(...l.getEntries().map(e=>e.duration)));__sizeObserver.observe({type:'longtask'});} """)
        panel=self.panel();panel.locator('[data-backup-size-check]').click()
        samples=[]
        for _ in range(5):
            samples.append(self.page.evaluate("""async()=>{const t=performance.now();document.querySelector('[data-tab=training]').click();while(!document.querySelector('[data-act=finish]'))await new Promise(r=>setTimeout(r,0));return performance.now()-t}"""))
            self.panel()
        expect(panel.locator('[data-backup-size-report]')).to_be_visible(timeout=120000)
        with self.page.expect_download() as pending:panel.locator('[data-backup-size-report-download]').click()
        report=json.loads(Path(pending.value.path()).read_text())
        self.page.evaluate('__sizeObserver.disconnect()')
        self.assertEqual(self.fingerprint(),before)
        Path('/tmp/pushpull-backup-size-synthetic.json').write_text(json.dumps({'report':report,'navigationMs':samples,'mainLongTaskMs':self.page.evaluate('Math.max(0,...__sizeLongTasks)')}))
        self.assertGreater(report['representationBytes']['sourceAsJsonStringAgain'],200000000)
        self.assertLess(max(samples),1000)
        print('Synthetic backup-size navigation ms:',samples,'report timings:',report['timingsMs'],'largest main task ms:',self.page.evaluate('Math.max(0,...__sizeLongTasks)'),flush=True)
        self.assertFalse(self.alerts,self.alerts)
