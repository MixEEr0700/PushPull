/** Local PPC1 adaptation only. Commits remain in the established importer. */
import {openCompactBackup} from './compact-backup-reader.mjs';
import {JSON_OBJECT} from './canonical-json-transport.mjs';
import {readCanonicalBackup,validateCanonicalBackup} from './canonical-backup.mjs';
import {readCompactModel} from './compact-backup-writer.mjs';
import {validateCompactSource} from './compact-backup-preview.mjs';
import {compareBackupData} from './legacy-model.mjs';
export async function inspectCompactRestore(file,current=null,{signal,limits}={}){
 try{
  const container=await openCompactBackup(file,{signal,limits});
  const source=container.manifest.objects.some(o=>o.id===JSON_OBJECT)?await readCanonicalBackup(file,{signal,limits}):await readCompactModel(file,{signal,limits});
  if(source.format==='pushpull-canonical'){validateCanonicalBackup(source,{signal});return {format:'PPC1',canonical:true,canonicalCounts:{drafts:source.drafts.length,buffers:source.buffers.length,preferences:Object.keys(source.preferences).length},summary:validateCompactSource({...source.source,archives:[]},()=>signal?.throwIfAborted()),comparison:null};}signal?.throwIfAborted();
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
