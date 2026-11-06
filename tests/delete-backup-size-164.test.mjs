import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';import {runInNewContext} from 'node:vm';
import {createProtocol,objectRecord,LIMITS,validateAllocation} from '../model/journal-protocol.mjs';
test('encoded object limit is applied after JSON escaping, without lifting production limits',async()=>{
 assert.equal(LIMITS.objectBytes,134217728);assert.equal(LIMITS.totalBytes,536870912);
 const raw='"\\'.repeat(300),cap=1024;assert.ok(raw.length<cap);assert.ok(JSON.stringify({raw}).length>cap);
 await assert.rejects(objectRecord({raw},{...LIMITS,objectBytes:cap}),/protocol JSON size/);
 const plain=await objectRecord({raw:'x'.repeat(600)},{...LIMITS,objectBytes:cap});assert.ok(plain.bytes<cap);
});
test('checkpoint budget can raise the same message before any source record is built',async()=>{
 const data=JSON.parse(readFileSync('tests/fixtures/v1.json'));const storage=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{crypto,structuredClone});const source={format:'pushpull-backup',version:2,data,catalog:structuredClone(storage.parseBackup(data).catalog),archives:[]};
 await assert.rejects(createProtocol(source,{limits:{objectBytes:512,totalBytes:1024,records:1000},checkpoints:[{id:'synthetic',protocol:2,raw:'x'.repeat(1025)}]}),/protocol JSON size/);
 assert.throws(()=>validateAllocation({bytes:1025,records:1,maxObjectBytes:1},{...LIMITS,totalBytes:1024}),/retained size\/count limit/);
});
