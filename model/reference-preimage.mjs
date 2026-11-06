/** Reference-only recovery manifests. Existing immutable records are never rewritten. */
import {STORES,ROW_STORES,materialize,equalJSON,LIMITS,protocolInput} from './journal-protocol.mjs';
import {sha,encodedJSON} from './journal-index.mjs';
import {requireThat as check} from './backup-json.mjs';
export const FORMAT='pushpull-reference-preimage';
export function referenceOf(raw){if(typeof raw!=='string'||!raw.startsWith('{"format":"'+FORMAT+'",'))return null;const p=JSON.parse(raw);check(p.version===1&&typeof p.checkpointId==='string'&&/^[a-f0-9]{64}$/.test(p.sha256),'preimage pointer');return p;}
export async function makeReference(before){
 const source=await materialize(before);
 const manifest={format:FORMAT,version:1,state:before.state,rows:Object.fromEntries(ROW_STORES.map(k=>[k,before.records[k]])),inventory:Object.fromEntries(['journalObjects','journalIndex','journalCheckpoints'].map(k=>[k,before.records[k].map(r=>r.id)]))};
 const raw=JSON.stringify(manifest);encodedJSON(raw,LIMITS.objectBytes);
 const cp={id:'preimage:'+Date.now()+':'+crypto.randomUUID(),protocol:2,raw,sha256:await sha(raw)};
 const pointer={format:FORMAT,version:1,checkpointId:cp.id,sha256:cp.sha256};
 const restored=await resolveReference(pointer,{...before,records:{...before.records,journalCheckpoints:[...before.records.journalCheckpoints,cp]}});
 check(equalJSON(restored.source,source),'preimage reconstruction');return {cp,pointer};
}
export async function resolveReference(pointer,current){
 const cp=current.records.journalCheckpoints.find(c=>c.id===pointer.checkpointId);
 check(cp&&cp.sha256===pointer.sha256&&await sha(cp.raw)===pointer.sha256,'preimage checkpoint integrity');
 encodedJSON(cp.raw,LIMITS.objectBytes);const m=protocolInput(JSON.parse(cp.raw));check(m.format===FORMAT&&m.version===1&&Object.keys(m).sort().join(',')==='format,inventory,rows,state,version'&&Object.keys(m.rows).sort().join(',')===[...ROW_STORES].sort().join(',')&&Object.keys(m.inventory).sort().join(',')==='journalCheckpoints,journalIndex,journalObjects','preimage manifest');
 const records=Object.fromEntries(STORES.map(k=>[k,[]]));
 for(const k of ROW_STORES){check(Array.isArray(m.rows[k]),'preimage rows');records[k]=m.rows[k];}
 for(const k of ['journalObjects','journalIndex','journalCheckpoints']){check(Array.isArray(m.inventory[k])&&new Set(m.inventory[k]).size===m.inventory[k].length,'preimage inventory');const map=new Map(current.records[k].map(r=>[r.id,r]));records[k]=m.inventory[k].map(id=>{const r=map.get(id);check(r,'missing preimage reference');return r;});}
 records.journalState=[m.state];const bundle={state:m.state,records},source=await materialize(bundle);return {bundle,source};
}
export async function validateRescueBundle(bundle){
 check(Object.keys(bundle).sort().join(',')==='records,state'&&Object.keys(bundle.records).sort().join(',')===[...STORES].sort().join(','),'portable preimage shape');
 for(const store of STORES)check(Array.isArray(bundle.records[store])&&new Set(bundle.records[store].map(r=>r.id)).size===bundle.records[store].length,'portable preimage duplicate record');
 const source=await(await import('./journal-idb.mjs')).auditBundle(bundle),queue=[source],seen=new Set();
 for(const cp of bundle.records.journalCheckpoints)if(cp.protocol===2&&typeof cp.raw==='string'&&cp.raw.startsWith('{"format":"'+FORMAT+'",')){check(seen.size<10000,'preimage reference limit');seen.add(cp.id);queue.push((await resolveReference({checkpointId:cp.id,sha256:cp.sha256},bundle)).source);}
 while(queue.length){for(const a of queue.pop().archives){const p=referenceOf(a.raw);if(!p||seen.has(p.checkpointId))continue;check(seen.size<10000,'preimage reference limit');seen.add(p.checkpointId);queue.push((await resolveReference(p,bundle)).source);}}
 return source;
}
