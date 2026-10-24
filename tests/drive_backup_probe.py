"""Opt-in synthetic Drive memory probe; never reads a user profile/account.

Run from the checkout: python3 tests/drive_backup_probe.py --restore-cycles 4 --heap-mib 768
Requires the existing Playwright/Chromium test dependencies. Large cases are NOT
part of normal unittest discovery. No training content or credentials are logged.
"""
import argparse
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect
from test_browser import QuietServer, ROOT


def emit(kind, **values):
    print(json.dumps({'kind': kind, **values}), flush=True)


def renderer_rss():
    """Linux RSS for this probe's descendant renderers, not other applications."""
    processes={};total=0
    try:
        for entry in os.scandir('/proc'):
            if not entry.name.isdigit():continue
            try:
                fields=Path(entry.path,'stat').read_text().rsplit(')',1)[1].split()
                processes[int(entry.name)]=(int(fields[1]),int(fields[21])*os.sysconf('SC_PAGE_SIZE'))
            except (OSError, IndexError, ValueError):pass
        pending=[os.getpid()];seen=set()
        while pending:
            pid=pending.pop()
            if pid in seen:continue
            seen.add(pid);pending.extend(child for child,(parent,_) in processes.items() if parent==pid)
            try:
                if b'--type=renderer' in Path(f'/proc/{pid}/cmdline').read_bytes():total+=processes[pid][1]
            except (OSError, KeyError):pass
    except OSError:return None
    return total or None


