/** B1 only: detached exporter. No storage, DOM, network or production hooks. */
import {decodeBackup,V4_LIMITS} from './backup-v4.mjs';
import {portable,record,canonical,freeze,requireThat as check} from './backup-json.mjs';
import {createLegacyModel} from './legacy-model.mjs';
import {readLegacyBackup} from './legacy-backup.mjs';
const utf8=new TextEncoder();
const sha=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
const aborted=signal=>{if(signal?.aborted)throw new DOMException('Backup export cancelled','AbortError');};
function policy(overrides){
 check(record(overrides),'v4 export: invalid limits');const limits={...V4_LIMITS};
 for(const [key,value] of Object.entries(overrides)){
  check(Object.hasOwn(limits,key)&&Number.isSafeInteger(value)&&value>0&&value<=limits[key],'v4 export: limits may only be lowered');limits[key]=value;
 }return limits;
}
// No full escaped string just to determine its size. Count the exact bytes of
// JSON.stringify(string), including lone surrogates and boundary-spanning pairs.
function stringBytes(value,limit){
 let bytes=2;
 for(let i=0;i<value.length;i++){
  const c=value.charCodeAt(i);
  if(c===34||c===92||[8,9,10,12,13].includes(c))bytes+=2;
  else if(c<32)bytes+=6;
  else if(c>=0xd800&&c<=0xdbff&&i+1<value.length&&value.charCodeAt(i+1)>=0xdc00&&value.charCodeAt(i+1)<=0xdfff){bytes+=4;i++;}
  else if(c>=0xd800&&c<=0xdfff)bytes+=6;
  else bytes+=c<128?1:c<2048?2:3;
  check(bytes<=limit,'v4 export: decoded size limit');
 }check(bytes<=limit,'v4 export: decoded size limit');return bytes;
}
function jsonBytes(value,limit,depth=0){
 check(depth<=V4_LIMITS.depth,'v4 export: nesting limit');
 if(typeof value==='string')return stringBytes(value,limit);
 if(value===null||typeof value!=='object')return JSON.stringify(value).length;
 const array=Array.isArray(value),keys=Object.keys(value);let size=2;
 for(let i=0;i<keys.length;i++){
  if(i)size++;
  if(!array)size+=stringBytes(keys[i],limit)+1;
  size+=jsonBytes(value[keys[i]],limit,depth+1);check(size<=limit,'v4 export: JSON size limit');
 }check(size<=limit,'v4 export: JSON size limit');return size;
}
function serialize(value,limit){jsonBytes(value,limit);return JSON.stringify(value);}
function encodeString(value,size){
 const bytes=new Uint8Array(size);let offset=0;
 const put=text=>{const written=utf8.encodeInto(text,bytes.subarray(offset));check(written.read===text.length,'v4 export: string encoding');offset+=written.written;};
 put('"');
 for(let start=0;start<value.length;){
  let end=Math.min(value.length,start+32768);
  if(end<value.length&&value.charCodeAt(end-1)>=0xd800&&value.charCodeAt(end-1)<=0xdbff&&value.charCodeAt(end)>=0xdc00&&value.charCodeAt(end)<=0xdfff)end--;
  put(JSON.stringify(value.slice(start,end)).slice(1,-1));start=end;
 }
 put('"');check(offset===size,'v4 export: encoded size mismatch');return bytes;
}
async function compress(bytes,limit,signal){
 check(typeof CompressionStream==='function','v4 export: gzip encoding unavailable');
 const reader=new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip')).getReader();
 let size=0;const chunks=[];
 try{while(true){aborted(signal);const {value,done}=await reader.read();if(done)break;size+=value.length;check(size<=limit,'v4 export: stored size limit');chunks.push(value);}}
 catch(error){await reader.cancel().catch(()=>{});throw error;}finally{reader.releaseLock();}
 const stored=new Uint8Array(size);let offset=0;for(const chunk of chunks){stored.set(chunk,offset);offset+=chunk.length;}return stored;
}
function base64(bytes){
 const pieces=[];for(let i=0;i<bytes.length;i+=8192)pieces.push(String.fromCharCode(...bytes.subarray(i,i+8192)));
 return btoa(pieces.join(''));
}
// Object equality without two additional full serializations of large raw strings.
function equal(a,b){
 if(a===b)return true;
 if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;
 const keys=Object.keys(a);return keys.length===Object.keys(b).length&&keys.every(k=>Object.hasOwn(b,k)&&equal(a[k],b[k]));
}
function diagnostic(error,stage,limit,codeUnits){
 if(!/size limit/.test(error.message))return error;
 error.message+=` [stage=${stage}; limitBytes=${limit}${codeUnits===undefined?'':`; codeUnits=${codeUnits}`}]`;
 return error;
}
function detach(source,limits){
 check(source?.format==='pushpull-backup'&&source.version===2&&(source.archives===undefined||Array.isArray(source.archives)),'v4 export: expected complete v2 snapshot');
 check((source.archives??[]).length<=limits.archives,'v4 export: archive count limit');portable(source);
 let metadataBytes=0;
 const rows=(source.archives??[]).map(({raw,...metadata})=>{
  check(raw===null||typeof raw==='string','v4 export: archive raw');metadataBytes+=jsonBytes(metadata,limits.fileBytes);
  check(metadataBytes<=limits.fileBytes,'v4 export: file size limit');return {...structuredClone(metadata),raw};
 });
 // Snapshot every mutable field before the first await, retain immutable raw
 // strings directly instead of structured-cloning the entire rescue archive.
 const liveSource={...source,archives:[]};try{jsonBytes(liveSource,limits.decodedBlobBytes);}catch(error){throw diagnostic(error,'live-preflight',limits.decodedBlobBytes);}
 return {source:structuredClone(liveSource),archives:rows};
}
/** Input: complete detached v2 snapshot OR existing v1/v2/v3/v4 JSON text.
 * Returns {text,diagnostics} only after full decoder verification and equality.
 * createdAt is explicit; no automatic archive/preimage, download or database I/O.
 */
