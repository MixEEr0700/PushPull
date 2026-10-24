// Test-only writer. Not shipped, imported or used by the production application.
import {canonical} from '../../model/backup-json.mjs';
import {createLegacyModel,exportBackup} from '../../model/legacy-model.mjs';
import {initialize,exercisesFor,recordEntry} from '../../model/journal.mjs';
import {activate} from '../../model/v2-plan.mjs';
import {captureSessionSnapshot} from '../../model/training-model.mjs';
import {newPerformance,flatten} from '../../model/performance.mjs';
import {stagePlan,stageActivation} from '../../model/plan-import.mjs';
export const AT='2026-10-24T12:00:00.000Z';
export const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
export async function seal(d){
 const manifest={...d,blobs:d.blobs.map(({data,...b})=>b),integrity:{algorithm:'SHA-256'}};
 d.integrity={algorithm:'SHA-256',digest:await hash(new TextEncoder().encode(canonical(manifest)))};return d;
}
export async function blob(value,compression='gzip'){
 const bytes=new TextEncoder().encode(JSON.stringify(value));
 const stored=compression==='none'?bytes:new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
 const digest=await hash(bytes);let data='';
 for(let i=0;i<stored.length;i+=8192)data+=String.fromCharCode(...stored.subarray(i,i+8192));
 return {id:'sha256:'+digest,encoding:'json-string-utf8',compression,storedBytes:stored.length,decodedBytes:bytes.length,storedSha256:await hash(stored),decodedSha256:digest,data:btoa(data)};
}
export async function encodeFixture(live,archives=[],compression='gzip'){
 const blobs=new Map(),add=async value=>{const b=await blob(value,compression);blobs.set(b.id,b);return b.id;};
 const liveRef=await add(live),rows=[];
 for(const {raw,...metadata} of archives)rows.push({metadata,blobId:raw===null?null:await add(raw)});
 return seal({format:'pushpull-backup',version:4,createdAt:AT,metadata:{fixture:'synthetic-only',future:{retained:true}},
  live:{formatVersion:JSON.parse(live).version,blobId:liveRef},archives:rows,blobs:[...blobs.values()],integrity:{algorithm:'SHA-256',digest:''}});
}
export function archiveFixtures(v1,v2,v3){
 const raws=[null,'',v1,v2,v3,'  {"future":99} \n','{broken','not JSON','Ł😀\u0000\ud800X\udfff','same raw','same raw',
  JSON.stringify({format:'pushpull-idb-recovery',version:1,backups:[{unverified:true}],unknown:'preserve'})];
 return raws.map((raw,i)=>({id:'archive-'+i,kind:i===11?'before-import':'synthetic',createdAt:AT,sourceId:'old-id-'+i,extension:{order:i,unknown:[null,false,'Ł']},raw}));
}
/** Small complete native journal: old records, four V2 units, TEST V3, notes,
 * technique, separate sides, backoffs, drops, independent group members. */
export function nativeData(old,packet){
 let data=structuredClone(old);for(const s of data.sessions)s.status='done';data.activeId=null;
 data.trainingJournal=initialize('synthetic-v4-owner');activate(data,AT);
 const add=unit=>{
  const seq=Math.max(0,...data.sessions.map(s=>s.seq))+1;
  const s={id:'native-'+seq,seq,date:'2026-10-24',status:'done',type:unit};data.sessions.push(s);
  const j=data.trainingJournal,snap=captureSessionSnapshot(j.model,{id:'snapshot-'+seq,sessionId:s.id,planVersionId:j.activePlanVersionId,unitId:unit,startedAt:AT});
  j.sessionSnapshots.push(structuredClone(snap));s.journalSnapshotId=snap.id;
  for(const ex of exercisesFor(data,s)){
   const performance=newPerformance(ex);
   performance.rows.forEach((r,i)=>{r.id=s.id+'-'+ex.id+'-row-'+i;r.segments.forEach((seg,k)=>Object.assign(seg,{id:r.id+'-seg-'+k,kg:String(10+i+k),reps:String(8+i)}));});
   const series=flatten(performance),entry={id:s.id+'-'+ex.id,sessionId:s.id,exerciseId:ex.id,performance,series,kg:series[0].kg,reps:series[0].reps,createdAt:AT};
   recordEntry(data,entry);data.entries.push(entry);
  }
 };
 for(const unit of ['PUSH A','PULL A','PUSH B','PULL B'])add(unit);
 data=stagePlan(data,packet,data.trainingJournal.model.ownerId);data=stageActivation(data,packet.planVersion.id,AT);
 for(const unit of packet.planVersion.units)add(unit.id);
 data.sessions.at(-1).status='active';data.activeId=data.sessions.at(-1).id;
 data.changes??={};(data.changes['PUSH-A-1']??=[]).push({date:'2026-10-24',kind:'technique',text:'Syntetyczny znacznik — bez przeliczenia kg'});
 data.exercises['PUSH A'][0].notes+='\nNotatka testowa Ł😀';
 data.trainingJournal.model.userNotes.push({id:'native-note',exerciseId:'PUSH-A-1',sessionId:data.sessions.at(-1).id,text:'Notatka użytkownika',origin:'user',revision:1,source:{kind:'owner',reference:'fixture',recordedAt:AT}});
 return data;
}
export async function sourceV3(v2){return exportBackup(await createLegacyModel(JSON.stringify(v2),{ownerId:v2.data.trainingJournal?.model.ownerId??'synthetic-v4-owner',createdAt:AT}));}
