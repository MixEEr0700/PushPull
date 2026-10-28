import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import * as editor from '../model/performance-editor.mjs';
import {buildPlan,views,PLAN_ID} from '../model/v2-plan.mjs';
import {flatten,newPerformance,validatePerformance,comparison} from '../model/performance.mjs';
import {captureSessionSnapshot} from '../model/training-model.mjs';
import {createProtocol,materialize} from '../model/journal-protocol.mjs';
import {parseModelBackup} from '../model/legacy-model.mjs';
import {exportBackupV4} from '../model/backup-v4-export.mjs';
import {exportBackupV5} from '../model/backup-v5.mjs';
import {exportBackupV6,decodeBackup} from '../model/backup-v6.mjs';
import {nativeData,AT,sourceV3} from './fixtures/backup-v4-fixture.mjs';
const model=buildPlan('issue101'),ex=(type,id)=>views(model,PLAN_ID,type,{}).find(x=>x.id===id);
const optional=ex('PUSH A','PUSH-A-6'),required=ex('PULL A','PULL-A-1'),plain=ex('PUSH A','PUSH-A-1'),drop=ex('PUSH A','PUSH-A-5');
const current=x=>editor.state(x.id,'s');
const fill=p=>{for(const r of p.rows)for(const s of r.segments){s.kg='24';s.reps='10'}return p};
const form=x=>({dataset:{id:x.id,session:'s'},innerHTML:''});
function setup(x,p=null){editor.clear();globalThis.confirm=()=>true;globalThis.alert=()=>{};editor.editor(x,'s',p?{performance:p}:null,null);}
function act(x,action,row=0,segment=0,common=false){const f=form(x),b={dataset:{richAction:action,row:String(row),segment:String(segment),commonPair:String(common)},closest:()=>f};editor.click({target:{closest:()=>b}});return f.innerHTML;}
function change(x,field,value){const f=form(x);editor.change({target:{value,closest:()=>f,matches:s=>s.split(',').includes('['+field+']')}});return f.innerHTML;}
function checkResult(x,p){const snap=captureSessionSnapshot(model,{id:'snap',sessionId:'session',planVersionId:PLAN_ID,unitId:model.positions.find(y=>y.id===x.positionId).unitId,startedAt:AT});const series=flatten(p),entry={exerciseId:x.id,journalPositionId:x.positionId,journalVariantId:x.journalVariantId,performance:p,series,kg:series[0].kg,reps:series[0].reps};return validatePerformance(p,snap,entry);}

