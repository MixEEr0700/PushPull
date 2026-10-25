import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {runInNewContext} from 'node:vm';
import {freeze,portable,immutableJSON} from '../model/backup-json.mjs';
import {prepareLegacyBackup,readLegacyBackup,legacySource,legacySourceVersion} from '../model/legacy-backup.mjs';
import {createLegacyModelFromSource} from '../model/legacy-model.mjs';
import {createBackup} from '../model/backup.mjs';
import {nativeData,AT} from './fixtures/backup-v4-fixture.mjs';
import {buildPlan,PLAN_ID} from '../model/v2-plan.mjs';
const old=JSON.parse(readFileSync('tests/fixtures/v1.json','utf8'));
const packet=JSON.parse(readFileSync('tests/fixtures/plan-v3.json','utf8'));
const contract=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
function source(native=false){
 const data=native?nativeData(old,packet):structuredClone(old);
 const {catalog}=contract.parseBackup(data);
 return {format:'pushpull-backup',version:2,data,catalog:structuredClone(catalog),archives:[]};
}
const options={ownerId:'synthetic-v4-owner',createdAt:AT};
let oldDirectory,oldModule;
async function previous(){
 if(!oldModule){
  oldDirectory=mkdtempSync(join(tmpdir(),'pushpull-stage-b-reader-'));
  execFileSync('tar',['-x','-C',oldDirectory],{input:execFileSync('git',['archive','4a74d1d','model'])});
  oldModule=await import(pathToFileURL(join(oldDirectory,'model/legacy-model.mjs')));
 }
 return oldModule;
}
after(()=>{if(oldDirectory)rmSync(oldDirectory,{recursive:true,force:true});});

test('portable proofs require every reachable object to be frozen, including unknown fields',()=>{
 const value=Object.freeze({child:{future:[1]}});
 assert.equal(immutableJSON(value),false);portable(value);
 value.child.future[0]=Infinity;assert.throws(()=>portable(value),/number/);
 const complete=freeze({future:[null,'Ł😀',1]});assert.equal(immutableJSON(complete),true);
 for(let i=0;i<4;i++)portable(complete);
 for(const invalid of [Object.freeze({get future(){return 1}}),Object.freeze({future:[undefined]}),Object.freeze({future:NaN}),Object.freeze({future:-0}),Object.freeze({future:new Date()})])assert.throws(()=>immutableJSON(invalid));
 const cycle={};cycle.future=cycle;Object.freeze(cycle);assert.throws(()=>immutableJSON(cycle),/cycle/);
});

test('domain validation reuses only fully immutable successful model/snapshot proofs',async()=>{
 let code=readFileSync('model/training-model.mjs','utf8');
 code='export let fullModels=0,fullSnapshots=0;\n'+code.replace('  json(model); record(model,','  fullModels++;json(model); record(model,').replace("  json(x); record(x,'schemaVersion id sessionId planVersionId unitId startedAt model');","  fullSnapshots++;json(x); record(x,'schemaVersion id sessionId planVersionId unitId startedAt model');");
 const measured=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
 const m=buildPlan('owner'),snapshot=freeze({schemaVersion:1,id:'snap',sessionId:'session',planVersionId:PLAN_ID,unitId:'PUSH A',startedAt:AT,model:m,extension:{retained:[1]}});
 measured.validateSessionSnapshot(snapshot);const counts=[measured.fullModels,measured.fullSnapshots];
 measured.validateSessionSnapshot(snapshot);measured.validateModel(m);
 assert.deepEqual([measured.fullModels,measured.fullSnapshots],counts);
 const shallow=Object.freeze(structuredClone(snapshot));measured.validateSessionSnapshot(shallow);
 shallow.extension.retained[0]=Infinity;assert.throws(()=>measured.validateSessionSnapshot(shallow),/non-finite/);
 const mutable=structuredClone(m);measured.validateModel(mutable);mutable.positions[0].variantId='missing';assert.throws(()=>measured.validateModel(mutable),/reference/);
 const invalid=freeze({...m,ownerId:''});for(let i=0;i<2;i++)assert.throws(()=>measured.validateModel(invalid),/owner/);
 const unknown=structuredClone(m);unknown.extension={child:1};Object.freeze(unknown);measured.validateModel(unknown);
 unknown.extension.child=Symbol('not-json');assert.throws(()=>measured.validateModel(unknown),/non-JSON/);
});

