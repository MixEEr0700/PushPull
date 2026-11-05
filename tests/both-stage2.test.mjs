import test from 'node:test';import assert from 'node:assert/strict';
import {performanceValue} from '../model/performance-editor.mjs';
const row=side=>({id:'id-'+side,setId:'set-1',side,groupId:null,round:null,segments:[{id:'segment-'+side,kg:'20',reps:'8'}]});
test('an explicit both-sides result can be validated without inventing a second row',()=>{const state={performance:{version:2,loadConvention:{unit:'kg',basis:'per-implement',description:null},rows:[row('both')]},sidePairs:[]},before=structuredClone(state);assert.deepEqual(performanceValue(state),state.performance);assert.deepEqual(state,before)});
test('a missing historical side continues to fail safely',()=>{const state={performance:{version:2,loadConvention:{unit:'kg',basis:'per-implement',description:null},rows:[row('left')]},sidePairs:[]};assert.throws(()=>performanceValue(state),/para L\/P/)});

test('only fresh editor results become both; an existing asymmetric entry retains sides and source values',async()=>{
 const {buildPlan,views,PLAN_ID}=await import('../model/v2-plan.mjs');const {newPerformance}=await import('../model/performance.mjs');const editor=await import('../model/performance-editor.mjs');
 const ex=views(buildPlan('both-test'),PLAN_ID,'PULL A',{}).find(e=>e.id==='PULL-A-1');ex.loadConvention={unit:'kg',basis:null,description:null};
 const old=newPerformance(ex);old.loadConvention.basis='per-implement';for(const r of old.rows)for(const s of r.segments){s.kg='20';s.reps='8';}const before=structuredClone(old);
 editor.clear();editor.editor(ex,'new',null,{performance:old});assert.ok(editor.state(ex.id,'new').performance.rows.every(r=>r.side==='both'));assert.deepEqual(old,before);
 old.rows[1].segments[0].kg='21';const asymmetric=structuredClone(old);editor.editor(ex,'old',{performance:old},null);assert.deepEqual(editor.performanceFor(ex.id,'old'),asymmetric);assert.deepEqual(old,asymmetric);
});
