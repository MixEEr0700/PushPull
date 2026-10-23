import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {execFileSync} from 'node:child_process';
import {createModel,captureSessionSnapshot,createResultReference} from '../model/training-model.mjs';
import {createBackup,validateBackup,exportBackup,previewBackup,restoreBackup,readLegacyBackup} from '../model/backup.mjs';
const options={createdAt:'2026-10-22T12:00:00.000Z',metadata:{source:'isolated-test',future:{schema:7,notes:'Ł — 🏋️'}}};
const source={kind:'trainer',reference:'fixture; not active V2',recordedAt:null};
function payload() {
  const model=createModel({schemaVersion:1,ownerId:'owner',
    exercises:['old-dips','new-machine'].map(id=>({id,name:id,status:'confirmed',legacyId:id,source})),
    variants:['old-dips','new-machine'].map(id=>({id:'v-'+id,exerciseId:id,label:id,machine:null,grip:null,support:null,execution:null,laterality:'unilateral',source})),
    planVersions:[1,2].map(number=>({id:'plan-'+number,planId:'plan',number,label:'Version '+number,units:[{id:'unit',name:'Test',order:0}],source})),
    positions:['old-dips','new-machine'].map((id,i)=>({id:'p-'+id,exerciseId:id,variantId:'v-'+id,planVersionId:'plan-'+(i+1),unitId:'unit',order:0,label:id,
      legacyPositionId:id,replacesPositionId:i?'p-old-dips':null,setState:'specified',confirmation:'confirmed',loadConvention:{unit:'kg',basis:'machine-indication',description:null},source})),
    sets:['old-dips','new-machine'].flatMap(id=>[0,1].map(i=>({id:'s-'+id+i,positionId:'p-'+id,order:i,role:i?'backoff':'main',reps:i?{min:8,max:10}:null,rir:null,tempo:[2,null,1,null],side:'each',backoffFromSetId:i?'s-'+id+'0':null,restSeconds:null,source}))),
    drops:[{id:'drop',setId:'s-old-dips0',segments:[{id:'seg',order:0,reps:null,rir:null,tempo:null}],source}],groups:[],
    coachInstructions:[{id:'coach',planVersionId:'plan-1',positionId:'p-old-dips',revision:1,text:'Instrukcja trenera',confirmation:'confirmed',source}],
    userNotes:[{id:'note',exerciseId:'old-dips',sessionId:'session',revision:1,text:'Historyczna notatka',origin:'legacy-shared',source:{...source,kind:'legacy'}}],extension:{retain:[false,null,'100,5']}});
  const snapshot=captureSessionSnapshot(model,{id:'snapshot',sessionId:'session',planVersionId:'plan-1',unitId:'unit',startedAt:options.createdAt});
  const reference=createResultReference(snapshot,{resultId:'result',positionId:'p-old-dips',setId:'s-old-dips0',side:'left',groupId:null,round:null});
  return {model,sessionSnapshots:[snapshot],resultReferences:[reference],
    sessionRecords:[{id:'session',snapshotId:'snapshot',payloadVersion:99,data:{startedAt:options.createdAt,unknown:[null,{labels:['a','Ł']}],notes:'Notatka sesji'}}],
    resultRecords:[{id:'result',sessionId:'session',binding:'snapshot',payloadVersion:42,data:{
      segments:[{id:'r1',side:'left',load:{raw:'40,5',unit:'kg'},reps:7},{id:'r2',side:'left',load:{raw:'32',unit:'kg'},reps:11}],
      rightSide:{unrecorded:true},groups:{rounds:[{members:['distinct-a','distinct-b'],future:true}]},source:{raw:'unmodified'},future:[null,false,{tempo:[2,null,1,0]}]}}],legacySources:[],futureEnvelope:{notDiscarded:true}};
}
function oldCode() {
  return runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\n({storage:PushPullStorage,db:PushPullDB})',{structuredClone,crypto:globalThis.crypto});
}
const legacy1=readFileSync('tests/fixtures/v1.json','utf8');
function legacy2() {
  const {catalog}=oldCode().db.parseBackup(JSON.parse(legacy1));
  return JSON.stringify({format:'pushpull-backup',version:2,data:JSON.parse(legacy1),catalog,
    archives:[{id:'exact-before',kind:'before-import',createdAt:options.createdAt,raw:legacy1}]},null,2);
}

