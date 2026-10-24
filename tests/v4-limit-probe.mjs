/** Synthetic-only reproducer. Never opens storage or reads user files. */
import {exportBackupV4} from '../model/backup-v4-export.mjs';
export async function probe(snapshot,bytes=64*1024*1024,limits={}){
 const output=[];
 for(const stage of ['live','archive','nested-archive']){
  const source=structuredClone(snapshot),raw=stage==='nested-archive'?JSON.stringify({raw:JSON.stringify({raw:'x'.repeat(bytes)})}):'x'.repeat(bytes);
  if(stage==='live')source.data.syntheticOpaque=raw;
  else source.archives=[{id:'synthetic',kind:'recovery',createdAt:'2026-10-24T00:00:00.000Z',raw}];
  const start=performance.now();let message='';
  try{await exportBackupV4(source,{createdAt:'2026-10-24T00:00:00.000Z',limits});}
  catch(error){message=error.message;}
  if(!message.includes('decoded size limit'))throw Error('Expected decoded limit at '+stage+': '+message);
  if((stage==='live'?source.data.syntheticOpaque:source.archives[0].raw)!==raw)throw Error('Source mutated');
  output.push({stage,rawCodeUnits:raw.length,jsonStringBytes:new TextEncoder().encode(JSON.stringify(raw)).length,ms:Math.round(performance.now()-start),rejected:true});
 }
 return output;
}
