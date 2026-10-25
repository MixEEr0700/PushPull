import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

function environment(){
 let serializations=0;
 const code=readFileSync('indexeddb.js','utf8').replace('  function sort(value) {','  globalThis.comparison={sameStoredModel,canonical};\n  function sort(value) {');
 const context={JSON:{parse:JSON.parse,stringify:(...args)=>{serializations++;return JSON.stringify(...args)}}};
 runInNewContext(code,context);
 return {...context.comparison,count:()=>serializations};
}

test('complete model comparison preserves canonical JSON equality, key order, arrays and unknown fields',()=>{
 const e=environment(),values=[null,true,false,0,-0,1,1e100,'','Ł😀\ud800','a\\"\n',[null,''],{b:2,a:1},{a:1,b:2},{a:null},{},{future:{nested:[{opaque:'raw'}]}}];
 for(const a of values)for(const b of values)assert.equal(e.sameStoredModel(a,b),e.canonical(a)===e.canonical(b));
 const source={key:'training-model-v1',revision:3,document:{metadata:{unknown:['Ł😀',null]},payload:{model:{ownerId:'synthetic'},legacySources:[{id:'source',raw:'original bytes'}]},integrity:{digest:'unchanged',counts:{results:1}}}};
 const reordered={document:source.document,revision:source.revision,key:source.key};
 assert.equal(e.sameStoredModel(source,reordered),true);
 const changes=[x=>x.revision++,x=>x.document.metadata.unknown[0]='changed',x=>x.document.payload.model.ownerId='other',x=>x.document.payload.legacySources[0].raw+=' ',x=>x.document.integrity.counts.results++,x=>x.document.future={retained:true},x=>delete x.document.metadata];
 for(const change of changes){const next=structuredClone(source);change(next);assert.equal(e.sameStoredModel(source,next),false);assert.equal(next.document.integrity.digest,source.document.integrity.digest,'the unchanged digest must not bypass any field');}
 assert.deepEqual(source.document.metadata.unknown,['Ł😀',null]);
});

test('seeded JSON trees and mutations agree with the existing canonical gate',()=>{
 const e=environment();let state=12;
 const random=n=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state%n;};
 function value(depth){
  if(!depth)return [null,random(1000),'Ł😀\\"\n'+random(9),!!random(2)][random(4)];
  if(random(2))return Array.from({length:random(5)},()=>value(depth-1));
  return Object.fromEntries(Array.from({length:random(5)},(_,i)=>['key-'+i,value(depth-1)]));
 }
 for(let i=0;i<500;i++){
  const a=value(4),b=structuredClone(a),c=value(4);
  assert.equal(e.sameStoredModel(a,b),true);
  assert.equal(e.sameStoredModel(a,c),e.canonical(a)===e.canonical(c));
 }
});

test('unchanged multimegabyte raw model values require no JSON serialization',()=>{
 const e=environment(),a={revision:3,document:{payload:{legacySources:[{raw:'Ł😀\\"'.repeat(256*1024)}]},integrity:{digest:'checked independently'}}},b=structuredClone(a),before=e.count();
 assert.equal(e.sameStoredModel(a,b),true);
 assert.equal(e.count()-before,0,'CAS/readback must compare every field without escaped raw copies');
 b.document.payload.legacySources[0].raw+='x';assert.equal(e.sameStoredModel(a,b),false);
});

test('legacy non-JSON canonical fallbacks retain omissions, sparse arrays and numeric normalization',()=>{
 const e=environment(),values=[undefined,null,NaN,Infinity,-Infinity,{a:undefined},{a:()=>1},{a:Symbol('opaque')},{},[undefined],[null],Array(1),[],new Date(0),new Map(),{a:NaN},{a:null}];
 for(const a of values)for(const b of values)assert.equal(e.sameStoredModel(a,b),e.canonical(a)===e.canonical(b));
 assert.throws(()=>e.sameStoredModel({x:1n},{x:1n}),/BigInt/);
});
