/** Canonical document budget, separate from the small manifest/graph parser. */
import {parseJson} from './backup-json.mjs';
export const CANONICAL_PARSE_BUDGET=64*1024*1024;
// Reserve UTF8 input + worst-case UTF16 text (3*bytes), then conservative
// per-token allocation credit. This is an admission charge, NOT a heap promise.
export function parseCanonicalJSON(text,bytes,{depth,ms},signal){
 const start=performance.now();let nesting=0,tokens=0;
 const guard=()=>{signal?.throwIfAborted();if(performance.now()-start>ms)throw Error('PPC1 JSON: time limit');};
 const check=(v,m)=>{if(!v)throw Error('PPC1 JSON: '+m);};
 check(bytes*3<=CANONICAL_PARSE_BUDGET,'parse memory budget');
 for(let i=0;i<text.length;i++){
  if(i%4096===0)guard();const c=text[i];
  if(c==='"'){
   tokens++;let closed=false;
   while(++i<text.length){if(i%4096===0)guard();if(text[i]==='\\')i++;else if(text[i]==='"'){closed=true;break;}}
   check(closed,'truncated string');
  }else if(c==='{'||c==='['){check(++nesting<=depth,'nesting limit');tokens++;}
  else if(c==='}'||c===']')nesting--;
  else if(c==='-'||c>='0'&&c<='9'){
   const begin=i;while(i+1<text.length&&/[0-9eE+.\-]/.test(text[i+1]))i++;
   check(i-begin<128,'numeric token limit');tokens++;
  }else if(c==='t'||c==='f'||c==='n'){tokens++;i+=(c==='f'?5:4)-1;}
  check(bytes*3+tokens*64<=CANONICAL_PARSE_BUDGET,'parse memory budget');
 }
 guard();const value=parseJson(text);guard();return value;
}
