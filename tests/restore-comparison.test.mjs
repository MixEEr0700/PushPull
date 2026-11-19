import test from 'node:test';
import assert from 'node:assert/strict';
import {compareCanonicalRestore} from '../model/restore-comparison.mjs';

function backup(sessions=[],entries=[]){
 return {source:{data:{sessions,entries,exercises:{},changes:{},nextType:'PUSH A'},catalog:{plans:[],planVersions:[],sessionVersions:{}}},drafts:[],buffers:[],preferences:{},drive:{clientId:''}};
}
const session={id:'session',seq:1,status:'done'};
const entry={id:'result',sessionId:'session',series:[{kg:'40',reps:'10'}]};
test('an exact extension is distinct from an older backup or an equal-size conflicting history',()=>{
 const local=backup([session],[entry]),newer=structuredClone(local);
 newer.source.data.sessions.push({id:'next',seq:2,status:'done'});
 newer.source.data.nextType='PULL B';
 assert.equal(compareCanonicalRestore(local,newer).risky,false);
 assert.deepEqual(compareCanonicalRestore(local,newer).sections.sessions,{localOnly:0,copyOnly:1,changed:0});
 assert.equal(compareCanonicalRestore(newer,local).risky,true);
 const changed=backup([session],[{...entry,series:[{kg:'45',reps:'10'}]}]);
 assert.deepEqual(compareCanonicalRestore(local,changed).sections.results,{localOnly:0,copyOnly:0,changed:1});
 assert.equal(compareCanonicalRestore(local,changed).risky,true);
 const divergent=backup([{...session,id:'other'}]);
 assert.deepEqual(compareCanonicalRestore(local,divergent).sections.sessions,{localOnly:1,copyOnly:1,changed:0});
 assert.equal(compareCanonicalRestore(local,divergent).risky,true);
});
test('drafts, buffers, notes, technique, settings and plan changes can each gate replacement',()=>{
 const incoming=backup([session],[entry]);
 const cases=[
  ['drafts',local=>local.drafts=[{key:'draft',value:{reps:'9'}}]],
  ['buffers',local=>local.buffers=[{key:'edit',raw:'draft text'}]],
  ['preferences',local=>local.preferences.units='kg'],
  ['notes',local=>local.source.data.trainingJournal={model:{userNotes:[{id:'note',text:'own'}]}}],
  ['technique',local=>local.source.data.changes.press=[{date:'2026-10-21',text:'own'}]],
  ['plans',local=>local.source.catalog.plans.push({id:'plan'})]
 ];
 for(const [key,alter] of cases){
  const local=structuredClone(incoming);
  alter(local);
  const review=compareCanonicalRestore(local,incoming);
  assert.equal(review.sections[key].localOnly,1,key);
  assert.equal(review.risky,true,key);
 }
 assert.equal(compareCanonicalRestore(incoming,incoming).sameContent,true);
});
test('starter plan replacement is safe, and a same-size edit of a genuinely used plan is gated',()=>{
 const local=backup(),starter=structuredClone(local.source),incoming=backup([session],[entry]);
 local.source.data.exercises.press={target:'default'};
 starter.data.exercises=structuredClone(local.source.data.exercises);
 incoming.source.data.exercises.press={target:'personal'};
 assert.equal(compareCanonicalRestore(local,incoming,starter).risky,false);
 local.source.data.exercises.press.target='editing';
 assert.equal(compareCanonicalRestore(local,incoming,starter).risky,true);
});
