import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {openDriveBackup,makeNode,properties,readNode,inspectBackup} from '../model/drive-sync.mjs';
const fixture=()=>JSON.parse(readFileSync(new URL('fixtures/v1.json',import.meta.url)));
const clone=structuredClone;
class Database {
 constructor(){this.value=fixture();this.revision=1;this.model=null;this.error=null;this.state=null;this.drafts=[];this.preimages=[];}
 async readDriveState(){return clone(this.state);}
 async writeDriveState(value,expected){assert.equal(this.state?.token??null,expected);this.state={...clone(value),token:crypto.randomUUID()};return clone(this.state);}
 export(){return clone(this.value);}
 async readDrafts(){return clone(this.drafts);}
 change(note){this.value.exercises['PULL B'][0].notes=note;this.revision++;}
}
class Drive {
 constructor(files=new Map()){this.files=files;this.authenticated=false;this.account='account-A';this.creates=0;}
 clear(){this.authenticated=false;}
 async load(){}
 async connect(){this.authenticated=true;return {id:this.account,label:this.account};}
 async list(){return [...this.files.values()].map(({text,...f})=>clone(f));}
 async create(text,appProperties){this.creates++;if(this.failBefore)throw Error('Google 500');const id=crypto.randomUUID();this.files.set(id,{id,appProperties:clone(appProperties),text,createdTime:new Date().toISOString()});if(this.afterCreate)await this.afterCreate();if(this.ambiguous){this.ambiguous=false;throw Error('Lost response');}return {id};}
 async read(id){return this.files.get(id).text;}
}
async function setup(database=new Database(),transport=new Drive(),options={}){
 const sync=await openDriveBackup({database,transport,online:()=>true,withLock:fn=>fn(),...options});
 await sync.configure('123-test.apps.googleusercontent.com');await sync.connect();
 return {database,transport,sync};
}
const contents=async file=>(await inspectBackup(JSON.parse(file.text).backup)).data;

test('legacy conflict and outbox survive cutover; manual upload uses current full data, never old queue',async()=>{
 const db=new Database(),old=await makeNode(JSON.stringify(db.value),[]);
 db.state={clientId:'123-test.apps.googleusercontent.com',enabled:true,selected:'account-A',accounts:{'account-A':{base:[crypto.randomUUID()],ackRevision:18,outbox:{node:old,revision:19},resolution:{id:'old-choice'},failures:8}}};
 db.revision=30;const archived=clone(db.state.accounts);db.change('today');db.drafts=[{id:'unfinished-B'}];
 const before=db.export(),drive=new Drive(),{sync}=await setup(db,drive);
 assert.equal(db.state.enabled,false);assert.equal(db.state.mode,'manual');assert.deepEqual(db.state.accounts['account-A'].outbox,archived['account-A'].outbox);
 assert.equal(drive.creates,0);await sync.retryNow();sync.localChanged();assert.equal(drive.creates,0);
 const uploaded=await sync.upload();assert.equal(uploaded.revision,31);assert.equal(drive.files.size,1);
 const file=[...drive.files.values()][0];assert.deepEqual(await contents(file),before);
 assert.notEqual(JSON.parse(file.text).id,old.id);assert.deepEqual(JSON.parse(file.text).parents,[]);
 assert.deepEqual(db.export(),before);assert.deepEqual(db.drafts,[{id:'unfinished-B'}]);
 assert.deepEqual(db.state.accounts['account-A'].outbox,archived['account-A'].outbox);
 sync.close();const reopened=await openDriveBackup({database:db,transport:drive,online:()=>true,withLock:fn=>fn()});await reopened.connect();
 assert.equal(drive.creates,1);await reopened.upload();assert.equal(drive.files.size,2);
});

test('two devices always append independent current copies; previous files remain byte identical',async()=>{
 const files=new Map(),a=await setup(new Database(),new Drive(files)),b=await setup(new Database(),new Drive(files));
 a.database.change('A');b.database.change('B');await Promise.all([a.sync.upload(),b.sync.upload()]);
 const before=clone([...files.entries()]);a.database.change('A newer');await a.sync.upload();
 assert.equal(files.size,3);for(const [id,file] of before)assert.deepEqual(files.get(id),file);
 const result=await a.sync.download();assert.equal(result.choices.length,3);assert.match(result.warning,/różne historie/);
 assert.deepEqual((await inspectBackup((await a.sync.download([...files.keys()][1])).backup)).data,b.database.value);
 assert.equal(a.database.value.exercises['PULL B'][0].notes,'A newer');
});

