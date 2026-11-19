import '../storage.js';
import '../indexeddb.js';
/** Local PPC1 adaptation only. Commits remain in the established importer. */
import {compareCanonicalRestore} from './restore-comparison.mjs';
import {openCompactBackup} from './compact-backup-reader.mjs';
import {JSON_OBJECT,readCanonicalJSON} from './canonical-json-transport.mjs';
import {readCanonicalBackup,validateCanonicalBackup,assertCanonicalRestoreKeys} from './canonical-backup.mjs';
import {readCompactModel} from './compact-backup-writer.mjs';
import {validateCompactSource} from './compact-backup-preview.mjs';
import {compareBackupData,backupSummary} from './legacy-model.mjs';
export async function inspectCompactRestore(file,current=null,{signal,limits,starter}={}){
 try{
  const container=await openCompactBackup(file,{signal,limits});
  let source=container.manifest.objects.some(o=>o.id===JSON_OBJECT)?await readCanonicalJSON(container,{signal,limits}):await readCompactModel(file,{signal,limits});
  if(source.format==='pushpull-protocol-rescue'){if(source.version!==1||Object.keys(source).sort().join(',')!=='bundle,format,version')throw Error('unsupported-sections');const bundle=source.bundle,restored=await(await import('./reference-preimage.mjs')).validateRescueBundle(bundle);signal?.throwIfAborted();return {format:'PPC1',source:restored,portableBundle:bundle,summary:validateCompactSource(restored,()=>signal?.throwIfAborted()),comparison:compareBackupData(current,restored.data)};}

  if(source.format==='pushpull-canonical'){
   validateCanonicalBackup(source,{signal});assertCanonicalRestoreKeys(source);
   const existing=current instanceof Blob?await readCanonicalBackup(current,{signal}):null;
   const counts=value=>({drafts:value.drafts.length,buffers:value.buffers.length,preferences:Object.keys(value.preferences).length});
   return {format:'PPC1',canonical:true,canonicalCounts:counts(source),summary:validateCompactSource({...source.source,archives:[]},()=>signal?.throwIfAborted()),
    review:existing?compareCanonicalRestore(existing,source,starter):null,
    currentSummary:existing?backupSummary(existing.source.data):null,
    currentCounts:existing?counts(existing):null};
  }
  signal?.throwIfAborted();
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
 globalThis.onmessage=async({data})=>{try{globalThis.postMessage({preview:await inspectCompactRestore(data.raw,data.current,{starter:data.starter})});}catch(error){globalThis.postMessage({error:error.message});}};
}
