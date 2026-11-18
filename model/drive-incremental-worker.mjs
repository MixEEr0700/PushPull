import {makePoint,restorePoint,uploadPoint} from './drive-incremental.mjs';
import {readCanonicalBackup} from './canonical-backup.mjs';
export async function execute(task,args,transport,{signal}={}){
 if(task==='prepare'){const value=args.file instanceof Blob?await readCanonicalBackup(args.file):args.file;const previous=args.parent?await restorePoint(transport,args.parent,{signal}):null;return {packet:(await makePoint(value,previous)).packet};}
 const r=task==='upload'?await uploadPoint(transport,args,{signal}):await restorePoint(transport,args.fileId,{signal});
 return {file:r.file,fileId:r.fileId,digest:r.digest,generation:r.generation};
}
if(typeof DedicatedWorkerGlobalScope!=='undefined'&&globalThis instanceof DedicatedWorkerGlobalScope){
 let next=0;const pending=new Map(),transport=Object.fromEntries(['readPoint','createPoint'].map(method=>[method,(...args)=>new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});postMessage({rpc:{id,method,args:args.slice(0,method==='readPoint'?1:3)}})})]));
 onmessage=async({data})=>{if(data.reply){const p=pending.get(data.reply.id);if(!p)return;pending.delete(data.reply.id);data.reply.error?p.reject(Object.assign(Error(data.reply.error.message),data.reply.error)):p.resolve(data.reply.value);return;}
 try{postMessage({result:await execute(data.task,data.args,transport)});}catch(e){postMessage({error:{message:e.message,auth:e.auth,status:e.status}})}};
}
