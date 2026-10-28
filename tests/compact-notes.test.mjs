import test from 'node:test';
import assert from 'node:assert/strict';
import {buildPlan,views,PLAN_ID,userNoteBinding} from '../model/v2-plan.mjs';
test('note presentation preserves but does not borrow arbitrary legacy IDs or notes of another plan',()=>{
 const model=buildPlan('note-test'),data={trainingJournal:{model:structuredClone(model)}};
 const id='PUSH-A-1',other='other-plan';
 data.trainingJournal.model.planVersions.push({...structuredClone(model.planVersions[0]),id:other});
 const notes=data.trainingJournal.model.userNotes;
 notes.push({id:'old-custom-id',exerciseId:id,sessionId:null,origin:'user',text:'global legacy'}, {id:'user:'+other+':'+id,exerciseId:id,sessionId:null,origin:'user',text:'other version'});
 const get=()=>views(model,PLAN_ID,'PUSH A',data).find(e=>e.id===id);
 assert.equal(get().notes,'');
 notes.unshift({id:'user:'+PLAN_ID+':'+id,exerciseId:id,sessionId:null,origin:'user',text:'this version'});
 const before=structuredClone(data);assert.equal(get().notes,'this version');assert.deepEqual(data,before);
 notes.shift();notes.shift();assert.equal(get().notes,''); // never borrow the other version
});
test('session-bound notes are preserved but never borrowed as general exercise notes',()=>{
 const model=buildPlan('session-note-test'),data={trainingJournal:{model:structuredClone(model)}};
 data.trainingJournal.model.userNotes.push({id:'native-session-note',exerciseId:'PUSH-A-1',sessionId:'other-session',origin:'user',text:'only that historical session'});
 const before=structuredClone(data);
 assert.equal(views(model,PLAN_ID,'PUSH A',data).find(e=>e.id==='PUSH-A-1').notes,'');
 assert.deepEqual(data,before);
});

test('ambiguous variants fail closed without a new note ID contract or data migration',()=>{
 const m=structuredClone(buildPlan('variant-note-test')),p=m.positions[0],other={...p,id:'another-position',variantId:'another-variant',unitId:'PULL A'};
 m.positions.push(other);
 m.userNotes.push({id:'user:'+PLAN_ID+':'+p.exerciseId,exerciseId:p.exerciseId,sessionId:null,origin:'user',text:'ambiguous old version note',revision:3});
 const before=structuredClone(m);
 assert.equal(userNoteBinding(m,PLAN_ID,p.exerciseId,p.variantId),null);
 assert.equal(userNoteBinding(m,PLAN_ID,p.exerciseId,other.variantId),null);
 assert.equal(userNoteBinding(m,PLAN_ID,p.exerciseId,'unknown-variant'),null);
 assert.deepEqual(m,before);
});
test('source and legacy-shared records cannot become editable own notes even at the scoped ID',()=>{
 const m=structuredClone(buildPlan('provenance-note-test')),p=m.positions[0],id='user:'+PLAN_ID+':'+p.exerciseId;
 for(const origin of ['source-note','legacy-shared']){
  m.userNotes=[{id,exerciseId:p.exerciseId,sessionId:null,origin,text:'not an own note',revision:1}];
  const before=structuredClone(m);assert.equal(userNoteBinding(m,PLAN_ID,p.exerciseId,p.variantId).text,'');assert.deepEqual(m,before);
 }
});
