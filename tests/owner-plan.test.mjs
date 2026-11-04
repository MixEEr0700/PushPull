import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {stagePlan} from '../model/plan-import.mjs';import {userNoteBinding,editUserNote} from '../model/v2-plan.mjs';
const p=JSON.parse(fs.readFileSync('plans/PushPull-01.07.2026.json'));
const fresh=()=>({version:1,exercises:{'PUSH A':[],'PULL A':[],'PUSH B':[],'PULL B':[]},sessions:[],entries:[],changes:{},nextType:'PUSH A',activeId:null});
test('owner plan has independent positions, exact ordered units, empty actual history and unspecified abdomen/calves',()=>{
 const d=fresh(),next=stagePlan(d,p),m=next.trainingJournal.model;
 assert.deepEqual(p.planVersion.units.map(u=>u.name),['Push A','Pull A','Push B','Pull B']);assert.deepEqual(p.planVersion.units.map(u=>p.positions.filter(x=>x.unitId===u.id).length),[8,8,9,10]);assert.equal(new Set(p.positions.map(x=>x.exerciseId)).size,35);
 const extracted=JSON.parse(fs.readFileSync('docs/plan-01-07-2026-extracted.json'));
 for(const [i,u] of extracted.units.entries())assert.deepEqual(p.positions.filter(x=>x.unitId===p.planVersion.units[i].id).map(x=>x.label),u.positions.map(x=>x.name));
 assert.deepEqual(next.sessions,[]);assert.deepEqual(next.entries,[]);assert.deepEqual(d,fresh());
 for(const x of Object.values(next.exercises).flat())assert.equal(x.initialKg,'');
 for(const pos of p.positions.filter(x=>['Brzuch','Łydki'].includes(x.label))){const sets=p.sets.filter(x=>x.positionId===pos.id);assert.equal(sets.length,1);assert.equal(sets[0].reps,null);assert.equal(sets[0].rir,null);assert.equal(sets[0].tempo,null);}
 assert.equal(p.drops.length,6);assert.equal(p.groups.length,1);assert.equal(p.groups[0].betweenMembersSeconds,15);
 for(const n of p.initialUserNotes){const pos=p.positions.find(x=>x.exerciseId===n.exerciseId),binding=userNoteBinding(m,p.planVersion.id,pos.exerciseId,pos.variantId);assert.equal(binding.text,n.text);}
});
test('initial notes are editable and foreign or duplicate notes fail without mutating input',()=>{
 const d=fresh(),m=stagePlan(d,p).trainingJournal.model,n=p.initialUserNotes[0],pos=p.positions.find(x=>x.exerciseId===n.exerciseId),b=userNoteBinding(m,p.planVersion.id,pos.exerciseId,pos.variantId);
 const edited=editUserNote(m,{versionId:p.planVersion.id,exerciseId:pos.exerciseId,variantId:pos.variantId,noteId:b.id,base:b.text,revision:b.revision,text:'Edytowane',recordedAt:'2026-11-04T00:00:00.000Z'});assert.equal(userNoteBinding(edited.model,p.planVersion.id,pos.exerciseId,pos.variantId).text,'Edytowane');assert.equal(b.text,n.text);
 for(const notes of [[{exerciseId:'foreign',text:'x'}],[n,n]])assert.throws(()=>stagePlan(d,{...p,initialUserNotes:notes}));assert.deepEqual(d,fresh());
});