test('latest valid backup uses server time not phone clock; corrupt latest requires explicit fallback',async()=>{
 const {sync,transport,database}=await setup();await sync.upload();const first=[...transport.files.values()][0];first.createdTime='2026-10-22T12:00:00Z';
 database.change('latest today');await sync.upload();const last=[...transport.files.values()][1];last.createdTime='2026-10-22T13:00:00Z';
 assert.deepEqual((await inspectBackup((await sync.download()).backup)).data,database.value);
 last.text=last.text.replace('latest today','tampered');
 const fallback=await sync.download();assert.equal(fallback.choices.length,1);assert.match(fallback.warning,/Pominięto/);assert.equal(fallback.backup,undefined);
 assert.deepEqual((await inspectBackup((await sync.download(first.id)).backup)).data,fixture());
 await assert.rejects(sync.download(last.id),/nieprawidłowa/);
});

test('legacy backup chains remain downloadable; divergent or undated copies need simple choice',async()=>{
 const {sync,transport}=await setup();
 const root=await makeNode(JSON.stringify(fixture()),[]),newer=fixture();newer.exercises['PULL B'][0].notes='new history';
 const child=await makeNode(JSON.stringify(newer),[root.id]);
 for(const [i,node] of [root,child].entries()){const f=await transport.create(JSON.stringify(node),properties(node));transport.files.get(f.id).createdTime=`2026-10-22T1${i}:00:00Z`;}
 const replay=await transport.create(JSON.stringify(root),properties(root));transport.files.get(replay.id).createdTime='2099-01-01T00:00:00Z';
 assert.deepEqual((await inspectBackup((await sync.download()).backup)).data,newer,'later server timestamp of a replayed ancestor must not win');
 const independent=await makeNode(JSON.stringify(fixture()),[]);await transport.create(JSON.stringify(independent),properties(independent));
 assert.ok((await sync.download()).choices);for(const f of transport.files.values())delete f.createdTime;
 assert.ok((await sync.download()).choices);
});

test('offline, authorization, failed POST or failed verification never consume results, drafts or old copies',async()=>{
 let online=true;const {sync,database,transport}=await setup(new Database(),new Drive(),{online:()=>online});
 database.change('safe local');database.drafts=[{id:'local-only'}];const before=database.export();
 online=false;await assert.rejects(sync.upload(),/Internetu/);assert.equal(transport.creates,0);
 online=true;transport.authenticated=false;await assert.rejects(sync.upload(),/Połącz/);await sync.connect();
 transport.failBefore=true;await assert.rejects(sync.upload(),/500/);transport.failBefore=false;
 const read=transport.read.bind(transport);transport.read=async()=>{throw Error('read failed')};
 await assert.rejects(sync.upload(),/read failed/);assert.ok(!sync.status.detail.includes('zweryfikowana'));assert.equal(transport.files.size,1);
 transport.read=read;await sync.upload();assert.equal(transport.files.size,2);
 assert.deepEqual(database.export(),before);assert.deepEqual(database.drafts,[{id:'local-only'}]);
 database.error=Error('bad database');await assert.rejects(sync.upload(),/odzyskaj/);assert.equal(transport.files.size,2);
});

test('local revision changed while preparing export cannot upload a mixed snapshot',async()=>{
 const {sync,database,transport}=await setup();database.model={};database.exportModelBackup=async()=>{database.change('changed during export');return JSON.stringify(fixture())};
 await assert.rejects(sync.upload(),/zmieniły/);assert.equal(transport.creates,0);
});

test('new local commit during network upload is preserved and reported as newer local data',async()=>{
 const {sync,database,transport}=await setup();transport.afterCreate=async()=>database.change('after snapshot');
 await sync.upload();assert.match(sync.status.detail,/W międzyczasie/);assert.equal(database.value.exercises['PULL B'][0].notes,'after snapshot');
 assert.equal((await contents([...transport.files.values()][0])).exercises['PULL B'][0].notes,fixture().exercises['PULL B'][0].notes);
});

test('account/client changes in another tab cannot reuse the old access token',async()=>{
 const db=new Database(),old=await setup(db,new Drive());const other=await openDriveBackup({database:db,transport:new Drive(),withLock:fn=>fn()});
 await other.disconnect();await assert.rejects(old.sync.upload(),/Połącz/);
 await old.sync.connect();old.transport.account='account-B';await assert.rejects(old.sync.connect(),/inne konto/);
 await old.sync.disconnect();await old.sync.connect();assert.equal(db.state.selected,'account-B');
 await other.configure('456-new.apps.googleusercontent.com');await assert.rejects(old.sync.upload(),/Połącz/);assert.equal(old.transport.creates,0);
});

test('full JSON validation rejects damaged and unsupported documents, preserving legacy extensions',async()=>{
 const extended=fixture();extended.data={opaque:'legacy extension'};
 assert.deepEqual((await inspectBackup(JSON.stringify(extended))).data,extended);
 for(const bad of ['{broken','null','{"version":900}'])await assert.rejects(makeNode(bad,[]));
});
