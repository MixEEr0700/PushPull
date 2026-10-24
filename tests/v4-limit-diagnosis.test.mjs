import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {probe} from './v4-limit-probe.mjs';
const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
const data=JSON.parse(readFileSync('tests/fixtures/v1.json'));
const snapshot={format:'pushpull-backup',version:2,data,catalog:JSON.parse(JSON.stringify(db.parseBackup(data).catalog)),archives:[]};
test('actual 64 MiB single-string limit independently rejects live and opaque archive without mutation',async()=>{
 const result=await probe(snapshot);assert.equal(result.length,3);console.log(JSON.stringify(result));
});