test('101: optional L/P survives delete-all, JSON draft restart and add with one UI row and two blank records',()=>{
 setup(optional);act(optional,'sides');assert.equal(current(optional).executionMode,'paired');for(let i=0;i<3;i++)act(optional,'remove-set');
 const empty=JSON.parse(JSON.stringify(current(optional)));assert.equal(empty.performance.rows.length,0);assert.throws(()=>editor.performanceFor(optional.id,'s'),/Brak serii/);
 editor.clear();editor.restore(optional.id,'s',empty);editor.editor(optional,'s',null,null);const html=act(optional,'add-set'),p=current(optional).performance;
 assert.deepEqual(p.rows.map(r=>r.side),['left','right']);assert.notEqual(p.rows[0].id,p.rows[1].id);assert.notEqual(p.rows[0].segments[0].id,p.rows[1].segments[0].id);assert.equal(p.rows[0].setId,optional.targets[0].id);assert.ok(p.rows.every(r=>r.segments[0].kg===''&&r.segments[0].reps===''));
 assert.equal((html.match(/data-compact-row/g)||[]).length,1);assert.doesNotMatch(html,/data-rich-action="side-mode"|Scal L\/P|Rozdziel L\/P|Seria 1 \(L\/P\)/);fill(p);assert.equal(checkResult(optional,p).length,2);assert.equal(flatten(p).reduce((n,s)=>n+Number(s.kg)*Number(s.reps),0),480);
});
test('101: old empty optional evidence is unknown until explicit choice; single historical results are never doubled',()=>{
 setup(optional);const d=current(optional);d.performance.rows=[];delete d.executionMode;editor.restore(optional.id,'s',d);const html=editor.editor(optional,'s',null,null);assert.match(html,/data-execution-choice/);act(optional,'add-set');assert.equal(current(optional).performance.rows.length,0);
 change(optional,'data-execution-choice','single');act(optional,'add-set');assert.deepEqual(current(optional).performance.rows.map(r=>r.side),[null]);
 setup(optional,fill(newPerformance(optional)));for(let i=0;i<3;i++)act(optional,'remove-set');act(optional,'add-set');assert.deepEqual(current(optional).performance.rows.map(r=>r.side),[null]);
});
test('101: unknown/combined or contradictory plan kg never authorizes adding pairs after deletion',()=>{
 for(const basis of [null,'combined']){const x={...required,loadConvention:{...required.loadConvention,basis}};setup(x);for(let i=0;i<3;i++)act(x,'remove-set');const before=current(x);act(x,'add-set');assert.deepEqual(current(x),before);}
 const p=fill(newPerformance(required));p.loadConvention.basis='per-implement';setup(required,p);assert.match(editor.editor(required,'s',{performance:p},null),/readonly data-quick/);
});
test('101: ad-hoc drop targets the chosen parent, preserves goals/IDs, uses explicit marker and blank segment',()=>{
 const p=fill(newPerformance(plain)),before=structuredClone(p);setup(plain,p);const html=act(plain,'add-drop');assert.match(html,/data-drop-target/);assert.deepEqual(current(plain).performance,before);
 change(plain,'data-drop-target',p.rows[1].id);const after=current(plain).performance;assert.deepEqual(after.rows[0],before.rows[0]);assert.deepEqual(after.rows[2],before.rows[2]);assert.equal(after.rows[1].dropOrigin,'user');assert.equal(after.rows[1].setId,before.rows[1].setId);assert.deepEqual(after.rows[1].segments[0],before.rows[1].segments[0]);assert.equal(after.rows[1].segments[1].kg,'');
 fill(after);assert.equal(checkResult(plain,after).length,3);assert.equal(flatten(after).reduce((n,s)=>n+Number(s.kg)*Number(s.reps),0),960);assert.match(editor.summary({performance:after},plain.targets),/dropset/);
 const invented=structuredClone(after);delete invented.rows[1].dropOrigin;assert.throws(()=>checkResult(plain,invented),/drop prescription/);
 const bad=structuredClone(after);bad.rows[1].dropOrigin='plan';assert.throws(()=>checkResult(plain,bad),/drop prescription/);
});
test('101: remove all child segments then re-add after restart, including new unprescribed rows',()=>{
 for(const x of [plain,drop]){setup(x);for(let i=0;i<3;i++)act(x,'add-set');const index=current(x).performance.rows.length-1;assert.equal(current(x).performance.rows[index].setId,null);
  change(x,'data-drop-target',current(x).performance.rows[index].id);act(x,'remove-segment',index,1);assert.equal(current(x).performance.rows[index].segments.length,1);assert.equal(current(x).performance.rows[index].dropOrigin,undefined);
  const d=JSON.parse(JSON.stringify(current(x)));editor.clear();editor.restore(x.id,'s',d);editor.editor(x,'s',null,null);change(x,'data-drop-target',d.performance.rows[index].id);assert.equal(current(x).performance.rows[index].segments.length,2);assert.equal(current(x).performance.rows[index].dropOrigin,'user');
 }
 setup(drop);for(const i of [0,1,2])act(drop,'remove-segment',i,1);const ids=current(drop).performance.rows.map(r=>r.segments[0].id);act(drop,'add-drop');change(drop,'data-drop-target',current(drop).performance.rows[2].id);assert.deepEqual(current(drop).performance.rows.map(r=>r.segments[0].id),ids);assert.equal(current(drop).performance.rows[2].segments.length,2);
});
test('101: common L/P drop keeps both sides exactly once; asymmetry remains visible, unpaired target refused',()=>{
 const p=fill(newPerformance(required));setup(required,p);change(required,'data-drop-target',p.rows[0].id);const d=current(required);assert.deepEqual(d.performance.rows.map(r=>r.segments.length),[2,2,1,1,1,1]);assert.notEqual(d.performance.rows[0].segments[1].id,d.performance.rows[1].segments[1].id);fill(d.performance);assert.equal(checkResult(required,d.performance).length,6);assert.equal(flatten(d.performance).reduce((n,s)=>n+Number(s.kg)*Number(s.reps),0),1920);
 p.rows[1].segments[0].kg='21';setup(required,p);change(required,'data-drop-target',p.rows[1].id);assert.deepEqual(current(required).performance.rows[0],p.rows[0]);assert.equal(current(required).performance.rows[1].segments.length,2);
 p.rows.splice(1,1);setup(required,p);const before=current(required).performance;change(required,'data-drop-target',p.rows[0].id);assert.deepEqual(current(required).performance,before);
});
test('101: ad-hoc drops do not alter old measurement signatures or prescribed backoff/group roles',()=>{
 const snap=captureSessionSnapshot(model,{id:'old-signature',sessionId:'old-session',planVersionId:PLAN_ID,unitId:'PUSH A',startedAt:AT}),oldP=fill(newPerformance(plain));
 const measure=comparison({trainingJournal:{sessionSnapshots:[snap]}},{sessionId:snap.sessionId,exerciseId:plain.id,journalSnapshotId:snap.id,journalPositionId:plain.positionId,journalVariantId:plain.journalVariantId,performance:oldP});assert.equal(measure.value,JSON.stringify(Array.from({length:3},()=>[null,['main',false,null,null,[['24','10']]]])));
 const x=ex('PUSH A','PUSH-A-3'),p=fill(newPerformance(x));setup(x,p);change(x,'data-drop-target',p.rows[2].id);const after=fill(current(x).performance);assert.equal(checkResult(x,after).length,3);assert.equal(after.rows[2].setId,x.targets[2].id);assert.match(editor.summary({performance:after},x.targets),/back-off · dropset/);
 const g=ex('PULL B','PULL-B-6-SKI');setup(g,fill(newPerformance(g)));change(g,'data-drop-target',current(g).performance.rows[0].id);const gp=fill(current(g).performance);assert.equal(checkResult(g,gp).length,2);assert.equal(gp.rows[0].round,1);assert.equal(gp.rows[0].groupId,g.group.id);
});
test('101: protocol materialization and v3/v4/v5/v6 roundtrips preserve ad-hoc marker and all old source archives',async()=>{
 const old=JSON.parse(readFileSync('tests/fixtures/v1.json')),packet=JSON.parse(readFileSync('tests/fixtures/plan-v3.json')),data=nativeData(old,packet),e=data.entries.find(e=>e.exerciseId==='PULL-A-1'&&e.performance),original=structuredClone(data);
 for(const row of e.performance.rows.slice(0,2)){row.dropOrigin='user';row.segments.push({id:row.id+'-manual-drop',kg:'5',reps:'6'});}e.series=flatten(e.performance);
 const db=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{structuredClone,crypto});const source={format:'pushpull-backup',version:2,data,catalog:JSON.parse(JSON.stringify(db.parseBackup(data).catalog)),archives:[{id:'original',kind:'opaque',createdAt:AT,raw:'Ł😀\\\"\n'.repeat(131072)},{id:'null',kind:'opaque',createdAt:AT,raw:null}]};
 const before=JSON.stringify(source),result=await materialize(await createProtocol(source));assert.equal(JSON.stringify(result),before);const v3=await sourceV3(source);assert.deepEqual((await parseModelBackup(v3)).data,data);
 for(const exportFn of [exportBackupV4,exportBackupV5]){const out=await exportFn(source,{createdAt:AT}),stage=await decodeBackup(out.text);assert.deepEqual(stage.live.data,data);assert.deepEqual(stage.archives,source.archives);}
 const history=JSON.parse((await exportBackupV5(source,{createdAt:AT})).text),out=await exportBackupV6({history,createdAt:AT,evidence:{format:'pushpull-draft-evidence',version:1,sources:[]},capture:{version:1,historyRevision:1,startedAt:AT,completedAt:AT,consistency:'observed-stable',scope:'observed-origin'}}),stage=await decodeBackup(out.text);assert.deepEqual(stage.history.live.data,data);assert.deepEqual(stage.history.archives,source.archives);assert.equal(JSON.stringify(source),before);
 assert.deepEqual(data.trainingJournal,original.trainingJournal);assert.deepEqual(data.sessions,original.sessions);assert.deepEqual(data.entries.filter(x=>x.id!==e.id),original.entries.filter(x=>x.id!==e.id));
});

test('101: previously opaque origin metadata stays readable and is never stolen to authorize a manual drop',()=>{
 const p=fill(newPerformance(plain));p.rows[0].dropOrigin={external:'preserve'};assert.equal(checkResult(plain,p).length,3);setup(plain,p);const before=current(plain).performance;change(plain,'data-drop-target',p.rows[0].id);assert.deepEqual(current(plain).performance,before);
 const q=fill(newPerformance(drop));q.rows[0].dropOrigin='source-extension';assert.equal(checkResult(drop,q).length,3);setup(drop,q);change(drop,'data-drop-target',q.rows[0].id);assert.equal(current(drop).performance.rows[0].dropOrigin,'source-extension');assert.equal(current(drop).performance.rows[0].segments.length,3);
 const one=fill(newPerformance(plain));one.rows[0].dropOrigin='user';assert.equal(checkResult(plain,one).length,3);assert.doesNotMatch(editor.summary({performance:one},plain.targets),/dropset/);
});
