/** Isolated evidence envelope. No collectors, storage, restore, download or network. */
import {decodeBackup as decodeHistory} from './backup-v5.mjs';
import {boundedBackupJson,V4_LIMITS} from './backup-v4.mjs';
import {portable,record,canonical,freeze,requireThat as check} from './backup-json.mjs';
import {editorValueValid} from './workout-drafts.mjs';
const MiB=1024*1024,utf8=new TextEncoder();
export const V6_LIMITS=Object.freeze({...V4_LIMITS,draftStoredBytes:4*MiB,draftDecodedBytes:4*MiB,sourceBytes:MiB,sources:1024,identities:256});
const abort=s=>{if(s?.aborted)throw new DOMException('Backup cancelled','AbortError');};
const sha=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b)),n=>n.toString(16).padStart(2,'0')).join('');
const exact=(x,keys)=>check(record(x)&&Object.keys(x).length===keys.length&&keys.every(k=>Object.hasOwn(x,k)),'v6: missing or unsupported fields');
const iso=x=>typeof x==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(x).toISOString()===x;
const text=x=>typeof x==='string'&&x.length>0;
function policy(overrides={}){check(record(overrides),'v6: limits');const l={...V6_LIMITS};for(const [k,v] of Object.entries(overrides)){check(Object.hasOwn(l,k)&&Number.isSafeInteger(v)&&v>0&&v<=l[k],'v6: limits may only be lowered');l[k]=v;}return l;}
const historyLimits=l=>Object.fromEntries(Object.keys(V4_LIMITS).map(k=>[k,l[k]]));
// Exact JSON byte preflight without allocating an escaped copy of large input.
function stringSize(s,max){let n=2;for(let i=0;i<s.length;i++){const c=s.charCodeAt(i);if(c===34||c===92||[8,9,10,12,13].includes(c))n+=2;else if(c<32)n+=6;else if(c>=0xd800&&c<=0xdbff&&i+1<s.length&&s.charCodeAt(i+1)>=0xdc00&&s.charCodeAt(i+1)<=0xdfff){n+=4;i++;}else if(c>=0xd800&&c<=0xdfff)n+=6;else n+=c<128?1:c<2048?2:3;check(n<=max,'v6: size limit');}check(n<=max,'v6: size limit');return n;}
function jsonSize(x,max,depth=0){check(depth<=64,'v6: depth limit');if(typeof x==='string')return stringSize(x,max);if(x===null||typeof x!=='object')return JSON.stringify(x).length;let n=2;const array=Array.isArray(x);for(const [i,k] of Object.keys(x).entries()){n+=(i?1:0)+(array?0:stringSize(k,max)+1)+jsonSize(x[k],max,depth+1);check(n<=max,'v6: size limit');}return n;}
const seal=d=>canonical({...d,integrity:{algorithm:'SHA-256'}});
function captureValid(c){exact(c,['version','historyRevision','startedAt','completedAt','consistency','scope']);check(c.version===1&&Number.isSafeInteger(c.historyRevision)&&c.historyRevision>=0&&iso(c.startedAt)&&iso(c.completedAt)&&c.startedAt<=c.completedAt&&c.consistency==='observed-stable'&&c.scope==='observed-origin','v6: capture scope or revision');}
function draftValid(r){
 if(!record(r)||r.version!==1||!text(r.id)||r.key!=='workout-draft:'+r.id||!text(r.token)||!Number.isSafeInteger(r.sequence)||r.sequence<=0||!iso(r.updatedAt)||!record(r.context)||!text(r.sessionId)||!text(r.exerciseId)||r.context.sessionId!==r.sessionId||r.context.exerciseId!==r.exerciseId||!(r.baseline===null||record(r.baseline)))return false;
 const c=r.context;if(!['sessionType','status','snapshotId','planVersionId','positionId','variantId','legacyDefinition'].every(k=>Object.hasOwn(c,k)))return false;
 if(![c.sessionType,c.status,c.snapshotId,c.planVersionId,c.positionId,c.variantId].every(v=>v===null||typeof v==='string')||!(c.legacyDefinition===null||record(c.legacyDefinition)))return false;
 try{return !!editorValueValid(r.kind,r.value);}catch{return false;}
}
function evidenceValid(e,l){
 exact(e,['format','version','sources']);check(e.format==='pushpull-draft-evidence'&&e.version===1&&Array.isArray(e.sources)&&e.sources.length<=l.sources,'v6: evidence sources');
 const identities=new Set(),classification=[],groups=new Map();
 for(const [i,s] of e.sources.entries()){
  jsonSize(s,l.sourceBytes);let r=null,valid=false;
  if(s?.source==='idb-meta'){
   exact(s,['source','storageKey','value']);check(typeof s.storageKey==='string'&&s.storageKey.startsWith('workout-draft:')&&s.storageKey.length>14,'v6: IDB source key');r=s.value;valid=draftValid(r)&&s.storageKey===r.key;
  }else if(s?.source==='local-buffer'){
   exact(s,['source','storageKey','raw']);const prefix='pushpull_workout_draft_v1:';
   check(typeof s.storageKey==='string'&&s.storageKey.startsWith(prefix)&&s.storageKey.length>prefix.length&&typeof s.raw==='string','v6: buffer source');
   try{r=boundedBackupJson(s.raw,l,l.sourceBytes);valid=draftValid(r)&&(s.storageKey===prefix+r.id||s.storageKey===prefix+r.id+':'+r.token);}catch{valid=false;}
  }else if(s?.source==='editor-memory'){
   exact(s,['source','record','binding','durableToken','parent']);r=s.record;
   valid=draftValid(r)&&record(s.binding)&&canonical(s.binding.context)===canonical(r.context)&&canonical(s.binding.baseline)===canonical(r.baseline)&&(s.durableToken===null||text(s.durableToken))&&(s.parent===null||draftValid(s.parent));
  }else check(false,'v6: unknown source');
  // Retain every source, including malformed evidence. No winner by date/sequence.
  identities.add(text(r?.id)?r.id:'opaque:'+s.source+':'+(s.storageKey??i));
  if(text(r?.id)){
   const matches=s.source==='idb-meta'?s.storageKey==='workout-draft:'+r.id:s.source==='local-buffer'?(s.storageKey==='pushpull_workout_draft_v1:'+r.id||s.storageKey==='pushpull_workout_draft_v1:'+r.id+':'+r.token):r.key==='workout-draft:'+r.id;
   if(!matches)identities.add('unbound:'+s.source+':'+(s.storageKey??i));
  }
  if(text(s.parent?.id))identities.add(s.parent.id);
  check(identities.size<=l.identities,'v6: identity limit');
  classification.push({status:valid?'candidate':'quarantine'});
  if(valid){const group=groups.get(r.id)??[];group.push({index:i,record:r});groups.set(r.id,group);}
 }
 for(const group of groups.values()){const first=canonical(group[0].record);if(group.some(x=>canonical(x.record)!==first))for(const x of group)classification[x.index].status='conflict';}
 return classification;
}
function logicalHistory(d){const p=d.payload,index=new Map(p.blobs.map(b=>[b.id,b]));let n=index.get(p.live.blobId).decodedBytes;for(const a of p.archives)n+=index.get(a.blobId).decodedBytes;return n;}
async function stream(bytes,mode,max,signal){
 abort(signal);const transform=mode==='gzip'?new CompressionStream('gzip'):new DecompressionStream('gzip');
 const reader=new Blob([bytes]).stream().pipeThrough(transform).getReader(),chunks=[];let n=0;
 try{while(true){abort(signal);const {done,value}=await reader.read();if(done)break;n+=value.length;check(n<=max,'v6: stream size limit');chunks.push(value);}}
 catch(e){await reader.cancel().catch(()=>{});throw e;}finally{reader.releaseLock();}
 const out=new Uint8Array(n);let offset=0;for(const chunk of chunks){out.set(chunk,offset);offset+=chunk.length;}return out;
}
function base64(bytes){let s='';for(let i=0;i<bytes.length;i+=32768)s+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(s);}
function unbase64(s,n,max){check(Number.isSafeInteger(n)&&n>=0&&n<=max&&typeof s==='string'&&s.length===4*Math.ceil(n/3),'v6: stored size');let raw;try{raw=atob(s);}catch{check(false,'v6: base64');}check(raw.length===n&&btoa(raw)===s,'v6: noncanonical base64');return Uint8Array.from(raw,c=>c.charCodeAt(0));}
async function decoded(text,{limits={},signal}={}){
 const l=policy(limits);abort(signal);const d=boundedBackupJson(text,l,l.fileBytes);
 if(d?.version!==6)return decodeHistory(text,{limits:historyLimits(l),signal});
 exact(d,['format','version','createdAt','history','capture','drafts','integrity']);check(d.format==='pushpull-backup'&&iso(d.createdAt)&&d.history?.version===5,'v6: header/history');captureValid(d.capture);
 exact(d.integrity,['algorithm','digest']);check(d.integrity.algorithm==='SHA-256'&&await sha(utf8.encode(seal(d)))===d.integrity.digest,'v6: manifest checksum');
 const b=d.drafts;exact(b,['format','version','encoding','compression','storedBytes','decodedBytes','storedSha256','decodedSha256','data']);
 check(b.format==='pushpull-drafts'&&b.version===1&&b.encoding==='json-string-utf8'&&b.compression==='gzip'&&Number.isSafeInteger(b.decodedBytes)&&b.decodedBytes>=0&&b.decodedBytes<=l.draftDecodedBytes,'v6: draft descriptor');
 check(/^[a-f0-9]{64}$/.test(b.storedSha256)&&/^[a-f0-9]{64}$/.test(b.decodedSha256),'v6: digest');
 const logical=logicalHistory(d.history);check(Number.isSafeInteger(logical)&&logical>=0&&logical+b.decodedBytes<=l.totalDecodedBytes,'v6: aggregate logical limit');
 const history=await decodeHistory(JSON.stringify(d.history),{limits:historyLimits(l),signal});
 const stored=unbase64(b.data,b.storedBytes,l.draftStoredBytes);check(await sha(stored)===b.storedSha256,'v6: stored checksum');
 const bytes=await stream(stored,'gunzip',b.decodedBytes,signal);check(bytes.length===b.decodedBytes&&await sha(bytes)===b.decodedSha256,'v6: decoded checksum');
 const token=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes),evidenceText=boundedBackupJson(token,l,l.draftDecodedBytes);
 check(typeof evidenceText==='string'&&JSON.stringify(evidenceText)===token,'v6: canonical string token');
 const evidence=boundedBackupJson(evidenceText,l,l.draftDecodedBytes),classification=evidenceValid(evidence,l);abort(signal);
 return freeze({formatVersion:6,createdAt:d.createdAt,historyDocument:d.history,history,capture:d.capture,draftEvidence:evidence,classification,draftCoverage:'observed-origin'});
}
/** No partial staging and no user content in parser errors. */
export async function decodeBackup(text,options={}){
 try{return await decoded(text,options);}catch(e){if(e.name==='AbortError')throw new DOMException('Backup cancelled','AbortError');throw Error('v6: invalid backup or limit/checksum failure');}
}
export async function exportBackupV6(input,{limits={},signal}={}){
 const l=policy(limits);abort(signal);portable(input);
 exact(input,['history','evidence','capture','createdAt']);check(input.history?.version===5&&iso(input.createdAt),'v6: input');captureValid(input.capture);
 check(Array.isArray(input.evidence?.sources)&&input.evidence.sources.length<=l.sources,'v6: sources required');
 jsonSize(input.history,l.fileBytes);jsonSize(input.evidence,l.draftDecodedBytes);
 evidenceValid(input.evidence,l);
 const evidenceText=JSON.stringify(input.evidence);stringSize(evidenceText,l.draftDecodedBytes);
 const detached=structuredClone(input),history=detached.history;
 const historyStage=await decodeHistory(JSON.stringify(history),{limits:historyLimits(l),signal});
 const bytes=utf8.encode(JSON.stringify(evidenceText));check(logicalHistory(history)+bytes.length<=l.totalDecodedBytes,'v6: aggregate logical limit');
 const stored=await stream(bytes,'gzip',l.draftStoredBytes,signal);
 const drafts={format:'pushpull-drafts',version:1,encoding:'json-string-utf8',compression:'gzip',storedBytes:stored.length,decodedBytes:bytes.length,storedSha256:await sha(stored),decodedSha256:await sha(bytes),data:base64(stored)};
 const d={format:'pushpull-backup',version:6,createdAt:detached.createdAt,history,capture:detached.capture,drafts,integrity:{algorithm:'SHA-256'}};
 jsonSize(d,l.fileBytes);d.integrity.digest=await sha(utf8.encode(seal(d)));jsonSize(d,l.fileBytes);
 const text=JSON.stringify(d),stage=await decodeBackup(text,{limits,signal});
 check(canonical(stage.draftEvidence)===canonical(detached.evidence)&&canonical(stage.historyDocument)===canonical(history)&&canonical(stage.capture)===canonical(detached.capture),'v6: self verification');
 abort(signal);return {text,diagnostics:Object.freeze({formatVersion:6,fileBytes:utf8.encode(text).length,sources:detached.evidence.sources.length,quarantined:stage.classification.filter(x=>x.status==='quarantine').length,conflicts:stage.classification.filter(x=>x.status==='conflict').length,historyVersion:historyStage.formatVersion})};
}

/** Additive read-only API; no format/codec change. */
export function inspectDraftEvidence(evidence,{limits={}}={}){
 const l=policy(limits);portable(evidence);jsonSize(evidence,l.draftDecodedBytes);
 stringSize(JSON.stringify(evidence),l.draftDecodedBytes);
 return freeze({classification:evidenceValid(evidence,l)});
}
