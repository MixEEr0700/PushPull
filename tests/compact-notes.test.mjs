import test from 'node:test';
import assert from 'node:assert/strict';
import {buildPlan,views,PLAN_ID} from '../model/v2-plan.mjs';
test('note presentation preserves arbitrary legacy IDs and isolates notes of plan versions',()=>{
 const model=buildPlan('note-test'),data={trainingJournal:{model:structuredClone(model)}};
 const id='PUSH-A-1',other='other-plan';
 data.trainingJournal.model.planVersions.push({...structuredClone(model.planVersions[0]),id:other});
 const notes=data.trainingJournal.model.userNotes;
 notes.push({id:'old-custom-id',exerciseId:id,origin:'user',text:'global legacy'}, {id:'user:'+other+':'+id,exerciseId:id,origin:'user',text:'other version'});
 const get=()=>views(model,PLAN_ID,'PUSH A',data).find(e=>e.id===id);
 assert.equal(get().notes,'global legacy');
 notes.unshift({id:'user:'+PLAN_ID+':'+id,exerciseId:id,origin:'user',text:'this version'});
 const before=structuredClone(data);assert.equal(get().notes,'this version');assert.deepEqual(data,before);
 notes.shift();notes.shift();assert.equal(get().notes,''); // never borrow the other version
});
