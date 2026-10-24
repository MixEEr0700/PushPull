import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {exportBackupV5} from '../model/backup-v5.mjs';
import {exportBackupV4} from '../model/backup-v4-export.mjs';
import {exportBackupV6,decodeBackup,V6_LIMITS} from '../model/backup-v6.mjs';
import {canonical} from '../model/backup-json.mjs';
import {AT,nativeData,sourceV3} from './fixtures/backup-v4-fixture.mjs';
const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
const old=JSON.parse(readFileSync('tests/fixtures/v1.json'));
const snapshot={format:'pushpull-backup',version:2,data:old,catalog:JSON.parse(JSON.stringify(db.parseBackup(old).catalog)),archives:[]};
const history=JSON.parse((await exportBackupV5(snapshot,{createdAt:AT})).text);
const capture={version:1,historyRevision:1,startedAt:AT,completedAt:AT,consistency:'observed-stable',scope:'observed-origin'};
const row=(token,sequence=1)=>({version:1,key:'workout-draft:d',id:'d',token,sequence,sessionId:'s',exerciseId:'e',updatedAt:AT,
 context:{sessionId:'s',exerciseId:'e',sessionType:'PUSH A',status:'active',snapshotId:null,planVersionId:null,positionId:null,variantId:null,legacyDefinition:null},baseline:null,kind:'legacy',value:{kg:'1,',reps:'',series:[{id:'r',kg:'',reps:''}]},unknown:{unicode:'Ł😀\ud800\0'}});
const a=row('a'),b=row('b',2);
const evidence={format:'pushpull-draft-evidence',version:1,sources:[
 {source:'idb-meta',storageKey:a.key,value:a},
 {source:'local-buffer',storageKey:'pushpull_workout_draft_v1:d:b',raw:'  '+JSON.stringify(b)+'\n'},
 {source:'local-buffer',storageKey:'pushpull_workout_draft_v1:bad',raw:'malformed\ud800\0'},
 {source:'editor-memory',record:b,binding:{context:b.context,baseline:b.baseline},durableToken:null,parent:a},
 {source:'idb-meta',storageKey:a.key,value:a}]};
