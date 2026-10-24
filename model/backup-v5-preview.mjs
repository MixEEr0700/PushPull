/** C1: existing decoder + disposable memory database. No IndexedDB/network API. */
import {decodeBackup} from './backup-v5.mjs';
import {V4_LIMITS} from './backup-v4.mjs';
import {backupSummary} from './legacy-model.mjs';
const abort=signal=>{if(signal?.aborted)throw new DOMException('Anulowano podgląd','AbortError');};
export function sameTrialData(a,b){
 if(a===b)return true;
 if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;
 const keys=Object.keys(a);return keys.length===Object.keys(b).length&&keys.every(k=>Object.hasOwn(b,k)&&sameTrialData(a[k],b[k]));
}
export function createTrialDatabase(){
 let value=null,revision=0;
 return Object.freeze({
  get revision(){return revision;},
  read(){return structuredClone(value);},
  clear(){value=null;revision++;},
  async restore(stage,{expectedRevision=revision,signal}={}){
   abort(signal);const next=structuredClone(stage);
   // Transaction boundary: no partial state, stale revision or cancelled commit.
   await Promise.resolve();abort(signal);
   if(revision!==expectedRevision)throw Error('Zmieniono izolowaną bazę.');
   const readback=structuredClone(next);
   if(!sameTrialData(stage,readback))throw Error('Niezgodność próbnego odtworzenia.');
   value=next;revision++;return readback;
  }
 });
}
async function previewValidatedV5(file,{signal,limits={},getRevision=()=>0}={}){
 const revision=getRevision();abort(signal);
 const max=Math.min(limits.fileBytes??V4_LIMITS.fileBytes,V4_LIMITS.fileBytes);
 if(file.size>max)throw Error('Plik przekracza limit podglądu v5.');
 const stage=await decodeBackup(await file.text(),{limits,signal});
 if(stage.formatVersion!==5)throw Error('Wybierz kopię v5. Starsze kopie mają dotychczasowy podgląd.');
 abort(signal);const trial=createTrialDatabase();
 try{
  const restored=await trial.restore(stage,{signal});
  if(!sameTrialData(stage,restored))throw Error('Niezgodność próbnego odtworzenia.');
  if(getRevision()!==revision)throw Error('Bieżąca baza zmieniła się. Otwórz podgląd ponownie.');
  abort(signal);
  const summary=backupSummary(restored.live.data);
  return Object.freeze({formatVersion:5,plans:summary.plans.length,activeVersion:summary.activePlanId!==null,
   sessions:summary.sessions,results:summary.results,snapshots:summary.snapshots,
   series:restored.live.data.entries.reduce((n,e)=>n+(Array.isArray(e.series)?e.series.length:0),0),
   archives:restored.archives.length,nullArchives:restored.archives.filter(a=>a.raw===null).length,
   trialEqual:true,draftsIncluded:false});
 }finally{trial.clear();}
}

/** Never expose parser excerpts or raw input through user-facing error messages. */
export async function previewBackupV5(file,options={}){
 try{return await previewValidatedV5(file,options);}
 catch(error){
  if(error.name==='AbortError')throw new DOMException('Anulowano podgląd','AbortError');
  if(/zmieniła/.test(error.message))throw Error('Bieżąca baza zmieniła się. Otwórz podgląd ponownie.');
  if(/limit|size/.test(error.message))throw Error('Przekroczono limit rozmiaru lub złożoności kopii v5.');
  if(error.message.startsWith('Wybierz kopię v5'))throw Error('Wybierz kopię v5. Starsze kopie mają dotychczasowy podgląd.');
  throw Error('Nieprawidłowa lub uszkodzona kopia v5. Weryfikacja integralności (checksum/struktura) nie powiodła się. Nie zapisano danych.');
 }
}
