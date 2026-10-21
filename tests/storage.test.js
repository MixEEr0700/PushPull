'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {KEY, open, validate} = require('../storage.js');
const fresh = () => ({version:1, exercises:Object.fromEntries(['PUSH A','PULL A','PUSH B','PULL B'].map((t,i)=>[t,[{id:'ex'+i,name:t,sets:2,target:'8–10',initialKg:'',tempo:'',rir:'',notes:''}]])),sessions:[],entries:[],changes:{},nextType:'PUSH A',activeId:null});
function fixture(){const d=fresh();d.sessions=[{id:'s1',seq:1,type:'PUSH A',date:'2026-10-21',status:'done'}];d.entries=[{id:'e1',sessionId:'s1',exerciseId:'ex0',kg:'100',reps:'10',series:[{kg:'100',reps:'10'},{kg:'80',reps:'8'}]}];d.changes={ex0:[{date:'2026-10-21',kind:'Technika',text:'Opis'}]};return d}
function memory(raw=null){const map=new Map(raw===null?[]:[[KEY,raw]]);return {map,getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),get length(){return map.size},key:i=>[...map.keys()][i]}}
test('legacy v1, missing optional fields, unknown extensions and exact identifiers survive',()=>{const d=fixture();delete d.changes;delete d.entries[0].series;d.extension={future:'retained'};const store=memory(JSON.stringify(d)),db=open(store,fresh);assert.equal(db.error,null);db.commit(db.value);assert.deepEqual(JSON.parse(store.getItem(KEY)),d)});
for(const raw of ['{bad','null','false','0','""','',JSON.stringify({...fresh(),version:2}),JSON.stringify({version:1})]){
 test('load preserves invalid original '+JSON.stringify(raw),()=>{const store=memory(raw),db=open(store,fresh);assert.ok(db.error);assert.throws(()=>db.commit(fresh()));assert.equal(store.getItem(KEY),raw);assert.equal(store.length,1)})
}
const invalid={
 'unknown version':d=>d.version=2,'invalid leap day':d=>d.sessions[0].date='2025-02-29',
 'duplicate session':d=>d.sessions.push({...d.sessions[0]}),'duplicate sequence':d=>d.sessions.push({...d.sessions[0],id:'s2'}),
 'missing session':d=>d.entries[0].sessionId='missing','wrong workout':d=>d.entries[0].exerciseId='ex1',
 'duplicate exercise':d=>d.exercises['PULL A'][0].id='ex0','unsafe identifier':d=>d.entries[0].id='"><img>',
 'missing notes':d=>delete d.exercises['PUSH A'][0].notes,'invalid sets':d=>d.exercises['PUSH A'][0].sets=0,
 'unknown rotation':d=>d.nextType='PUSH C','active mismatch':d=>d.activeId='s1',
 'unreferenced active':d=>d.sessions[0].status='active','duplicate entry':d=>d.entries.push({...d.entries[0],id:'e2'}),
 'negative kg':d=>d.entries[0].kg=-1,'infinite kg':d=>d.entries[0].kg=Infinity,
 'fractional reps':d=>d.entries[0].reps='1.5','zero reps':d=>d.entries[0].reps='0',
 'empty series':d=>d.entries[0].series=[],'invalid series':d=>d.entries[0].series[1].reps='NaN',
 'main/series mismatch':d=>d.entries[0].kg='10','orphan change':d=>d.changes.unknown=[],
 'bad change':d=>d.changes.ex0[0].date='2026-02-30','prototype key':d=>d.extra=JSON.parse('{"__proto__":{}}')
};
for(const [name,mutate] of Object.entries(invalid)) test('rejects '+name+' before any write',()=>{const original=JSON.stringify(fixture()),store=memory(original),db=open(store,fresh),d=fixture();mutate(d);assert.throws(()=>db.commit(d,{importing:true}));assert.equal(store.getItem(KEY),original);assert.equal(store.length,1)});
test('absent storage initializes only on explicit save',()=>{const store=memory(),db=open(store,fresh);assert.equal(store.length,0);db.commit(db.value);assert.deepEqual(JSON.parse(store.getItem(KEY)),fresh())});
test('security/read failure cannot initialize or import over inaccessible storage',()=>{const store={getItem(){throw Error('SecurityError')},setItem(){assert.fail('write')}};const db=open(store,fresh);assert.ok(db.error);assert.throws(()=>db.commit(fresh(),{importing:true}))});
for(const failure of ['backup','primary']) test('import '+failure+' write failure leaves original and committed memory intact',()=>{const raw=JSON.stringify(fixture()),store=memory(raw),db=open(store,fresh);store.setItem=(k,v)=>{if((failure==='backup')===(k!==KEY))throw Error('QuotaExceededError');store.map.set(k,v)};assert.throws(()=>db.commit(fresh(),{importing:true}));assert.equal(store.getItem(KEY),raw);assert.deepEqual(db.value,fixture());if(failure==='primary')assert.equal(store.getItem(db.backups()[0]),raw)});
test('normal failed save leaves committed memory intact',()=>{const store=memory(JSON.stringify(fixture())),db=open(store,fresh);store.setItem=()=>{throw Error('quota')};assert.throws(()=>db.commit(fresh()));assert.deepEqual(db.value,fixture())});
test('imports keep distinct exact preimages, list/download and restore through validated import',()=>{const original=' '+JSON.stringify(fixture())+'\n',store=memory(original),db=open(store,fresh);const first=db.commit(fresh(),{importing:true});assert.equal(db.readBackup(first),original);const second=db.commit(validate(JSON.parse(db.readBackup(first))),{importing:true});assert.notEqual(first,second);assert.deepEqual(db.value,fixture());assert.equal(db.backups().length,2);assert.throws(()=>db.readBackup(KEY))});
test('recovery import backs up unsupported raw without parsing it',()=>{const store=memory('{invalid'),db=open(store,fresh);const key=db.commit(fixture(),{importing:true});assert.equal(db.readBackup(key),'{invalid');assert.equal(db.error,null);assert.deepEqual(db.value,fixture())});
test('other-tab change aborts before backup/write',()=>{const store=memory(JSON.stringify(fixture())),db=open(store,fresh);store.map.set(KEY,'other tab');assert.throws(()=>db.commit(fresh(),{importing:true}));assert.equal(store.getItem(KEY),'other tab');assert.equal(store.length,1)});

test('legacy fallback decimal session and entry IDs remain valid',()=>{const d=fixture();d.sessions[0].id='17700000000.25';d.entries[0].sessionId=d.sessions[0].id;d.entries[0].id='17700000001.75';assert.equal(validate(d),d)});

test('updated legacy adapter refuses writes and imports after IndexedDB ownership',()=>{const raw=JSON.stringify(fixture()),store=memory(raw);store.map.set('pushpull_indexeddb_owner','pushpull:1');const db=open(store,fresh);assert.ok(db.error);assert.throws(()=>db.commit(fresh()));assert.throws(()=>db.commit(fresh(),{importing:true}));assert.equal(store.getItem(KEY),raw)});
