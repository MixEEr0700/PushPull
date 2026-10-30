import {test} from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {planCompleteRestore,storePolicy,metaPolicy,localPolicy,RESTORE_BLOCKERS} from '../model/complete-backup-restore-plan.mjs';
import {writeCompleteContract,COMPLETE_STORES} from '../model/complete-backup-contract.mjs';
import {completeFixture} from './fixtures/complete-contract-fixture.mjs';import {previewFixture} from './fixtures/compact-preview-fixture.mjs';
async function input(){const s=previewFixture(JSON.parse(readFileSync('tests/fixtures/v1.json')),JSON.parse(readFileSync('tests/fixtures/plan-test-3x5.json')),true);delete s.settings;delete s.metadata;return completeFixture(s);}
test('complete evidence remains exact; fresh protocol materializes all source fields, never replays Drive or checkpoints',async()=>{
 const s=await input(),before=structuredClone(s),p=await planCompleteRestore(await writeCompleteContract(s));
 assert.deepStrictEqual(p.evidence,s);assert.deepStrictEqual(s,before);assert.deepStrictEqual(p.candidate.source,s.source);
 assert.notEqual(p.candidate.graph.state.epoch,s.indexedDB.stores.journalState[0].epoch);assert.equal(p.candidate.graph.state.revision,0);
 assert.equal(p.candidate.graph.state.ownerId,s.indexedDB.stores.journalState[0].ownerId);assert.deepStrictEqual(p.candidate.graph.records.journalCheckpoints,[]);
 assert.deepStrictEqual(p.candidate.drive,{mode:'manual',enabled:false,selected:null,accounts:{},clientId:''});
 assert.deepStrictEqual(p.stores.map(r=>r.store),COMPLETE_STORES);assert.equal(p.canCommit,false);assert.equal(p.productionComplete,false);assert.deepStrictEqual(p.blockers,RESTORE_BLOCKERS);
 assert.equal(p.meta.length,s.indexedDB.stores.meta.length);assert.equal(p.local.length,s.localStorage.length);
});
test('every policy is explicit, unknown stores/keys refuse, unknown meta never activates',()=>{
 assert.throws(()=>storePolicy('extra'));assert.throws(()=>localPolicy('other-app'));
 assert.equal(metaPolicy('unknown-token'),'retain-unclassified-evidence-no-activation');
 assert.equal(metaPolicy('workout-draft:one'),'preserve-draft-rebind-CAS-before-activation');
 for(const k of COMPLETE_STORES)assert.ok(storePolicy(k));
});
test('incomplete/corrupt/overbudget/cancelled input cannot produce a plan',async()=>{
 const s=await input(),f=await writeCompleteContract(s);await assert.rejects(planCompleteRestore(f.slice(0,-1)));await assert.rejects(planCompleteRestore(f,{limits:{totalDecodedBytes:1}}));
 const c=new AbortController();c.abort();await assert.rejects(planCompleteRestore(f,{signal:c.signal}),{name:'AbortError'});
});
