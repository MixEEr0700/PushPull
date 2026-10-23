import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {
  Side, createModel, validateModel, validateExerciseIdentity, validateExerciseVariant,
  validatePlanVersion, validatePlanPosition, validateSetPrescription, validateDropPrescription,
  validateGroupPrescription, validateLoadConvention, validateCoachInstruction, validateUserNote,
  captureSessionSnapshot, validateSessionSnapshot, createResultReference, validateResultReference
} from '../model/training-model.mjs';

const source = (kind='trainer',reference='DOCX:T2/R3/C1') => ({kind,reference,recordedAt:null});
const convention = () => ({unit:null,basis:null,description:null});
const exercise = (id,name=id) => ({id,name,status:'confirmed',legacyId:id,source:source('legacy',id)});
const variant = (id,exerciseId,fields={}) => ({id,exerciseId,label:id,machine:null,grip:null,support:null,execution:null,laterality:null,source:source(),...fields});
const position = (id,exerciseId,variantId,order,fields={}) => ({id,exerciseId,variantId,order,planVersionId:'v1',unitId:'unit',label:id,legacyPositionId:exerciseId,replacesPositionId:null,setState:'specified',confirmation:'confirmed',loadConvention:convention(),source:source(),...fields});
const set = (id,positionId,order,fields={}) => ({id,positionId,order,role:'main',reps:{min:5,max:7},rir:{min:0,max:0},tempo:[2,0,1,0],side:null,backoffFromSetId:null,restSeconds:null,source:source(),...fields});
function fixture() {
  return {schemaVersion:1,ownerId:'local-owner',
    exercises:[exercise('PUSH-A-3','Klatka maszyna'),exercise('narciarz'),exercise('szrugsy'),exercise('PUSH-A-8','Brzuch')],
    variants:[variant('chest','PUSH-A-3',{laterality:'unilateral'}),variant('ski','narciarz'),variant('shrugs','szrugsy'),variant('unknown','PUSH-A-8')],
    planVersions:[{id:'v1',planId:'plan',number:1,label:'Test plan',units:[{id:'unit',name:'Any training unit',order:0}],source:source()}],
    positions:[position('chest-position','PUSH-A-3','chest',0),position('ski-position','narciarz','ski',1),position('shrugs-position','szrugsy','shrugs',2),position('abs-position','PUSH-A-8','unknown',3,{setState:'unspecified',confirmation:'pending'})],
    sets:[set('main-1','chest-position',0,{side:Side.EACH}),set('main-2','chest-position',1,{side:Side.EACH}),set('backoff','chest-position',2,{role:'backoff',reps:{min:8,max:10},backoffFromSetId:'main-2',side:Side.EACH}),
      ...['ski-position','shrugs-position'].flatMap(p=>[0,1].map(i=>set(p+i,p,i,{reps:{min:8,max:10}})))],
    drops:[{id:'drop',setId:'main-1',segments:null,source:source()}],
    groups:[{id:'pair',planVersionId:'v1',unitId:'unit',kind:'paired',positionIds:['ski-position','shrugs-position'],rounds:2,betweenMembersSeconds:15,afterRoundSeconds:null,source:source('owner','D4')}],
    coachInstructions:[{id:'coach',planVersionId:'v1',positionId:'chest-position',revision:1,text:'Trainer instruction',confirmation:'confirmed',source:source()}],
    userNotes:[{id:'note',exerciseId:'PUSH-A-3',sessionId:null,text:'Dokładna notatka — Ł',origin:'legacy-shared',revision:1,source:source('legacy','existing notes')}]};
}
const capture = model => captureSessionSnapshot(model,{id:'snapshot',sessionId:'existing-session-id',planVersionId:'v1',unitId:'unit',startedAt:'2026-10-22T10:00:00.000Z'});
const ref = (snapshot,fields={}) => createResultReference(snapshot,{resultId:'existing-entry-id',positionId:'chest-position',setId:'main-1',side:Side.LEFT,groupId:null,round:null,...fields});