test('structured bridge matches previous writer bytes, SHA and reader for native history and opaque Unicode archives',async()=>{
 const reader=await previous();
 for(const native of [false,true]){
  const input=source(native);input.data.extension={future:[null,false,'Ł😀\ud800'],raw:'keep \\"\n'};
  input.archives=[{id:'opaque',kind:'recovery',createdAt:AT,unknown:{retained:true},raw:'Ł😀\\"\n'.repeat(128*1024)},{id:'null',kind:'recovery',createdAt:AT,raw:null}];
  const raw=JSON.stringify(input),expected=await reader.createLegacyModel(raw,options),actual=await createLegacyModelFromSource(input,options);
  assert.equal(JSON.stringify(actual),JSON.stringify(expected));
  assert.equal(actual.payload.legacySources[0].raw,raw);
  const parsed=await reader.parseModelBackup(JSON.stringify(actual));assert.deepEqual(parsed.document,actual);
  assert.equal(JSON.stringify(input),raw,'writer must not mutate or freeze caller data');
  assert.equal(Object.isFrozen(input.data),false);
 }
});

test('structured bridge detaches mutable and shallow-frozen callers before crypto awaits',async()=>{
 for(const shallow of [false,true]){
  const input=source(true);input.data.extension={future:['before']};input.archives=[{id:'raw',kind:'recovery',createdAt:AT,raw:'original'}];
  if(shallow)Object.freeze(input);
  const raw=JSON.stringify(input),pending=createLegacyModelFromSource(input,options);
  input.data.extension.future[0]='after';input.data.trainingJournal.sessionSnapshots[0].model.exercises[0].name='changed after await';input.archives[0].raw='changed';
  const actual=await pending;assert.equal(actual.payload.legacySources[0].raw,raw);
  assert.notEqual(actual.payload.sessionSnapshots[0].model.exercises[0].name,'changed after await');
 }
 const input=freeze(source(true)),actual=await createLegacyModelFromSource(input,options);
 assert.equal(actual.payload.sessionSnapshots,input.data.trainingJournal.sessionSnapshots,'validated immutable snapshots are shared rather than cloned again');
 assert.throws(()=>{actual.payload.sessionSnapshots[0].model.exercises[0].name='edit'},TypeError);
});

test('a legacy proof cannot be supplied by a caller or transferred to an altered source',async()=>{
 const view=prepareLegacyBackup(source());const proven=legacySource(view,'current');
 assert.equal(legacySourceVersion(proven),2);
 assert.throws(()=>legacySource({...view},'forged'),/verified/);
 const forged=freeze({...proven,raw:'{"version":1,"version":2}'});
 assert.throws(()=>legacySourceVersion(forged),/duplicate/);
 const payload=freeze({model:null,sessionSnapshots:[],resultReferences:[],sessionRecords:[],resultRecords:[],legacySources:[forged]});
 await assert.rejects(createBackup(payload,{createdAt:AT,metadata:{}}),/duplicate/);
});

test('untrusted text still rejects duplicate keys and lossy numbers; structured values reject nonportable extensions',async()=>{
 const input=source();const raw=JSON.stringify(input);
 assert.throws(()=>readLegacyBackup(raw.replace('"version":2','"version":2,"version":2')),/duplicate/);
 input.data.extension={n:9007199254740992};const lossy=JSON.stringify(input).replace('9007199254740992','9007199254740993');
 assert.throws(()=>readLegacyBackup(lossy),/losslessly/);
 for(const value of [undefined,()=>1,Infinity,-0,Symbol('x')]){
  const bad=source();bad.data.extension={value};await assert.rejects(createLegacyModelFromSource(bad,options));
 }
});

test('released prepared revisions do not retain raw/parsed history in proof caches under a 128 MiB heap',()=>{
 const module=pathToFileURL(join(process.cwd(),'model/legacy-model.mjs')).href;
 const code=`import {readFileSync} from 'node:fs';import {createLegacyModelFromSource} from ${JSON.stringify(module)};
 const input=JSON.parse(readFileSync(0,'utf8'));global.gc();const before=process.memoryUsage().heapUsed;
 for(let i=0;i<12;i++){const value=structuredClone(input);value.archives=[{id:'large',kind:'recovery',createdAt:'${AT}',raw:'x'.repeat(3*1024*1024)+i}];await createLegacyModelFromSource(value,${JSON.stringify(options)});global.gc();}
 global.gc();console.log(JSON.stringify({before,after:process.memoryUsage().heapUsed}));`;
 const memory=JSON.parse(execFileSync(process.execPath,['--max-old-space-size=128','--expose-gc','--input-type=module','-e',code],{input:JSON.stringify(source()),encoding:'utf8'}));
 assert.ok(memory.after-memory.before<40*1024*1024,JSON.stringify(memory));
});
