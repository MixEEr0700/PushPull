import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {writeCompactModel,readCompactModel} from '../model/compact-backup-writer.mjs';
import {openCompactBackup} from '../model/compact-backup-reader.mjs';
globalThis.crypto??=webcrypto;
const fixture=()=>({history:JSON.parse(readFileSync(new URL('./fixtures/v1.json',import.meta.url))),sessions:[{id:'s',snapshotId:'p',results:[{side:'L',reps:10,kg:12},{side:'R',reps:9,kg:12}],draft:{kg:'12,',reps:''}}],snapshots:[{id:'p',instructions:'original'}],plans:{active:'p',versions:[{id:'p',userNotes:'😀\ud800\udfff\0é'}]},archives:[{id:'a',raw:' { "opaque": "\\ud800" } ',metadata:{custom:true}},{id:'null',raw:null},{id:'empty',raw:''}],settings:{unknown:[false,null,-0,1e100],compatibility:{retained:'yes'}}});
test('entire model, all unknown fields and UTF16 code units roundtrip; shared graph identity',async()=>{
 const source=fixture();source.alias=source.snapshots;Object.defineProperty(source,'__proto__',{value:{safe:true},enumerable:true});
 const file=await writeCompactModel(source),out=await readCompactModel(file);assert.deepStrictEqual(out,source);assert.equal(out.alias,out.snapshots);assert.ok(Object.isFrozen(out.alias));assert.throws(()=>{out.snapshots[0].instructions='changed';},TypeError);assert.equal(Object.getPrototypeOf(out),Object.prototype);
});
test('deduplication, gzip/none, large repeated archive; synthetic benchmark',async()=>{
 const source=fixture();source.archives.push({id:'large',raw:'x'.repeat(8*1024*1024)});source.archives.push({id:'same',raw:source.archives.at(-1).raw});
 const start=performance.now(),file=await writeCompactModel(source),written=performance.now(),out=await readCompactModel(file);assert.deepStrictEqual(out,source);
 const reader=await openCompactBackup(file);assert.ok(reader.manifest.objects.some(o=>new Set(o.parts).size<o.parts.length));assert.ok(reader.manifest.chunks.some(c=>c.compression==='gzip'));
 console.log(JSON.stringify({synthetic:true,jsonBytes:Buffer.byteLength(JSON.stringify(source)),ppc1Bytes:file.size,writeMs:written-start,readMs:performance.now()-written,rss:process.memoryUsage().rss}));
 const none=await writeCompactModel(fixture(),{compression:false});assert.deepStrictEqual(await readCompactModel(none),fixture());assert.ok((await openCompactBackup(none)).manifest.chunks.every(c=>c.compression==='none'));
});
test('reject unsupported values rather than silently changing them',async()=>{
 const cyclic={};cyclic.self=cyclic;const getter={get x(){throw Error('must not execute');}};
 for(const v of [undefined,NaN,Infinity,1n,new Date(),cyclic,getter,[,1],Object.assign([],{extra:1}),{x:undefined}])await assert.rejects(writeCompactModel(v));
});
test('limits, cancellation, corrupt payload and truncation never publish restored model',async()=>{
 const s=fixture();for(const limits of [{totalDecodedBytes:1},{fileBytes:40},{manifestBytes:1},{chunks:1},{chunkStoredBytes:1},{depth:1},{tokens:1}])await assert.rejects(writeCompactModel(s,{limits}));
 const c=new AbortController();c.abort();await assert.rejects(writeCompactModel(s,{signal:c.signal}),{name:'AbortError'});
 const f=await writeCompactModel(s);await assert.rejects(readCompactModel(f.slice(0,-1)));const b=new Uint8Array(await f.arrayBuffer());b[b.length-1]^=1;await assert.rejects(readCompactModel(new Blob([b])));
});
test('capture precedes async work; later caller edits cannot change the file',async()=>{
 const source=fixture(),expected=structuredClone(source),pending=writeCompactModel(source);source.settings.compatibility.retained='changed';source.archives[0].raw='changed';assert.deepStrictEqual(await readCompactModel(await pending),expected);
});
test('malformed domain graph rejected even with correct transport hashes',async()=>{
 const {createHash}=await import('node:crypto');const hash=b=>createHash('sha256').update(b).digest('hex');
 async function container(nodes,root=0){const raw=Buffer.from(JSON.stringify({format:'pushpull-model-graph',version:1,root,nodes})),manifest=Buffer.from(JSON.stringify({format:'pushpull-compact',version:1,chunks:[{storedBytes:raw.length,decodedBytes:raw.length,storedSha256:hash(raw),decodedSha256:hash(raw),compression:'none'}],objects:[{id:'graph',parts:[0],bytes:raw.length}]})),header=Buffer.alloc(40);header.write('PPC1');header.writeUInt32BE(manifest.length,4);Buffer.from(hash(manifest),'hex').copy(header,8);return new Blob([header,manifest,raw]);}
 for(const nodes of [[['array',[0]]],[['value',true],['value',false]],[['string','missing']],[['number','NaN']],[['array',[99]]]])await assert.rejects(readCompactModel(await container(nodes)));
});
test('8 MiB opaque archive roundtrip under 64 MiB V8 old-space',async()=>{
 const {spawnSync}=await import('node:child_process');
 const run=spawnSync(process.execPath,['--max-old-space-size=64','--input-type=module','-e',`import {writeCompactModel,readCompactModel} from './model/compact-backup-writer.mjs';const x={archive:'x'.repeat(8*1024*1024)};const f=await writeCompactModel(x);const r=await readCompactModel(f);if(r.archive!==x.archive)throw Error('loss');console.log(JSON.stringify({bytes:f.size,rss:process.memoryUsage().rss}));`],{cwd:new URL('..',import.meta.url),encoding:'utf8',timeout:30000});assert.equal(run.status,0,run.stderr);console.log('Synthetic 64 MiB old-space:',run.stdout.trim());
});
test('full native V2 journal with all snapshots, plans, L/P, drops and source archives',async()=>{
 const {nativeData,archiveFixtures}=await import('./fixtures/backup-v4-fixture.mjs');
 const old=JSON.parse(readFileSync(new URL('./fixtures/v1.json',import.meta.url))),packet=JSON.parse(readFileSync(new URL('./fixtures/plan-test-3x5.json',import.meta.url)));
 const data=nativeData(old,packet);const source={data,archives:archiveFixtures(JSON.stringify(old),'opaque v2','opaque v3'),settings:{future:{all:'preserved'}}};
 assert.deepStrictEqual(await readCompactModel(await writeCompactModel(source)),source);
});
