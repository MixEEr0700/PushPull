/** Incomplete editor state, deliberately outside approved workout records.
 * Unique draft IDs per editing page prevent one tab overwriting another tab's draft.
 * The synchronous buffer covers the interval before strict IndexedDB completion.
 */
import {canonical} from './backup-json.mjs';
const PREFIX='pushpull_workout_draft_v1:';
const key=(sid,eid)=>JSON.stringify([sid,eid]);
const same=(a,b)=>canonical(a)===canonical(b);
const clone=structuredClone;
// Local empty editor is recoverable, but not a valid v6 result-evidence value.
const recoverable=(kind,value)=>editorValueValid(kind,value)||kind==='legacy'&&typeof value?.kg==='string'&&typeof value.reps==='string'&&Array.isArray(value.series)&&value.series.length===0||kind==='v2'&&value?.performance?.version===2&&Array.isArray(value.performance.rows)&&value.performance.rows.length===0;
export function editorValueValid(kind,value){
 if(kind==='legacy')return value && typeof value.kg==='string' && typeof value.reps==='string' && Array.isArray(value.series) && value.series.length>0 && value.series.every(r=>typeof r.kg==='string'&&typeof r.reps==='string');
 return kind==='v2' && value?.performance?.version===2 && Array.isArray(value.performance.rows) && value.performance.rows.length>0 && value.performance.rows.every(r=>typeof r.id==='string'&&Array.isArray(r.segments)&&r.segments.length>0&&r.segments.every(s=>typeof s.id==='string'&&typeof s.kg==='string'&&typeof s.reps==='string'));
}
export async function openDrafts(database){
 let records=[],active=new Map(),restored=new Map(),queue=Promise.resolve(),storageError=null,readError=null;
 let changed=()=>{};
 const errors=new Map();
 function buffered(){
  const rows=[];
  try{for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(!k?.startsWith(PREFIX))continue;const raw=localStorage.getItem(k);try{rows.push(JSON.parse(raw));}catch{rows.push({id:k.slice(PREFIX.length),corrupt:true,raw});}}}
  catch(e){storageError=e;readError=e;}
  return rows;
 }
 async function reload(){
  readError=null;let saved=[];try{saved=await database.readDrafts();}catch(e){storageError=e;readError=e;}
  const merged=new Map();
  for(const r of [...saved,...buffered(),...[...active.values()].map(s=>s.record).filter(Boolean)]){
   if(!r || typeof r.id!=='string')continue;
   const old=merged.get(r.id);
   if(!old || r.sequence>old.sequence)merged.set(r.id,r);
   else if(r.sequence===old.sequence && r.token!==old.token)merged.set(r.id+':'+r.token,r);
  }
  records=[...merged.values()];changed();return records;
 }
 function replace(record){records=records.filter(r=>r.id!==record.id);records.push(record);}
 function buffer(record){try{localStorage.setItem(PREFIX+record.id+':'+record.token,JSON.stringify(record));return true;}catch(e){storageError=e;return false;}}
 function clearBuffer(record){
  // Each token has its own immutable key: read/remove cannot erase a later edit
  // written by an older still-open tab between those two storage operations.
  try{const keys=[];for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(k?.startsWith(PREFIX+record.id+':'))keys.push(k);}
   for(const k of keys){const value=JSON.parse(localStorage.getItem(k));if(value?.id===record.id&&value.sequence<=record.sequence)localStorage.removeItem(k);}
  }catch(e){storageError=e;}
 }
 async function remove(record){
  // CAS removal also protects a still-open old editing page after recovery.
  if(!record.corrupt && !await database.removeDraft(record))return false;
  if(record.corrupt){try{if(localStorage.getItem(PREFIX+record.id)===record.raw)localStorage.removeItem(PREFIX+record.id);}catch(e){throw e;}}
  else clearBuffer(record);
  records=records.filter(r=>r.id!==record.id||r.token!==record.token);errors.delete(record.id);return true;
 }
 function enqueue(work){queue=queue.then(work).catch(e=>{storageError=e;changed();});return queue;}
 const api={
  set onchange(fn){changed=fn;},
  get records(){return clone(records);},get error(){return storageError;},get readError(){return readError;},
  reload,
  // Read active capture memory directly, never the merged recovery view.
  readEvidence(){return [...active.values()].map(s=>({source:'editor-memory',record:clone(s.record),binding:clone(s.binding),durableToken:s.durableToken,parent:clone(s.parent)}));},
  reset(){active.clear();restored.clear();return reload();},
  compatible(record,binding){return record?.version===1&&typeof record.id==='string'&&record.key==='workout-draft:'+record.id&&typeof record.token==='string'&&Number.isSafeInteger(record.sequence)&&record.sequence>0&&same(record.context,binding.context)&&same(record.baseline,binding.baseline)&&recoverable(record.kind,record.value);},
  take(sessionId,exerciseId){const k=key(sessionId,exerciseId),value=restored.get(k);restored.delete(k);return value&&clone(value);},
  resume(record,binding){
   if(!api.compatible(record,binding))throw Error('Szkic nie odpowiada obecnej sesji lub wynikowi. Pobierz go do odzyskania; nie nadpisano danych.');
   const k=key(record.sessionId,record.exerciseId);
   active.set(k,{binding:clone(binding),record:null,durableToken:null,parent:record});
   restored.set(k,{kind:record.kind,value:clone(record.value)});
  },
  capture(binding,kind,value){
   const k=key(binding.context.sessionId,binding.context.exerciseId);
   let state=active.get(k);
   if(!state){
    // Existing saved drafts must be explicitly resumed/discarded first.
    // Editing afresh creates an independent branch rather than destroying them.
    state={binding:clone(binding),record:null,durableToken:null,parent:null};active.set(k,state);
   }
   const previous=state.record;
   const record={key:'workout-draft:'+(previous?.id??crypto.randomUUID()),id:null,version:1,token:crypto.randomUUID(),sequence:(previous?.sequence??0)+1,
    sessionId:binding.context.sessionId,exerciseId:binding.context.exerciseId,context:state.binding.context,baseline:state.binding.baseline,kind,value:clone(value),updatedAt:new Date().toISOString()};
   record.id=record.key.slice('workout-draft:'.length);state.record=record;
   replace(record);
   const inBuffer=buffer(record);errors.set(record.id,inBuffer?'buffered':'pending');changed();
   enqueue(async()=>{
    try{
     await database.writeDraft(record,state.durableToken);state.durableToken=record.token;clearBuffer(record);if(state.record?.token===record.token)errors.delete(record.id);
     if(state.parent){const parent=state.parent;if(await remove(parent))state.parent=null;}
    }catch(e){storageError=e;if(state.record?.token===record.token)errors.set(record.id,inBuffer?'buffered':'failed');}
    changed();
   });
  },
  status(sessionId,exerciseId){const s=active.get(key(sessionId,exerciseId));if(!s?.record)return '';const status=errors.get(s.record.id);return status==='failed'?'Nie utrwalono szkicu — nie zamykaj strony. Pobierz szkic.':status==='pending'?'Zapisywanie szkicu…':status==='buffered'?'Szkic w buforze odzyskiwania; oczekuje na IndexedDB.':'Szkic zapisany lokalnie · wynik niezatwierdzony';},
  assertCurrent(binding){const state=active.get(key(binding.context.sessionId,binding.context.exerciseId));if(state&&!same(state.binding,binding))throw Error('Zatwierdzony wynik lub plan zmienił się od rozpoczęcia szkicu. Zachowano szkic do odzyskania.');},
  ticket(sessionId,exerciseId){const s=active.get(key(sessionId,exerciseId));return s&&clone({record:s.record,parent:s.parent});},
  async confirmed(sessionId,exerciseId,ticket){
   await queue;
   const k=key(sessionId,exerciseId),state=active.get(k);if(!state)return;
   try{if(ticket?.record)await remove(ticket.record);
   if(ticket?.parent)await remove(ticket.parent);}catch(e){storageError=e;changed();return;}
   if(state.record?.token===ticket?.record?.token){active.delete(k);restored.delete(k);}changed();
  },
  async discard(record){await queue;if(!await remove(record))throw Error('Szkic zmienił się w innej karcie. Zachowano nowszą wersję.');for(const [k,s] of active)if(s.record?.id===record.id||s.parent?.id===record.id){active.delete(k);restored.delete(k);}changed();},
  flush(){return queue;}
 };
 await reload();return api;
}
