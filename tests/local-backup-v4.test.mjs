import test from 'node:test';
import assert from 'node:assert/strict';
import {exportLocalV4,previewLocalV4} from '../model/local-backup-v4.mjs';
import {readFile} from 'node:fs/promises';
import {decodeBackup,V4_LIMITS} from '../model/backup-v4.mjs';
const old=JSON.parse(await readFile(new URL('./fixtures/v1.json',import.meta.url)));
const {runInNewContext}=await import('node:vm');
const db=runInNewContext(await readFile('storage.js','utf8')+'\n'+await readFile('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
const source={format:'pushpull-backup',version:2,data:old,catalog:JSON.parse(JSON.stringify(db.parseBackup(old).catalog)),archives:[]};
const AT='2026-10-24T10:00:00.000Z';
test('local v4 adapter exports the complete detached snapshot and exposes summary only',async()=>{
 const before=structuredClone(source);
 const result=await exportLocalV4({export:()=>source,model:null},{createdAt:AT});
 assert.deepEqual(source,before);
 const stage=await decodeBackup(result.text);assert.deepEqual(stage.live.data,old);
 const preview=await previewLocalV4(new Blob([result.text]));
 assert.deepEqual(Object.keys(preview).sort(),['archives','summary']);
 assert.equal(preview.summary.sessions,old.sessions.length);assert.equal(preview.summary.createdAt,AT);
});
test('pre-journal model uses full existing v3 bridge; failed bridge never falls back to partial v2',async()=>{
 let calls=0;
 await assert.rejects(exportLocalV4({export:()=>source,model:{},exportModelBackup:async()=>{calls++;throw Error('bridge unavailable');}},{createdAt:AT}),/bridge unavailable/);
 assert.equal(calls,1);
});
test('preview rejects oversized input before reading and refuses legacy restore capability',async()=>{
 await assert.rejects(previewLocalV4({size:V4_LIMITS.fileBytes+1,text:()=>assert.fail('must not read')}),/limit/);
 await assert.rejects(previewLocalV4(new Blob([JSON.stringify(old)])),/v1\/v2\/v3/);
});
test('revision change during asynchronous export refuses download result',async()=>{
 const db={revision:1,export:()=>source,model:null};
 const pending=exportLocalV4(db,{createdAt:AT});db.revision++;
 await assert.rejects(pending,/zmieniła/);
});
test('local v5 refuses unrepresented legacy model metadata and preserves native snapshot',async()=>{
 const {exportLocalV5}=await import('../model/local-backup-v4.mjs');
 await assert.rejects(exportLocalV5({export:()=>source,model:{}},{createdAt:AT}),/bridge/);
 const result=await exportLocalV5({revision:1,export:()=>source,model:null},{createdAt:AT});
 const stage=await(await import('../model/backup-v5.mjs')).decodeBackup(result.text);
 assert.deepEqual(stage.live.data,source.data);assert.deepEqual(stage.archives,source.archives);
});
