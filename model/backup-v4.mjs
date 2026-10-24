/** Isolated stage-A reader. No storage, DOM, network, writer or production hooks. */
import {canonical,parseJson,record,freeze,requireThat as check} from './backup-json.mjs';
import {readLegacyBackup} from './legacy-backup.mjs';
import {parseModelBackup} from './legacy-model.mjs';

const MiB=1024*1024;
export const V4_LIMITS=Object.freeze({fileBytes:32*MiB,storedBlobBytes:16*MiB,
 decodedBlobBytes:64*MiB,totalDecodedBytes:128*MiB,blobs:1024,archives:10000,
 depth:64,tokens:1000000});
const hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const size=x=>Number.isSafeInteger(x)&&x>=0;
const sha=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
const utf8=new TextEncoder();
const exact=(x,keys)=>check(record(x)&&Object.keys(x).length===keys.length&&keys.every(k=>Object.hasOwn(x,k)),'v4: unsupported or missing fields');
function aborted(signal){if(signal?.aborted)throw new DOMException('Backup staging cancelled','AbortError');}
function limitsFor(overrides){
 check(record(overrides),'v4: limits must be a record');
 const limits={...V4_LIMITS};
 for(const [key,value] of Object.entries(overrides)){
  check(Object.hasOwn(limits,key)&&Number.isSafeInteger(value)&&value>0&&value<=limits[key],'v4: limits may only be lowered');limits[key]=value;
 }
 return limits;
}
// Bound nesting and numeric tokens BEFORE the existing lossless JSON scanner,
// recursive validators, canonicalization and BigInt decimal comparison run.
function json(text,limits,maxBytes){
 check(typeof text==='string'&&text.length<=maxBytes,'v4: text size limit');
 let depth=0,tokens=0;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(c==='"'){
   tokens++;let closed=false;
   while(++i<text.length){if(text[i]==='\\')i++;else if(text[i]==='"'){closed=true;break;}}
   check(closed,'v4: truncated string');
  }else if(c==='{'||c==='['){check(++depth<=limits.depth,'v4: nesting limit');tokens++;}
  else if(c==='}'||c===']')depth--;
  else if(c==='-'||c>='0'&&c<='9'){
   const start=i;while(i+1<text.length&&/[0-9eE+.\-]/.test(text[i+1]))i++;
   check(i-start<128,'v4: numeric token limit');tokens++;
  }else if(c==='t'||c==='f'||c==='n'){
   tokens++;i+=(c==='f'?5:4)-1;
  }
  check(tokens<=limits.tokens,'v4: token limit');
 }
 check(utf8.encode(text).length<=maxBytes,'v4: UTF-8 size limit');
 return parseJson(text);
}
function base64(text,expected,limit){
 check(typeof text==='string'&&expected<=limit&&text.length===4*Math.ceil(expected/3),'v4: stored size limit');
 const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
 const padding=expected%3===0?0:3-expected%3;
 for(let i=0;i<text.length;i++)check(i<text.length-padding?alphabet.includes(text[i]):text[i]==='=','v4: invalid base64');
 if(padding)check((alphabet.indexOf(text[text.length-padding-1])&((1<<(2*padding))-1))===0,'v4: noncanonical base64');
 const raw=atob(text);check(raw.length===expected,'v4: stored size mismatch');
 return Uint8Array.from(raw,c=>c.charCodeAt(0));
}
async function expand(bytes,blob,limits,signal){
 aborted(signal);
 if(blob.compression==='none'){
  check(bytes.length===blob.decodedBytes,'v4: decoded size mismatch');return bytes;
 }
 check(typeof DecompressionStream==='function','v4: gzip decoding unavailable');
 const reader=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip')).getReader();
 const chunks=[];let total=0;
 try{
  while(true){
   aborted(signal);const {value,done}=await reader.read();if(done)break;
   total+=value.length;
   check(total<=blob.decodedBytes&&total<=limits.decodedBlobBytes,'v4: decompression size limit');chunks.push(value);
  }
 }catch(error){await reader.cancel().catch(()=>{});throw error;}
 finally{reader.releaseLock();}
 check(total===blob.decodedBytes,'v4: decoded size mismatch');
 const result=new Uint8Array(total);let offset=0;
 for(const chunk of chunks){result.set(chunk,offset);offset+=chunk.length;}
 return result;
}
async function legacy(text,limits){
 const d=json(text,limits,limits.decodedBlobBytes);
 if(d?.version===3){
  if(Array.isArray(d.payload?.legacySources))for(const source of d.payload.legacySources)json(source.raw,limits,limits.decodedBlobBytes);
  // Same supported source-backed v3 as today's full journal importer. Never
  // flatten unknown future v3 payloads into a partial history.
  const p=await parseModelBackup(text);
  return {formatVersion:3,raw:text,document:p.document,data:p.data,catalog:p.catalog,archives:p.archives??[]};
 }
 const p=readLegacyBackup(text);
 return {formatVersion:p.formatVersion,raw:text,document:p.original,data:p.data,catalog:p.catalog,archives:p.original.archives??[]};
}
function archiveMetadata(x){
 check(record(x)&&!Object.hasOwn(x,'raw')&&typeof x.id==='string'&&x.id.length>0&&
  typeof x.kind==='string'&&typeof x.createdAt==='string'&&Number.isFinite(Date.parse(x.createdAt)),'v4: archive metadata');
}
/** Return one detached immutable staging value, only after ALL checks succeed.
 * Limits can be lowered, never disabled. Caller retains its data on rejection.
 * Legacy v1/v2/source-backed v3 are delegated to the established readers.
 */
