import test from 'node:test';
import assert from 'node:assert/strict';
import {summary,editor,state,forget} from '../model/performance-editor.mjs';
import {buildPlan,views,PLAN_ID} from '../model/v2-plan.mjs';
import {newPerformance,flatten} from '../model/performance.mjs';
const ex=views(buildPlan('summary-test'),PLAN_ID,'PULL B',{}).find(e=>e.id==='PULL-B-1');
const text=html=>{const rows=html.split('<span class="last-series-row">').slice(1);return rows.length?rows.map(r=>r.replace(/<[^>]*>/g,'')):[html.replace(/<[^>]*>/g,'')];};
function result(exercise=ex){const performance=newPerformance(exercise);for(const r of performance.rows)for(const s of r.segments){s.kg='105';s.reps='15';}return {performance};}
const lines=(e,targets=ex.targets,asSets=false)=>text(summary(e,targets,asSets));

test('three prescribed L/P pairs compress to exactly one line; rendering leaves data, projections and editor drafts unchanged',()=>{
 const e=result(),before=structuredClone(e),projection=flatten(e.performance);
 editor(ex,'summary-draft',e,null);const draft=state(ex.id,'summary-draft');
 assert.deepEqual(lines(e),['L/P 15 × 105 kg']);assert.deepEqual(e,before);assert.deepEqual(flatten(e.performance),projection);assert.deepEqual(state(ex.id,'summary-draft'),draft);forget(ex.id,'summary-draft');
});
test('only asymmetric third set displays L/P, in actual recorded order',()=>{
 const e=result();e.performance.rows[4].segments[0].reps='12';e.performance.rows[5].segments[0].reps='14';e.performance.rows.reverse();
 assert.deepEqual(lines(e),['Seria 3: L 12 × 105 kg · P 14 × 105 kg','Seria 2: L/P 15 × 105 kg','Seria 1: L/P 15 × 105 kg']);
 e.performance.rows.find(r=>r.setId===ex.targets[2].id&&r.side==='right').segments[0].kg='95';
 assert.equal(lines(e)[0],'Seria 3: L 12 × 105 kg · P 14 × 95 kg');
});
test('different sets with equal sides have one row per actual set; optional separated and unsplit records are supported',()=>{
 const e=result();for(const r of e.performance.rows.filter(r=>r.setId===ex.targets[2].id))r.segments[0].reps='12';
 assert.deepEqual(lines(e),['Seria 1: L/P 15 × 105 kg','Seria 2: L/P 15 × 105 kg','Seria 3: L/P 12 × 105 kg']);
 const optional={...ex,sideMode:'optional'},unsplit=result(optional);assert.deepEqual(lines(unsplit),['15 × 105 kg']);
 unsplit.performance.rows=structuredClone(e.performance.rows);assert.deepEqual(lines(unsplit),lines(e));
 const legacy=result({...ex,sideMode:null});legacy.performance.rows[2].segments[0].kg='90';assert.deepEqual(lines(legacy),['Seria 1: 15 × 105 kg','Seria 2: 15 × 105 kg','Seria 3: 15 × 90 kg']);
});
test('incomplete pairs stay visible; identical balanced extras compress without changing their identities',()=>{
 const e=result();e.performance.rows.splice(5,1);assert.equal(lines(e).length,3);assert.match(lines(e)[2],/Seria 3: L 15 × 105 kg · para L\/P nieustalona/);
 const extra=structuredClone(result().performance.rows.slice(0,2));extra.forEach(r=>{r.id=crypto.randomUUID();r.setId=null;});e.performance.rows=extra;
 assert.deepEqual(lines(e),['L/P 15 × 105 kg']);
 e.performance.rows.push(...structuredClone(extra).map(r=>({...r,id:crypto.randomUUID()})));
 assert.deepEqual(lines(e),['L/P 15 × 105 kg']); // balanced, identical actual values; no pairing inferred
 e.performance.rows[0].segments[0].reps='13';assert.equal(lines(e).length,2);assert.match(lines(e)[0],/L 13.*P 15/);
 const bad=result();bad.performance.rows[0].segments[0].kg='';assert.match(summary(bad,ex.targets),/niepełny wynik/);assert.notDeepEqual(lines(bad),['L/P 15 × 105 kg']);
 bad.performance.rows[0].segments=undefined;assert.match(summary(bad,ex.targets),/Brak pełnych danych/);assert.match(summary({performance:{rows:[]}}),/Brak pełnych danych/);
 // More physical records than targets: extra target-less results stay visible.
 const more=result(),onePair=structuredClone(result().performance.rows.slice(0,2));onePair.forEach(r=>r.setId=null);onePair[0].segments[0].reps='10';more.performance.rows.push(...onePair);
 assert.equal(lines(more).length,4);assert.match(lines(more)[3],/^Seria 4: L 10 × 105 kg · P 15 × 105 kg$/);
});
test('drops preserve segment order and backoff remains labelled even if weights/reps are identical',()=>{
 const m=buildPlan('summary-special'),drop=views(m,PLAN_ID,'PUSH A',{}).find(e=>e.id==='PUSH-A-5'),backoff=views(m,PLAN_ID,'PUSH A',{}).find(e=>e.id==='PUSH-A-3');
 const d=result(drop);d.performance.rows[0].segments[1].kg='30';d.performance.rows[0].segments[1].reps='6';
 assert.match(lines(d,drop.targets)[0],/dropset: 15 × 105 kg → 6 × 30 kg/);assert.equal(lines(d,drop.targets).length,3);
 assert.match(lines(result(backoff),backoff.targets)[2],/Seria 3 · back-off: 15 × 105 kg/);
});
test('rounds remain meaningful; independent A/B cards have independent compact results; escaping is retained',()=>{
 const p=views(buildPlan('summary-rounds'),PLAN_ID,'PULL B',{}),a=p.find(e=>e.id==='PULL-B-6-SKI'),b=p.find(e=>e.id==='PULL-B-6-SHRUGS');
 assert.deepEqual(lines(result(a),a.targets),['Runda 1: 15 × 105 kg','Runda 2: 15 × 105 kg']);
 assert.deepEqual(lines(result(a),a.targets,true),['15 × 105 kg']);const other=result(b);other.performance.rows.forEach(r=>r.segments[0].kg='20');assert.deepEqual(lines(other,b.targets,true),['15 × 20 kg']);
 const e=result();e.performance.rows[0].segments[0].kg='<img onerror=alert(1)>';assert.ok(!summary(e,ex.targets).includes('<img'));assert.match(summary(e,ex.targets),/&lt;img/);
});

