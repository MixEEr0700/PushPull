import test from 'node:test';import assert from 'node:assert/strict';
import {performanceValue} from '../model/performance-editor.mjs';
const row=side=>({id:'id-'+side,setId:'set-1',side,groupId:null,round:null,segments:[{id:'segment-'+side,kg:'20',reps:'8'}]});
test('an explicit both-sides result can be validated without inventing a second row',()=>{const state={performance:{version:2,loadConvention:{unit:'kg',basis:'per-implement',description:null},rows:[row('both')]},sidePairs:[]},before=structuredClone(state);assert.deepEqual(performanceValue(state),state.performance);assert.deepEqual(state,before)});
test('a missing historical side continues to fail safely',()=>{const state={performance:{version:2,loadConvention:{unit:'kg',basis:'per-implement',description:null},rows:[row('left')]},sidePairs:[]};assert.throws(()=>performanceValue(state),/para L\/P/)});