export async function decodeBackup(text,{limits:overrides={},signal}={}){
 const limits=limitsFor(overrides);aborted(signal);
 const d=json(text,limits,limits.fileBytes);
 if(d?.version!==4){const live=await legacy(text,limits);aborted(signal);return freeze({formatVersion:live.formatVersion,live,archives:live.archives});}
 exact(d,['format','version','createdAt','metadata','live','archives','blobs','integrity']);
 check(d.format==='pushpull-backup'&&typeof d.createdAt==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(d.createdAt)&&
  Number.isFinite(Date.parse(d.createdAt))&&new Date(d.createdAt).toISOString()===d.createdAt&&record(d.metadata),'v4: header');
 exact(d.live,['formatVersion','blobId']);check([1,2,3].includes(d.live.formatVersion),'v4: live version');
 exact(d.integrity,['algorithm','digest']);check(d.integrity.algorithm==='SHA-256'&&hex(d.integrity.digest),'v4: manifest integrity');
 check(Array.isArray(d.blobs)&&d.blobs.length>0&&d.blobs.length<=limits.blobs&&Array.isArray(d.archives)&&d.archives.length<=limits.archives,'v4: manifest count limit');
 const index=new Map(),referenced=new Set([d.live.blobId]),ids=new Set();let total=0;
 for(const b of d.blobs){
  exact(b,['id','encoding','compression','storedBytes','decodedBytes','storedSha256','decodedSha256','data']);
  check(hex(b.decodedSha256)&&hex(b.storedSha256)&&b.id==='sha256:'+b.decodedSha256&&!index.has(b.id),'v4: blob identity');
  check(b.encoding==='json-string-utf8'&&['none','gzip'].includes(b.compression),'v4: unsupported blob encoding');
  check(size(b.storedBytes)&&b.storedBytes<=limits.storedBlobBytes&&size(b.decodedBytes)&&b.decodedBytes<=limits.decodedBlobBytes,'v4: blob size limit');
  total+=b.decodedBytes;check(total<=limits.totalDecodedBytes,'v4: aggregate size limit');index.set(b.id,b);
 }
 for(const a of d.archives){
  exact(a,['metadata','blobId']);archiveMetadata(a.metadata);
  check(!ids.has(a.metadata.id),'v4: duplicate archive ID');ids.add(a.metadata.id);
  if(a.blobId!==null){check(typeof a.blobId==='string','v4: archive reference');referenced.add(a.blobId);}
 }
 check(referenced.size===index.size&&[...referenced].every(id=>index.has(id)),'v4: missing or unreferenced blob');
 const manifest={...d,blobs:d.blobs.map(({data,...descriptor})=>descriptor),integrity:{algorithm:'SHA-256'}};
 check(await sha(utf8.encode(canonical(manifest)))===d.integrity.digest,'v4: manifest checksum');
 // No output or callbacks expose partial state. Only one blob expanded at a time.
 const values=new Map();
 for(const b of d.blobs){
  aborted(signal);
  const bytes=base64(b.data,b.storedBytes,limits.storedBlobBytes);
  check(await sha(bytes)===b.storedSha256,'v4: stored checksum');
  const expanded=await expand(bytes,b,limits,signal);
  check(await sha(expanded)===b.decodedSha256,'v4: decoded checksum');
  const token=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(expanded);
  const value=json(token,limits,limits.decodedBlobBytes);
  check(typeof value==='string'&&JSON.stringify(value)===token,'v4: expected canonical JSON string');values.set(b.id,value);
 }
 const live=await legacy(values.get(d.live.blobId),limits);
 check(live.formatVersion===d.live.formatVersion&&live.archives.length===0,'v4: live version or embedded archives');
 const archives=d.archives.map(a=>({...a.metadata,raw:a.blobId===null?null:values.get(a.blobId)}));
 aborted(signal);
 return freeze({formatVersion:4,createdAt:d.createdAt,metadata:d.metadata,live,archives});
}