test('each independent contract validates records; model preserves unknown JSON and caller data',()=>{
  const input=fixture();input.extension={future:[false,null,'Ł']};input.sets[0].extension={raw:'100,5'};
  const original=structuredClone(input),model=createModel(input);
  for (const [validate,value] of [[validateExerciseIdentity,model.exercises[0]],[validateExerciseVariant,model.variants[0]],
    [validatePlanVersion,model.planVersions[0]],[validatePlanPosition,model.positions[0]],[validateSetPrescription,model.sets[0]],
    [validateDropPrescription,model.drops[0]],[validateGroupPrescription,model.groups[0]],[validateLoadConvention,model.positions[0].loadConvention],
    [validateCoachInstruction,model.coachInstructions[0]],[validateUserNote,model.userNotes[0]]]) assert.equal(validate(value),value);
  assert.deepEqual(input,original);assert.deepEqual(JSON.parse(JSON.stringify(model)),original);
  assert.throws(()=>{model.sets[0].reps.min=99},TypeError);
  input.userNotes[0].text='Later edit';assert.equal(model.userNotes[0].text,original.userNotes[0].text);
});

test('unknown targets stay unknown: abs/calves, incomplete tempo, unknown loads, no guessed defaults',()=>{
  const input=fixture();input.sets[0].reps=null;input.sets[0].rir=null;input.sets[0].tempo=[2,null,1,null];
  const model=createModel(input);assert.deepEqual(model.positions[3].loadConvention,convention());
  assert.equal(model.sets[0].reps,null);assert.deepEqual(model.sets[0].tempo,[2,null,1,null]);
  assert.equal(model.sets.filter(s=>s.positionId==='abs-position').length,0);
  const missing=fixture();delete missing.sets[0].reps;assert.throws(()=>createModel(missing),/missing reps/);
  input.sets.push(set('invented','abs-position',0));assert.throws(()=>createModel(input),/unspecified/);
});

test('backoff is a third distinct target with no automatic load formula',()=>{
  const model=createModel(fixture());const target=model.sets[2];
  assert.equal(model.sets.filter(s=>s.positionId==='chest-position').length,3);
  assert.deepEqual(target.reps,{min:8,max:10});assert.equal(target.backoffFromSetId,'main-2');
  assert.equal(Object.hasOwn(target,'kg'),false);
  for (const id of ['backoff','ski-position0']) { const bad=fixture();bad.sets[2].backoffFromSetId=id;assert.throws(()=>createModel(bad)); }
});

test('drop has flexible unknown segment count or arbitrary ordered templates, without fixed weights',()=>{
  for (const count of [1,3,7]) {
    const input=fixture();input.drops[0].segments=Array.from({length:count},(_,i)=>({id:'segment-'+i,order:i,reps:null,rir:null,tempo:null}));
    assert.equal(createModel(input).drops[0].segments.length,count);
  }
  assert.equal(createModel(fixture()).drops[0].segments,null);
  const bad=fixture();bad.drops[0].segments=[];assert.throws(()=>createModel(bad));
});

test('two-round pair has separate exercise results, 15s internal rest and no invented post-pair rest',()=>{
  const snapshot=capture(fixture());
  const references=['ski-position','shrugs-position'].flatMap(p=>[1,2].map(round=>ref(snapshot,{resultId:p+round,positionId:p,setId:p+(round-1),side:null,groupId:'pair',round})));
  assert.equal(new Set(references.map(r=>r.exerciseId)).size,2);
  assert.equal(snapshot.model.groups[0].betweenMembersSeconds,15);assert.equal(snapshot.model.groups[0].afterRoundSeconds,null);
  assert.throws(()=>ref(snapshot,{positionId:'ski-position',setId:'ski-position0',side:null,groupId:'pair',round:3}));
  const superset=fixture();superset.groups[0].kind='superset';superset.groups[0].rounds=null;superset.groups[0].betweenMembersSeconds=null;
  assert.equal(createModel(superset).groups[0].kind,'superset');
});

test('side references are separate, retain explicit load convention and never convert legacy measurements',()=>{
  const input=fixture();input.positions[0].loadConvention={unit:'kg',basis:'per-implement',description:'one dumbbell'};
  input.extension={legacy:{id:'historical-entry',kg:'42.5',reps:'10',tonnage:425}};
  const model=createModel(input),snapshot=capture(model),left=ref(snapshot),right=ref(snapshot,{resultId:'right-result',side:Side.RIGHT});
  assert.notEqual(left.side,right.side);assert.equal(model.extension.legacy.tonnage,425);assert.equal(input.extension.legacy.kg,'42.5');
  assert.throws(()=>ref(snapshot,{side:Side.BILATERAL}));assert.throws(()=>ref(snapshot,{side:Side.EACH}));
});

