import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {writeCompactModel} from '../model/compact-backup-writer.mjs';
import {createCompactPreview} from '../model/compact-backup-preview.mjs';
import {previewFixture} from './fixtures/compact-preview-fixture.mjs';
const fixture=()=>previewFixture(JSON.parse(readFileSync('tests/fixtures/v1.json')),JSON.parse(readFileSync('tests/fixtures/plan-test-3x5.json')));
test('complete native V2 preview verifies existing domain rules without exposing contents',async()=>{
 const source=fixture(),before=structuredClone(source),p=createCompactPreview(),r=await p.preview(await writeCompactModel(source),{getRevision:()=>4});
 assert.equal(r.canRestore,false);assert.equal(r.revisionChecked,true);assert.equal(r.sessions,source.data.sessions.length);assert.equal(r.results,source.data.entries.length);assert.equal(r.archives,source.archives.length);assert.equal(r.settingsPresent,true);assert.equal(r.plans,source.catalog.plans.length);assert.equal(r.catalogVersions,source.catalog.planVersions.length);assert.ok(r.nativePlanVersions>0);assert.deepStrictEqual(source,before);assert.deepStrictEqual(await p.read(),r);assert.ok(Object.isFrozen(r));assert.ok(!JSON.stringify(r).includes(source.data.exercises['PUSH A'][0].name));
});
test('transport-valid but semantically inconsistent models and plans fail closed',async()=>{
 for(const change of [s=>s.data.trainingJournal=false,s=>s.data.entries[0].sessionId='missing-private-id',s=>s.data.activeId='missing',s=>s.catalog.sessionVersions={},s=>s.data.trainingJournal.sessionSnapshots[0].sessionId='missing',s=>s.data.trainingJournal.model.planVersions[0].id='missing',s=>s.archives[0].id=s.archives[1].id,s=>s.data.trainingJournal.importedPlans[0].approval.status='not-approved',s=>s.data.trainingJournal.importedPlans[0].continuity[0].previousPositionId='missing',s=>s.data.entries.find(e=>e.performance).series[0].kg='999999']){
  const s=fixture();change(s);const p=createCompactPreview();await assert.rejects(p.preview(await writeCompactModel(s)),e=>{assert.ok(['invalid-model','unsupported-model'].includes(e.code));assert.ok(!e.message.includes('private-id'));return true;});assert.equal(await p.read(),null);
 }
});
test('unsupported graph shapes, resource limits and corrupt containers are not successful previews',async()=>{
 const p=createCompactPreview();await assert.rejects(p.preview(await writeCompactModel({data:{}})),{code:'unsupported-model'});
 const file=await writeCompactModel(fixture());await assert.rejects(p.preview(file.slice(0,-1)),{code:'invalid-container'});
 await assert.rejects(p.preview(file,{limits:{totalDecodedBytes:1}}),{code:'limit'});assert.equal(await p.read(),null);
});
test('revision changes during preview and after publication invalidate reports',async()=>{
 const file=await writeCompactModel(fixture()),p=createCompactPreview();let n=0;
 await assert.rejects(p.preview(file,{getRevision:()=>n++}),{code:'revision'});assert.equal(await p.read(),null);
 let revision=1;await p.preview(file,{getRevision:()=>revision});revision++;await assert.rejects(p.read(),{code:'revision'});assert.equal(await p.read(),null);
 await assert.rejects(p.preview(file,{getRevision:()=>{throw Error('secret credential');}}),e=>e.code==='source-unavailable'&&!e.message.includes('secret'));
});
test('abort and superseded operations cannot publish late summaries',async()=>{
 const file=await writeCompactModel(fixture()),p=createCompactPreview();let release;
 const pending=p.preview(file,{getRevision:()=>new Promise(r=>release=r)});p.cancel();release(1);await assert.rejects(pending,{name:'AbortError'});assert.equal(await p.read(),null);
 const stale=p.preview(file,{getRevision:()=>new Promise(r=>release=r)});const current=p.preview(file);release(1);await assert.rejects(stale,{name:'AbortError'});const latest=await current;assert.equal(await p.read(),latest);
 const c=new AbortController();c.abort();await assert.rejects(p.preview(file,{signal:c.signal}),{name:'AbortError'});
});
test('source probe failures clear a published report; cancellation does not wait for a stalled probe',async()=>{
 const file=await writeCompactModel(fixture()),p=createCompactPreview();let available=true;
 await p.preview(file,{getRevision:()=>{if(!available)throw Error('private token');return 'root';}});available=false;
 await assert.rejects(p.read(),{code:'source-unavailable'});assert.equal(await p.read(),null);
 let release;const pending=p.preview(file,{getRevision:()=>new Promise(r=>release=r)});p.cancel();
 await Promise.race([assert.rejects(pending,{name:'AbortError'}),new Promise((_,reject)=>setTimeout(()=>reject(Error('cancel stalled')),200))]);release('late');assert.equal(await p.read(),null);
});
test('large opaque archives and settings remain accounted for but are never claimed restorable',async()=>{
 const s=fixture();s.archives[0].raw='archive \\ud800'.repeat(262144);const p=createCompactPreview(),f=await writeCompactModel(s),r=await p.preview(f);
 assert.equal(r.archives,s.archives.length);assert.ok(r.opaqueArchives>0);assert.equal(r.canRestore,false);assert.equal(r.revisionChecked,false);assert.ok(r.warnings.length>=3);
 const b=new Uint8Array(await f.arrayBuffer());b[8]^=1;await assert.rejects(p.preview(new Blob([b])),{code:'invalid-container'});assert.equal(await p.read(),null);
 b[8]^=1;b[b.length-1]^=1;await assert.rejects(p.preview(new Blob([b])),{code:'invalid-container'});
 const future=fixture();future.data.trainingJournal.model.planVersions[0].executionVersion=99;await assert.rejects(p.preview(await writeCompactModel(future)),{code:'unsupported-model'});
});

test('a stalled freshness recheck is cancellable without publishing old data',async()=>{
 const p=createCompactPreview(),file=await writeCompactModel(fixture());let calls=0,release;
 await p.preview(file,{getRevision:()=>++calls<=2?'root':new Promise(r=>release=r)});
 const pending=p.read();p.cancel();await Promise.race([assert.rejects(pending,{name:'AbortError'}),new Promise((_,reject)=>setTimeout(()=>reject(Error('read cancellation stalled')),200))]);release('late');assert.equal(await p.read(),null);
});

test('legacy-only complete v2 is supported, but native references without a journal are refused',async()=>{
 const s=previewFixture(JSON.parse(readFileSync('tests/fixtures/v1.json')),null,false),p=createCompactPreview();
 const r=await p.preview(await writeCompactModel(s));assert.equal(r.nativePlanVersions,0);assert.equal(r.plans,s.catalog.plans.length);
 s.entriesExtension='unknown';await assert.rejects(p.preview(await writeCompactModel(s)),{code:'unsupported-model'});delete s.entriesExtension;
 s.data.entries[0].journalSnapshotId='missing-journal';await assert.rejects(p.preview(await writeCompactModel(s)),{code:'invalid-model'});assert.equal(await p.read(),null);
});