const input={history,evidence,capture,createdAt:AT};
const seal=async d=>{d.integrity={algorithm:'SHA-256'};d.integrity.digest=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(d)))).toString('hex');return JSON.stringify(d)};
test('all evidence versions/conflicts/duplicates/metadata/unfinished Unicode preserved, no winner',async()=>{
 const before=structuredClone(input),out=await exportBackupV6(input),stage=await decodeBackup(out.text);
 assert.deepEqual(input,before);assert.deepEqual(stage.draftEvidence,evidence);assert.deepEqual(stage.historyDocument,history);
 assert.deepEqual(stage.classification.map(x=>x.status),['conflict','conflict','quarantine','conflict','conflict']);
 assert.equal(stage.draftCoverage,'observed-origin');assert.equal('complete' in stage,false);assert.ok(Object.isFrozen(stage.draftEvidence));
 const second=await exportBackupV6(input);assert.equal(second.text,out.text);
});
test('native V2/TEST model and archive above 64 MiB roundtrip, v2 editor values retained',async()=>{
 const data=nativeData(old,JSON.parse(readFileSync('tests/fixtures/plan-v3.json')));
 const raw='x'.repeat(65*1024*1024)+'\ud800';
 const big={...snapshot,data,catalog:JSON.parse(JSON.stringify(db.parseBackup(data).catalog)),archives:[{id:'big',kind:'opaque',createdAt:AT,raw},{id:'nil',kind:'recovery',createdAt:AT,raw:null}]};
 const h=JSON.parse((await exportBackupV5(big,{createdAt:AT})).text);
 const r={...a,id:'v2',key:'workout-draft:v2',kind:'v2',future:{retained:true}};
 r.value={performance:{version:2,rows:[{id:'r',segments:[{id:'s',kg:'',reps:'1,'}]}]}};

 const e={...evidence,sources:[{source:'idb-meta',storageKey:r.key,value:r}]};
 const out=await exportBackupV6({...input,history:h,evidence:e}),stage=await decodeBackup(out.text);
 assert.deepEqual(stage.history.live.data,data);assert.deepEqual(stage.history.archives,big.archives);assert.deepEqual(stage.draftEvidence,e);
 console.log(JSON.stringify(out.diagnostics));
});
test('all prior formats v1-v5 delegated without changing data',async()=>{
 const v2=JSON.stringify(snapshot),v3=await sourceV3(snapshot),v4=(await exportBackupV4(snapshot,{createdAt:AT})).text;
 for(const [i,text] of [JSON.stringify(old),v2,v3,v4,JSON.stringify(history)].entries()){
  const stage=await decodeBackup(text);assert.equal(stage.formatVersion,i+1);assert.deepEqual(stage.live.data,old);
 }
});
test('missing/unknown sources, forged completeness and non-JSON inputs rejected; corrupt records quarantined',async()=>{
 for(const sources of [undefined,[{source:'unknown'}],[{source:'local-buffer',storageKey:'pushpull_workout_draft_v1:d'}],[{source:'idb-meta',storageKey:'drive-sync-v1',value:a}]]){
  await assert.rejects(exportBackupV6({...input,evidence:{...evidence,sources}}));
 }
 await assert.rejects(exportBackupV6({...input,capture:{...capture,scope:'complete-device'}}));
 const cyclic={};cyclic.cycle=cyclic;await assert.rejects(exportBackupV6({...input,evidence:{...evidence,sources:[{source:'idb-meta',storageKey:a.key,value:cyclic}]}}));
 const out=await exportBackupV6({...input,evidence:{...evidence,sources:[{source:'idb-meta',storageKey:a.key,value:{...a,sequence:-1}}]}});
 assert.equal((await decodeBackup(out.text)).classification[0].status,'quarantine');
});
test('corruption, removed section, truncated gzip, bad size after rehash, and abort expose no partial result',async()=>{
 const out=await exportBackupV6(input),original=JSON.parse(out.text);
 await assert.rejects(decodeBackup(out.text.slice(0,-1)));
 for(const mutate of [d=>{delete d.drafts;},d=>{d.drafts.data=d.drafts.data.slice(0,-4);},d=>{d.drafts.decodedBytes=1;},d=>{d.history.archives.push({});}]){
  const d=structuredClone(original);mutate(d);await assert.rejects(decodeBackup(await seal(d)));
 }
 const d=structuredClone(original);d.capture.historyRevision++;await assert.rejects(decodeBackup(JSON.stringify(d)));
 const controller=new AbortController();const pending=exportBackupV6(input,{signal:controller.signal});controller.abort();await assert.rejects(pending,{name:'AbortError'});
 const c=new AbortController();const read=decodeBackup(out.text,{signal:c.signal});c.abort();await assert.rejects(read,{name:'AbortError'});
});
test('all budgets only lower: sources, identities, source bytes, decoded/stored, shared logical bytes',async()=>{
 for(const limits of [{sources:2},{identities:1},{sourceBytes:50},{draftDecodedBytes:100},{draftStoredBytes:10},{totalDecodedBytes:100},{fileBytes:100}])await assert.rejects(exportBackupV6(input,{limits}));
 await assert.rejects(exportBackupV6(input,{limits:{draftDecodedBytes:V6_LIMITS.draftDecodedBytes+1}}));
});
test('4 MiB budget accommodates 256 small independent drafts and rejects oversized raw before compression',async()=>{
 const sources=Array.from({length:256},(_,i)=>{const value={...a,id:'draft-'+i,key:'workout-draft:draft-'+i};return {source:'idb-meta',storageKey:value.key,value};});
 const out=await exportBackupV6({...input,evidence:{...evidence,sources}});assert.equal((await decodeBackup(out.text)).draftEvidence.sources.length,256);
 sources.push({source:'idb-meta',storageKey:'workout-draft:257',value:{...a,id:'257',key:'workout-draft:257'}});await assert.rejects(exportBackupV6({...input,evidence:{...evidence,sources}}));
 const source={source:'local-buffer',storageKey:'pushpull_workout_draft_v1:huge',raw:'x'.repeat(1024*1024)};
 await assert.rejects(exportBackupV6({...input,evidence:{...evidence,sources:[source]}}));
});
test('draft budget near 4 MiB and exact source-count boundary, without truncation',async()=>{
 const sources=Array.from({length:6},(_,i)=>({source:'local-buffer',storageKey:'pushpull_workout_draft_v1:q'+i,raw:'x'.repeat(600000)}));
 const out=await exportBackupV6({...input,evidence:{...evidence,sources}});assert.equal((await decodeBackup(out.text)).draftEvidence.sources.length,6);
 sources.push({source:'local-buffer',storageKey:'pushpull_workout_draft_v1:q7',raw:'x'.repeat(600000)});await assert.rejects(exportBackupV6({...input,evidence:{...evidence,sources}}));
 const duplicates=Array.from({length:1024},()=>({source:'idb-meta',storageKey:a.key,value:a}));
 const many=await exportBackupV6({...input,evidence:{...evidence,sources:duplicates}});assert.equal((await decodeBackup(many.text)).draftEvidence.sources.length,1024);
 duplicates.push(duplicates[0]);await assert.rejects(exportBackupV6({...input,evidence:{...evidence,sources:duplicates}}));
});
test('joint budget counts history plus drafts; truncated gzip with valid hashes is rejected',async()=>{
 const out=await exportBackupV6(input),d=JSON.parse(out.text),p=d.history.payload;
 const bytes=p.blobs.find(b=>b.id===p.live.blobId).decodedBytes+d.drafts.decodedBytes-1;
 await assert.rejects(exportBackupV6(input,{limits:{totalDecodedBytes:bytes}}),/aggregate/);
 await assert.rejects(decodeBackup(out.text,{limits:{totalDecodedBytes:bytes}}));
 const truncated=Buffer.from(d.drafts.data,'base64').subarray(0,-8);
 d.drafts.data=truncated.toString('base64');d.drafts.storedBytes=truncated.length;
 d.drafts.storedSha256=Buffer.from(await crypto.subtle.digest('SHA-256',truncated)).toString('hex');
 await assert.rejects(decodeBackup(await seal(d)));
});
test('writer captures mutable evidence/history before awaits, no post-await version replacement',async()=>{
 const source=structuredClone(input),before=structuredClone(source),pending=exportBackupV6(source);
 source.evidence.sources[0].value.value.kg='changed';source.capture.historyRevision=99;source.history.archives=[];
 const result=await pending,stage=await decodeBackup(result.text);
 assert.deepEqual(stage.draftEvidence,before.evidence);assert.deepEqual(stage.historyDocument,before.history);assert.deepEqual(stage.capture,before.capture);
});

test('malformed legacy/V2 rows remain exact quarantined evidence rather than aborting export',async()=>{
 for(const [kind,value] of [['legacy',{kg:'',reps:'',series:[null]}],['v2',{performance:{version:2,rows:[null]}}]]){
  const record={...a,kind,value},e={...evidence,sources:[{source:'idb-meta',storageKey:a.key,value:record}]};
  const out=await exportBackupV6({...input,evidence:e}),stage=await decodeBackup(out.text);
  assert.deepEqual(stage.draftEvidence,e);assert.equal(stage.classification[0].status,'quarantine');
 }
});

test('quarantined sources cannot bypass identity budget by claiming one ID under different keys',async()=>{
 const sources=Array.from({length:256},(_,i)=>({source:'idb-meta',storageKey:'workout-draft:other-'+i,value:a}));
 await assert.rejects(exportBackupV6({...input,evidence:{...evidence,sources}}),/identity limit/);
});
