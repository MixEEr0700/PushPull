import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {valueProfile,textProfile,escapedProfile} from '../model/backup-size-json.mjs';
import {inventory,anonymousReport} from '../model/backup-size.mjs';
import {createProtocol} from '../model/journal-protocol.mjs';
import {nativeData,AT} from './fixtures/backup-v4-fixture.mjs';
const bytes=s=>Buffer.byteLength(s);
const storage=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});
function source(native=true){
 const old=JSON.parse(readFileSync('tests/fixtures/v1.json')),packet=JSON.parse(readFileSync('tests/fixtures/plan-v3.json'));
 const data=native?nativeData(old,packet):old;
 return {format:'pushpull-backup',version:2,data,catalog:structuredClone(storage.parseBackup(data).catalog),archives:[{id:'opaque-private-id',kind:'opaque',createdAt:AT,raw:'private note Ł😀\\"\n\ud800'.repeat(128)},{id:'null-id',kind:'opaque',createdAt:AT,raw:null}]};
}
function reader(bundle){
 const data=new Map(Object.entries(bundle.records).map(([k,rows])=>[k,new Map(rows.map(r=>[r.id,r]))]));
 return {data,async get(s,k){return data.get(s).get(k)},async keys(s,max){return [...data.get(s).keys()].slice(0,max)}};
}
test('byte-only counters match native compact, pretty and repeated escaping including Unicode',()=>{
 for(const v of [null,true,123,-4.5,'','Ł😀\ud800\udfff\u0000\b\t\n\f\r"\\',[],{},[1,{a:[2,3],empty:{}}],{a:{b:{c:[false,null,'x']}}},source()]){
  const compact=JSON.stringify(v),p=valueProfile(v),t=textProfile(compact);
  assert.deepEqual(t,p);assert.equal(p.bytes,bytes(compact));assert.equal(p.pretty,bytes(JSON.stringify(v,null,2)));
  assert.equal(escapedProfile(p).bytes,bytes(JSON.stringify(compact)));
  assert.equal(escapedProfile(escapedProfile(p)).bytes,bytes(JSON.stringify(JSON.stringify(compact))));
 }
 assert.throws(()=>valueProfile([,]));assert.throws(()=>valueProfile(new Date()));assert.throws(()=>textProfile('{"x":1}\n'));
});
test('disjoint native and legacy inventories match independent full JSON oracles without exporting',async()=>{
 for(const native of [false,true]){
  const input=source(native),bundle=await createProtocol(input),r=reader(bundle),before=JSON.stringify(bundle);
  const report=await inventory(r);
  assert.equal(report.sourceBytes.total,bytes(JSON.stringify(input)));
  assert.equal(report.sourceBytes.history,bytes(JSON.stringify(input.data.sessions))+bytes(JSON.stringify(input.data.entries))+bytes(JSON.stringify(input.data.changes??{})));
  assert.equal(report.sourceBytes.snapshots,input.data.trainingJournal?bytes(JSON.stringify(input.data.trainingJournal.sessionSnapshots)):0);
  assert.equal(report.sourceBytes.archives,bytes(JSON.stringify(input.archives)));
  assert.equal(report.sourceBytes.catalog,bytes(JSON.stringify(input.catalog)));
  assert.equal(report.representationBytes.sourcePretty,bytes(JSON.stringify(input,null,2)));
  assert.equal(report.representationBytes.sourceAsJsonStringAgain,bytes(JSON.stringify(JSON.stringify(JSON.stringify(input)))));
  assert.equal(report.storedBytes.total,Object.values(bundle.records).flat().reduce((n,v)=>n+bytes(JSON.stringify(v)),0));
  assert.equal(report.sourceBytes.total,report.representationBytes.uniqueReferencedObjects+report.representationBytes.repeatedReferencedObjects+report.representationBytes.referenceEnvelope);
  assert.equal(JSON.stringify(bundle),before);assert.equal(report.counts.sessions,input.data.sessions.length);
  assert.equal(report.counts.results,input.data.entries.length);assert.equal(report.counts.archives,2);
  if(native)assert.ok(report.counts.repeatedReferences>0&&report.representationBytes.repeatedReferencedObjects>0);
  assert.ok(!JSON.stringify(report).includes('private'));assert.ok(!JSON.stringify(report).includes(AT));
  const bad=structuredClone(report);bad.counts.secret='PRIVATE';assert.throws(()=>anonymousReport(bad));
 }
});
test('large history reuses snapshot models but counts every serialized occurrence exactly',async()=>{
 const input=source(),d=input.data,s=d.sessions.find(v=>v.journalSnapshotId),snap=d.trainingJournal.sessionSnapshots.find(n=>n.id===s.journalSnapshotId);
 for(let i=0;i<400;i++){const id='large-size-session-'+i,sid='large-size-snapshot-'+i;d.sessions.push({...s,id,seq:1000+i,status:'done',journalSnapshotId:sid});d.trainingJournal.sessionSnapshots.push({...snap,id:sid,sessionId:id});}
 input.catalog=structuredClone(storage.parseBackup(d).catalog);const report=await inventory(reader(await createProtocol(input)));
 assert.equal(report.sourceBytes.total,bytes(JSON.stringify(input)));assert.equal(report.counts.snapshots,d.trainingJournal.sessionSnapshots.length);
 assert.ok(report.representationBytes.repeatedReferencedObjects>1000000);
});
test('cancel, reader error, missing data, changed revision and unsafe budgets publish no result',async()=>{
 const bundle=await createProtocol(source(false));
 const aborted=new AbortController();aborted.abort();await assert.rejects(inventory(reader(bundle),{signal:aborted.signal}),{code:'cancelled'});
 await assert.rejects(inventory(reader(bundle),{limits:{objectBytes:32}}),{code:'limit'});
 await assert.rejects(inventory(reader(bundle),{expectedRevision:bundle.state.revision+1}),{code:'changed'});
 const r=reader(bundle),get=r.get;let states=0;r.get=async(s,k)=>{const value=await get(s,k);return s==='journalState'&&++states>1?{...value,revision:value.revision+1}:value};
 await assert.rejects(inventory(r),{code:'changed'});
 const missing=reader(bundle);missing.data.get('journalObjects').delete(bundle.records.journalArchives[0].ref);await assert.rejects(inventory(missing));
 const broken=reader(bundle);broken.get=async()=>{throw Error('PRIVATE token')};await assert.rejects(inventory(broken));
 const timed=reader(bundle);let time=0;await assert.rejects(inventory(timed,{now:()=>time++,limits:{timeoutMs:2}}),{code:'limit'});
});

