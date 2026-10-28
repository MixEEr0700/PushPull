import test from 'node:test';
import assert from 'node:assert/strict';
import * as editor from '../model/performance-editor.mjs';
import {buildPlan,views,PLAN_ID} from '../model/v2-plan.mjs';
import {newPerformance,flatten} from '../model/performance.mjs';
const exercises=type=>views(buildPlan('compact99'),PLAN_ID,type,{});
const unilateral=exercises('PULL A').find(e=>e.id==='PULL-A-1');
const bilateral=exercises('PUSH A')[0],drop=exercises('PUSH A').find(e=>e.id==='PUSH-A-5');
const fill=p=>{for(const r of p.rows)for(const s of r.segments){s.kg='24';s.reps='10'}return p};
function setup(ex,p=fill(newPerformance(ex)),entry=true){editor.clear();globalThis.confirm=()=>true;globalThis.alert=()=>{};return editor.editor(ex,'s',entry?{performance:p}:null,entry?null:{performance:p});}
function act(ex,action,row=0,common=false,segment=0){const form={dataset:{id:ex.id,session:'s'},innerHTML:''};const b={dataset:{richAction:action,row:String(row),segment:String(segment),commonPair:String(common)},closest:()=>form};editor.click({target:{closest:()=>b}});return form.innerHTML;}
const count=(html,needle)=>(html.match(new RegExp(needle,'g'))||[]).length;
test('99: one compact row per verified pair renders without changing any source record or ID, tonnage once per side',()=>{
 const p=fill(newPerformance(unilateral)),before=structuredClone(p),html=setup(unilateral,p);
 assert.equal(count(html,'data-compact-row'),3);assert.equal(count(html,'data-common-pair="true"'),9);
 assert.equal(count(html,'data-rich-action="side-mode"'),0);assert.doesNotMatch(html,/Seria 1 \(L\/P\)|Wspólna edycja|Rozdziel|Scal L\/P|tempo|RIR/);
 assert.deepEqual(editor.performanceFor(unilateral.id,'s'),before);assert.deepEqual(p,before);
 assert.equal(flatten(editor.performanceFor(unilateral.id,'s')).reduce((n,s)=>n+Number(s.kg)*Number(s.reps),0),1440);
});
test('99: paired drops add/remove in exact order with independent IDs; no mutation from just viewing',()=>{
 const ex={...drop,sideMode:'required'},p=fill(newPerformance(ex));let html=setup(ex,p);assert.equal(count(html,'data-compact-row'),6);assert.match(html,/>\+1<\/span>/);
 html=act(ex,'add-segment',0,true);let d=editor.state(ex.id,'s');assert.deepEqual(d.performance.rows.map(r=>r.segments.length),[3,3,2,2,2,2]);assert.match(html,/>\+2<\/span>/);
 assert.notEqual(d.performance.rows[0].segments[2].id,d.performance.rows[1].segments[2].id);
 act(ex,'remove-segment',0,true,2);assert.deepEqual(editor.state(ex.id,'s').performance,p);
});
test('99: all first/last ordinary and paired rows can be removed; zero-row drafts never become fictional results',()=>{
 for(const ex of [bilateral,unilateral]){setup(ex);for(let i=0;i<3;i++)act(ex,'remove-set',0,ex===unilateral);assert.equal(editor.state(ex.id,'s').performance.rows.length,0);assert.throws(()=>editor.performanceFor(ex.id,'s'),/Brak serii/);act(ex,'add-set');const p=editor.state(ex.id,'s').performance;assert.equal(p.rows.length,ex===unilateral?2:1);assert.ok(p.rows.every(r=>r.segments[0].kg===''&&r.segments[0].reps===''));}
});
test('99: combined and unknown conventions never get shared inputs or multiply/reinterpret historic data',()=>{
 for(const basis of ['combined',null]){const ex={...unilateral,loadConvention:{...unilateral.loadConvention,basis}},p=fill(newPerformance(ex)),before=structuredClone(p),html=setup(ex,p);assert.match(html,/data-side-exception/);assert.match(html,/readonly data-quick/);assert.equal(count(html,'data-common-pair="true"'),0);assert.deepEqual(editor.performanceFor(ex.id,'s'),before);assert.equal(flatten(before).length,6);}
});
test('99: asymmetry and extra segment metadata remain visible and immutable until explicit confirmed correction',()=>{
 const p=fill(newPerformance(unilateral));p.rows[1].segments[0].kg='21';const before=structuredClone(p),html=setup(unilateral,p);assert.match(html,/L: 10 × 24 kg \| P: 10 × 21 kg/);assert.deepEqual(editor.performanceFor(unilateral.id,'s'),before);
 globalThis.confirm=()=>false;act(unilateral,'merge-left');assert.deepEqual(editor.performanceFor(unilateral.id,'s'),before);
 globalThis.confirm=()=>true;act(unilateral,'merge-right');const after=editor.performanceFor(unilateral.id,'s');assert.equal(after.rows[0].segments[0].kg,'21');assert.deepEqual(after.rows.map(r=>r.id),before.rows.map(r=>r.id));assert.deepEqual(after.rows.map(r=>r.segments[0].id),before.rows.map(r=>r.segments[0].id));
 p.rows[1].segments[0].opaque={note:'zachowaj źródło'};setup(unilateral,p);let warning='';globalThis.alert=m=>warning=m;act(unilateral,'merge-left');assert.match(warning,/metadane/);assert.deepEqual(editor.state(unilateral.id,'s').performance,p);
});
test('99: orphan and duplicate prescribed sides stay exceptional, without silently inferred winning pairing',()=>{
 for(const mode of ['missing','duplicate']){const p=fill(newPerformance(unilateral));if(mode==='missing')p.rows.splice(1,1);else p.rows.push({...structuredClone(p.rows[0]),id:'other-left',segments:[{id:'other-segment',kg:'22',reps:'7'}]});const before=structuredClone(p),html=setup(unilateral,p);assert.match(html,/data-missing-side/);assert.deepEqual(editor.state(unilateral.id,'s').performance,before);assert.throws(()=>editor.performanceFor(unilateral.id,'s'),/para/);}
});
test('99: stale common-row commands fail closed after source asymmetry, retaining every value',()=>{
 const p=fill(newPerformance(unilateral));p.rows[1].segments[0].kg='21';setup(unilateral,p);let warning='';globalThis.alert=m=>warning=m;act(unilateral,'remove-set',0,true);assert.match(warning,/zmieniły/);assert.deepEqual(editor.state(unilateral.id,'s').performance,p);
});
test('99: ordinary 1/2/3 rows and a single drop segment are compact without inventing goals or rows',()=>{
 for(const n of [1,2,3]){const p=fill(newPerformance(bilateral));p.rows.splice(n);const html=setup(bilateral,p);assert.equal(count(html,'data-compact-row'),n);assert.deepEqual(editor.performanceFor(bilateral.id,'s'),p);}
 const p=fill(newPerformance(drop));for(const r of p.rows)r.segments.splice(1);let html=setup(drop,p);assert.equal(count(html,'data-compact-row'),3);html=act(drop,'add-segment');assert.match(html,/>\+1<\/span>/);assert.equal(editor.state(drop.id,'s').performance.rows[0].segments.length,2);
});
test('99: group deletion/readdition restores only a missing prescribed round, never invents group references',()=>{
 const ex=exercises('PULL B').find(e=>e.id==='PULL-B-6-SKI'),p=fill(newPerformance(ex));setup(ex,p);act(ex,'remove-set');act(ex,'add-set');const rows=editor.state(ex.id,'s').performance.rows;
 assert.equal(rows.length,2);assert.deepEqual(new Set(rows.map(r=>r.setId)),new Set(p.rows.map(r=>r.setId)));assert.ok(rows.every(r=>r.groupId===ex.group.id&&r.round===ex.targets.find(t=>t.id===r.setId).order+1));assert.notEqual(rows.at(-1).id,p.rows[0].id);assert.equal(rows.at(-1).segments[0].kg,'');act(ex,'add-set');assert.equal(editor.state(ex.id,'s').performance.rows.length,2);
});
