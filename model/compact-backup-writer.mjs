/** Isolated JSON-compatible model graph. No database, export UI or Drive. */
import {openCompactBackup,COMPACT_LIMITS} from './compact-backup-reader.mjs';
import {boundedBackupJson} from './backup-v4.mjs';
import {freeze} from './backup-json.mjs';
const check=(v,m)=>{if(!v)throw Error('compact graph: '+m);};
const sha=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b)),x=>x.toString(16).padStart(2,'0')).join('');
const enc=new TextEncoder();
function context({limits:overrides={},signal}={}){
 const limits={...COMPACT_LIMITS};for(const [k,v] of Object.entries(overrides)){check(Object.hasOwn(limits,k)&&Number.isSafeInteger(v)&&v>0&&v<=limits[k],'limits');limits[k]=v;}
 const at=performance.now();const guard=()=>{if(signal?.aborted)throw new DOMException('Cancelled','AbortError');check(performance.now()-at<=limits.ms,'time limit');};guard();return {limits,guard,signal};
}
// Capture all properties before the first await; no getters, sparse arrays or silent JSON coercion.
function capture(root,guard){
 let properties=0;const nodes=[],seen=new Map(),active=new Set(),strings=new Map(),structures=new Map();
 function visit(v,depth=0){
  guard();check(depth<=64,'model depth');
  if(typeof v==='string'&&strings.has(v))return strings.get(v);
  check(!active.has(v),'cycle');if(v&&typeof v==='object'&&seen.has(v))return seen.get(v);
  let node;
  if(v===null||typeof v==='boolean')node=['value',v];
  else if(typeof v==='number'){check(Number.isFinite(v),'nonfinite number');node=['number',Object.is(v,-0)?'-0':String(v)];}
  else if(typeof v==='string')node=['string',v];
  else{
   check(v&&typeof v==='object'&&(Array.isArray(v)||Object.getPrototypeOf(v)===Object.prototype||Object.getPrototypeOf(v)===null),'nonportable value');active.add(v);
   const keys=Reflect.ownKeys(v);properties+=keys.length;check(keys.length<=10000&&properties<=100000,'property limit');check(keys.every(k=>typeof k==='string'),'symbol property');
   for(const k of keys){const d=Object.getOwnPropertyDescriptor(v,k);check(Object.hasOwn(d,'value')&&(d.enumerable||Array.isArray(v)&&k==='length'),'accessor or hidden property');}
   if(Array.isArray(v)){check(keys.length===v.length+1&&Array.from({length:v.length},(_,i)=>Object.hasOwn(v,i)).every(Boolean),'sparse or extended array');node=['array',v.map(x=>visit(x,depth+1))];}
   else node=['object',keys.map(k=>[visit(k,depth+1),visit(v[k],depth+1)])];
   active.delete(v);
  }
  const key=typeof v==='string'?null:JSON.stringify(node);let id=key===null?undefined:structures.get(key);
  if(id===undefined){check(nodes.length<10000,'node limit');id=nodes.length;nodes.push(node);if(key!==null)structures.set(key,id);}
  if(typeof v==='string')strings.set(v,id);else if(v&&typeof v==='object')seen.set(v,id);return id;
 }
 return {format:'pushpull-model-graph',version:1,root:visit(root),nodes};
}
export async function writeCompactModel(model,options={}){
 const {limits,guard}=context(options),graph=capture(model,guard),chunks=[],payload=[],objects=[],dedup=new Map();let logical=0,storedTotal=0;
 const width=Math.min(256*1024,limits.chunkStoredBytes,limits.chunkDecodedBytes);check(width>=2,'chunk limit');
 async function object(id,parts){
  const refs=[];let size=0;
  for(const bytes of parts){
   guard();size+=bytes.length;logical+=bytes.length;check(logical<=limits.totalDecodedBytes,'logical budget');
   const digest=await sha(bytes);guard();let index=dedup.get(digest);
   if(index===undefined){
    check(chunks.length<limits.chunks,'chunks');let stored=bytes,compression='none';
    if(options.compression!==false&&bytes.length){const compressed=new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());guard();if(compressed.length<bytes.length){stored=compressed;compression='gzip';}}
    storedTotal+=stored.length;check(storedTotal<=limits.fileBytes,'file budget');index=chunks.length;dedup.set(digest,index);payload.push(new Blob([stored]));
    chunks.push({storedBytes:stored.length,decodedBytes:bytes.length,storedSha256:await sha(stored),decodedSha256:digest,compression});guard();
   }
   refs.push(index);check(refs.length<=limits.chunks,'parts');
  }
  objects.push({id,parts:refs,bytes:size});check(objects.length<=limits.chunks,'objects');
 }
 // UTF-16LE code units preserve lone surrogates, NUL and non-normalized strings exactly.
 for(let i=0;i<graph.nodes.length;i++)if(graph.nodes[i][0]==='string'){
  const s=graph.nodes[i][1],id='s'+i;
  function* parts(){const units=Math.floor(width/2);if(!s.length)yield new Uint8Array();for(let p=0;p<s.length;p+=units){const b=new Uint8Array(2*Math.min(units,s.length-p)),view=new DataView(b.buffer);for(let j=0;j<b.length/2;j++)view.setUint16(j*2,s.charCodeAt(p+j),true);yield b;}}
  await object(id,parts());graph.nodes[i]=['string',id];
 }
 const texts=[`{"format":"pushpull-model-graph","version":1,"root":${graph.root},"nodes":[`];let metadataSize=texts[0].length+2;
 for(const [i,node] of graph.nodes.entries()){const text=(i?',':'')+JSON.stringify(node);metadataSize+=text.length;check(metadataSize<=limits.manifestBytes,'graph size');texts.push(text);}texts.push(']}');
 const graphBytes=enc.encode(texts.join(''));check(graphBytes.length<=limits.manifestBytes,'graph size');
 function* graphParts(){for(let p=0;p<graphBytes.length;p+=width)yield graphBytes.slice(p,p+width);}
 await object('graph',graphParts());
 const manifest=enc.encode(JSON.stringify({format:'pushpull-compact',version:1,chunks,objects}));check(manifest.length<=limits.manifestBytes,'manifest size');
 const head=new Uint8Array(40);head.set([80,80,67,49]);new DataView(head.buffer).setUint32(4,manifest.length);head.set(Uint8Array.from((await sha(manifest)).match(/../g),h=>parseInt(h,16)),8);
 const file=new Blob([head,manifest,...payload]);guard();check(file.size<=limits.fileBytes,'file budget');
 // Existing reader is the final transport gate; no partial file on failure.
 await openCompactBackup(file,options);guard();
 return file;
}
export async function readCompactModel(file,options={}){
 const {limits,guard}=context(options),reader=await openCompactBackup(file,options);
 const descriptor=reader.manifest.objects.find(o=>o.id==='graph');check(descriptor&&descriptor.bytes<=limits.manifestBytes,'graph size');
 const bytes=new Uint8Array(descriptor.bytes);let p=0;for await(const b of reader.readObject('graph')){guard();bytes.set(b,p);p+=b.length;}
 const graph=boundedBackupJson(new TextDecoder('utf-8',{fatal:true}).decode(bytes),limits,limits.manifestBytes);
 check(graph&&Object.keys(graph).sort().join(',')==='format,nodes,root,version'&&graph.format==='pushpull-model-graph'&&graph.version===1&&Array.isArray(graph.nodes)&&graph.nodes.length<=10000,'graph schema');
 const values=new Map(),active=new Set(),used=new Set(['graph']);
 async function visit(i,depth=0){
  guard();check(Number.isSafeInteger(i)&&i>=0&&i<graph.nodes.length&&depth<=64,'reference or depth');check(!active.has(i),'cycle');if(values.has(i))return values.get(i);active.add(i);
  const n=graph.nodes[i];check(Array.isArray(n)&&n.length===2,'node');const [type,v]=n;let out;
  if(type==='value'){check(v===null||typeof v==='boolean','value');out=v;}
  else if(type==='number'){check(typeof v==='string'&&Number.isFinite(Number(v))&&(v==='-0'||String(Number(v))===v),'number');out=Number(v);}
  else if(type==='string'){
   check(typeof v==='string'&&v==='s'+i,'string reference');used.add(v);let text='';
   for await(const b of reader.readObject(v)){guard();check(b.length%2===0,'UTF16 alignment');const view=new DataView(b.buffer,b.byteOffset,b.byteLength);for(let k=0;k<b.length;k+=8192){const units=[];for(let j=k;j<Math.min(k+8192,b.length);j+=2)units.push(view.getUint16(j,true));text+=String.fromCharCode(...units);}}
   out=text;
  }else if(type==='array'){check(Array.isArray(v),'array');out=[];for(const ref of v)out.push(await visit(ref,depth+1));}
  else if(type==='object'){check(Array.isArray(v),'object');out={};for(const pair of v){check(Array.isArray(pair)&&pair.length===2,'entry');const key=await visit(pair[0],depth+1);check(typeof key==='string'&&!Object.hasOwn(out,key),'duplicate key');Object.defineProperty(out,key,{value:await visit(pair[1],depth+1),writable:true,enumerable:true,configurable:true});}}
  else throw Error('compact graph: node type');
  active.delete(i);values.set(i,out);return out;
 }
 const result=await visit(graph.root);check(values.size===graph.nodes.length&&used.size===reader.manifest.objects.length,'unreachable data');guard();return freeze(result);
}
