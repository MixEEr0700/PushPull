import test from 'node:test';
import assert from 'node:assert/strict';
import {editor,state,restore,forget,summary,parameters} from '../model/performance-editor.mjs';
import {newPerformance,flatten} from '../model/performance.mjs';
import {buildPlan,views,PLAN_ID} from '../model/v2-plan.mjs';
const exercises=views(buildPlan('compact95'),PLAN_ID,'PUSH A',{}),ex=exercises[0];
const result=(reps=['10','10','9'])=>{const performance=newPerformance(ex);performance.rows.forEach((r,i)=>{r.segments[0].kg='80';r.segments[0].reps=reps[i]});return {performance};};
const text=h=>h.replace(/<[^>]*>/g,'');
test('95: all 10/10/9 values retain order; all equal values compress; rendering never changes rows',()=>{
 for(const [reps,want] of [[['10','10','9'],/10 × 80 kg.*10 × 80 kg.*9 × 80 kg/],[['10','9','10'],/10 × 80 kg.*9 × 80 kg.*10 × 80 kg/],[['10','10','10'],/^10 × 80 kg$/]]){
  const e=result(reps),before=structuredClone(e);assert.match(text(summary(e,ex.targets)),want);assert.deepEqual(e,before);
 }
 const one=result(['7']);one.performance.rows.splice(1);assert.equal(text(summary(one,ex.targets)),'7 × 80 kg');
});
test('95: quick fields seed actual individual values, preserve extra/removed rows and use fresh identities',()=>{
 const e=result(),before=structuredClone(e);e.performance.rows.splice(1,1);e.performance.rows.push({...structuredClone(e.performance.rows[0]),id:'extra',setId:null});
 const expected=structuredClone(e),html=editor(ex,'new-session',null,e),d=state(ex.id,'new-session');assert.deepEqual(e,expected);
 assert.match(html,/data-quick="reps"[^>]*value="10"/);assert.match(html,/data-quick="kg"[^>]*value="80"/);
 assert.deepEqual(d.performance.rows.map(r=>r.segments[0].reps),['10','9','10']);assert.equal(d.performance.rows.at(-1).setId,null);
 assert.ok(!d.performance.rows.some(r=>e.performance.rows.some(old=>old.id===r.id)));assert.deepEqual(before.performance.rows.map(r=>r.segments[0].reps),['10','10','9']);
 const ids=d.performance.rows.map(r=>r.id);editor(ex,'new-session',null,result(['5','5','5']));assert.deepEqual(state(ex.id,'new-session').performance.rows.map(r=>r.id),ids);forget(ex.id,'new-session');
});
test('95: restored editor draft takes precedence, including unfinished Unicode values and row identities',()=>{
 const draft={performance:result().performance,open:false,custom:true};draft.performance.rows[0].segments[0].kg='80,';draft.performance.rows[2].segments[0].reps='９';restore(ex.id,'draft',draft);
 const html=editor(ex,'draft',null,result(['5','5','5']));assert.match(html,/value="80,"/);assert.deepEqual(state(ex.id,'draft').performance,draft.performance);forget(ex.id,'draft');
});
test('95: incompatible load or target context is never used to seed a new result',()=>{
 for(const wrong of ['load','target']){const e=result();if(wrong==='load')e.performance.loadConvention.unit='lb';else e.performance.rows[0].setId='foreign-target';editor(ex,wrong,null,e);assert.equal(state(ex.id,wrong).performance.rows[0].segments[0].kg,'');forget(ex.id,wrong);}
});
test('95: compact plan text preserves real ranges, tempo, unknown values and backoff/drop roles',()=>{
 assert.equal(parameters({...ex,targets:ex.targets.map(t=>({...t,reps:{min:8,max:10},tempo:[2,1,1,1],rir:{min:0,max:0}}))}),'3 × 8–10 | tempo 2111 | RIR 0');
 assert.doesNotMatch(parameters(exercises.find(e=>e.id==='PUSH-A-3')),/back-off/);assert.ok(exercises.find(e=>e.id==='PUSH-A-3').targets.some(t=>t.role==='backoff'));assert.match(parameters(exercises.find(e=>e.id==='PUSH-A-5')),/drop/);
 assert.equal(parameters({...ex,targets:[{reps:null,tempo:null,rir:null,role:'main'}]}),'1 × nieokreślone | tempo nieokreślone | RIR nieokreślone');
});
test('95: equal numeric values with different side/role/segment semantics never become one fictional result',()=>{
 const e=result(['10','10','10']);e.performance.rows[1].side='left';const html=summary(e,ex.targets);assert.match(text(html),/L 10 × 80 kg/);assert.equal((html.match(/last-series-row/g)||[]).length,3);
 const other=result(['10','10','10']),before=flatten(other.performance);const targets=structuredClone(ex.targets);targets[2].role='backoff';assert.doesNotMatch(summary(other,targets),/back-off/);assert.equal((summary(other,targets).match(/last-series-row/g)||[]).length,3);assert.deepEqual(flatten(other.performance),before);
});

test('95: identical drops compact the entire ordered segment sequence, not its first pair',()=>{
 const drop=exercises.find(e=>e.id==='PUSH-A-5'),performance=newPerformance(drop);
 for(const r of performance.rows){r.segments[0].kg='20';r.segments[0].reps='10';r.segments[1].kg='10';r.segments[1].reps='6';}
 const before=structuredClone(performance);assert.equal(text(summary({performance},drop.targets)),'dropset: 10 × 20 kg → 6 × 10 kg');assert.deepEqual(performance,before);
 performance.rows[2].segments[1].reps='5';assert.equal((summary({performance},drop.targets).match(/last-series-row/g)||[]).length,3);
});