export async function exportBackupV4(input,{createdAt,metadata,limits:overrides={},signal}={}){
 const limits=policy(overrides);aborted(signal);
 check(typeof createdAt==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(createdAt)&&Number.isFinite(Date.parse(createdAt))&&new Date(createdAt).toISOString()===createdAt,'v4 export: explicit createdAt required');
 if(metadata!==undefined){portable(metadata);check(record(metadata),'v4 export: metadata must be a record');jsonBytes(metadata,limits.fileBytes);metadata=structuredClone(metadata);}
 let live,expected,archives,source,original;
 if(typeof input==='string'){
  const stage=await decodeBackup(input,{limits,signal});archives=stage.archives;
  if(stage.formatVersion===4){
   check(metadata===undefined||equal(metadata,stage.metadata),'v4 export: preserve existing container metadata');metadata=stage.metadata;
   live=stage.live.raw;expected=stage.live.document;
  }else if(stage.live.formatVersion===1){
   check(!Object.hasOwn(stage.live.document,'archives'),'v4 export: ambiguous v1 archive extension');live=stage.live.raw;expected=stage.live.document;
  }else{
   original=stage.live.formatVersion===3?stage.live.document:null;
   const v2=original?readLegacyBackup(original.payload.legacySources[0].raw).original:stage.live.document;
   source=structuredClone({...v2,archives:[]});
  }
 }else{const snapshot=detach(input,limits);source=snapshot.source;archives=snapshot.archives;}
 metadata??={};portable(metadata);aborted(signal);
 // Necessary lower bound of the final file, before retaining base64 strings.
 // Exact final sizing and the decoder still validate the complete container.
 let fileMinimum=jsonBytes(metadata,limits.fileBytes);
 for(const {raw,...info} of archives){fileMinimum+=jsonBytes(info,limits.fileBytes);check(fileMinimum<=limits.fileBytes,'v4 export: file size limit');}
 if(source){
  let raw;try{raw=serialize(source,limits.decodedBlobBytes);}catch(error){throw diagnostic(error,'live-document',limits.decodedBlobBytes);}
  if(source.data?.trainingJournal||original){
   const ownerId=original?.payload.model.ownerId??source.data.trainingJournal.model.ownerId;
   expected=await createLegacyModel(raw,{ownerId,createdAt:original?.createdAt??createdAt});
   if(original){
    const comparable=d=>({...d,payload:{...d.payload,legacySources:[]},integrity:{...d.integrity,digest:''}});
    check(equal(comparable(original),comparable(expected)),'v4 export: model changed while separating archives');
   }
   try{live=serialize(expected,limits.decodedBlobBytes);}catch(error){throw diagnostic(error,'live-model',limits.decodedBlobBytes);}
  }else{expected=source;live=raw;}
 }
 check(archives.length<=limits.archives,'v4 export: archive count limit');
 const byText=new Map(),blobs=[],rows=[],archiveBlobs=new Set();let decodedTotal=0;
 let rawUnits=0,largest=0,nulls=0,duplicates=0;
 async function add(value,stage='live-token'){
  aborted(signal);if(byText.has(value))return byText.get(value);
  check(blobs.length<limits.blobs,'v4 export: blob count limit');
  let size;try{size=stringBytes(value,limits.decodedBlobBytes);}catch(error){throw diagnostic(error,stage,limits.decodedBlobBytes,value.length);}
  decodedTotal+=size;
  check(decodedTotal<=limits.totalDecodedBytes,'v4 export: aggregate size limit');
  const bytes=encodeString(value,size),decodedSha256=await sha(bytes),stored=await compress(bytes,limits.storedBlobBytes,signal);
  fileMinimum+=4*Math.ceil(stored.length/3);check(fileMinimum<=limits.fileBytes,'v4 export: file size limit');
  const id='sha256:'+decodedSha256;
  blobs.push({id,encoding:'json-string-utf8',compression:'gzip',storedBytes:stored.length,decodedBytes:size,storedSha256:await sha(stored),decodedSha256,data:base64(stored)});
  byText.set(value,id);return id;
 }
 const liveId=await add(live);
 for(const {raw,...info} of archives){
  aborted(signal);
  let blobId=null;
  if(raw===null)nulls++;
  else{
   check(typeof raw==='string','v4 export: archive raw');rawUnits+=raw.length;largest=Math.max(largest,raw.length);
   blobId=await add(raw,info.kind==='before-import'?'preimage-token':'opaque-archive-token');if(archiveBlobs.has(blobId))duplicates++;archiveBlobs.add(blobId);
  }
  rows.push({metadata:info,blobId});
 }
 const d={format:'pushpull-backup',version:4,createdAt,metadata,live:{formatVersion:expected.version,blobId:liveId},archives:rows,blobs,integrity:{algorithm:'SHA-256',digest:''}};
 const manifest={...d,blobs:blobs.map(({data,...b})=>b),integrity:{algorithm:'SHA-256'}};
 d.integrity.digest=await sha(utf8.encode(serializeCanonical(manifest,limits.fileBytes)));
 const fileBytes=jsonBytes(d,limits.fileBytes),text=JSON.stringify(d);
 const verified=await decodeBackup(text,{limits,signal});
 check(equal(verified.live.document,expected)&&equal(verified.archives,archives)&&equal(verified.metadata,metadata)&&verified.createdAt===createdAt,'v4 export: lossless verification failed');
 if(source)check(equal(verified.live.data,source.data)&&equal(verified.live.catalog,source.catalog),'v4 export: source history or catalog changed');
 aborted(signal);
 const physical=blobs.filter(b=>archiveBlobs.has(b.id));
 return freeze({text,diagnostics:{formatVersion:4,fileBytes,liveCodeUnits:live.length,archiveRecords:archives.length,nullArchives:nulls,
  archiveRawCodeUnits:rawUnits,largestArchiveCodeUnits:largest,uniqueArchiveBlobs:archiveBlobs.size,deduplicatedArchiveRecords:duplicates,
  archiveEncodedBytes:physical.reduce((n,b)=>n+b.decodedBytes,0),archiveStoredBytes:physical.reduce((n,b)=>n+b.storedBytes,0),
  totalBlobs:blobs.length,totalDecodedBytes:decodedTotal,totalStoredBytes:blobs.reduce((n,b)=>n+b.storedBytes,0)}});
}
function serializeCanonical(value,limit){jsonBytes(value,limit);return canonical(value);}