test('new PUSH-A-4 machine identity replaces a plan position without relabelling historic dips',()=>{
  const input=fixture();input.exercises.push(exercise('PUSH-A-4','Dipy'),{id:'new-machine',name:'Unidentified machine',status:'unresolved',legacyId:null,source:source('owner','D2/O1')});
  input.variants.push(variant('dips','PUSH-A-4'),variant('new-machine-variant','new-machine',{grip:'neutral',support:'high seat',source:source('owner','D2')}));
  input.positions.push(position('old-dips','PUSH-A-4','dips',4,{setState:'unspecified'}));
  input.planVersions.push({...structuredClone(input.planVersions[0]),id:'v2',number:2});
  input.positions.push(position('new-position','new-machine','new-machine-variant',0,{planVersionId:'v2',setState:'unspecified',confirmation:'pending',legacyPositionId:'PUSH-A-4',replacesPositionId:'old-dips'}));
  const old=capture(input),next=captureSessionSnapshot(input,{id:'next-snapshot',sessionId:'new-session',planVersionId:'v2',unitId:'unit',startedAt:'2026-10-23T10:00:00.000Z'});
  assert.equal(ref(old,{positionId:'old-dips',setId:null,side:null}).exerciseId,'PUSH-A-4');
  assert.equal(ref(next,{positionId:'new-position',setId:null,side:null}).exerciseId,'new-machine');
  assert.equal(next.model.positions.find(p=>p.id==='new-position').replacesPositionId,'old-dips');
  assert.throws(()=>ref(next,{positionId:'old-dips',setId:null,side:null}),/binding/);
  assert.throws(()=>validateResultReference({...ref(old),exerciseId:'new-machine'},old));
  assert.equal(input.exercises.find(e=>e.id==='PUSH-A-4').name,'Dipy');
  assert.throws(()=>validateExerciseIdentity({...input.exercises.at(-1),legacyId:'PUSH-A-4'}),/preserved/);
});

test('snapshot is self-contained, immutable and survives later plan/instruction changes and JSON roundtrip',()=>{
  const input=fixture(),snapshot=capture(input),original=JSON.stringify(snapshot),reference=ref(snapshot);
  input.planVersions[0].label='Edited later';input.variants[0].grip='Changed';input.sets[0].reps.max=12;input.coachInstructions[0].text='Revised';
  assert.equal(JSON.stringify(snapshot),original);assert.equal(snapshot.model.userNotes.length,0);
  assert.throws(()=>{snapshot.model.coachInstructions[0].text='overwrite'},TypeError);
  const restored=JSON.parse(original);assert.equal(validateSessionSnapshot(restored),restored);
  assert.equal(validateResultReference(JSON.parse(JSON.stringify(reference)),restored).resultId,'existing-entry-id');
  assert.throws(()=>validateResultReference({...reference,sessionId:'old-session'},restored));
  const other=structuredClone(restored);other.model.ownerId='other-profile';
  assert.throws(()=>validateResultReference(reference,other),/binding/);
});

test('coach instructions and legacy-shared notes keep distinct text and authorship',()=>{
  const input=fixture();input.coachInstructions[0].source=source('unknown','C2');input.coachInstructions[0].confirmation='unverified';
  const snapshot=capture(input);assert.equal(snapshot.model.coachInstructions[0].confirmation,'unverified');
  const model=createModel(input);assert.equal(model.userNotes[0].origin,'legacy-shared');assert.equal(model.userNotes[0].source.recordedAt,null);
  input.coachInstructions[0].confirmation='confirmed';assert.throws(()=>createModel(input),/unattributed/);
});

