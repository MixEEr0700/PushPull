import {test} from 'node:test';
import assert from 'node:assert/strict';
import {gzipSync} from 'node:zlib';
import {createHash,webcrypto} from 'node:crypto';
import {openCompactBackup} from '../model/compact-backup-reader.mjs';
globalThis.crypto??=webcrypto;
const hash=b=>createHash('sha256').update(b).digest('hex');
function fixture(values=['hello','世界'],gzip=false,edit=()=>{}){
 const raw=values.map(v=>Buffer.from(v)),stored=raw.map(b=>gzip?gzipSync(b):b);
 const m={format:'pushpull-compact',version:1,chunks:raw.map((b,i)=>({storedBytes:stored[i].length,decodedBytes:b.length,storedSha256:hash(stored[i]),decodedSha256:hash(b),compression:gzip?'gzip':'none'})),objects:[{id:'history',parts:raw.map((_,i)=>i),bytes:raw.reduce((n,b)=>n+b.length,0)}]};edit(m);
 const manifest=Buffer.from(JSON.stringify(m)),head=Buffer.alloc(40);head.write('PPC1');head.writeUInt32BE(manifest.length,4);Buffer.from(hash(manifest),'hex').copy(head,8);
 return new Blob([head,manifest,...stored]);
}
test('complete none/gzip fragmented Unicode and opaque bytes, frozen manifest',async()=>{
 for(const gzip of [false,true]){const r=await openCompactBackup(fixture(['a\0','世界','x'.repeat(2000000)],gzip));let size=0;for await(const b of r.readObject('history'))size+=b.length;assert.equal(size,2000008);assert.ok(Object.isFrozen(r.manifest.objects));}
});
test('corruption, missing/trailing payload and wrong manifest hash',async()=>{
 const f=fixture();await assert.rejects(openCompactBackup(f.slice(0,f.size-1)));await assert.rejects(openCompactBackup(new Blob([f,'x'])));
 const bytes=new Uint8Array(await f.arrayBuffer());bytes[bytes.length-1]^=1;await assert.rejects(openCompactBackup(new Blob([bytes])),/stored hash/);bytes[8]^=1;await assert.rejects(openCompactBackup(new Blob([bytes])),/manifest hash/);
});
test('rehashed malformed descriptors, references, duplicate ids, unused chunks',async()=>{
 for(const edit of [m=>m.objects[0].parts=[99],m=>m.objects.push(m.objects[0]),m=>m.objects[0].parts=[0],m=>m.chunks[0].decodedSha256='0'.repeat(64),m=>m.version=2,m=>m.chunks[0].extra=1])await assert.rejects(openCompactBackup(fixture(undefined,false,edit)));
});
test('decompression bomb and dishonest decoded length rejected',async()=>{
 await assert.rejects(openCompactBackup(fixture(['x'.repeat(2000000)],true,m=>{m.chunks[0].decodedBytes=1;m.objects[0].bytes=1;})),/decompression size/);
});
test('all resource overrides enforce lower-only limits; cancellation and timeout',async()=>{
 const f=fixture();for(const limits of [{fileBytes:40},{manifestBytes:1},{chunks:1},{chunkStoredBytes:1},{chunkDecodedBytes:1},{totalDecodedBytes:1},{depth:1},{tokens:1},{ms:0},{fileBytes:1e10}])await assert.rejects(openCompactBackup(f,{limits}));
 const c=new AbortController();c.abort();await assert.rejects(openCompactBackup(f,{signal:c.signal}),{name:'AbortError'});
 const r=await openCompactBackup(f,{signal:new AbortController().signal});await assert.rejects(async()=>{for await(const b of r.readObject('missing'))void b;});
});
test('deadline and abort also apply after validation, without exposing more chunks',async()=>{
 const controller=new AbortController(),r=await openCompactBackup(fixture(),{signal:controller.signal});controller.abort();
 await assert.rejects(async()=>{for await(const b of r.readObject('history'))void b;},{name:'AbortError'});
 const timed=await openCompactBackup(fixture(),{limits:{ms:100}});await new Promise(resolve=>setTimeout(resolve,120));
 await assert.rejects(async()=>{for await(const b of timed.readObject('history'))void b;},/time limit/);
});