test('v3 full export/preview/restore preserves every record, snapshot, ID, future payload and extension',async()=>{
  const input=payload(),original=structuredClone(input),backup=await createBackup(input,options);
  const text=await exportBackup(backup),preview=await previewBackup(text),restored=await restoreBackup(preview);
  assert.equal(preview.kind,'model');assert.equal(preview.formatVersion,3);
  assert.deepEqual(restored.restored.payload,original);assert.deepEqual(input,original);
  assert.equal(restored.restored.payload.sessionSnapshots[0].planVersionId,'plan-1');
  assert.equal(restored.restored.payload.resultReferences[0].exerciseId,'old-dips');
  assert.equal(restored.restored.payload.model.positions[1].replacesPositionId,'p-old-dips');
  assert.equal(restored.restored.payload.resultRecords[0].data.segments[0].load.raw,'40,5');
  assert.equal(await exportBackup(restored.restored),text);
  assert.notEqual(restored.restored,backup);assert.equal(Object.isFrozen(restored.restored.payload.resultRecords[0].data),true);
  assert.equal(restored.previousBackup,null);
});

test('group members and rounds, back-off and separate sides survive without merging results',async()=>{
  const p=structuredClone(payload()),m=p.model;
  m.positions.push({...structuredClone(m.positions[1]),id:'pair-member',planVersionId:'plan-1',order:1,replacesPositionId:null,setState:'unspecified'});
  m.groups=[{id:'pair',planVersionId:'plan-1',unitId:'unit',kind:'superset',positionIds:['p-old-dips','pair-member'],rounds:2,betweenMembersSeconds:15,afterRoundSeconds:null,source}];
  const snapshot=captureSessionSnapshot(m,{id:'snapshot',sessionId:'session',planVersionId:'plan-1',unitId:'unit',startedAt:options.createdAt});
  p.sessionSnapshots=[snapshot];p.resultReferences=[];p.resultRecords=[];
  for (const round of [1,2]) for (const positionId of ['p-old-dips','pair-member']) {
    const resultId=positionId+'-'+round,side=round===1?'left':'right';
    p.resultReferences.push(createResultReference(snapshot,{resultId,positionId,setId:positionId==='p-old-dips'?'s-old-dips'+(round-1):null,side,groupId:'pair',round}));
    p.resultRecords.push({id:resultId,sessionId:'session',binding:'snapshot',payloadVersion:27,data:{side,segments:[{kg:round===1?40:29,reps:7},{kg:15,reps:12}],extra:{group:'retained'}}});
  }
  const d=(await restoreBackup(await previewBackup(await exportBackup(await createBackup(p,options))))).restored;
  assert.deepEqual(d.payload,p);assert.equal(d.payload.resultRecords.length,4);
  assert.equal(d.payload.model.sets[1].role,'backoff');assert.equal(d.payload.model.groups[0].rounds,2);
});

test('unknown JSON keys at every envelope level are retained and covered by checksum',async()=>{
  const p=payload();p.resultRecords[0].data=JSON.parse('{"constructor":{"__proto__":"ordinary JSON data"},"toString":null}');
  let d=await createBackup(p,options);
  // Recompute an independently prepared envelope to exercise forward extension retention.
  const {canonical}=await import('../model/backup-json.mjs');
  d=structuredClone(d);d.future={additional:'metadata'};d.integrity.future={writer:7};
  const unsigned=structuredClone(d);delete unsigned.integrity.digest;
  d.integrity.digest=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(unsigned)))).toString('hex');
  const raw=await exportBackup(d),restored=await restoreBackup(await previewBackup(raw));
  assert.deepEqual(restored.restored,d);assert.equal(Object.prototype.polluted,undefined);
  d.future.additional='corrupted';await assert.rejects(validateBackup(d),/checksum/);
});

