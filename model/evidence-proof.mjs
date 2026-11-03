/** Bounded Merkle proof for native JSON evidence, without aggregate escaping. */
import {portable} from './backup-json.mjs';
import {hashJSON,shaBytes} from './journal-index.mjs';
import {LIMITS} from './journal-protocol.mjs';
const encoder=new TextEncoder(),WIDTH=32768;
export async function evidenceProof(value,{maxBytes=LIMITS.totalBytes}={}){
 portable(value);const seen=new WeakMap(),strings=new Map(),scalars=new Map();let bytes=0;
 const charge=n=>{bytes+=n;if(bytes>maxBytes)throw Error('Limit materiału ratunkowego (native evidence bytes).');};
 async function string(v){if(strings.has(v))return strings.get(v);const hashes=[];for(let p=0;p<v.length;){let end=Math.min(p+WIDTH,v.length);if(end<v.length&&v.charCodeAt(end-1)>=0xd800&&v.charCodeAt(end-1)<=0xdbff)end--;const text=v.slice(p,end);charge(encoder.encode(text).length);const b=new Uint8Array(text.length*2),view=new DataView(b.buffer);for(let i=0;i<text.length;i++)view.setUint16(i*2,text.charCodeAt(i),true);hashes.push(await shaBytes(b));p=end;}const h=await hashJSON(['utf16le',v.length,hashes]);strings.set(v,h);return h;}
 async function visit(v){if(typeof v==='string')return string(v);if(v===null||typeof v!=='object'){charge(16);const key=JSON.stringify(v);if(!scalars.has(key))scalars.set(key,hashJSON(['scalar',v]));return scalars.get(key);}if(seen.has(v))return seen.get(v);const work=(async()=>{charge(16);const array=Array.isArray(v),keys=Object.keys(v),groups=[];for(let p=0;p<keys.length;p+=128){const rows=[];for(const k of keys.slice(p,p+128))rows.push([await string(k),await visit(v[k])]);groups.push(await hashJSON(rows));}return hashJSON([array?'array':'object',keys.length,groups]);})();seen.set(v,work);return work;}
 return {sha256:await visit(value),bytes};
}
/** Legacy evidence keeps its original exact digest; refuse oversized expansion
 * BEFORE JSON.stringify, including DAGs whose physical graph is tiny. */
export function boundedJSONStringify(value,maxBytes){
 portable(value);const seen=new WeakMap();
 function size(v){if(typeof v==='string'){let n=2;for(let p=0;p<v.length;){let end=Math.min(p+WIDTH,v.length);if(end<v.length&&v.charCodeAt(end-1)>=0xd800&&v.charCodeAt(end-1)<=0xdbff)end--;n+=encoder.encode(JSON.stringify(v.slice(p,end))).length-2;p=end;if(n>maxBytes)return maxBytes+1;}return n;}if(v===null||typeof v!=='object')return JSON.stringify(v).length;if(seen.has(v))return seen.get(v);const array=Array.isArray(v),keys=Object.keys(v);let n=2+Math.max(0,keys.length-1);for(const k of keys){n+=(array?0:size(k)+1)+size(v[k]);if(n>maxBytes)break;}seen.set(v,n);return n;}
 if(size(value)>maxBytes)throw Error('Limit materiału ratunkowego (legacy JSON bytes).');return JSON.stringify(value);
}
