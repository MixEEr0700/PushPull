/** Complete synthetic v2 source; never reads storage or private databases. */
import {nativeData,archiveFixtures} from './backup-v4-fixture.mjs';
export function previewFixture(old,packet,native=true){
 const data=native?nativeData(old,packet):structuredClone(old),plans=[],planVersions=[],sessionVersions={};
 for(const [id,exercises] of Object.entries(data.exercises)){
  const versionId=id+':fixture';plans.push({id,label:'synthetic',currentVersion:versionId});
  planVersions.push({id:versionId,planId:id,provenance:'recorded',exercises:exercises.map(({notes,...e})=>e)});
  for(const s of data.sessions)if(s.type===id)sessionVersions[s.id]={versionId,provenance:'session-start'};
 }
 return {format:'pushpull-backup',version:2,data,catalog:{plans,planVersions,sessionVersions},archives:archiveFixtures('opaque v1','opaque v2','opaque v3'),settings:{synthetic:true,extension:{unicode:'Ł😀\ud800\0'}},metadata:{purpose:'synthetic-only'}};
}