// D2 examples are contract fixtures, not a production plan or seed/migration.
test('all ten owner-selected D2 variants fit the model while unresolved machine parameters remain absent',()=>{
  const choices=[
    ['PUSH-A-1','siedząc obunóż','bilateral'],['PUSH-A-4','neutralny chwyt; wysokie siedzisko',null],
    ['PULL-A-1','leżąc jednonóż','unilateral'],['PULL-A-3','maszyna na górze; nachwyt',null],
    ['PULL-A-5','wyciąg poziomy jednorącz','unilateral'],['PUSH-B-1','siedząc obunóż','bilateral'],
    ['PUSH-B-7','jednorącz w odwiedzeniu ramienia','unilateral'],['PULL-B-3','podparcie klatki i brzucha 30–45° do biodra','unilateral'],
    ['PULL-B-4','jednorącz kable/wyciąg do biodra','unilateral'],['PULL-B-5','maszyna na górze; dolny chwyt',null]
  ];
  const input=fixture();input.positions=[];input.sets=[];input.drops=[];input.groups=[];input.coachInstructions=[];input.userNotes=[];input.exercises=[];input.variants=[];
  choices.forEach(([legacyId,label,laterality],order)=>{
    const identity=legacyId==='PUSH-A-4' ? 'separate-machine' : legacyId;
    input.exercises.push({...exercise(identity),legacyId:identity===legacyId?legacyId:null,status:legacyId==='PUSH-A-4'?'unresolved':'confirmed'});
    input.variants.push(variant('variant-'+order,identity,{label,laterality,source:source('owner','D2')}));
    input.positions.push(position('position-'+order,identity,'variant-'+order,order,{legacyPositionId:legacyId,setState:'unspecified',confirmation:'pending',source:source('owner','D2')}));
  });
  assert.equal(createModel(input).variants.length,10);assert.equal(input.positions.find(p=>p.legacyPositionId==='PUSH-A-4').exerciseId,'separate-machine');
});

const invalid={
  'duplicate identity':m=>m.exercises.push(structuredClone(m.exercises[0])),
  'missing exercise':m=>m.variants[0].exerciseId='missing',
  'wrong identity for variant':m=>m.positions[0].variantId='ski',
  'unknown unit':m=>m.positions[0].unitId='other',
  'duplicate order':m=>m.positions[1].order=0,
  'invalid rep range':m=>m.sets[0].reps={min:10,max:5},
  'fractional rep':m=>m.sets[0].reps={min:1.5,max:2},
  'negative RIR':m=>m.sets[0].rir={min:-1,max:0},
  'wrong tempo':m=>m.sets[0].tempo=[2,0,1],
  'negative rest':m=>m.groups[0].betweenMembersSeconds=-1,
  'duplicate plan version number':m=>m.planVersions.push({...structuredClone(m.planVersions[0]),id:'duplicate-version'}),
  'replacement cycle':m=>{m.planVersions[0].number=null;m.planVersions.push({...structuredClone(m.planVersions[0]),id:'v2',number:null});m.positions.push(position('cycle','PUSH-A-8','unknown',0,{planVersionId:'v2',setState:'unspecified',replacesPositionId:'abs-position'}));m.positions[3].replacesPositionId='cycle'},
  'same exercise in pair':m=>m.groups[0].positionIds=['ski-position','ski-position'],
  'orphan drop':m=>m.drops[0].setId='missing',
  'wrong instruction version':m=>m.coachInstructions[0].planVersionId='missing',
  'wrong note exercise':m=>m.userNotes[0].exerciseId='missing',
  'implicit load convention':m=>delete m.positions[0].loadConvention,
  'wrong side for variant':m=>m.sets[0].side=Side.BILATERAL,
  'unknown schema':m=>m.schemaVersion=2,
  'undefined extension':m=>m.extension=undefined,
  'nonfinite extension':m=>m.extension=NaN,
  'date extension':m=>m.extension=new Date(),
  'sparse array extension':m=>m.extension=new Array(1),
  'cyclic extension':m=>m.extension=m,
  'unsafe key':m=>m.extension=JSON.parse('{"__proto__":{}}')
};
test('rejects invalid structures and cross-record relations without mutating inputs',()=>{
  for (const [name,mutate] of Object.entries(invalid)) {const input=fixture();mutate(input);const before=structuredClone(input);assert.throws(()=>validateModel(input),undefined,name);assert.deepEqual(input,before,name);}
});

test('model import has no browser/storage side effects and approved UI stays byte-identical',()=>{
  const base='012fe5a8d2da4107dea5a01f27c4faffec544430';
  for (const file of ['index.html','style.css','manifest.webmanifest','icon.svg','icons/icon-192.png','icons/icon-512.png','icons/icon-maskable-512.png']) {
    assert.deepEqual(readFileSync(new URL('../'+file,import.meta.url)),execFileSync('git',['show',base+':'+file]),file);
  }
  // An import in a process with trap globals cannot accidentally open old stores.
  execFileSync(process.execPath,['--input-type=module','-e',`for(const key of ['indexedDB','localStorage','document','fetch'])Object.defineProperty(globalThis,key,{get(){throw Error(key)}});await import('./model/training-model.mjs');`]);
});
