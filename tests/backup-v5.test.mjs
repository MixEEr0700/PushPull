import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {exportBackupV5,decodeBackup} from '../model/backup-v5.mjs';
import {exportBackupV4} from '../model/backup-v4-export.mjs';
const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
const data=JSON.parse(readFileSync('tests/fixtures/v1.json'));
const snapshot={format:'pushpull-backup',version:2,data,catalog:JSON.parse(JSON.stringify(db.parseBackup(data).catalog)),archives:[]};
const options={createdAt:'2026-10-24T00:00:00.000Z'};
test('v5 large archive above v4 single blob limit, metadata/null/empty/lone surrogates preserved',async()=>{
 const raw='x'.repeat(65*1024*1024)+'\ud800\0😀';
 const source={...snapshot,archives:[{id:'a',kind:'before-import',createdAt:options.createdAt,extra:{retained:true},raw},{id:'b',kind:'opaque',createdAt:options.createdAt,raw:null},{id:'c',kind:'opaque',createdAt:options.createdAt,raw:''}]};
 const result=await exportBackupV5(source,options),stage=await decodeBackup(result.text);
 assert.deepEqual(stage.archives,source.archives);assert.deepEqual(stage.live.data,source.data);
 console.log(JSON.stringify(result.diagnostics));
 await assert.rejects(decodeBackup(result.text.slice(0,-1)));
 const corrupt=JSON.parse(result.text);corrupt.archives[0].parts.reverse();await assert.rejects(decodeBackup(JSON.stringify(corrupt)),/checksum/);
});
test('abort, logical expansion budget and old v4 reader compatibility',async()=>{
 const source={...snapshot,archives:[{id:'a',kind:'opaque',createdAt:options.createdAt,raw:'x'.repeat(1024)}]};
 const controller=new AbortController();controller.abort();await assert.rejects(exportBackupV5(source,{...options,signal:controller.signal}),{name:'AbortError'});
 await assert.rejects(exportBackupV5(source,{...options,limits:{totalDecodedBytes:100}}),/limit/);
 const old=await exportBackupV4(snapshot,options);assert.equal((await decodeBackup(old.text)).formatVersion,4);
 assert.equal((await decodeBackup(JSON.stringify(data))).formatVersion,1);
});
test('v4 size diagnostics distinguish live, opaque and preimage without contents or IDs',async()=>{
 for(const kind of ['live','opaque','before-import']){
  const source=structuredClone(snapshot),value='x'.repeat(40000);
  if(kind==='live')source.data.syntheticOpaque=value;
  else source.archives=[{id:'private-id-must-not-leak',kind,createdAt:options.createdAt,raw:value}];
  await assert.rejects(exportBackupV4(source,{...options,limits:{decodedBlobBytes:32768}}),e=>e.message.includes(kind==='live'?'stage=live':kind==='opaque'?'stage=opaque':'stage=preimage')&&!e.message.includes('private-id'));
 }
});
test('rehashed invalid references, missing fragments and mid-operation abort are rejected',async()=>{
 const source={...snapshot,archives:[{id:'a',kind:'opaque',createdAt:options.createdAt,raw:'x'.repeat(300000)}]};
 const out=await exportBackupV5(source,options);
 const {canonical}=await import('../model/backup-json.mjs');
 const rehash=async d=>{d.integrity={algorithm:'SHA-256'};d.integrity.digest=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(d)))).toString('hex');return JSON.stringify(d)};
 for(const alter of [d=>d.archives[0].parts.reverse(),d=>d.archives[0].parts.pop(),d=>d.payload.blobs.pop()]){
  const d=JSON.parse(out.text);alter(d);await assert.rejects(decodeBackup(await rehash(d)));
 }
 const controller=new AbortController(),pending=exportBackupV5(source,{...options,signal:controller.signal});controller.abort();await assert.rejects(pending,{name:'AbortError'});
});
