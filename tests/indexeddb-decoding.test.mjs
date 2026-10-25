import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

// Exercise the actual storage decoder and its integrity gate, without replacing
// them with a second implementation or depending on noisy wall-clock thresholds.
const code=readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8').replace(
 '  async function open(fresh) {',
 '  globalThis.storageInternals={encode,verifyRows,validateCatalog};\n  async function open(fresh) {'
 )+'\nPushPullDB';
const fixture=()=>JSON.parse(readFileSync('tests/fixtures/v1.json','utf8'));
const json=value=>JSON.parse(JSON.stringify(value));
function environment(){
 let copiedHistory=0;
 const context={crypto,structuredClone:value=>{copiedHistory+=(value?.sessions?.length||0)+(value?.entries?.length||0);return structuredClone(value)}};
 const db=runInNewContext(code,context);
 return {db,api:context.storageInternals,copies:()=>copiedHistory};
}
function encoded(env,data){
 const catalog=env.db.parseBackup(data).catalog,e=env.api.encode(data,catalog);
 const root={rest:e.rest,changeKeys:e.changeKeys,hasChanges:e.hasChanges,catalogOrder:{plans:catalog.plans.map(p=>p.id),planVersions:catalog.planVersions.map(p=>p.id)},counts:Object.fromEntries(Object.entries(e.rows).map(([k,v])=>[k,v.length]))};
 return {root,rows:e.rows,catalog};
}

test('indexed rows retain original session/result order, exact series, null/absent and extensions',()=>{
 const env=environment(),data=fixture();
 data.entries[0].series=[{kg:data.entries[0].kg,reps:data.entries[0].reps,id:'first',opaque:'Ł😀'},{kg:'0',reps:'12',id:'second'}];
 data.entries[1].series=null;delete data.entries[2].series;
 data.future={unchanged:['',null,'\ud800']};
 const {root,rows,catalog}=encoded(env,data);
 for(const values of Object.values(rows))values.reverse();
 assert.deepEqual(json(env.api.verifyRows(root,rows)),json({data,catalog}));
});

test('decoder still rejects an orphan set and a set linked to the wrong entry',()=>{
 const env=environment();
 for(const kind of ['orphan','wrong-entry']){
  const {root,rows}=encoded(env,fixture());
  rows.sets[0].entryId=kind==='orphan'?'missing':rows.entries.find(e=>e.id!==rows.sets[0].entryId).id;
  assert.throws(()=>env.api.verifyRows(root,rows));
 }
});

test('loading many results visits stored set rows a bounded number of times',()=>{
 const env=environment(),data=fixture();data.sessions=[];data.entries=[];data.activeId=null;
 for(let n=0;n<128;n++){
  const sessionId='history-'+n;data.sessions.push({id:sessionId,seq:n+1,type:'PUSH A',date:'2026-01-01',status:'done'});
  data.entries.push({id:'result-'+n,sessionId,exerciseId:'PUSH-A-1',kg:'10',reps:'8',series:[{kg:'10',reps:'8'},{kg:'9',reps:'10'}]});
 }
 const {root,rows}=encoded(env,data),count=rows.sets.length;let reads=0;
 rows.sets=new Proxy(rows.sets,{get(target,key,receiver){if(typeof key==='string'&&/^\d+$/.test(key))reads++;return Reflect.get(target,key,receiver)}});
 assert.deepEqual(json(env.api.verifyRows(root,rows).data),data);
 assert.ok(reads<=4*count,`stored set visits must stay linear: ${reads} for ${count} rows`);
});

test('archived plan validation does not copy discarded history, and still validates parameters/links',()=>{
 const env=environment(),data=fixture();
 data.futureMetadata={retained:true};
 const {catalog}=encoded(env,data),before=env.copies();
 env.api.validateCatalog(data,catalog);
 assert.equal(env.copies()-before,0,'catalog validation must not copy sessions/results for each plan');
 const missing=json(catalog);delete missing.sessionVersions[data.sessions[0].id];
 assert.throws(()=>env.api.validateCatalog(data,missing));
 const invalid=json(catalog);invalid.planVersions[0].exercises[0].sets=0;
 assert.throws(()=>env.api.validateCatalog(data,invalid));
 assert.equal(data.futureMetadata.retained,true);
});
