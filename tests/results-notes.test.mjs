import test from 'node:test';
import assert from 'node:assert/strict';
import {buildPlan,PLAN_ID,editUserNote} from '../model/v2-plan.mjs';
import {newPerformance,flatten} from '../model/performance.mjs';
import {views} from '../model/v2-plan.mjs';
import {summary,updateQuick} from '../model/performance-editor.mjs';
const model=buildPlan('results-notes'),ex=views(model,PLAN_ID,'PUSH A',{}).find(e=>e.id==='PUSH-A-1');
const command={versionId:PLAN_ID,exerciseId:ex.id,variantId:ex.journalVariantId,noteId:'user:'+PLAN_ID+':'+ex.id,base:'',revision:0,text:'Ł 😀\nNote',recordedAt:'2026-10-28T12:00:00.000Z'};
test('own note delta retains every source field and validates context/revision, not dates',()=>{
 const before=structuredClone(model),{model:next,note}=editUserNote(model,command);
 assert.deepEqual(model,before);assert.equal(note.revision,1);assert.equal(note.text,command.text);
 assert.equal(next.coachInstructions,model.coachInstructions);assert.equal(next.positions,model.positions);
 for(const key of ['versionId','variantId','exerciseId','noteId'])assert.throws(()=>editUserNote(model,{...command,[key]:'foreign'}),/kontekstu/);
 assert.throws(()=>editUserNote(next,command),/zmieniła/);
 const changed=editUserNote(next,{...command,base:note.text,revision:1,text:''});assert.equal(changed.note.revision,2);assert.equal(changed.note.text,'');
 assert.throws(()=>editUserNote(next,{...command,base:note.text,revision:1,text:null}),/treść/);
 const bad=structuredClone(next);bad.userNotes[0].origin='legacy-shared';assert.throws(()=>editUserNote(bad,command),/innego kontekstu/);
 const corrupt=structuredClone(model);corrupt.positions[0].variantId='missing';assert.throws(()=>editUserNote(corrupt,command));
});
test('quick changes only linked main values, never independent corrections/drop children/IDs',()=>{
 const p=newPerformance(ex);p.rows.forEach(r=>{r.segments[0].kg='20';r.segments[0].reps='10'});p.rows[2].segments[0].reps='9';
 p.rows[0].dropOrigin='user';p.rows[0].segments.push({id:'child',kg:'10',reps:'5'});const before=structuredClone(p);
 updateQuick(p.rows.map(r=>r.segments[0]),'reps','12','10');assert.deepEqual(p.rows.map(r=>r.segments[0].reps),['12','12','9']);
 updateQuick(p.rows.map(r=>r.segments[0]),'kg','25','20',[true,false,false]);assert.deepEqual(p.rows.map(r=>r.segments[0].kg),['20','25','25']);
 assert.deepEqual(p.rows[0].segments[1],before.rows[0].segments[1]);assert.deepEqual(p.rows.map(r=>r.id),before.rows.map(r=>r.id));assert.equal(flatten(p).length,4);const empty=[{kg:''},{kg:''}];updateQuick(empty,'kg','25','20',[false,true]);assert.deepEqual(empty,[{kg:'25'},{kg:''}]);
});
test('compact results keep actual group order, semantic differences, sides, complete drops; no backoff copy',()=>{
 const x=views(model,PLAN_ID,'PUSH A',{}).find(e=>e.id==='PUSH-A-3'),p=newPerformance(x);p.rows.forEach(r=>{r.segments[0].kg='20';r.segments[0].reps='3'});
 const before=structuredClone(p),html=summary({performance:p},x.targets,false,true);
 assert.equal((html.match(/class="result-unit"/g)||[]).length,3);assert.doesNotMatch(html,/back-?off/);assert.deepEqual(p,before);
 const d=views(model,PLAN_ID,'PUSH A',{}).find(e=>e.id==='PUSH-A-5'),dp=newPerformance(d);dp.rows.forEach((r,i)=>{r.segments[0].kg='20';r.segments[0].reps='3';r.segments[1].kg=String(10-i);r.segments[1].reps='3'});
 assert.match(summary({performance:dp},d.targets,false,true),/3×20 \+ drop 3×10/);assert.equal((summary({performance:dp},d.targets,false,true).match(/class="result-unit"/g)||[]).length,3);
 const plain=newPerformance(ex);plain.rows.forEach(r=>{r.segments[0].kg='20';r.segments[0].reps='3'});assert.equal((summary({performance:plain},ex.targets,false,true).match(/class="result-unit"/g)||[]).length,1);
});
