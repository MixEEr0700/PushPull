/** Append-only canonical recovery points. No source database writes. */
import {canonical} from './backup-json.mjs';
import {validateCanonicalBackup,writeCanonicalBackup} from './canonical-backup.mjs';
const MAX=128*1024*1024,COUNT=50000,DEPTH=32;
const check=(v,m)=>{if(!v)throw Error('Drive PPC1: '+m)};
export const digest=async v=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(v)))),b=>b.toString(16).padStart(2,'0')).join('');
// Paths are JSON-encoded arrays, never interpreted as property setters.
export function partition(value){
 const rows={};let count=0;
 function walk(v,path){check(path.length<=64&&++count<=COUNT,'object count limit');const key=JSON.stringify(path);
  if(Array.isArray(v)){rows[key]={array:v.length};v.forEach((x,i)=>{check(++count<=COUNT,'object count limit');rows[JSON.stringify([...path,i])]={value:x}});}
  else if(v&&typeof v==='object'){rows[key]={keys:Object.keys(v)};for(const k of Object.keys(v))walk(v[k],[...path,k]);}
  else rows[key]={value:v};
 }
 walk(value,[]);check(Object.keys(rows).length<=COUNT,'object count limit');return rows;
}
function materialize(rows){
 let seen=0;const used=new Set();
 function read(path,depth=0){check(depth<=64&&++seen<=COUNT,'tree limit');const key=JSON.stringify(path),r=rows[key];check(r&&!used.has(key),'missing/repeated object');used.add(key);
  if(Object.hasOwn(r,'value')){check(Object.keys(r).length===1,'value shape');return r.value;}
  if(Object.hasOwn(r,'array')){check(Object.keys(r).length===1&&Number.isSafeInteger(r.array)&&r.array>=0&&r.array<=COUNT,'array limit');return Array.from({length:r.array},(_,i)=>read([...path,i],depth+1));}
  check(Object.keys(r).length===1&&Array.isArray(r.keys)&&r.keys.every(k=>typeof k==='string')&&new Set(r.keys).size===r.keys.length,'object shape');return Object.fromEntries(r.keys.map(k=>[k,read([...path,k],depth+1)]));
 }
 const value=read([]);check(used.size===Object.keys(rows).length,'unreachable objects');return validateCanonicalBackup(value);
}
export async function makePoint(value,previous=null){
 validateCanonicalBackup(value);const rows=partition(value),root=await digest(rows);
 const base=!previous||previous.generation>=DEPTH;
 const changed=Object.fromEntries(Object.entries(rows).filter(([k,v])=>base||canonical(previous.rows[k]??null)!==canonical(v)));
 const removed=base?[]:Object.keys(previous.rows).filter(k=>!Object.hasOwn(rows,k));
 const objects={},refs={};for(const [key,value] of Object.entries(changed)){const sha=await digest(value);refs[key]=sha;objects[sha]=value;}
 const body={format:'pushpull-drive-ppc1',version:1,parent:base?null:previous.fileId,parentDigest:base?null:previous.digest,generation:base?0:previous.generation+1,root,changed:refs,objects,removed};
 const bytes=new TextEncoder().encode(canonical(body)).length;check(bytes<=MAX,'decoded size limit');if(!base&&(previous.chainBytes??0)+bytes+256>MAX)return makePoint(value,null);return {packet:{...body,digest:await digest(body)},rows};
}
export async function restorePoint(transport,fileId,{signal}={}){
 const chain=[],visited=new Set();let next=fileId,downloaded=0;
 while(next){signal?.throwIfAborted();check(!visited.has(next)&&chain.length<=DEPTH,'cycle/chain limit');visited.add(next);const raw=await (transport.readPoint??transport.read).call(transport,next);check(typeof raw==='string'&&raw.length<=MAX,'file limit');downloaded+=new TextEncoder().encode(raw).length;check(downloaded<=MAX,'chain memory limit');const p=JSON.parse(raw),{digest:sha,...body}=p;
  check(Object.keys(p).sort().join(',')==='changed,digest,format,generation,objects,parent,parentDigest,removed,root,version','manifest fields');
  check(p.format==='pushpull-drive-ppc1'&&p.version===1&&await digest(body)===sha,'manifest integrity');check(Number.isSafeInteger(p.generation)&&p.generation>=0&&p.generation<=DEPTH,'generation');check(p.changed&&typeof p.changed==='object'&&!Array.isArray(p.changed)&&Array.isArray(p.removed)&&p.removed.every(k=>typeof k==='string')&&new Set(p.removed).size===p.removed.length,'delta shape');check(p.removed.every(k=>!Object.hasOwn(p.changed,k)),'conflicting tombstone');
  check(p.objects&&typeof p.objects==='object'&&!Array.isArray(p.objects),'object pool');check(Object.keys(p.changed).length<=COUNT&&Object.keys(p.objects).length<=COUNT,'object count limit');const used=new Set(Object.values(p.changed));check(used.size===Object.keys(p.objects).length,'object pool references');for(const sha of used)check(typeof sha==='string'&&Object.hasOwn(p.objects,sha)&&await digest(p.objects[sha])===sha,'object integrity');chain.push(p);next=p.parent;check(next===null||typeof next==='string'&&next.length>0&&next.length<=256,'parent');
 }
 let rows=Object.create(null),prior=null,total=0;
 for(const p of chain.reverse()){signal?.throwIfAborted();total+=canonical(p).length;check(total<=MAX,'chain memory limit');check(prior?p.parentDigest===prior.digest&&p.generation===prior.generation+1:p.parent===null&&p.parentDigest===null&&p.generation===0&&p.removed.length===0,'chain order');for(const k of p.removed){check(Object.hasOwn(rows,k),'missing tombstone');delete rows[k];}for(const [k,v] of Object.entries(p.changed))Object.defineProperty(rows,k,{value:p.objects[v],writable:true,configurable:true,enumerable:true});check(Object.keys(rows).length<=COUNT&&await digest(rows)===p.root,'model integrity');prior=p;}
 check(prior,'empty chain');const value=materialize(rows);return {value,rows,digest:prior.digest,generation:prior.generation,chainBytes:downloaded,fileId,file:await writeCanonicalBackup(value,{signal})};
}
/** Caller persists pending BEFORE network. Reuse the same reserved Google ID
 * after ambiguous POST; GET never trusts an HTTP success alone. */
export async function uploadPoint(transport,pending,{signal}={}){
 signal?.throwIfAborted();let remote;
 try{remote=await (transport.readPoint??transport.read).call(transport,pending.fileId);}catch(e){if(e.status!==404)throw e;}
 if(remote===undefined){try{await transport.createPoint(pending.fileId,canonical(pending.packet),pending.packet.digest);}catch(e){if(e.auth)throw e;/* POST may have committed; authoritative GET follows. */}}
 signal?.throwIfAborted();const raw=await (transport.readPoint??transport.read).call(transport,pending.fileId);check(raw.length<=MAX&&canonical(JSON.parse(raw))===canonical(pending.packet),'upload readback');
 const restored=await restorePoint(transport,pending.fileId,{signal});check(restored.digest===pending.packet.digest,'readback identity');return restored;
}
