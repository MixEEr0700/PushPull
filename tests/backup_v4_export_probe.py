"""Opt-in B1 measurements on fresh synthetic profiles; metadata-only output.

No user profile, backup path, account, Drive or production v4 storage integration.
"""
import argparse
import functools
import http.server
import json
import shutil
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect
from test_browser import QuietServer, ROOT
from backup_size_probe import HISTORY
from drive_backup_probe import renderer_rss


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',choices=['restores','history'],required=True)
    parser.add_argument('--restores',type=int,choices=range(5),default=4)
    parser.add_argument('--sessions',type=int,choices=[12,60,120],default=120)
    args=parser.parse_args()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietServer,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/'
    try:
        with tempfile.TemporaryDirectory(prefix='pushpull-b1-') as profile,sync_playwright() as pw:
            def launch():return pw.chromium.launch_persistent_context(profile,executable_path=shutil.which('chromium'),args=['--no-sandbox','--enable-precise-memory-info'],service_workers='block',viewport={'width':390,'height':844})
            context=launch();page=context.new_page();page.on('dialog',lambda d:d.accept());page.goto(url)
            expect(page.locator('[data-act=start]')).to_be_visible()
            page.locator('[data-tab=settings]').click();page.locator('[data-view=plans]').click()
            page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
            with page.expect_download():page.locator('[data-plan-activate]').click()
            expect(page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
            page.evaluate("async()=>{window.b1=await import('/model/backup-v4-export.mjs')}")
            context.set_offline(True)
            if args.scenario=='history':
                packet=json.loads((ROOT/'tests/fixtures/plan-v3.json').read_text())
                page.evaluate(HISTORY,{'count':args.sessions,'packet':packet})
            for cycle in range(args.restores+1 if args.scenario=='restores' else 1):
                metrics=page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{
                 const source=db.export(),revision=db.revision,options={createdAt:'2026-10-24T12:00:00.000Z'};
                 const start=performance.now(),out=await b1.exportBackupV4(source,options),ms=Math.round(performance.now()-start),heap=performance.memory.usedJSHeapSize;
                 const second=await b1.exportBackupV4(source,options);
                 if(out.text!==second.text||db.revision!==revision)throw Error('export changed source or grew');
                 return {ms,heap,sessions:source.data.sessions.length,results:source.data.entries.length,
                  snapshots:source.data.trainingJournal?.sessionSnapshots.length??0,repeatIdentical:true,...out.diagnostics};
                }finally{db.close()}}""")
                metrics.update(scenario=args.scenario,restoreCycle=cycle,rendererRssCheckpoint=renderer_rss())
                print(json.dumps(metrics),flush=True)
                if args.scenario=='restores' and cycle<args.restores:
                    page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const text=await d.exportModelBackup();await d.importModelBackup(text)}finally{d.close()}}""")
            # Existing open() verifies persisted data/model checksums on restart.
            expected=(metrics['sessions'],metrics['results'],metrics['archiveRecords'])
            context.close();context=launch();page=context.new_page();page.goto(url)
            expect(page.locator('[data-act=start]')).to_be_visible(timeout=120000)
            actual=page.evaluate("async()=>{const d=await PushPullDB.open(()=>{});try{return [d.value.sessions.length,d.value.entries.length,d.export().archives.length]}finally{d.close()}}")
            assert tuple(actual)==expected
            print(json.dumps({'restartVerified':True,'scenario':args.scenario}),flush=True);context.close()
    finally:
        server.shutdown();server.server_close();thread.join()


if __name__=='__main__':main()
