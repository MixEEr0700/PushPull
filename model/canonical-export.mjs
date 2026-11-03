/** UI orchestration only: synchronous buffers, worker lifecycle, stale guard. */
const prefixes=['pushpull_workout_draft_v1:','pushpull-note-ui-v1:'];
export function localCanonicalBuffers(restoreId=null){
 const pending=localStorage.getItem('pushpull_canonical_restore_pending');if(pending&&pending!==restoreId)throw Error('Przywracanie pending.');
 const keys=[];for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(prefixes.some(p=>key?.startsWith(p)))keys.push(key);else if(key?.startsWith('pushpull')&&!['pushpull_skeleton_v1','pushpull_indexeddb_owner','pushpull_canonical_restore_pending'].includes(key)&&!key.startsWith('pushpull_skeleton_v1_backup_'))throw Error('Nieznane trwałe dane localStorage.');}
 let bytes=0;if(keys.length>10000)throw Error('Limit buforów PPC1.');return keys.sort().map(key=>{const raw=localStorage.getItem(key);if(typeof raw!=='string')throw Error('Bufor zmienił się.');bytes+=2*(key.length+raw.length);if(bytes>64*1024*1024)throw Error('Limit pamięci buforów PPC1.');return {key,raw};});
}
export function exportCanonicalLocal({getRevision,signal,onProgress=()=>{}}={}){
 const started=performance.now();let firstPhase=null;
 let buffers,revision;try{signal?.throwIfAborted();buffers=localCanonicalBuffers();revision=getRevision();}catch(e){return Promise.reject(e);}
 return new Promise((resolve,reject)=>{
  const worker=new Worker(new URL('./canonical-export-worker.mjs',import.meta.url),{type:'module'});let dirty=false;
  const changed=e=>{if(e.storageArea===localStorage&&(e.key===null||prefixes.some(p=>e.key.startsWith(p))))dirty=true;};
  const finish=(error,result)=>{clearTimeout(timer);worker.terminate();removeEventListener('storage',changed);signal?.removeEventListener('abort',abort);error?reject(error):resolve(result);};
  const abort=()=>finish(new DOMException('Anulowano eksport PPC1.','AbortError'));
  const timer=setTimeout(()=>finish(Error('Przekroczono czas eksportu PPC1.')),60000);
  addEventListener('storage',changed);signal?.addEventListener('abort',abort,{once:true});
  worker.onerror=()=>finish(Error('Nie można uruchomić kodowania PPC1.'));
  worker.onmessage=({data})=>{try{
   if(data.phase){firstPhase??=performance.now();onProgress(data.phase);return;}
   if(data.error)throw Error(data.error);signal?.throwIfAborted();
   if(dirty||getRevision()!==revision||!sameBuffers(localCanonicalBuffers(),buffers))throw Error('Dane zmieniły się podczas eksportu. Ponów operację.');if(data.result?.metrics){data.result.metrics.startupMs=(firstPhase??performance.now())-started;data.result.metrics.totalMs=performance.now()-started;}finish(null,data.result);
  }catch(e){finish(e);}};
  worker.postMessage({buffers,revision});
 });
}

function sameBuffers(a,b){return a.length===b.length&&a.every((r,i)=>r.key===b[i].key&&r.raw===b[i].raw);}