test('integrity, record counters, versions and syntax reject corruption before restoration',async()=>{
  const d=await createBackup(payload(),options),before=await exportBackup(d),state={history:before};
  const cases=[['{',''],[JSON.stringify({...d,version:4}),''],[JSON.stringify({...d,payload:{...d.payload,resultRecords:[]}}),''],
    [before.replace('Instrukcja trenera','zmieniona instrukcja'),''],[JSON.stringify({...d,integrity:{...d.integrity,counts:{...d.integrity.counts,sets:999}}}),'']];
  for (const [raw] of cases) await assert.rejects(previewBackup(raw));
  assert.equal(state.history,before);assert.equal(await exportBackup(d),before);
});

test('duplicate IDs, incomplete records and inconsistent cross-record relations fail explicitly',async()=>{
  const mutations=[p=>p.sessionSnapshots.push(p.sessionSnapshots[0]),p=>p.sessionRecords.push(p.sessionRecords[0]),
    p=>p.resultRecords.push(p.resultRecords[0]),p=>p.resultReferences.push(p.resultReferences[0]),
    p=>p.resultRecords[0].sessionId='missing',p=>p.resultReferences[0].exerciseId='new-machine',
    p=>p.sessionRecords[0].snapshotId=null,p=>p.resultReferences=[],p=>p.resultRecords=[],
    p=>p.resultRecords[0].binding='uninterpreted',p=>p.sessionRecords=[],p=>delete p.legacySources,
    p=>p.resultRecords[0].payloadVersion=0,p=>delete p.resultRecords[0].data,
    p=>p.model.userNotes[0].sessionId='missing',p=>p.sessionSnapshots[0].model.ownerId='other'];
  for (const mutate of mutations) {const p=structuredClone(payload());mutate(p);await assert.rejects(createBackup(p,options));}
});

test('unknown historical result semantics stay unbound, with no inferred snapshot or target',async()=>{
  const p=payload();p.sessionSnapshots=[];p.resultReferences=[];p.sessionRecords[0].snapshotId=null;
  p.resultRecords[0].binding='uninterpreted';p.resultRecords[0].payloadVersion=null;
  const restored=await restoreBackup(await previewBackup(await exportBackup(await createBackup(p,options))));
  assert.deepEqual(restored.restored.payload,p);assert.equal(restored.restored.payload.sessionSnapshots.length,0);
});

test('confirmation preserves exact prior backup, invalid replacement never mutates current isolated state',async()=>{
  const previous=legacy2(),input=await exportBackup(await createBackup(payload(),options)),preview=await previewBackup(input);
  let isolated={history:previous};const original=structuredClone(isolated);
  await assert.rejects(restoreBackup(preview,{currentBackup:previous}),/confirmation/);
  await assert.rejects(restoreBackup(preview,{currentBackup:'{',confirmReplacement:true}));
  await assert.rejects(restoreBackup(structuredClone(preview)),/verified preview/);
  assert.deepEqual(isolated,original);
  const next=await restoreBackup(preview,{currentBackup:previous,confirmReplacement:true});
  isolated=next.restored;assert.equal(next.previousBackup,previous);assert.equal(isolated.version,3);
  assert.deepEqual(JSON.parse(next.previousBackup),JSON.parse(previous));
});

test('v1 and real v2 legacy backups retain exact text, all data, catalog, archives and unknown fields',async()=>{
  for (const raw of [legacy1,legacy2()]) {
    assert.doesNotThrow(()=>oldCode().db.parseBackup(JSON.parse(raw)));
    const adapter=readLegacyBackup(raw);assert.equal(adapter.raw,raw);assert.deepEqual(adapter.original,JSON.parse(raw));
    assert.equal(adapter.semantics,'legacy-unknown');
    if (adapter.formatVersion===1) assert.equal(adapter.catalog,null);
    const preview=await previewBackup(raw),restored=await restoreBackup(preview);
    assert.equal(restored.raw,raw);assert.deepEqual(restored.restored,JSON.parse(raw));
    const p={model:null,sessionSnapshots:[],resultReferences:[],sessionRecords:[],resultRecords:[],legacySources:[{
      id:'original-file',formatVersion:adapter.formatVersion,semantics:'legacy-unknown',raw,metadata:{unknownHistory:true}}]};
    const wrapped=await restoreBackup(await previewBackup(await exportBackup(await createBackup(p,options))));
    assert.equal(wrapped.restored.payload.legacySources[0].raw,raw);assert.equal(wrapped.restored.payload.model,null);
  }
  const v2=JSON.parse(legacy2());v2.future={unrecognized:true};v2.catalog.extra={retained:true};
  assert.deepEqual(readLegacyBackup(JSON.stringify(v2)).original,v2);
});