class DriveServer(QuietServer):
    # Native HTTP avoids DevTools copying large POST bodies into Playwright.
    files={}

    def reply(self, value, status=200):
        body=value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)));self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):pass

    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/drive/v3/about':
            self.reply({'user':{'permissionId':'synthetic','emailAddress':'synthetic@example.invalid'}})
        elif path=='/drive/v3/files':self.reply({'files':[]})
        elif path.startswith('/drive/v3/files/'):
            self.reply(type(self).files[path.rsplit('/',1)[1]])
        else:super().do_GET()

    def do_POST(self):
        if not self.path.startswith('/upload/drive/v3/files'):self.reply({},404);return
        body=self.rfile.read(int(self.headers['Content-Length']))
        boundary=self.headers['Content-Type'].split('boundary=')[1].encode()
        text=body.split(b'--'+boundary)[2].split(b'\r\n\r\n',1)[1].removesuffix(b'\r\n')
        file_id='synthetic-'+str(len(type(self).files)+1)
        type(self).files[file_id]=text
        emit('post-stored',bytes=len(text),files=len(type(self).files))
        self.reply({'id':file_id})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opaque-mib',type=int,choices=range(33),default=0)
    parser.add_argument('--restore-cycles',type=int,choices=range(5),default=0)
    parser.add_argument('--heap-mib',type=int,choices=[0,128,256,512,768],default=0)
    parser.add_argument('--copies',type=int,choices=range(1,4),default=1)
    parser.add_argument('--drive-ref',help='Optional baseline commit (7–40 hex digits)')
    parser.add_argument('--no-trace',action='store_true',help='No source checkpoints')
    args=parser.parse_args()
    if args.drive_ref and not re.fullmatch('[a-fA-F0-9]{7,40}',args.drive_ref):
        parser.error('--drive-ref must be a commit hash')
    if args.opaque_mib and args.restore_cycles:
        parser.error('Use opaque data and archive nesting as separate bounded probes')
    DriveServer.files={}
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(DriveServer,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/'
    flags=['--no-sandbox','--enable-precise-memory-info']
    outcome='setup-error';stage='seed';before=None
    try:
        with tempfile.TemporaryDirectory(prefix='pushpull-probe-') as profile, sync_playwright() as pw:
            def attach(context):
                def instrument(route):
                    source=subprocess.check_output(['git','show',args.drive_ref+':model/drive-sync.mjs'],cwd=ROOT).decode() if args.drive_ref else (ROOT/'model/drive-sync.mjs').read_text()
                    if not args.no_trace:
                        gate='if(!same(node,verified))' if 'if(!same(node,verified))' in source else 'if(node.backup!==verified.backup||node.digest!==verified.digest)'
                        points=[
                            ('const revision=database.revision,current=database.value;', "globalThis.__probe('upload-start');const revision=database.revision,current=database.value;globalThis.__probe('value-read');"),
                            ('const node=await makeNode(backup,[],inspect);', "globalThis.__probe('export-end',{chars:backup.length});const node=await makeNode(backup,[],inspect);globalThis.__probe('makeNode-end');"),
                            ('await inspect(backup);', "globalThis.__probe('inspect-start');await inspect(backup);globalThis.__probe('inspect-end');"),
                            ('const file=await transport.create(', "globalThis.__probe('create-start');const file=await transport.create("),
                            ('const verified=await readNode(', "globalThis.__probe('POST-end');const verified=await readNode("),
                            (gate,"globalThis.__probe('readNode-end');"+gate),
                            ('const summary=backupSummary(current', "globalThis.__probe('comparison-end');const summary=backupSummary(current"),
                        ]
                        for old,new in points:
                            if old not in source:raise ValueError('Unsupported probe source')
                            source=source.replace(old,new)
                    route.fulfill(body=source,content_type='text/javascript')
                context.route('**/model/drive-sync.mjs',instrument)
                page=context.new_page()
                page.add_init_script("""const realFetch=globalThis.fetch;
                  globalThis.fetch=(url,options)=>realFetch(typeof url==='string'?url.replace('https://www.googleapis.com',location.origin):url,options);
                  globalThis.google={accounts:{oauth2:{hasGrantedAllScopes:()=>true,initTokenClient:o=>({requestAccessToken:()=>o.callback({access_token:'synthetic-only',expires_in:3600})})}}};
                  globalThis.__probe=(stage,extra={})=>console.log('DRIVE_PROBE '+JSON.stringify({stage,heap:performance.memory.usedJSHeapSize,...extra}));
                  globalThis.__done=0;globalThis.__uploading=false;globalThis.__failed=false;
                  new MutationObserver(()=>{const text=document.querySelector('[data-drive-status]')?.textContent||'';
                    if(text.includes('Trwa operacja Google Drive'))globalThis.__uploading=true;
                    if(globalThis.__uploading&&text.includes('Kopia zapisana i zweryfikowana')){globalThis.__done++;globalThis.__uploading=false;}
                    if(globalThis.__uploading&&text.startsWith('Błąd:')){globalThis.__failed=true;globalThis.__uploading=false;}
                  }).observe(document,{subtree:true,childList:true,characterData:true});""")
                page.on('console',lambda message:emit('checkpoint',**json.loads(message.text[12:]),rendererRss=renderer_rss()) if message.text.startswith('DRIVE_PROBE ') else None)
                page.on('crash',lambda _:emit('renderer-crash',stage=stage))
                page.on('dialog',lambda dialog:dialog.accept())
                return page

            def launch(limit=0):
                return pw.chromium.launch_persistent_context(profile,executable_path=shutil.which('chromium'),args=flags+([f'--js-flags=--max-old-space-size={limit}'] if limit else []),service_workers='block',viewport={'width':390,'height':844})

            def fingerprint(page):
                # Output contains only equality, never these data/metadata hashes.
                return page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const hash=async v=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(v)))),x=>x.toString(16).padStart(2,'0')).join('');return {data:await hash(d.value),drafts:await hash(await d.readDrafts()),drive:await hash(await d.readDriveState()??null),archives:d.backups(),revision:d.revision}}finally{d.close()}}""")

            context=launch();page=attach(context);page.goto(url)
            expect(page.locator('[data-act=start]')).to_be_visible()
            page.locator('[data-tab=settings]').click();page.locator('[data-view=plans]').click()
            page.locator('#importedPlanId').select_option('v2-owner-2026-10-22')
            with page.expect_download():page.locator('[data-plan-activate]').click()
            expect(page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible(timeout=60000)
            page.evaluate("""async n=>{const d=await PushPullDB.open(()=>{});try{const v=d.value;v.extension={synthetic:'x'.repeat(n*1024*1024)};await d.commit(v)}finally{d.close()}}""",args.opaque_mib)
            for cycle in range(args.restore_cycles):
                stats=page.evaluate("""async()=>{const d=await PushPullDB.open(()=>{});try{const text=await d.exportModelBackup(),source=JSON.parse(JSON.parse(text).payload.legacySources[0].raw);const stats={v3Bytes:new TextEncoder().encode(text).length,archives:source.archives.length,archiveChars:source.archives.reduce((n,a)=>n+(a.raw?.length||0),0)};await d.importModelBackup(text);return stats}finally{d.close()}}""")
                emit('synthetic-restore',cycle=cycle+1,**stats)
            context.close();context=launch(args.heap_mib);page=attach(context);stage='load';page.goto(url)
            expect(page.locator('[data-act=start]')).to_be_visible(timeout=30000)
            page.locator('[data-tab=settings]').click();page.get_by_text('Opcje zaawansowane Google',exact=True).click()
            page.locator('#driveConfig input').fill('123-test.apps.googleusercontent.com');page.locator('#driveConfig button').click()
            page.locator('[data-drive-action=connect]').click();expect(page.locator('[data-drive-action=connect]')).to_be_hidden()
            before=fingerprint(page);old_files={};stage='upload'
            try:
                for copy in range(args.copies):
                    started=time.monotonic()
                    page.locator('[data-drive-action=upload]').click()
                    page.wait_for_function('n=>globalThis.__done>=n||globalThis.__failed',arg=copy+1,timeout=120000)
                    if page.evaluate('globalThis.__failed'):raise RuntimeError('Upload was not verified')
                    expect(page.locator('[data-drive-status]')).to_contain_text('Kopia zapisana i zweryfikowana',timeout=120000)
                    assert len(DriveServer.files)==copy+1
                    for key,digest in old_files.items():assert hashlib.sha256(DriveServer.files[key]).hexdigest()==digest
                    old_files={key:hashlib.sha256(text).hexdigest() for key,text in DriveServer.files.items()}
                    emit('verified',copy=copy+1,seconds=round(time.monotonic()-started,3),nodeBytes=[len(text) for text in DriveServer.files.values()],v3Bytes=[len(json.loads(text)['backup'].encode()) for text in DriveServer.files.values()])
                outcome='verified'
            except Exception as error:
                outcome='not-verified';emit('operation-error',type=type(error).__name__)
            context.close()
            # Uncapped restart distinguishes a failed page/upload from lost local data.
            context=launch();page=attach(context);stage='recovery';page.goto(url)
            expect(page.locator('[data-act=start]')).to_be_visible(timeout=60000)
            unchanged=fingerprint(page)==before
            emit('summary',outcome=outcome,storedFiles=len(DriveServer.files),localUnchanged=unchanged)
            if not unchanged:outcome='local-state-changed'
            context.close()
    except Exception as error:
        outcome='probe-error';emit('probe-error',stage=stage,type=type(error).__name__)
    finally:
        server.shutdown();server.server_close();thread.join()
    return 0 if outcome=='verified' else 1


if __name__=='__main__':raise SystemExit(main())
