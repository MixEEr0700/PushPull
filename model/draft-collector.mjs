/** Read-only observations, not a globally atomic backup/collector of unknown tabs. */
import {inspectDraftEvidence} from './backup-v6.mjs';
import {canonical,freeze} from './backup-json.mjs';
const PREFIX='pushpull_workout_draft_v1:';
const abort=s=>{if(s?.aborted)throw new DOMException('Anulowano odczyt szkiców','AbortError');};
const failure=code=>Object.assign(Error('Kolektor szkiców: '+code),{code});
const evidence=sources=>({format:'pushpull-draft-evidence',version:1,sources});
function validate(sources,limits){if(!Array.isArray(sources)||sources.length>(limits.sources??1024))throw failure('limit-or-source-error');try{return inspectDraftEvidence(evidence(sources),{limits});}catch{throw failure('limit-or-source-error');}}
function waiting(promise,signal){
 abort(signal);if(!signal)return promise;
 return new Promise((resolve,reject)=>{
  const cancel=()=>{signal.removeEventListener('abort',cancel);reject(new DOMException('Anulowano odczyt szkiców','AbortError'));};
  signal.addEventListener('abort',cancel,{once:true});
  Promise.resolve(promise).then(value=>{signal.removeEventListener('abort',cancel);resolve(value);},error=>{signal.removeEventListener('abort',cancel);reject(error);});
 });
}
export function readBuffer(storage){
 const out=[],length=storage.length;for(let i=0;i<length;i++){const k=storage.key(i);if(typeof k!=='string')throw failure('unstable');if(!k.startsWith(PREFIX))continue;const raw=storage.getItem(k);if(raw===null)throw failure('unstable');out.push({source:'local-buffer',storageKey:k,raw});}
 if(storage.length!==length)throw failure('unstable');
 return out.sort((a,b)=>a.storageKey<b.storageKey?-1:a.storageKey>b.storageKey?1:0);
}
export async function collectDrafts({database,getMemory,storage=()=>globalThis.localStorage,peers,signal,limits={},attempts=2,pause=()=>new Promise(r=>setTimeout(r,0))}){
 if(!Number.isSafeInteger(attempts)||attempts<1||attempts>3)throw failure('invalid-attempts');
 const known=new Set(),startedAt=new Date().toISOString();
 async function observe(){
  abort(signal);let idb,buffer,memory,remote=[];
  try{idb=await waiting(database.readDraftObservation(),signal);}catch(e){throw failure(e.code==='draft-read-limit'?'limit-or-source-error':'idb-unavailable');}abort(signal);
  if(!Number.isSafeInteger(idb?.historyRevision)||!Array.isArray(idb?.sources))throw failure('idb-unavailable');
  try{buffer=readBuffer(storage());}catch(e){throw failure(e.code==='unstable'?'unstable':'local-unavailable');}
  try{memory=getMemory();if(!Array.isArray(memory))throw Error();}catch{throw failure('memory-unavailable');}
  validate([...idb.sources,...buffer,...memory],limits);
  if(peers){try{remote=await waiting(peers.observe({signal}),signal);}catch(e){abort(signal);throw failure('peer-unavailable');}}
  abort(signal);if(!Array.isArray(remote)||remote.length>32)throw failure('peer-limit');const ids=new Set();
  for(const p of remote){if(!p||typeof p.id!=='string'||ids.has(p.id)||!Array.isArray(p.sources))throw failure('peer-unavailable');ids.add(p.id);known.add(p.id);if(p.error)throw failure('peer-unavailable');}
  if([...known].some(id=>!ids.has(id)))throw failure('peer-unavailable');
  remote.sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);
  const sources=[...idb.sources,...buffer,...memory,...remote.flatMap(p=>p.sources)];
  validate(sources,limits);
  return {historyRevision:idb.historyRevision,sources:structuredClone(sources),responders:remote.map(p=>p.id)};
 }
 for(let attempt=1;attempt<=attempts;attempt++){
  let first,second;
  try{first=await observe();await waiting(pause(),signal);abort(signal);second=await observe();}
  catch(e){abort(signal);if(e.code==='unstable'&&attempt<attempts)continue;throw e;}
  if(canonical(first)!==canonical(second)){if(attempt<attempts)continue;throw failure('unstable');}
  const inspected=validate(second.sources,limits);abort(signal);
  return freeze({evidence:evidence(second.sources),classification:inspected.classification,
   capture:{version:1,historyRevision:second.historyRevision,startedAt,completedAt:new Date().toISOString(),consistency:'observed-stable',scope:'observed-origin'},
   coverage:{idb:'read',localStorage:'read',memory:'captured-editor-state',respondingTabs:second.responders.length,otherTabs:'unknown',atomicAcrossSources:false},
   diagnostics:{attempts:attempt,sources:second.sources.length,conflicts:inspected.classification.filter(x=>x.status==='conflict').length,quarantined:inspected.classification.filter(x=>x.status==='quarantine').length}});
 }
}
/** Only respondents are observed. No discovery claim, persistent registry or write locks. */
export function openDraftObserver(getMemory,{Channel=globalThis.BroadcastChannel,timeoutMs=60}={}){
 if(!Channel)return null;
 if(!Number.isSafeInteger(timeoutMs)||timeoutMs<1||timeoutMs>500)throw failure('invalid-timeout');
 let channel;try{channel=new Channel('pushpull-draft-observer-v1');}catch{return null;}
 const id=crypto.randomUUID(),pending=new Map();let closed=false;
 channel.onmessage=({data:d})=>{
  if(closed||!d||typeof d.request!=='string')return;
  if(d.type==='request'){
   try{const sources=getMemory();validate(sources,{});channel.postMessage({type:'response',request:d.request,id,sources});}
   catch{try{channel.postMessage({type:'response',request:d.request,id,sources:[],error:true});}catch{}}
  }else if(d.type==='response'&&typeof d.id==='string'&&pending.has(d.request)){const responses=pending.get(d.request);if(responses.size<33||responses.has(d.id))responses.set(d.id,{id:d.id,sources:d.sources,error:d.error});}
 };
 return {observe({signal}={}){
  abort(signal);if(closed)return Promise.reject(failure('peer-unavailable'));
  return new Promise((resolve,reject)=>{
   const request=crypto.randomUUID(),responses=new Map();let timer;
   const clean=()=>{clearTimeout(timer);pending.delete(request);signal?.removeEventListener('abort',cancel);};
   const cancel=()=>{clean();reject(new DOMException('Anulowano odczyt szkiców','AbortError'));};
   signal?.addEventListener('abort',cancel,{once:true});pending.set(request,responses);
   timer=setTimeout(()=>{clean();closed?reject(failure('peer-unavailable')):resolve([...responses.values()]);},timeoutMs);
   try{channel.postMessage({type:'request',request});}catch{clean();reject(failure('peer-unavailable'));}
  });
 },close(){closed=true;channel.close();}};
}