test('missing prescribed rows and unrelated targets cannot renumber actual extra sets',()=>{
 const e=result();e.performance.rows=e.performance.rows.slice(0,2);const extra=structuredClone(e.performance.rows);extra.forEach(r=>{r.id=crypto.randomUUID();r.setId=null;r.segments[0].kg='90';});e.performance.rows.push(...extra);
 const other={id:'unrelated-target',order:99,positionId:'other'};
 assert.deepEqual(lines(e,[...ex.targets,other]),['Seria 1: L/P 15 × 105 kg','Seria 2: L/P 15 × 90 kg']);
 const before=structuredClone(e);summary(e,ex.targets);assert.deepEqual(e,before);
});

test('2, 3 and 8 equal sets including individually added plain rows compress independent of identities',()=>{
 for(const n of [2,3,8]){const e=result({...ex,sideMode:'optional'});e.performance.rows=Array.from({length:n},(_,i)=>({...structuredClone(e.performance.rows[0]),id:'row'+i,setId:i<ex.targets.length?ex.targets[i].id:null}));const before=structuredClone(e);assert.deepEqual(lines(e),['15 × 105 kg']);assert.deepEqual(e,before);e.performance.rows[n-1].segments[0].reps='14';assert.equal(lines(e).length,n);}
});

test('balanced totals cannot hide mismatched prescribed sides or opaque row semantics',()=>{
 const e=result();e.performance.rows=[e.performance.rows[0],e.performance.rows[3]];assert.equal(lines(e).length,2);assert.ok(lines(e).every(s=>s.includes('nieustalona')));
 const d=result({...ex,sideMode:'optional'});d.performance.rows[1].opaqueMeaning='different';assert.equal(lines(d).length,3);
 delete d.performance.rows[1].opaqueMeaning;d.performance.rows[1].segments[0].kg='105.0';assert.deepEqual(lines(d),['15 × 105 kg']);
});
