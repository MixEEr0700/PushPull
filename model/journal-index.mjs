/** Persistent, content-addressed AVL index. Crypto is never run in an IDB tx. */
import {freeze,portable,requireThat as check} from './backup-json.mjs';
export const checkAbort=signal=>{if(signal?.aborted)throw signal.reason??new DOMException('Aborted','AbortError');};
export async function sha(value){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),b=>b.toString(16).padStart(2,'0')).join('');}
export const hashJSON=value=>sha(JSON.stringify(value));
export const indexKey=(store,id)=>JSON.stringify([store,id]);
export async function verifyNode(node){
 check(node&&Object.keys(node).join(',')==='id,key,value,left,right,height','index shape');
 check(typeof node.key==='string'&&/^[a-f0-9]{64}$/.test(node.value)&&[node.left,node.right].every(v=>v===null||/^[a-f0-9]{64}$/.test(v))&&Number.isSafeInteger(node.height)&&node.height>0,'index fields');
 const {id,...body}=node;check(id===await hashJSON(body),'index SHA-256');return freeze(node);
}
export async function editIndex(root,read,changes,{signal}={}){
 const added=new Map(),observed=new Map();
 async function get(id){
  if(id===null)return null;checkAbort(signal);
  if(added.has(id))return added.get(id);
  if(!observed.has(id))observed.set(id,await verifyNode(await read(id)));
  return observed.get(id);
 }
 const height=async id=>(await get(id))?.height??0;
 async function node(key,value,left,right){const body={key,value,left,right,height:1+Math.max(await height(left),await height(right))},id=await hashJSON(body);added.set(id,freeze({id,...body}));return id;}
 async function balance(key,value,left,right){
  const delta=await height(left)-await height(right);
  if(delta>1){
   let l=await get(left);
   if(await height(l.left)<await height(l.right)){
    const r=await get(l.right);left=await node(r.key,r.value,await node(l.key,l.value,l.left,r.left),r.right);l=await get(left);
   }
   return node(l.key,l.value,l.left,await node(key,value,l.right,right));
  }
  if(delta < -1){
   let r=await get(right);
   if(await height(r.right)<await height(r.left)){
    const l=await get(r.left);right=await node(l.key,l.value,l.left,await node(r.key,r.value,l.right,r.right));r=await get(right);
   }
   return node(r.key,r.value,await node(key,value,left,r.left),r.right);
  }
  return node(key,value,left,right);
 }
 async function insert(id,key,value){
  const old=await get(id);if(!old)return node(key,value,null,null);
  if(key===old.key)return node(key,value,old.left,old.right);
  return key<old.key?balance(old.key,old.value,await insert(old.left,key,value),old.right):balance(old.key,old.value,old.left,await insert(old.right,key,value));
 }
 for(const [key,value] of changes){checkAbort(signal);root=await insert(root,key,value);}
 return {root,added,observed};
}
export async function buildIndex(leaves,{signal}={}){
 const sorted=[...leaves].sort(([a],[b])=>a<b?-1:a>b?1:0),nodes=new Map();
 check(new Set(sorted.map(([k])=>k)).size===sorted.length,'duplicate index key');
 async function build(start,end){
  checkAbort(signal);if(start===end)return null;const mid=(start+end)>>1;
  const left=await build(start,mid),right=await build(mid+1,end),[key,value]=sorted[mid];
  const body={key,value,left,right,height:1+Math.max(nodes.get(left)?.height??0,nodes.get(right)?.height??0)},id=await hashJSON(body);nodes.set(id,freeze({id,...body}));return id;
 }
 return {root:await build(0,sorted.length),nodes};
}
export async function auditIndex(root,read,leaves,{signal}={}){
 const pending=new Map(leaves),seen=new Set();
 async function visit(id,lower=null,upper=null){
  checkAbort(signal);if(id===null)return 0;check(!seen.has(id),'index cycle or shared branch');seen.add(id);
  const n=await verifyNode(await read(id));check((lower===null||n.key>lower)&&(upper===null||n.key<upper),'index order');
  check(pending.get(n.key)===n.value,'index record mismatch');pending.delete(n.key);
  const left=await visit(n.left,lower,n.key),right=await visit(n.right,n.key,upper);
  check(n.height===1+Math.max(left,right)&&Math.abs(left-right)<=1,'index balance');return n.height;
 }
 portable(root);await visit(root);check(pending.size===0,'index missing records');return seen;
}
