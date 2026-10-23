import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {initialize} from '../model/journal.mjs';
import {activate,PLAN_ID} from '../model/v2-plan.mjs';
import {stagePlan,stageActivation} from '../model/plan-import.mjs';
import {backupSummary,compareBackupData,inspectFullBackup,createLegacyModel,exportBackup} from '../model/legacy-model.mjs';
const fixture=()=>JSON.parse(readFileSync('tests/fixtures/v1.json'));
function states(){let b=fixture();b.trainingJournal=initialize('owner-B');activate(b,'2026-10-23T10:00:00.000Z');const p=JSON.parse(readFileSync('tests/fixtures/plan-test-3x5.json'));const a=stageActivation(stagePlan(b,p),p.planVersion.id,'2026-10-23T11:00:00.000Z');return {a,b};}

test('preview compares actual complete versions and same-ID changes without inventing V1 or dates',()=>{
 const {a,b}=states(),before=structuredClone(a);const s=backupSummary(a);
 assert.equal(s.completePlans,2);assert.equal(s.activePlan,'TEST 3×5');assert.equal(s.createdAt,null);assert.equal(s.activations,2);
 assert.deepEqual(s.plans.map(p=>p.id),[PLAN_ID,'synthetic-v3']);assert.equal(backupSummary(fixture()).plans.length,0);
 b.entries[0].kg='1';b.entries[0].series=null;
 const c=compareBackupData(b,a);assert.equal(c.identical,false);assert.equal(c.results.changed,1);assert.equal(c.sessions.localOnly,0);
 assert.equal(compareBackupData(a,a).identical,true);assert.deepEqual(a,before);
});

test('full source-backed v3 is verified before summary; damage and unsupported JSON never create a preview',async()=>{
 const {a,b}=states(),db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto:globalThis.crypto});
 const {catalog}=db.parseBackup(a),document=await createLegacyModel(JSON.stringify({format:'pushpull-backup',version:2,data:a,catalog,archives:[]}),{ownerId:'owner-B',createdAt:'2026-10-23T12:00:00.000Z'});
 const raw=await exportBackup(document),p=await inspectFullBackup(raw,b);
 assert.equal(p.summary.activePlan,'TEST 3×5');assert.equal(p.summary.createdAt,'2026-10-23T12:00:00.000Z');assert.equal(p.summary.completePlans,2);assert.equal(p.comparison.identical,false);
 assert.equal((await inspectFullBackup(JSON.stringify(fixture()))).summary.createdAt,null);
 for(const text of ['{broken','null','{"version":999}',raw.replace('TEST 3×5','damaged')])await assert.rejects(inspectFullBackup(text,b));
});
