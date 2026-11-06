/** Synthetic-only sizing of the exact backupBefore preimage and protocol limits. */
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {performance} from 'node:perf_hooks';
import {createLegacyModelFromSource} from '../model/legacy-model.mjs';
import {createProtocol,LIMITS,objectRecord} from '../model/journal-protocol.mjs';
import {startSession,exercisesFor,recordEntry} from '../model/journal.mjs';
import {newPerformance,flatten} from '../model/performance.mjs';
import {nativeData,AT} from '../tests/fixtures/backup-v4-fixture.mjs';
const storage=runInNewContext(readFileSync('storage.js','utf8')+'\n'+readFileSync('indexeddb.js','utf8')+'\nPushPullDB',{crypto,structuredClone});
const bytes=v=>Buffer.byteLength(JSON.stringify(v));
const old=JSON.parse(readFileSync('tests/fixtures/v1.json')),packet=JSON.parse(readFileSync('tests/fixtures/plan-v3.json'));
const results=[];
for(const profile of (process.argv.includes('--large-only')?['large-history']:['small','history','archive'])){
 const data=profile==='small'?structuredClone(old):nativeData(old,packet);
 if(profile==='large-history')while(data.sessions.length<40){const seq=data.sessions.length+1,type=data.trainingJournal.model.planVersions.find(p=>p.id===data.trainingJournal.activePlanVersionId).units[0].id,s={id:crypto.randomUUID(),seq,type,date:'2026-10-24',status:'done'};data.sessions.push(s);await startSession(data,s,AT);for(const ex of exercisesFor(data,s)){const p=newPerformance(ex);for(const r of p.rows)for(const seg of r.segments){seg.kg='20';seg.reps='8';}const series=flatten(p),e={id:crypto.randomUUID(),sessionId:s.id,exerciseId:ex.id,createdAt:AT,kg:series[0].kg,reps:series[0].reps,performance:p,series};recordEntry(data,e);data.entries.push(e);}}
 const source={format:'pushpull-backup',version:2,data,catalog:structuredClone(storage.parseBackup(data).catalog),archives:[]};
 if(profile==='archive')source.archives.push({id:'synthetic-raw',kind:'before-import',createdAt:AT,raw:'"\\'.repeat(128*1024)});
 for(let operation=0;operation<(profile==='large-history'?1:4);operation++){
  const t=performance.now(),document=await createLegacyModelFromSource(source,{ownerId:data.trainingJournal?.model.ownerId??'synthetic',createdAt:AT}),raw=JSON.stringify(document),archive={id:'synthetic-'+operation,kind:'before-import',createdAt:AT,raw};
  const candidate={...source,archives:[...source.archives,archive]};
  const bounded={...LIMITS,objectBytes:8*1024*1024,totalBytes:32*1024*1024};let outcome='PASS',max=0,total=0;
  try{const protocol=await createProtocol(candidate,{limits:bounded});max=Math.max(...protocol.records.journalObjects.map(r=>r.bytes));total=protocol.records.journalObjects.reduce((n,r)=>n+r.bytes,0);}catch(e){outcome=e.message;}
  results.push({profile,operation,sessions:data.sessions.length,results:data.entries.length,snapshots:data.trainingJournal?.sessionSnapshots.length??0,dataBytes:bytes(data),snapshotBytes:bytes(data.trainingJournal?.sessionSnapshots??[]),catalogBytes:bytes(source.catalog),archiveCount:source.archives.length,priorArchivesBytes:bytes(source.archives),preimageBytes:Buffer.byteLength(raw),archiveObjectBytes:bytes(archive),sourceBytes:bytes(candidate),objectLimit:bounded.objectBytes,totalLimit:bounded.totalBytes,maxObjectBytes:max,totalObjectBytes:total,outcome,ms:Math.round(performance.now()-t)});
  if(outcome!=='PASS')break;source.archives.push(archive);
 }
}
// Test the unchanged real production cap directly, without building a giant database.
let productionBoundary;
try{await objectRecord('x'.repeat(LIMITS.objectBytes));productionBoundary='unexpected success';}catch(e){productionBoundary={limit:LIMITS.objectBytes,asciiPayloadBytes:LIMITS.objectBytes,encodedObjectBytes:LIMITS.objectBytes+2,error:e.message};}
console.log(JSON.stringify({synthetic:true,limits:LIMITS,results,productionBoundary},null,2));
