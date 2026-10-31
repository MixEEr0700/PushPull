/** Versioned JSON payload inside the unchanged PPC1 transport container. */
import {openCompactBackup,COMPACT_LIMITS} from './compact-backup-reader.mjs';
import {boundedBackupJson} from './backup-v4.mjs';
import {freeze,portable} from './backup-json.mjs';
const check=(v,m)=>{if(!v)throw Error('PPC1 JSON: '+m);};
const hash=async b=>new Uint8Array(await crypto.subtle.digest('SHA-256',b));
const hex=b=>Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');
export const JSON_OBJECT='canonical-json-v1';
export async function writeCanonicalJSON(input,{signal,limits:overrides={}}={}){
 const limits={...COMPACT_LIMITS};for(const [k,v] of Object.entries(overrides)){check(Object.hasOwn(limits,k)&&Number.isSafeInteger(v)&&v>0&&v<=limits[k],'limits');limits[k]=v;}
 const start=performance.now(),guard=()=>{signal?.throwIfAborted();check(performance.now()-start<=limits.ms,'time limit');};
 guard();portable(input);const text=JSON.stringify(input);check(text.length<=limits.totalDecodedBytes,'text limit');
 const bytes=new TextEncoder().encode(text);check(bytes.length<=limits.totalDecodedBytes,'decoded limit');
 const chunks=[],payload=[],parts=[],width=Math.min(256*1024,limits.chunkDecodedBytes,limits.chunkStoredBytes);
 for(let p=0;p<bytes.length;p+=width){
  guard();check(chunks.length<limits.chunks,'chunk limit');const decoded=bytes.subarray(p,p+width);
  let stored=new Uint8Array(await new Response(new Blob([decoded]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer()),compression='gzip';
  if(stored.length>=decoded.length){stored=decoded;compression='none';}
  guard();parts.push(chunks.length);chunks.push({storedBytes:stored.length,decodedBytes:decoded.length,storedSha256:hex(await hash(stored)),decodedSha256:hex(await hash(decoded)),compression});payload.push(stored);
 }
 const manifest=new TextEncoder().encode(JSON.stringify({format:'pushpull-compact',version:1,chunks,objects:[{id:JSON_OBJECT,parts,bytes:bytes.length}]}));
 check(manifest.length<=limits.manifestBytes,'manifest limit');const head=new Uint8Array(40);head.set([80,80,67,49]);new DataView(head.buffer).setUint32(4,manifest.length);head.set(await hash(manifest),8);
 const file=new Blob([head,manifest,...payload]);check(file.size<=limits.fileBytes,'file limit');guard();
 // Validate the new representation before publishing any file.
 await readCanonicalJSON(await openCompactBackup(file,{signal,limits}),{signal,limits});guard();return file;
}
export async function readCanonicalJSON(reader,{signal,limits={}}={}){
 const bounds={...COMPACT_LIMITS,...limits},start=performance.now(),guard=()=>{signal?.throwIfAborted();check(performance.now()-start<=bounds.ms,'time limit');};guard();
 check(reader.manifest.objects.length===1&&reader.manifest.objects[0].id===JSON_OBJECT,'encoding');const object=reader.manifest.objects[0];check(object.bytes<=bounds.totalDecodedBytes,'decoded limit');
 const bytes=new Uint8Array(object.bytes);let p=0;for await(const b of reader.readObject(JSON_OBJECT)){guard();bytes.set(b,p);p+=b.length;}
 const value=boundedBackupJson(new TextDecoder('utf-8',{fatal:true}).decode(bytes),bounds,bounds.totalDecodedBytes);portable(value);guard();return freeze(value);
}
