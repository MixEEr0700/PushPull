"""Loopback-only, read-only server for a verified PushPull static artifact.
Use a separately approved private HTTPS reverse proxy; never serve the checkout.
"""
import argparse
import functools
import hashlib
import http.server
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
from build_release import ASSETS, FILES, ROOT

CSP="default-src 'self'; script-src 'self' https://accounts.google.com/gsi/; style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style; img-src 'self' data: blob:; connect-src 'self' https://www.googleapis.com https://accounts.google.com/gsi/; frame-src https://accounts.google.com; manifest-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
TYPES={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.webmanifest':'application/manifest+json','.svg':'image/svg+xml','.png':'image/png','.json':'application/json; charset=utf-8'}

def verify_release(directory):
    directory=Path(directory).resolve()
    metadata=json.loads((directory/'release.json').read_text())
    if metadata.get('format')!='pushpull-static-release' or metadata.get('version')!=1:raise ValueError('Not a PushPull static release')
    if set(metadata.get('files',{}))!=set(FILES)-{'release.json'}:raise ValueError('Unexpected release assets')
    actual={str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=set(FILES):raise ValueError('Only the allowlisted runtime artifact may be served')
    for name,expected in metadata['files'].items():
        path=directory/name
        if path.is_symlink() or not path.resolve().is_relative_to(directory):raise ValueError('Unsafe release path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Release integrity mismatch: '+name)
    return directory

class ReleaseHandler(http.server.BaseHTTPRequestHandler):
    server_version='PushPullTest/1'
    sys_version=''
    def __init__(self,*args,directory,base_path='/',**kwargs):
        self.directory=Path(directory)
        self.base_path=base_path
        super().__init__(*args,**kwargs)
    def log_message(self,*args):pass
    def end_headers(self):
        self.send_header('Cache-Control','no-cache, must-revalidate')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',CSP)
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Strict-Transport-Security','max-age=31536000')
        super().end_headers()
    def do_GET(self):self.serve_body(True)
    def do_HEAD(self):self.serve_body(False)
    def do_POST(self):self.send_error(405)
    def serve_body(self,body):
        path=unquote(urlsplit(self.path).path)
        if not path.startswith(self.base_path):self.send_error(404);return
        name=path[len(self.base_path):] or 'index.html'
        if name not in FILES:self.send_error(404);return
        file=self.directory/name
        if file.is_symlink() or not file.is_file():self.send_error(404);return
        content=file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type',TYPES[file.suffix])
        self.send_header('Content-Length',str(len(content)))
        self.end_headers()
        if body:self.wfile.write(content)

def make_server(directory,port=8000,base_path='/'):
    directory=verify_release(directory)
    if not base_path.startswith('/') or not base_path.endswith('/') or '..' in base_path or '%' in base_path:raise ValueError('Base path must be / or /path/')
    handler=functools.partial(ReleaseHandler,directory=directory,base_path=base_path)
    return http.server.ThreadingHTTPServer(('127.0.0.1',port),handler)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'dist')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--base-path',default='/')
    args=parser.parse_args()
    server=make_server(args.directory,args.port,args.base_path)
    print('Verified static release; listening on loopback only. No HTTPS/public hosting activated.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as error:print(str(error),file=sys.stderr);sys.exit(1)
