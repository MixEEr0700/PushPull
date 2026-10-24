import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {exportBackupV5,decodeBackup} from '../model/backup-v5.mjs';
import {previewBackupV5,createTrialDatabase} from '../model/backup-v5-preview.mjs';
import {nativeData,archiveFixtures,sourceV3,AT} from './fixtures/backup-v4-fixture.mjs';
import {canonical} from '../model/backup-json.mjs';
const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
const old=JSON.parse(readFileSync('tests/fixtures/v1.json'));
const data=nativeData(old,JSON.parse(readFileSync('tests/fixtures/plan-v3.json')));
const v2={format:'pushpull-backup',version:2,data:old,catalog:JSON.parse(JSON.stringify(db.parseBackup(old).catalog)),archives:[]};
const source={format:'pushpull-backup',version:2,data,catalog:JSON.parse(JSON.stringify(db.parseBackup(data).catalog)),archives:archiveFixtures(JSON.stringify(old),JSON.stringify(v2),await sourceV3(v2))};
const out=await exportBackupV5(source,{createdAt:AT}),file=new Blob([out.text]);
test('native plans/active version/snapshots/series/archives survive full memory database roundtrip',async()=>{
 const stage=await decodeBackup(out.text),trial=createTrialDatabase();
 await trial.restore(stage);assert.deepEqual(trial.read(),stage);
 assert.deepEqual(trial.read().live.data,source.data);assert.deepEqual(trial.read().live.catalog,source.catalog);assert.deepEqual(trial.read().archives,source.archives);
 const report=await previewBackupV5(file);assert.equal(report.sessions,source.data.sessions.length);assert.equal(report.archives,source.archives.length);
 assert.equal(report.draftsIncluded,false);assert.equal(report.trialEqual,true);assert.equal(report.activeVersion,true);
 assert.equal('raw' in report,false);trial.clear();assert.equal(trial.read(),null);
});
test('memory transaction rollback on abort and revision conflict keeps previous full database',async()=>{
 const stage=await decodeBackup(out.text),trial=createTrialDatabase();await trial.restore(stage);
 const before=trial.read(),revision=trial.revision,controller=new AbortController();
 const pending=trial.restore(stage,{signal:controller.signal});controller.abort();await assert.rejects(pending,{name:'AbortError'});
 assert.deepEqual(trial.read(),before);assert.equal(trial.revision,revision);
 await assert.rejects(trial.restore(stage,{expectedRevision:revision-1}),/Zmieniono/);assert.deepEqual(trial.read(),before);
});
test('preview rejects file size before reading, corruption, truncation and changed current revision',async()=>{
 await assert.rejects(previewBackupV5({size:33*1024*1024,text:()=>assert.fail()}),/limit/);
 await assert.rejects(previewBackupV5(new Blob([out.text.slice(0,-1)])));
 const corrupt=JSON.parse(out.text);corrupt.archives.reverse();await assert.rejects(previewBackupV5(new Blob([JSON.stringify(corrupt)])),/checksum/);
 let revision=1;const pending=previewBackupV5({size:file.size,text:async()=>{revision++;return out.text;}},{getRevision:()=>revision});await assert.rejects(pending,/zmieniła/);
 const controller=new AbortController();controller.abort();await assert.rejects(previewBackupV5(file,{signal:controller.signal}),{name:'AbortError'});
 await assert.rejects(previewBackupV5(file,{limits:{totalDecodedBytes:100}}),/limit/);
});
test('65 MiB archive restores exactly without canonicalizing or displaying raw',async()=>{
 const raw='x'.repeat(65*1024*1024)+'\ud800';
 const snapshot={...v2,archives:[{id:'big',kind:'recovery',createdAt:AT,raw,extra:{retained:true}}]};
 const big=await exportBackupV5(snapshot,{createdAt:AT}),stage=await decodeBackup(big.text),trial=createTrialDatabase();
 await trial.restore(stage);assert.equal(trial.read().archives[0].raw,raw);
 assert.equal((await previewBackupV5(new Blob([big.text]))).archives,1);trial.clear();
});
test('decompression size mismatch remains rejected even after both manifests are rehashed',async()=>{
 const d=JSON.parse(out.text),b=d.payload.blobs[0];b.decodedBytes=1;
 const hash=async v=>Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(v)))).toString('hex');
 d.payload.integrity={algorithm:'SHA-256'};d.payload.integrity.digest=await hash({...d.payload,blobs:d.payload.blobs.map(({data,...x})=>x)});
 d.integrity={algorithm:'SHA-256'};d.integrity.digest=await hash(d);
 await assert.rejects(previewBackupV5(new Blob([JSON.stringify(d)])));
});
test('parser messages never disclose invalid JSON text',async()=>{
 await assert.rejects(previewBackupV5(new Blob(['private-secret-not-json'])),e=>!e.message.includes('private-secret')&&e.message.includes('Nieprawidłowa'));
});
