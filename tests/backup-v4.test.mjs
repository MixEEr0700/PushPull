import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {decodeBackup,V4_LIMITS} from '../model/backup-v4.mjs';
import {parseModelBackup} from '../model/legacy-model.mjs';
import {AT,hash,blob,seal,encodeFixture,archiveFixtures,nativeData,sourceV3} from './fixtures/backup-v4-fixture.mjs';
const v1=readFileSync('tests/fixtures/v1.json','utf8'),old=JSON.parse(v1);
const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
const v2={format:'pushpull-backup',version:2,data:old,catalog:JSON.parse(JSON.stringify(db.parseBackup(old).catalog)),archives:[]};
const v2text=JSON.stringify(v2),v3=await sourceV3(v2);
const data=nativeData(old,JSON.parse(readFileSync('tests/fixtures/plan-v3.json','utf8')));
const native={format:'pushpull-backup',version:2,data,catalog:JSON.parse(JSON.stringify(db.parseBackup(data).catalog)),archives:[]};
const nativeText=await sourceV3(native),archives=archiveFixtures(v1,v2text,v3);
const fixture=await encodeFixture(nativeText,archives);
const raw=JSON.stringify(fixture);
const decode=d=>decodeBackup(JSON.stringify(d));

test('v4 complete deterministic fixture roundtrip preserves all live data and archive code units',async()=>{
 assert.equal(JSON.stringify(await encodeFixture(nativeText,archives)),raw);
 const staged=await decodeBackup(raw);
 assert.deepEqual(staged.live.data,data);assert.deepEqual(staged.live.catalog,native.catalog);
 assert.equal(staged.live.raw,nativeText);assert.deepEqual(staged.archives,archives);
 assert.equal(staged.live.data.trainingJournal.activePlanVersionId,'synthetic-v3');
 assert.equal(staged.live.data.trainingJournal.sessionSnapshots.length,6);
 assert.ok(staged.live.data.entries.some(e=>e.performance?.rows.some(r=>r.side==='left')));
 assert.ok(staged.live.data.entries.some(e=>e.performance?.rows.some(r=>r.segments.length>1)));
 assert.ok(staged.live.data.entries.some(e=>e.performance?.rows.some(r=>r.groupId)));
 assert.ok(staged.live.data.trainingJournal.model.sets.some(s=>s.role==='backoff'));
 assert.deepEqual(staged.live.data.changes,data.changes);
 assert.equal(staged.archives[8].raw,'Ł😀\u0000\ud800X\udfff');
 assert.notEqual(staged.archives[9].id,staged.archives[10].id);
 assert.equal(fixture.archives[9].blobId,fixture.archives[10].blobId);
 assert.equal(Object.isFrozen(staged.archives[0]),true);
 assert.equal(Object.isFrozen(staged.live.data.trainingJournal),true);
 // Roundtrip entirely inside the synthetic harness; never an IndexedDB commit.
 const again=await encodeFixture(staged.live.raw,staged.archives);
 assert.equal(JSON.stringify(again),raw);
});

test('old v1/v2/source-backed v3 still decode without rewriting their original text or archives',async()=>{
 const withArchives={...v2,archives},old3=await sourceV3(withArchives);
 for(const text of [v1,JSON.stringify(withArchives,null,2),old3]){
  const stage=await decodeBackup(text);assert.equal(stage.live.raw,text);
  assert.deepEqual(stage.live.data,old);
  assert.deepEqual(stage.archives,JSON.parse(text).version===1?[]:archives);
 }
 for(const text of [v1,v2text,v3]){
  const stage=await decode(await encodeFixture(text,archives,'none'));
  assert.equal(stage.live.raw,text);assert.deepEqual(stage.archives,archives);
 }
 await assert.rejects(decode(await encodeFixture(old3,archives)),/embedded archives/);
 // The old parser still rejects v4 cleanly; no changes to old production paths.
 await assert.rejects(parseModelBackup(raw),/Nieobsługiwana wersja/);
});

test('v4 rejects missing/extra references, duplicate IDs, unsupported schemas and contradictory live metadata',async()=>{
 const changes=[d=>d.blobs.pop(),d=>d.blobs.push(d.blobs[0]),d=>d.archives.push(d.archives[0]),
  d=>d.live.blobId='https://example.invalid/external',d=>d.archives[0].blobId='missing',
  d=>d.live.formatVersion=1,d=>d.version=5,d=>d.format='other',d=>d.future='unrecognized',
  d=>d.blobs[0].compression='zip',d=>d.blobs[0].encoding='utf-16',d=>d.blobs[0].id='other',
  d=>d.archives[0].metadata.raw='shadow',d=>d.archives[0].metadata.createdAt='unknown',
  d=>d.blobs.push({...d.blobs[0],id:'sha256:'+'0'.repeat(64),decodedSha256:'0'.repeat(64)})];
 for(const mutate of changes){const d=structuredClone(fixture);mutate(d);await seal(d);await assert.rejects(decode(d));}
});

test('manifest, stored and decoded checksums reject independently re-signed corruptions',async()=>{
 let d=structuredClone(fixture);d.archives[0].metadata.extension.order=999;
 await assert.rejects(decode(d),/manifest checksum/);
 d=structuredClone(fixture);d.blobs[0].storedSha256='0'.repeat(64);await seal(d);
 await assert.rejects(decode(d),/stored checksum/);
 d=structuredClone(fixture);const first=d.blobs[0],previous=first.id;
 first.decodedSha256='0'.repeat(64);first.id='sha256:'+first.decodedSha256;
 d.live.blobId=first.id;for(const a of d.archives)if(a.blobId===previous)a.blobId=first.id;
 await seal(d);await assert.rejects(decode(d),/decoded checksum/);
 d=structuredClone(fixture);const bytes=Uint8Array.from(atob(d.blobs[0].data),c=>c.charCodeAt(0));
 bytes[bytes.length-5]^=1;d.blobs[0].data=btoa(String.fromCharCode(...bytes));d.blobs[0].storedSha256=await hash(bytes);await seal(d);
 await assert.rejects(decode(d)); // Real decompressor detects damaged gzip/CRC.
});

