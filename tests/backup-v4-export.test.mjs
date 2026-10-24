import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {exportBackupV4} from '../model/backup-v4-export.mjs';
import {decodeBackup,V4_LIMITS} from '../model/backup-v4.mjs';
import {AT,nativeData,sourceV3,archiveFixtures} from './fixtures/backup-v4-fixture.mjs';
const oldText=readFileSync('tests/fixtures/v1.json','utf8'),old=JSON.parse(oldText);
const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
const catalog=data=>JSON.parse(JSON.stringify(db.parseBackup(data).catalog));
const simple={format:'pushpull-backup',version:2,data:old,catalog:catalog(old),archives:[],extension:{unknown:[null,false,'Ł']}};
const simple3=await sourceV3(simple);
const native=nativeData(old,JSON.parse(readFileSync('tests/fixtures/plan-v3.json','utf8')));
const snapshot={format:'pushpull-backup',version:2,data:native,catalog:catalog(native),archives:archiveFixtures(oldText,JSON.stringify(simple),simple3),extension:{retained:true}};
const options={createdAt:AT,metadata:{origin:'synthetic-only',extension:{unknown:'Ł😀'}}};

test('B1 full snapshot export self-verifies every native record, plan, snapshot and archive without mutation',async()=>{
 const before=structuredClone(snapshot),out=await exportBackupV4(snapshot,options),stage=await decodeBackup(out.text);
 assert.deepEqual(snapshot,before);assert.deepEqual(stage.live.data,native);assert.deepEqual(stage.live.catalog,snapshot.catalog);assert.deepEqual(stage.archives,snapshot.archives);
 assert.equal(stage.live.formatVersion,3);assert.equal(stage.live.data.trainingJournal.activePlanVersionId,'synthetic-v3');
 assert.deepEqual(JSON.parse(stage.live.document.payload.legacySources[0].raw).extension,snapshot.extension);
 assert.equal(JSON.parse(stage.live.document.payload.legacySources[0].raw).archives.length,0);
 assert.equal(stage.live.data.trainingJournal.sessionSnapshots.length,6);
 assert.equal(out.diagnostics.fileBytes,new TextEncoder().encode(out.text).length);
 assert.equal(out.diagnostics.archiveRecords,snapshot.archives.length);
 assert.ok(out.diagnostics.deduplicatedArchiveRecords>=1);assert.equal(out.diagnostics.nullArchives,1);
 assert.ok(JSON.parse(out.text).blobs.every(b=>b.compression==='gzip'));
 assert.equal(Object.isFrozen(out.diagnostics),true);
 for(const [key,value] of Object.entries(out.diagnostics))assert.equal(typeof value,'number',key);
});

test('B1 existing v1/v2/v3 and repeated v4 exports keep all metadata and never archive previous output',async()=>{
 const v2={...simple,archives:snapshot.archives},v3=await sourceV3(v2);
 for(const text of [oldText,JSON.stringify(v2),v3]){
  const original=await decodeBackup(text),out=await exportBackupV4(text,options),stage=await decodeBackup(out.text);
  assert.deepEqual(stage.live.data,original.live.data);assert.deepEqual(stage.live.catalog,original.live.catalog);assert.deepEqual(stage.archives,original.archives);
  if(original.live.formatVersion===3){
   assert.deepEqual(stage.live.document.payload.model,original.live.document.payload.model);
   assert.deepEqual(stage.live.document.metadata,original.live.document.metadata);
   assert.equal(stage.live.document.createdAt,original.live.document.createdAt);
  }
 }
 let out=await exportBackupV4(snapshot,options);const first=out.text;
 for(let i=0;i<4;i++){
  out=await exportBackupV4(out.text,{createdAt:AT});assert.equal(out.text,first);
  assert.equal(out.diagnostics.archiveRecords,snapshot.archives.length);
 }
 await assert.rejects(exportBackupV4(first,{createdAt:AT,metadata:{overwrite:true}}),/preserve existing/);
});

test('B1 bounded token encoding preserves surrogate pairs across chunk boundaries and every escape',async()=>{
 const raws=['x'.repeat(32767)+'😀'+String.fromCharCode(0xd800)+'X'+String.fromCharCode(0xdfff),
  '\\"\b\t\n\f\r\u0000\u001f\u2028\u2029Ł😀'.repeat(4000),'',null,'null'];
 const source={...simple,archives:raws.map((raw,i)=>({id:'escape-'+i,kind:'opaque',createdAt:AT,raw}))};
 const out=await exportBackupV4(source,options),stage=await decodeBackup(out.text);
 assert.deepEqual(stage.archives,source.archives);
});

