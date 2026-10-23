import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {openDriveSync,graph,makeNode,properties,readNode,inspectBackup} from '../model/drive-sync.mjs';
const fixture=()=>JSON.parse(readFileSync(new URL('fixtures/v1.json',import.meta.url)));
const clone=structuredClone;
class Database {
 constructor(){this.value=fixture();this.revision=1;this.model=null;this.error=null;this.state=null;this.drafts=[];this.preimages=[];}
 async readDriveState(){return clone(this.state);}
 async writeDriveState(value,expected){assert.equal(this.state?.token??null,expected);this.state={...clone(value),token:crypto.randomUUID()};return clone(this.state);}
 export(){return clone(this.value);}
 async readDrafts(){return clone(this.drafts);}
 change(note){this.value.exercises['PULL B'][0].notes=note;this.revision++;}
 async restore(text){this.preimages.push(this.export());this.value=clone((await inspectBackup(text)).data);this.revision++;}
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
async function setup(database=new Database(),transport=new Drive()){
 const sync=await openDriveSync({database,transport,online:()=>true,auto:false,withLock:fn=>fn()});
 await sync.configure('123-test.apps.googleusercontent.com');await sync.connect();
 return {database,transport,sync};
}
async function flush(sync){await sync.retryNow();await sync.retryNow();}

test('durable IDB revision queue: offline, restart, expired authorization, newer commit during ambiguous POST',async()=>{
 const db=new Database(),drive=new Drive(),s=await setup(db,drive);
 drive.authenticated=false;db.change('offline approved');s.sync.localChanged();await s.sync.retry();
 assert.equal(drive.creates,0);assert.equal(s.sync.status.label,'Oczekuje na synchronizację');
 s.sync.close();const reopened=await openDriveSync({database:db,transport:drive,auto:false,withLock:fn=>fn(),online:()=>true});
 await reopened.connect();await reopened.retryNow();assert.ok(db.state.accounts['account-A'].outbox);
 drive.ambiguous=true;await reopened.retryNow();assert.equal(drive.files.size,1);
 db.change('newer approved while previous response lost');await reopened.retryNow();
 assert.equal(db.state.accounts['account-A'].ackRevision,2);assert.equal(db.state.accounts['account-A'].outbox.revision,3);
 await reopened.retryNow();assert.equal(drive.files.size,2);assert.equal(drive.creates,2);
 assert.equal(reopened.status.label,'Zsynchronizowano');assert.equal(db.state.accounts['account-A'].ackRevision,3);
 const g=graph(await drive.list()),node=await readNode(drive,g.nodes.get(g.heads[0]));
 assert.equal((await inspectBackup(node.backup)).data.exercises['PULL B'][0].notes,'newer approved while previous response lost');
});

test('two devices branch safely, explicit keep-local resolution retains both complete copies',async()=>{
 const files=new Map(),a=await setup(new Database(),new Drive(files));await flush(a.sync);
 const b=await setup(new Database(),new Drive(files));await b.sync.retryNow();assert.match(b.sync.status.detail,/Konflikt/);assert.equal(files.size,1);
 const root=(await b.sync.listCopies())[0],ticket=await b.sync.preview(root);
 await b.sync.restore(ticket,text=>b.database.restore(text));
 a.database.change('A');b.database.change('B');await a.sync.retryNow();await b.sync.retryNow();
 let release;const barrier=new Promise(r=>release=r);let count=0;
 a.transport.afterCreate=b.transport.afterCreate=async()=>{if(++count===2)release();await barrier;};
 await Promise.all([a.sync.retryNow(),b.sync.retryNow()]);
 assert.equal(files.size,3);let g=graph(await a.transport.list());assert.equal(g.heads.length,2);
 const versions=await Promise.all(g.heads.map(id=>readNode(a.transport,g.nodes.get(id))));
 assert.deepEqual(new Set((await Promise.all(versions.map(n=>inspectBackup(n.backup)))).map(p=>p.data.exercises['PULL B'][0].notes)),new Set(['A','B']));
 a.transport.afterCreate=null;
 const heads=await a.sync.listCopies();await a.sync.keepLocal(heads);await flush(a.sync);
 g=graph(await a.transport.list());assert.equal(g.heads.length,1);assert.equal(files.size,4);
 assert.deepEqual(g.nodes.get(g.heads[0]).parents,heads.sort());
 assert.equal(a.sync.status.label,'Zsynchronizowano');assert.equal(b.database.value.exercises['PULL B'][0].notes,'B');
});

test('restore validates integrity, rejects stale previews and drafts, preserves local preimage',async()=>{
 const a=await setup();await flush(a.sync);const b=await setup(new Database(),new Drive(a.transport.files));
 const id=(await b.sync.listCopies())[0],ticket=await b.sync.preview(id),local=b.database.export();
 b.database.drafts=[{id:'draft'}];await assert.rejects(b.sync.restore(ticket,t=>b.database.restore(t)),/szkice/);assert.deepEqual(b.database.export(),local);
 b.database.drafts=[];b.database.change('changed after preview');await assert.rejects(b.sync.restore(ticket,t=>b.database.restore(t)),/zmieniły/);
 const fresh=await b.sync.preview(id);await b.sync.restore(fresh,t=>b.database.restore(t));assert.equal(b.database.preimages.length,1);
 assert.equal(b.database.preimages[0].exercises['PULL B'][0].notes,'changed after preview');
 const file=[...a.transport.files.values()][0],old=file.text;file.text=old.replace('Prostowanie','Tampered');
 await assert.rejects(b.sync.preview(id),/integralności/);file.text=old;
 await assert.rejects(makeNode('{"version":900}',[]));
});

test('API failure and sync metadata quota never consume official commits or drafts',async()=>{
 const {sync,database,transport}=await setup();transport.failBefore=true;database.change('safe local');database.drafts=[{id:'local-only'}];
 await flush(sync);assert.equal(transport.files.size,0);assert.equal(sync.status.label,'Błąd');assert.equal(database.value.exercises['PULL B'][0].notes,'safe local');
 assert.deepEqual(database.drafts,[{id:'local-only'}]);transport.failBefore=false;
 await flush(sync);assert.equal(sync.status.label,'Zsynchronizowano');
 const node=await readNode(transport,graph(await transport.list()).nodes.values().next().value);
 assert.ok(!node.backup.includes('local-only'));database.change('quota during enqueue');
 database.writeDriveState=async()=>{throw Error('QuotaExceededError');};await sync.retry();
 assert.equal(database.revision,3);assert.equal(database.value.exercises['PULL B'][0].notes,'quota during enqueue');assert.equal(sync.status.label,'Błąd');
});

test('changing Google accounts requires explicit disconnect; old account queues are retained',async()=>{
 const {sync,database,transport}=await setup();await sync.retryNow();const old=clone(database.state.accounts['account-A']);
 transport.account='account-B';await assert.rejects(sync.connect(),/inne konto/);assert.equal(transport.authenticated,false);
 await sync.disconnect();await sync.connect();assert.deepEqual(database.state.accounts['account-A'],old);
 assert.equal(database.state.selected,'account-B');assert.deepEqual(database.state.accounts['account-B'].base,[]);
});

test('private node metadata deduplicates ambiguous retries and rejects corrupt relationships',async()=>{
 const extended=fixture();extended.data={opaque:'legacy extension'};
 assert.deepEqual((await inspectBackup(JSON.stringify(extended))).data,extended);
 const node=await makeNode(JSON.stringify(fixture()),[]),meta=properties(node);
 const f={id:'file',appProperties:meta};assert.equal(graph([f,{...f,id:'duplicate'}]).nodes.size,1);
 assert.throws(()=>graph([f,{...f,appProperties:{...meta,digest:'a'.repeat(64)}}]),/Konflikt/);
 const broken=await makeNode(JSON.stringify(fixture()),[crypto.randomUUID()]);assert.throws(()=>graph([{id:'x',appProperties:properties(broken)}]),/Niekompletny/);
});


test('another tab switching accounts cannot send data with the old tab token',async()=>{
 const db=new Database(),old=await setup(db,new Drive());await flush(old.sync);
 const otherTransport=new Drive();otherTransport.account='account-B';
 const other=await openDriveSync({database:db,transport:otherTransport,online:()=>true,auto:false,withLock:fn=>fn()});
 await other.disconnect();await other.connect();db.change('B local');
 const count=old.transport.creates;await old.sync.retryNow();assert.equal(old.transport.creates,count);
 assert.match(old.sync.status.detail,/Połącz Google/);assert.equal(db.state.selected,'account-B');
});

function addWorkout(db,label,kg){
 const type='PUSH A',exerciseId=db.value.exercises[type][0].id;
 const session={id:'session-'+label,seq:Math.max(...db.value.sessions.map(s=>s.seq))+1,date:'2026-10-22',type,status:'done'};
 db.value.sessions.push(session);db.value.entries.push({id:'result-'+label,sessionId:session.id,exerciseId,kg,reps:'8',series:[{kg,reps:'8'}]});db.revision++;
}
async function settle(sync){for(let i=0;i<5;i++)await sync.retryNow();}

test('keep local survives an older complete Drive listing and confirms upload by file ID',async()=>{
 const cloud=await setup();await flush(cloud.sync);const rootFiles=clone(await cloud.transport.list());
 cloud.database.change('new cloud base');await flush(cloud.sync);
 const phone=await setup(new Database(),new Drive(cloud.transport.files));addWorkout(phone.database,'android','83');phone.database.drafts=[{id:'unfinished-side-B'}];
 const heads=await phone.sync.listCopies(),before=clone(phone.database.value),oldCount=phone.transport.files.size;
 phone.transport.list=async()=>clone(rootFiles);
 await phone.sync.keepLocal(heads);
 // Google search can return an older but internally complete graph. Direct GET
 // by the POST's returned file ID still has the newly written document.
 phone.transport.list=async()=>clone(rootFiles);
 await settle(phone.sync);
 assert.equal(phone.sync.status.label,'Zsynchronizowano');assert.ok(phone.sync.status.lastSuccess);
 assert.deepEqual(phone.database.value,before);assert.deepEqual(phone.database.drafts,[{id:'unfinished-side-B'}]);
 assert.equal(phone.transport.files.size,oldCount+1);
 const all=Drive.prototype.list.call(phone.transport),g=graph(await all),node=await readNode(phone.transport,g.nodes.get(g.heads[0]));
 assert.deepEqual((await inspectBackup(node.backup)).data,before);assert.deepEqual(node.parents,heads);
 // Empty search results are also not proof that a confirmed parent vanished.
 phone.transport.list=async()=>[];addWorkout(phone.database,'empty-search','84');await settle(phone.sync);
 assert.equal(phone.sync.status.label,'Zsynchronizowano');
 const complete=graph(await Drive.prototype.list.call(phone.transport)),latest=await readNode(phone.transport,complete.nodes.get(complete.heads[0]));
 assert.deepEqual(latest.parents,[node.id]);assert.deepEqual((await inspectBackup(latest.backup)).data,phone.database.value);
});

test('two devices: keep local preserves pending UUID and publishes latest workout as a joined new copy',async()=>{
 const phone=await setup();await flush(phone.sync);
 const pc=await setup(new Database(),new Drive(phone.transport.files));
 const ticket=await pc.sync.preview((await pc.sync.listCopies())[0]);await pc.sync.restore(ticket,t=>pc.database.restore(t));await settle(pc.sync);
 // Explicit choice first aligns this phone to the current reviewed heads.
 await phone.sync.keepLocal(await phone.sync.listCopies());await settle(phone.sync);
 addWorkout(phone.database,'phone-pending','87');await phone.sync.retryNow();
 const pending=clone(phone.database.state.accounts['account-A'].outbox);assert.ok(pending);
 // Another client advances after the phone enqueues but before its upload.
 await pc.sync.keepLocal(await pc.sync.listCopies());await settle(pc.sync);
 addWorkout(pc.database,'pc-parallel','64');await settle(pc.sync);
 addWorkout(phone.database,'phone-latest','91');
 await phone.sync.retryNow();assert.match(phone.sync.status.detail,/Konflikt/);
 const heads=await phone.sync.listCopies(),local=clone(phone.database.value),oldFiles=clone([...phone.transport.files.values()]);
 await phone.sync.keepLocal(heads);
 assert.equal(phone.database.state.accounts['account-A'].outbox.node.id,pending.node.id,'keep must retain the durable original operation');
 phone.sync.close();phone.transport=new Drive(phone.transport.files);
 phone.sync=await openDriveSync({database:phone.database,transport:phone.transport,online:()=>true,auto:false,withLock:fn=>fn()});await phone.sync.connect();
 await settle(phone.sync);
 assert.equal(phone.sync.status.label,'Zsynchronizowano');assert.equal(phone.database.state.accounts['account-A'].ackRevision,phone.database.revision);
 const g=graph(await phone.transport.list());assert.equal(g.heads.length,1);assert.ok(g.nodes.has(pending.node.id));
 const latest=await readNode(phone.transport,g.nodes.get(g.heads[0]));assert.deepEqual((await inspectBackup(latest.backup)).data,local);
 for(const old of oldFiles)assert.deepEqual(phone.transport.files.get(old.id),old);
 assert.ok([...phone.transport.files.values()].some(f=>f.text.includes('pc-parallel')));
 assert.ok(pc.database.value.entries.some(e=>e.id==='result-pc-parallel'));
 assert.ok(!phone.database.value.entries.some(e=>e.id==='result-pc-parallel'),'no silent merge or replacement');
 // A new, unreviewed edit after listing still requires a fresh decision.
 const oldChoice=await phone.sync.listCopies();addWorkout(pc.database,'pc-later','66');await pc.sync.keepLocal(await pc.sync.listCopies());await settle(pc.sync);
 await assert.rejects(phone.sync.keepLocal(oldChoice),/Drive zmienił/);
 addWorkout(phone.database,'phone-later','92');const count=phone.transport.files.size;await settle(phone.sync);
 assert.match(phone.sync.status.detail,/Konflikt/);assert.equal(phone.transport.files.size,count);
});

test('POST receipt survives failed read-back and restart without duplicate upload or false success',async()=>{
 const phone=await setup();await flush(phone.sync);const roots=clone(await phone.transport.list());
 addWorkout(phone.database,'before-read-error','94');await phone.sync.retryNow();
 const id=phone.database.state.accounts['account-A'].outbox.node.id;
 const read=phone.transport.read.bind(phone.transport);let fail=true;
 phone.transport.read=async fileId=>{if(fail)throw Error('Interrupted verification');return read(fileId);};
 await phone.sync.retryNow();assert.equal(phone.sync.status.label,'Błąd');assert.notEqual(phone.database.state.accounts['account-A'].ackRevision,phone.database.revision);
 assert.ok(phone.database.state.accounts['account-A'].outbox.fileId);assert.equal(phone.transport.files.size,2);
 fail=false;phone.transport.list=async()=>clone(roots);
 phone.sync.close();
 const reopened=await openDriveSync({database:phone.database,transport:phone.transport,online:()=>true,auto:false,withLock:fn=>fn()});await reopened.connect();await settle(reopened);
 assert.equal(reopened.status.label,'Zsynchronizowano');assert.equal(phone.transport.files.size,2);
 const node=await readNode(phone.transport,graph(await Drive.prototype.list.call(phone.transport)).nodes.get(id));
 assert.deepEqual((await inspectBackup(node.backup)).data,phone.database.value);
});
