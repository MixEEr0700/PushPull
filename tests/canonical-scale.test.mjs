import {test} from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {canonicalFixture} from './canonical-fixture.mjs';import {createCanonicalBackup,writeCanonicalBackup,readCanonicalBackup} from '../model/canonical-backup.mjs';import {parseCanonicalJSON,CANONICAL_PARSE_BUDGET} from '../model/canonical-json-parser.mjs';import {boundedBackupJson} from '../model/backup-v4.mjs';import {COMPACT_LIMITS} from '../model/compact-backup-reader.mjs';
const old=JSON.parse(readFileSync('tests/fixtures/v1.json'));
test('4000-session reproduction: metadata parser refuses token count but document budget accepts exact payload',async()=>{const f=canonicalFixture(old,4000);f.preferences.snapshots=Array.from({length:4000},(_,i)=>({text:'Snapshot instruction '.repeat(20),version:i}));const c=createCanonicalBackup(f),text=JSON.stringify(c);assert.throws(()=>boundedBackupJson(text,COMPACT_LIMITS,COMPACT_LIMITS.totalDecodedBytes),/token limit/);assert.deepStrictEqual(await readCanonicalBackup(await writeCanonicalBackup(c)),c);});
test('small to large histories and repeated/unique snapshots roundtrip',async()=>{for(const n of [0,4,40,400,6000])for(const unique of [false,true]){const f=canonicalFixture(old,n);f.preferences.snapshots=Array.from({length:n},(_,i)=>({text:'Instructions'.repeat(10),version:unique?i:1}));const c=createCanonicalBackup(f);assert.deepStrictEqual(await readCanonicalBackup(await writeCanonicalBackup(c)),c);}});
test('preflight rejects dense JSON bomb, depth, oversized declaration, corruption and cancellation',async()=>{const bounds=COMPACT_LIMITS;
 const dense='['+'0,'.repeat(1100000)+'0]';assert.throws(()=>parseCanonicalJSON(dense,Buffer.byteLength(dense),bounds),/memory budget/);
 assert.throws(()=>parseCanonicalJSON('[]',CANONICAL_PARSE_BUDGET,bounds),/memory budget/);
 assert.throws(()=>parseCanonicalJSON('['.repeat(40)+'0'+']'.repeat(40),81,bounds),/nesting/);
 assert.throws(()=>parseCanonicalJSON('{"a":1,"a":2}',13,bounds),/duplicate/);
 assert.throws(()=>parseCanonicalJSON('[1e999]',7,bounds));
 const a=new AbortController();a.abort();assert.throws(()=>parseCanonicalJSON('{}',2,bounds,a.signal),{name:'AbortError'});
 const c=createCanonicalBackup(canonicalFixture(old,4)),f=await writeCanonicalBackup(c),bytes=new Uint8Array(await f.arrayBuffer());bytes[bytes.length-1]^=1;await assert.rejects(readCanonicalBackup(new Blob([bytes])));await assert.rejects(readCanonicalBackup(f.slice(0,-1)));await assert.rejects(readCanonicalBackup(f,{limits:{totalDecodedBytes:1}}));
});
async function forged(text,declared){
 const bytes=new TextEncoder().encode(text),stored=new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
 const sha=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b)),x=>x.toString(16).padStart(2,'0')).join('');
 const size=declared??bytes.length,manifest=new TextEncoder().encode(JSON.stringify({format:'pushpull-compact',version:1,chunks:[{storedBytes:stored.length,decodedBytes:size,storedSha256:await sha(stored),decodedSha256:await sha(bytes),compression:'gzip'}],objects:[{id:'canonical-json-v1',parts:[0],bytes:size}]}));
 const head=new Uint8Array(40);head.set([80,80,67,49]);new DataView(head.buffer).setUint32(4,manifest.length);head.set(Uint8Array.from((await sha(manifest)).match(/../g),x=>parseInt(x,16)),8);return new Blob([head,manifest,stored]);
}
test('valid hashes do not bypass dense allocation budget or inflate bound',async()=>{
 const dense='['+'0,'.repeat(1100000)+'0]';await assert.rejects(readCanonicalBackup(await forged(dense)),/parse memory budget/);
 await assert.rejects(readCanonicalBackup(await forged(dense,32)),/decompression size/);
});
test('existing deeper graph-compatible models keep nesting fallback',async()=>{const f=canonicalFixture(old,4);let value={leaf:'retained'};for(let i=0;i<35;i++)value={child:value};f.preferences.deep=value;const c=createCanonicalBackup(f);assert.deepStrictEqual(await readCanonicalBackup(await writeCanonicalBackup(c)),c);});
