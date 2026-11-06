import '../storage.js';
import '../indexeddb.js';
/** Local PPC1 adaptation only. Commits remain in the established importer. */
import {canonical} from './backup-json.mjs';
import {openCompactBackup} from './compact-backup-reader.mjs';
import {JSON_OBJECT,readCanonicalJSON} from './canonical-json-transport.mjs';
import {readCanonicalBackup,validateCanonicalBackup,assertCanonicalRestoreKeys} from './canonical-backup.mjs';
import {readCompactModel} from './compact-backup-writer.mjs';
import {validateCompactSource} from './compact-backup-preview.mjs';
import {compareBackupData,backupSummary} from './legacy-model.mjs';
export async function inspectCompactRestore(file,current=null,{signal,limits}={}){
 try{
  const container=await openCompactBackup(file,{signal,limits});
  let source=container.manifest.objects.some(o=>o.id===JSON_OBJECT)?await readCanonicalJSON(container,{signal,limits}):await readCompactModel(file,{signal,limits});
  if(source.format==='pushpull-protocol-rescue'){if(source.version!==1||Object.keys(source).sort().join(',')!=='bundle,format,version')throw Error('unsupported-sections');const bundle=source.bundle,restored=await(await import('./reference-preimage.mjs')).validateRescueBundle(bundle);signal?.throwIfAborted();return {format:'PPC1',source:restored,portableBundle:bundle,summary:validateCompactSource(restored,()=>signal?.throwIfAborted()),comparison:compareBackupData(current,restored.data)};}

  if(source.format==='pushpull-canonical'){validateCanonicalBackup(source,{signal});assertCanonicalRestoreKeys(source);const currentCanonical=current instanceof Blob?await readCanonicalBackup(current,{signal}):null;const oldNotes=currentCanonical?.source.data.trainingJournal?.model.userNotes??[],newNotes=source.source.data.trainingJournal?.model.userNotes??[];const noteDiff={added:newNotes.filter(n=>!oldNotes.some(o=>o.id===n.id)).length,removed:oldNotes.filter(n=>!newNotes.some(o=>o.id===n.id)).length,changed:newNotes.filter(n=>oldNotes.some(o=>o.id===n.id&&canonical(o)!==canonical(n))).length};return {format:'PPC1',canonical:true,canonicalCounts:{drafts:source.drafts.length,buffers:source.buffers.length,preferences:Object.keys(source.preferences).length},summary:validateCompactSource({...source.source,archives:[]},()=>signal?.throwIfAborted()),comparison:currentCanonical?compareBackupData(currentCanonical.source.data,source.source.data):null,currentSummary:currentCanonical?backupSummary(currentCanonical.source.data):null,noteDiff,notes:{current:currentCanonical?.source.data.trainingJournal?.model.userNotes.length??0,incoming:source.source.data.trainingJournal?.model.userNotes.length??0},currentCounts:currentCanonical?{drafts:currentCanonical.drafts.length,buffers:currentCanonical.buffers.length,preferences:Object.keys(currentCanonical.preferences).length}:null};}signal?.throwIfAborted();
  const summary=validateCompactSource(source,()=>signal?.throwIfAborted());
  // Existing atomic importer preserves exactly these sections. No silent drop.
  if(Object.keys(source).some(k=>!['format','version','data','catalog','archives'].includes(k)))throw Error('unsupported-sections');
  return {format:'PPC1',source,summary,comparison:compareBackupData(current,source.data)};
 }catch(error){
  if(error.name==='AbortError')throw new DOMException('Anulowano podgląd PPC1.','AbortError');
  if(error.message==='unsupported-sections')throw Error('PPC1 zawiera osobne ustawienia, szkice lub metadane, których obecny importer nie zachowa. Nie zmieniono danych.');
  throw Error('Nieprawidłowa, niekompletna, nieobsługiwana lub zbyt duża kopia PPC1. Nie zmieniono danych.');
 }
}
if(typeof DedicatedWorkerGlobalScope!=='undefined'&&globalThis instanceof DedicatedWorkerGlobalScope){
 globalThis.onmessage=async({data})=>{try{globalThis.postMessage({preview:await inspectCompactRestore(data.raw,data.current)});}catch(error){globalThis.postMessage({error:error.message});}};
}
