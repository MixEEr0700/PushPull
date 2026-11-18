import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createCanonicalBackup} from '../model/canonical-backup.mjs';
import {canonicalFixture} from './canonical-fixture.mjs';
import {openDriveBackup} from '../model/drive-sync.mjs';
import {createGoogleDrive} from '../model/google-drive.mjs';

const data=createCanonicalBackup(canonicalFixture(JSON.parse(readFileSync('tests/fixtures/v1.json')),4));
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
test('OAuth succeeds but a hung response body must settle with a usable error',async()=>{
 globalThis.google={accounts:{oauth2:{initTokenClient:({callback})=>({requestAccessToken:()=>callback({access_token:'synthetic',expires_in:3600})}),hasGrantedAllScopes:()=>true}}};
 const api=createGoogleDrive({timeoutMs:20,fetcher:async url=>url.includes('/about?')?new Response(JSON.stringify({user:{permissionId:'test-account'}})):new Response(new ReadableStream({start(){}}))});
 try{await api.connect('123-test.apps.googleusercontent.com');const result=await Promise.race([api.readPoint('point').catch(e=>e.message),new Promise(r=>setTimeout(()=>r('stalled'),200))]);assert.match(result,/Przekroczono czas/);}finally{delete globalThis.google;}
});
test('verified upload keeps a newer native finish intent without requiring a second readback',async()=>{
 let state=null,posts=0,ids=0;
 const files=new Map(),entered=deferred(),release=deferred();
 const database={revision:'local-revision',readDriveState:async()=>structuredClone(state),writeDriveState:async(v,token)=>{if((state?.token??null)!==token)throw Error('synthetic metadata CAS');state={...structuredClone(v),token:crypto.randomUUID()};return structuredClone(state);}};
 const transport={authenticated:false,clear(){this.authenticated=false;},async connect(){this.authenticated=true;return {id:'account'};},reservePointId:async()=>String(++ids),async readPoint(id){if(!files.has(id))throw Object.assign(Error('missing'),{status:404});return files.get(id);},async createPoint(id,text){posts++;entered.resolve();await release.promise;files.set(id,text);}};
 const engine=await openDriveBackup({database,transport,online:()=>true,withLock:f=>f(),captureCanonical:async()=>data});
 await engine.configure('123-test.apps.googleusercontent.com');await engine.connect();
 const writing=engine.queueCanonical();await Promise.race([entered.promise,writing.then(()=>assert.fail(engine.status.detail))]);state={...state,token:crypto.randomUUID(),ppc1Queue:'another-native-finish'};release.resolve();await writing;
 assert.equal(engine.status.verified!==null,true);assert.equal(state.ppc1Queue,'another-native-finish');assert.equal(state.accounts.account.ppc1.pending,undefined);assert.equal(posts,1);await engine.retryCanonical();assert.equal(posts,2);assert.equal(state.ppc1Queue,undefined);
});

test('an OAuth callback that never arrives times out and cannot revive an expired token',async()=>{
 let late;
 globalThis.google={accounts:{oauth2:{initTokenClient:({callback})=>({requestAccessToken:()=>{late=callback;}}),hasGrantedAllScopes:()=>true}}};
 try{
  const api=createGoogleDrive({oauthTimeoutMs:20,fetcher:()=>assert.fail('no account lookup without consent')});
  await assert.rejects(api.connect('123-test.apps.googleusercontent.com'),/czas logowania/);
  late({access_token:'late-synthetic',expires_in:3600});
  assert.equal(api.authenticated,false);
 }finally{delete globalThis.google;}
});

test('two independent devices append distinct histories and can verify the earlier point intact',async()=>{
 const {makePoint,uploadPoint,restorePoint}=await import('../model/drive-incremental.mjs');
 const files=new Map();
 const transport={async readPoint(id){if(!files.has(id))throw Object.assign(Error('missing'),{status:404});return files.get(id);},async createPoint(id,text){assert.ok(!files.has(id));files.set(id,text);}};
 const older=createCanonicalBackup(canonicalFixture(JSON.parse(readFileSync('tests/fixtures/v1.json')),2));
 const newer=await makePoint(data),stale=await makePoint(older);
 await uploadPoint(transport,{fileId:'new-device',packet:newer.packet});
 await uploadPoint(transport,{fileId:'old-device',packet:stale.packet});
 assert.equal(files.size,2);
 assert.deepEqual((await restorePoint(transport,'new-device')).value,data);
 assert.deepEqual((await restorePoint(transport,'old-device')).value,older);
});

test('reconnect cannot replace the OAuth token while a Drive operation is reading',async()=>{
 let state=null,connections=0;
 const started=deferred(),release=deferred();
 const database={readDriveState:async()=>structuredClone(state),writeDriveState:async v=>(state={...structuredClone(v),token:crypto.randomUUID()})};
 const transport={authenticated:false,clear(){this.authenticated=false;},async connect(){connections++;this.authenticated=true;return{id:'account'};},async listPoints(){started.resolve();await release.promise;return[];}};
 const engine=await openDriveBackup({database,transport,withLock:f=>f(),online:()=>true});
 await engine.configure('123-test.apps.googleusercontent.com');await engine.connect();
 const listing=engine.canonicalPoints();
 await started.promise;
 try{await assert.rejects(engine.connect(),/Trwa operacja/);assert.equal(connections,1);}
 finally{release.resolve();await listing;engine.close();}
});
