import test from 'node:test';
import assert from 'node:assert/strict';
import * as editor from '../model/performance-editor.mjs';
import {buildPlan,views,PLAN_ID} from '../model/v2-plan.mjs';
import {newPerformance,identicalSeries} from '../model/performance.mjs';
import {editorValueValid} from '../model/workout-drafts.mjs';
const ex=views(buildPlan('pairs-test'),PLAN_ID,'PULL A',{}).find(e=>e.id==='PULL-A-1');
function setup(){editor.clear();editor.editor(ex,'s',null,null);globalThis.confirm=()=>true;globalThis.alert=()=>{};}
function act(action,row=0){const form={dataset:{id:ex.id,session:'s'},innerHTML:''},button={dataset:{richAction:action,row:String(row)},closest:()=>form};editor.click({target:{closest:()=>button}});return editor.state(ex.id,'s');}
test('deletion removes the entire first pair including IDs and adding restores exactly two blank rows',()=>{setup();let d=editor.state(ex.id,'s'),old=structuredClone(d.performance.rows);d=act('remove-set');assert.deepEqual(d.performance.rows,old.slice(2));act('remove-set');d=act('remove-set');assert.equal(d.performance.rows.length,0);d=act('add-set');assert.equal(d.performance.rows.length,2);assert.deepEqual(d.performance.rows.map(r=>r.side),['left','right']);assert.ok(d.performance.rows.every(r=>r.segments[0].kg===''));});
test('explicit merge copies only chosen values, retaining both sides, segment IDs and metadata; cancel retains asymmetry',()=>{
 setup();const d=editor.state(ex.id,'s');d.performance.rows.forEach(r=>{r.segments[0].kg=r.side==='left'?'40':'35';r.segments[0].reps='9'});editor.restore(ex.id,'s',d);editor.editor(ex,'s',null,null);
 globalThis.confirm=()=>false;assert.deepEqual(act('merge-left').performance,d.performance);
 globalThis.confirm=()=>true;const merged=act('merge-right');assert.deepEqual(merged.performance.rows.map(r=>r.id),d.performance.rows.map(r=>r.id));assert.deepEqual(merged.performance.rows.map(r=>r.segments[0].id),d.performance.rows.map(r=>r.segments[0].id));assert.equal(merged.performance.rows[0].segments[0].kg,'35');assert.equal(merged.performance.rows[2].segments[0].kg,'40');
});
test('merge refuses different drop structures and metadata; never discards the longer segment sequence',()=>{
 setup();const d=editor.state(ex.id,'s');d.performance.rows[1].segments.push({id:'extra-drop',kg:'10',reps:'6'});editor.restore(ex.id,'s',d);editor.editor(ex,'s',null,null);let message='';globalThis.alert=m=>message=m;const after=act('merge-left');assert.deepEqual(after.performance,d.performance);assert.match(message,/strukturę/);const copied=act('copy');assert.deepEqual(copied.performance.rows[1].segments.at(-1),d.performance.rows[1].segments.at(-1));
});
test('ambiguous odd unprescribed rows do not acquire fictional pairs; adjacent complete pairs recover without ID changes',()=>{
 setup();const d=editor.state(ex.id,'s');for(const r of d.performance.rows){r.setId=null;r.segments[0].kg='20';r.segments[0].reps='8'}d.performance.rows.pop();d.sidePairs=[];const before=structuredClone(d.performance);editor.restore(ex.id,'s',d);editor.editor(ex,'s',null,null);assert.deepEqual(editor.state(ex.id,'s').performance,before);assert.throws(()=>editor.performanceFor(ex.id,'s'),/para/);
 d.performance.rows.push({...structuredClone(d.performance.rows[0]),id:'new-right',side:'right',segments:[{id:'new-segment',kg:'20',reps:'8'}]});editor.restore(ex.id,'s',d);editor.editor(ex,'s',null,null);assert.equal(editor.performanceFor(ex.id,'s').rows.length,6);
});
test('legacy display equality preserves side, role, segment and opaque semantic differences; backup evidence contract remains strict',()=>{
 const rows=[{id:'a',kg:'20',reps:'8'},{id:'b',kg:'20.0',reps:'8'}];assert.ok(identicalSeries(rows));for(const key of ['side','role','opaque']){assert.equal(identicalSeries([rows[0],{...rows[1],[key]:'different'}]),false)}assert.equal(editorValueValid('v2',{performance:{version:2,rows:[]}}),false);
});