test('legacy validation rejects broken graphs and versions without repairing or discarding records',()=>{
  const bad=[x=>x.entries.push(x.entries[0]),x=>x.entries[0].sessionId='missing',x=>x.version=100];
  for (const change of bad) {const x=JSON.parse(legacy1);change(x);assert.throws(()=>readLegacyBackup(JSON.stringify(x)));}
  const v2=JSON.parse(legacy2());v2.catalog.sessionVersions={};assert.throws(()=>readLegacyBackup(JSON.stringify(v2)));
});

test('old storage and IndexedDB importers reject v3 without writes or lost extra fields',async()=>{
  const d=await createBackup(payload(),options),old=oldCode(),writes=[];
  const store=old.storage.open({getItem:k=>k===old.storage.KEY?legacy1:null,setItem:(...args)=>writes.push(args)},()=>JSON.parse(legacy1));
  assert.throws(()=>old.storage.validate(d));assert.throws(()=>old.db.parseBackup(d));
  assert.throws(()=>store.commit(d,{importing:true}));assert.deepEqual(writes,[]);assert.equal(store.raw,legacy1);
});

test('JSON boundary rejects silent loss: duplicate keys, rounded numbers, getters, undefined and negative zero',async()=>{
  for (const raw of ['{"version":1,"version":2}','{"version":1,"vers\\u0069on":1}',
    '{"version":1,"unknown":9007199254740993}','{"unknown":1.00000000000000001}',
    '{"unknown":1e-1000}','{"unknown":-0}']) await assert.rejects(previewBackup(raw));
  for (const extra of [undefined,NaN,-0,new Date(),[undefined]]) {
    const p=payload();p.resultRecords[0].data=extra;await assert.rejects(createBackup(p,options));
  }
  const p=payload();Object.defineProperty(p.resultRecords[0],'computed',{enumerable:true,get(){throw Error('must never run');}});
  await assert.rejects(createBackup(p,options),/non-JSON property/);
});

test('complete empty model is valid; incomplete export cannot masquerade as an empty history',async()=>{
  const p={model:null,sessionSnapshots:[],resultReferences:[],sessionRecords:[],resultRecords:[],legacySources:[]};
  const b=await createBackup(p,options);assert.deepEqual((await restoreBackup(await previewBackup(await exportBackup(b)))).restored.payload,p);
  delete p.resultRecords;await assert.rejects(createBackup(p,options),/missing resultRecords/);
});

test('backup modules remain inert before explicit migration and do not access storage, DOM or network',async()=>{
  const paths=['index.html','style.css','manifest.webmanifest','icon.svg'];
  for (const path of paths) assert.deepEqual(readFileSync(path),execFileSync('git',['show',`063c02b5272ebb4066d498f82faf34e7353b588c:${path}`]));
  const script=`for(const k of ['indexedDB','localStorage','document','fetch'])Object.defineProperty(globalThis,k,{get(){throw Error(k+' access');}});const b=await import('./model/backup.mjs');const p={model:null,sessionSnapshots:[],resultReferences:[],sessionRecords:[],resultRecords:[],legacySources:[]};const d=await b.createBackup(p,${JSON.stringify(options)});await b.restoreBackup(await b.previewBackup(await b.exportBackup(d)));`;
  execFileSync(process.execPath,['--input-type=module','-e',script]);
});


test('long escaped archive strings scan without regexp-stack recursion and retain boundary checks',async()=>{
 const {parseJson}=await import('../model/backup-json.mjs');
 const archive='"\\'.repeat(3000000),raw=JSON.stringify({archive,x:1});
 assert.deepEqual(parseJson(raw),{archive,x:1});
 assert.throws(()=>parseJson(raw.slice(0,-1)+',"x":2}'),/duplicate JSON property/);
 assert.throws(()=>parseJson(raw.replace('"x":1','"x":9007199254740993')),/losslessly/);
});