test('B1 null, empty, duplicate raw and prototype metadata preserve independent records',async()=>{
 const source=structuredClone(snapshot);
 source.archives[0].extension=JSON.parse('{"__proto__":{"polluted":true},"constructor":{"future":1}}');
 const stage=await decodeBackup((await exportBackupV4(source,options)).text);
 assert.deepEqual(stage.archives,source.archives);assert.equal({}.polluted,undefined);
 assert.notEqual(stage.archives[9].id,stage.archives[10].id);assert.equal(stage.archives[9].raw,stage.archives[10].raw);
});

test('B1 captures mutable input and options before awaiting, preserving original history and raw',async()=>{
 const source=structuredClone(snapshot),metadata={note:'original'},before=structuredClone(source);
 const pending=exportBackupV4(source,{createdAt:AT,metadata});
 source.data.entries.length=0;source.archives[1].raw='newer edit';source.archives[2].extension.order=999;metadata.note='newer metadata';
 const stage=await decodeBackup((await pending).text);
 assert.deepEqual(stage.live.data,before.data);assert.deepEqual(stage.archives,before.archives);assert.deepEqual(stage.metadata,{note:'original'});
});

test('B1 limits never release output that the decoder cannot read, without truncation',async()=>{
 const source={...simple,archives:snapshot.archives},before=structuredClone(source);
 for(const limits of [{fileBytes:100},{storedBlobBytes:20},{decodedBlobBytes:100},{totalDecodedBytes:1000},{blobs:1},{archives:1},{depth:2},{tokens:10}]){
  await assert.rejects(exportBackupV4(source,{...options,limits}));assert.deepEqual(source,before);
 }
 for(const limits of [{fileBytes:V4_LIMITS.fileBytes+1},{fileBytes:0},{unknown:1}])await assert.rejects(exportBackupV4(snapshot,{...options,limits}));
});

test('B1 invalid, corrupt and ambiguous inputs are rejected rather than repaired or dropped',async()=>{
 for(const value of [null,{}, {...simple,version:9},{...simple,archives:null},{...simple,archives:[{id:'missing-raw'}]},
  {...simple,archives:[...snapshot.archives,snapshot.archives[0]]},'{broken'])await assert.rejects(exportBackupV4(value,options));
 const corrupt=JSON.parse(simple3);corrupt.integrity.digest='0'.repeat(64);await assert.rejects(exportBackupV4(JSON.stringify(corrupt),options));
 await assert.rejects(exportBackupV4(JSON.stringify({...old,archives:[]}),options),/ambiguous/);
 await assert.rejects(exportBackupV4(snapshot,{}),/createdAt/);
 const nonportable=structuredClone(simple);nonportable.extension.value=undefined;await assert.rejects(exportBackupV4(nonportable,options),/non-JSON/);
});

test('B1 cancellation or unavailable compression leaves source intact and returns no partial backup',async()=>{
 const before=structuredClone(snapshot),cancel=new AbortController();cancel.abort();
 await assert.rejects(exportBackupV4(snapshot,{...options,signal:cancel.signal}),{name:'AbortError'});
 const during=new AbortController(),pending=exportBackupV4(snapshot,{...options,signal:during.signal});queueMicrotask(()=>during.abort());
 await assert.rejects(pending,{name:'AbortError'});assert.deepEqual(snapshot,before);
 const original=globalThis.CompressionStream;
 try{globalThis.CompressionStream=undefined;await assert.rejects(exportBackupV4(simple,options),/gzip encoding unavailable/);}
 finally{globalThis.CompressionStream=original;}
});

test('B1 diagnostics contain only counts and sizes, never archive IDs, raw, names or checksums',async()=>{
 const source={...simple,archives:[{id:'SECRET-ARCHIVE-ID',kind:'SECRET-KIND',createdAt:AT,raw:'SECRET-CONTENT'}]};
 const {diagnostics}=await exportBackupV4(source,options),text=JSON.stringify(diagnostics);
 assert.equal(text.includes('SECRET'),false);assert.ok(Object.values(diagnostics).every(Number.isSafeInteger));
 assert.equal(diagnostics.archiveRawCodeUnits,14);assert.equal(diagnostics.largestArchiveCodeUnits,14);
});
