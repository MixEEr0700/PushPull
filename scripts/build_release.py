"""Build an allowlisted static artifact. Does not publish, upload or change data."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
ASSETS=(
    'index.html','style.css','app.js','storage.js','indexeddb.js',
    'model/training-model.mjs','model/backup.mjs','model/backup-json.mjs',
    'model/legacy-backup.mjs','model/legacy-model.mjs',
    'manifest.webmanifest','icon.svg','icons/icon-192.png','icons/icon-512.png','icons/icon-maskable-512.png',
)
FILES=(*ASSETS,'sw.js','release.json')

def sha(data):return hashlib.sha256(data).hexdigest()

def generate(root=ROOT):
    root=Path(root).resolve()
    files={}
    for name in ASSETS:
        path=root/name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('Missing or unsafe runtime asset: '+name)
        files[name]=path.read_bytes()
    template=(root/'scripts/service-worker.template.js').read_text()
    precache=[{'path':name,'sha256':sha(files[name])} for name in ASSETS]
    release=sha((template+json.dumps(precache,sort_keys=True)).encode())[:24]
    worker=template.replace('__RELEASE__',release).replace('__PRECACHE__',json.dumps(precache,indent=2))
    files['sw.js']=worker.encode()
    metadata={'format':'pushpull-static-release','version':1,'release':release,'files':{name:sha(body) for name,body in sorted(files.items())}}
    files['release.json']=(json.dumps(metadata,indent=2)+'\n').encode()
    return files

def build(output,root=ROOT):
    if Path(output).is_symlink():raise ValueError('Output must not be a symlink')
    output=Path(output).resolve()
    root=Path(root).resolve()
    if output==root or root.is_relative_to(output):raise ValueError('Output must not contain the checkout')
    files=generate(root)
    # Refuse to overwrite unknown files, including accidentally saved JSON backups.
    if output.exists():
        actual={str(p.relative_to(output)) for p in output.rglob('*') if p.is_file() or p.is_symlink()}
        if actual-set(FILES):raise ValueError('Output contains files outside the runtime allowlist')
        if any(p.is_symlink() for p in output.rglob('*')):raise ValueError('Symlink in output')
        if any((output/name).read_bytes()!=files[name] for name in actual):raise ValueError('Existing release is immutable; build into a new empty output directory')
    output.mkdir(parents=True,exist_ok=True)
    for name,body in files.items():
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    return json.loads(files['release.json'])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--refresh-worker',action='store_true')
    group.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    args=parser.parse_args()
    generated=generate()
    if args.refresh_worker:
        (ROOT/'sw.js').write_bytes(generated['sw.js'])
        print('Refreshed sw.js; no deployment performed')
    elif args.check:
        if (ROOT/'sw.js').read_bytes()!=generated['sw.js']:raise ValueError('Stale sw.js: run python3 scripts/build_release.py --refresh-worker')
        print('Worker and runtime asset hashes match')
    else:
        result=build(args.output)
        print('Built static release '+result['release']+' in '+str(args.output)+'; no deployment performed')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as error:print(str(error),file=sys.stderr);sys.exit(1)
