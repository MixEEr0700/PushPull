/** Experimental standalone transport reader. Never imports storage or restore. */
import {boundedBackupJson} from './backup-v4.mjs';
import {freeze} from './backup-json.mjs';
const M=1024*1024;
export const COMPACT_LIMITS=Object.freeze({fileBytes:512*M,manifestBytes:M,chunks:4096,chunkStoredBytes:2*M,chunkDecodedBytes:4*M,totalDecodedBytes:512*M,depth:32,tokens:100000,ms:30000});
const check=(v,m)=>{if(!v)throw Error('compact: '+m);};
const hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const integer=x=>Number.isSafeInteger(x)&&x>=0;
const exact=(v,keys)=>check(v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k)),'fields');
const sha=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b)),x=>x.toString(16).padStart(2,'0')).join('');
const decoder=new TextDecoder('utf-8',{fatal:true});
// Header: PPC1 (4), manifest byte length uint32 BE (4), SHA-256 of exact manifest bytes (32).
export async function openCompactBackup(file,{signal,limits:overrides={}}={}){
 const limits={...COMPACT_LIMITS};
 exact(overrides,Object.keys(overrides));
 for(const [k,v] of Object.entries(overrides)){check(Object.hasOwn(limits,k)&&Number.isSafeInteger(v)&&v>0&&v<=limits[k],'limits may only be lowered');limits[k]=v;}
 const started=performance.now();
 const guard=()=>{if(signal?.aborted)throw new DOMException('Cancelled','AbortError');check(performance.now()-started<=limits.ms,'time limit');};
 check(file instanceof Blob,'Blob required');check(file.size>=40&&file.size<=limits.fileBytes,'file size');guard();
 const head=new Uint8Array(await file.slice(0,40).arrayBuffer());guard();
 check(head[0]===80&&head[1]===80&&head[2]===67&&head[3]===49,'magic');
 const length=new DataView(head.buffer).getUint32(4);check(length>0&&length<=limits.manifestBytes&&40+length<=file.size,'manifest size');
 const bytes=new Uint8Array(await file.slice(40,40+length).arrayBuffer());guard();
 check(await sha(bytes)===Array.from(head.slice(8),x=>x.toString(16).padStart(2,'0')).join(''),'manifest hash');guard();
 const manifest=boundedBackupJson(decoder.decode(bytes),limits,limits.manifestBytes);
 exact(manifest,['format','version','chunks','objects']);
 check(manifest.format==='pushpull-compact'&&manifest.version===1,'version');
 check(Array.isArray(manifest.chunks)&&manifest.chunks.length>0&&manifest.chunks.length<=limits.chunks,'chunks');
 check(Array.isArray(manifest.objects)&&manifest.objects.length>0&&manifest.objects.length<=limits.chunks,'objects');
 let offset=40+length,total=0,logical=0;const spans=[],used=new Set(),ids=new Set();
 for(const c of manifest.chunks){
  exact(c,['storedBytes','decodedBytes','storedSha256','decodedSha256','compression']);
  check(integer(c.storedBytes)&&c.storedBytes<=limits.chunkStoredBytes&&integer(c.decodedBytes)&&c.decodedBytes<=limits.chunkDecodedBytes,'chunk size');
  check(hex(c.storedSha256)&&hex(c.decodedSha256)&&['none','gzip'].includes(c.compression),'chunk descriptor');
  total+=c.decodedBytes;check(total<=limits.totalDecodedBytes,'decoded budget');
  spans.push([offset,offset+c.storedBytes]);offset+=c.storedBytes;check(offset<=file.size,'incomplete payload');
 }
 check(offset===file.size,'trailing payload');
 for(const o of manifest.objects){
  exact(o,['id','parts','bytes']);check(typeof o.id==='string'&&/^[a-zA-Z0-9_-]{1,80}$/.test(o.id)&&!ids.has(o.id),'object id');ids.add(o.id);
  check(Array.isArray(o.parts)&&o.parts.length>0&&o.parts.length<=limits.chunks&&integer(o.bytes),'object parts');
  let count=0;for(const i of o.parts){check(integer(i)&&i<spans.length,'reference');used.add(i);count+=manifest.chunks[i].decodedBytes;}
  check(count===o.bytes,'object bytes');logical+=count;check(logical<=limits.totalDecodedBytes,'logical budget');
 }
 check(used.size===spans.length,'unused chunks');
 async function read(index){
  guard();const c=manifest.chunks[index],stored=new Uint8Array(await file.slice(...spans[index]).arrayBuffer());guard();
  check(await sha(stored)===c.storedSha256,'stored hash');guard();
  let result;
  if(c.compression==='none'){check(stored.length===c.decodedBytes,'decoded size');result=stored;}
  else{
   const reader=new Blob([stored]).stream().pipeThrough(new DecompressionStream('gzip')).getReader();
   const cancel=()=>{void reader.cancel().catch(()=>{});};signal?.addEventListener('abort',cancel,{once:true});
   result=new Uint8Array(c.decodedBytes);let position=0;
   try{while(true){guard();const {value,done}=await reader.read();guard();if(done)break;check(value.length<=result.length-position,'decompression size');result.set(value,position);position+=value.length;}check(position===result.length,'decoded size');}
   finally{signal?.removeEventListener('abort',cancel);await reader.cancel().catch(()=>{});reader.releaseLock();}
  }
  check(await sha(result)===c.decodedSha256,'decoded hash');guard();return result;
 }
 // No caller sees a successful container until every chunk is verified. Only one is retained.
 for(let i=0;i<spans.length;i++){await read(i);guard();}
 freeze(manifest);
 return Object.freeze({manifest,async *readObject(id){const o=manifest.objects.find(o=>o.id===id);check(o,'unknown object');for(const i of o.parts)yield await read(i);}});
}
