import {previewFixture} from './fixtures/compact-preview-fixture.mjs';
export function canonicalFixture(old,n){
 const data=structuredClone(old),template={type:"PUSH A",date:"2026-10-01",status:"done"};data.sessions=Array.from({length:n},(_,i)=>({...template,id:'session-'+i,seq:i+1}));data.entries=Array.from({length:n},(_,i)=>({...old.entries[0],id:"result-"+i,sessionId:"session-"+i}));data.activeId=null;
 const s=previewFixture(data,null,false);
 return {source:{format:s.format,version:s.version,data:s.data,catalog:s.catalog},drafts:[],buffers:[],preferences:{},drive:{clientId:''}};
}