test('checkpoint budget refuses before cloning rescue material',async()=>{
 const raw='{"retained":true}',{sha}=await import('../model/journal-index.mjs');
 const bundle=await createProtocol(source(false),{checkpoints:[{id:'rescue',protocol:2,raw,sha256:await sha(raw)}]});
 const r=reader(bundle),report=await inventory(r);
 assert.equal(report.storedBytes.checkpoints,bytes(JSON.stringify(bundle.records.journalCheckpoints[0])));
 let readCheckpoint=false;const get=r.get;r.get=async(s,k)=>{if(s==='journalCheckpoints')readCheckpoint=true;return get(s,k)};
 await assert.rejects(inventory(r,{limits:{checkpointBytes:8}}),{code:'limit'});assert.equal(readCheckpoint,false);
});

test('counter handles virtual serialization over 200 MB under 64 MiB V8 old-space',async()=>{
 const {execFileSync}=await import('node:child_process');
 const code=`import {valueProfile,escapedProfile} from './model/backup-size-json.mjs';
 const n=10*1024*1024,raw='"\\\\\\n'.repeat(n),started=performance.now();
 const p=valueProfile({raw}),twice=escapedProfile(escapedProfile(p));
 if(p.bytes!==n*6+10||twice.bytes<200000000)throw Error('counter mismatch');
 console.log(JSON.stringify({bytes:p.bytes,twice:twice.bytes,ms:Math.round(performance.now()-started),rss:process.resourceUsage().maxRSS*1024}));`;
 const result=JSON.parse(execFileSync(process.execPath,['--max-old-space-size=64','--input-type=module','-e',code],{encoding:'utf8',timeout:30000}));
 assert.ok(result.twice>200000000);console.log('Isolated counter / 64 MiB old-space:',result);
});
