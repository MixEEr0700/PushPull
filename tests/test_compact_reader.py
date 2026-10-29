"""Transport-only reader, synthetic bytes; no access to user storage."""
from test_browser import BrowserHarness
import base64,gzip,hashlib,json,struct,shutil

class CompactReader(BrowserHarness):
    def test_offline_bounded_reader_and_corruption(self):
        raw=('synthetic 世界\0'*100000).encode()
        stored=gzip.compress(raw)
        digest=lambda b:hashlib.sha256(b).hexdigest()
        manifest=json.dumps(dict(format='pushpull-compact',version=1,chunks=[dict(storedBytes=len(stored),decodedBytes=len(raw),storedSha256=digest(stored),decodedSha256=digest(raw),compression='gzip')],objects=[dict(id='history',parts=[0],bytes=len(raw))])).encode()
        data=b'PPC1'+struct.pack('>I',len(manifest))+hashlib.sha256(manifest).digest()+manifest+stored
        browser=self.pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--js-flags=--max-old-space-size=64'])
        context=browser.new_context(viewport={'width':390,'height':844})
        try:
            page=context.new_page();page.goto(self.url)
            page.evaluate("async()=>window.reader=await import('./model/compact-backup-reader.mjs')")
            context.set_offline(True)
            result=page.evaluate("""async encoded=>{
             const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0)),file=new Blob([bytes]);
             const r=await reader.openCompactBackup(file);let size=0;for await(const b of r.readObject('history'))size+=b.length;
             let corrupt=false,bomb=false,cancel=false;
             try{await reader.openCompactBackup(file.slice(0,-1))}catch{corrupt=true}
             try{await reader.openCompactBackup(file,{limits:{chunkDecodedBytes:100}})}catch{bomb=true}
             const c=new AbortController();c.abort();try{await reader.openCompactBackup(file,{signal:c.signal})}catch(e){cancel=e.name==='AbortError'}
             return {size,corrupt,bomb,cancel};
            }""",base64.b64encode(data).decode())
            self.assertEqual(result,dict(size=len(raw),corrupt=True,bomb=True,cancel=True))
        finally:context.close();browser.close()