test('truncation, invalid base64, gzip bombs and falsely declared sizes never return staging',async()=>{
 for(const text of [raw.slice(0,-1),raw.slice(0,raw.length/2),'{"version":4,"version":4}'])await assert.rejects(decodeBackup(text));
 for(const mutate of [d=>d.blobs[0].data=d.blobs[0].data.slice(0,-4),d=>d.blobs[0].data='!'+d.blobs[0].data.slice(1),d=>d.blobs[0].decodedBytes++,d=>d.blobs[0].storedBytes++]){
  const d=structuredClone(fixture);mutate(d);await seal(d);await assert.rejects(decode(d));
 }
 const b=await blob('x'.repeat(2*1024*1024));b.decodedBytes=256;
 const d=await encodeFixture(v1,[{id:'bomb',kind:'opaque',createdAt:AT,raw:'unused'}]);
 d.blobs[1]=b;d.archives[0].blobId=b.id;await seal(d);
 await assert.rejects(decode(d),/decompression size limit/);
});

test('hard limits reject aggregate/count/depth/token/numeric abuse and cannot be raised',async()=>{
 for(const limits of [{fileBytes:100},{storedBlobBytes:1},{decodedBlobBytes:100},{totalDecodedBytes:1000},{blobs:1},{archives:1},{depth:2},{tokens:10}])await assert.rejects(decodeBackup(raw,{limits}));
 for(const limits of [{fileBytes:V4_LIMITS.fileBytes+1},{fileBytes:0},{typo:1}])await assert.rejects(decodeBackup(raw,{limits}));
 await assert.rejects(decodeBackup('['.repeat(65)+'0'+']'.repeat(65)),/nesting/);
 await assert.rejects(decodeBackup('{"n":1e'+'1'.repeat(130)+'}'),/numeric/);
 await assert.rejects(decodeBackup('{"n":9007199254740993}'),/losslessly/);
 await assert.rejects(decodeBackup('[null,true,false,null]',{limits:{tokens:4}}),/token limit/);
});

test('unknown archive metadata is preserved as data without prototype pollution',async()=>{
 const rows=structuredClone(archives);
 rows[0].extension=JSON.parse('{"__proto__":{"polluted":true},"constructor":{"x":1},"unknown":[null,false]}');
 const stage=await decode(await encodeFixture(v1,rows));
 assert.deepEqual(stage.archives,rows);assert.equal({}.polluted,undefined);
 assert.equal(Object.hasOwn(stage.archives[0].extension,'__proto__'),true);
});

test('nested historical preimages are preserved opaque, not flattened or reinterpreted',async()=>{
 let previous=v3;
 for(let i=0;i<3;i++)previous=await sourceV3({...v2,archives:[{id:'nested-'+i,kind:'before-import',createdAt:AT,raw:previous}]});
 const rows=[{id:'historical-preimage',kind:'before-import',createdAt:AT,raw:previous}];
 const staged=await decode(await encodeFixture(v1,rows));
 assert.equal(staged.archives[0].raw,previous);
 const oldSource=await parseModelBackup(staged.archives[0].raw);
 assert.equal(oldSource.archives[0].id,'nested-2');assert.deepEqual(oldSource.data,old);
});

test('invalid UTF-8 and non-string/noncanonical blob encodings are rejected',async()=>{
 for(const bytes of [Uint8Array.of(0xc0,0xaf),new TextEncoder().encode('null'),new TextEncoder().encode(' "text" ')]){
  const d=await encodeFixture(v1),b=d.blobs[0],digest=await hash(bytes);
  Object.assign(b,{id:'sha256:'+digest,compression:'none',storedBytes:bytes.length,decodedBytes:bytes.length,storedSha256:digest,decodedSha256:digest,data:btoa(String.fromCharCode(...bytes))});
  d.live.blobId=b.id;await seal(d);await assert.rejects(decode(d));
 }
 const d=await encodeFixture(v1,[{id:'padding',kind:'opaque',createdAt:AT,raw:'xx'}],'none');
 assert.equal(d.blobs[1].data,'Inh4Ig==');
 d.blobs[1].data='Inh4Ih=='; // Same decoded bytes, forbidden nonzero padding bits.
 await assert.rejects(decode(d),/noncanonical base64/);
});

test('failed or cancelled decoding cannot expose partial state or modify previous staging/input',async()=>{
 const previous=await decodeBackup(raw),before=JSON.stringify(previous),bad=structuredClone(fixture);
 bad.blobs.at(-1).storedSha256='0'.repeat(64);await seal(bad);
 await assert.rejects(decode(bad));assert.equal(JSON.stringify(previous),before);assert.equal(JSON.stringify(fixture),raw);
 const controller=new AbortController();controller.abort();await assert.rejects(decodeBackup(raw,{signal:controller.signal}),{name:'AbortError'});
 const during=new AbortController(),pending=decodeBackup(raw,{signal:during.signal});queueMicrotask(()=>during.abort());
 await assert.rejects(pending,{name:'AbortError'});assert.equal(JSON.stringify(previous),before);
});
