import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {writeCompactModel} from '../model/compact-backup-writer.mjs';
import {inspectCompactRestore} from '../model/compact-backup-restore.mjs';
import {previewFixture} from './fixtures/compact-preview-fixture.mjs';
const fixture=()=>{const s=previewFixture(JSON.parse(readFileSync('tests/fixtures/v1.json')),JSON.parse(readFileSync('tests/fixtures/plan-test-3x5.json')));delete s.settings;delete s.metadata;return s;};
test('PPC1 adapts full validated native source without loss or mutation',async()=>{
 const s=fixture(),old=structuredClone(s),p=await inspectCompactRestore(await writeCompactModel(s),s.data);assert.deepStrictEqual(p.source,s);assert.deepStrictEqual(s,old);assert.equal(p.comparison.identical,true);assert.equal(p.format,'PPC1');assert.equal(p.summary.sessions,s.data.sessions.length);
});
test('unsupported separate settings/draft evidence cannot be silently dropped',async()=>{
 for(const key of ['settings','metadata','drafts']){const s=fixture();s[key]={private:'must remain'};await assert.rejects(inspectCompactRestore(await writeCompactModel(s)),e=>!e.message.includes('must remain'));}
});
test('corrupt, incomplete and semantically bad files refuse staging',async()=>{
 const s=fixture(),f=await writeCompactModel(s);await assert.rejects(inspectCompactRestore(f.slice(0,-1)));delete s.catalog;await assert.rejects(inspectCompactRestore(await writeCompactModel(s)));
 const bad=fixture();bad.data.activeId='missing';await assert.rejects(inspectCompactRestore(await writeCompactModel(bad)));
 const c=new AbortController();c.abort();await assert.rejects(inspectCompactRestore(f,null,{signal:c.signal}),{name:'AbortError'});
});
