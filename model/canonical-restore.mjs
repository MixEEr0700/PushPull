import {localCanonicalBuffers} from './canonical-export.mjs';
import {LOCAL_RESTORE_KEY,pendingCanonicalRestore} from './canonical-restore-gate.mjs';
export async function restoreCanonicalFile(file,baseline){
 if(localCanonicalBuffers().length||localStorage.getItem('pushpull_skeleton_v1')!==null)throw Error('Przywracanie wymaga czystego profilu bez buforów i starej historii.');
 return new Promise((resolve,reject)=>{
  const w=new Worker(new URL('./canonical-restore-worker.mjs',import.meta.url),{type:'module'});let id=null,claimed=false,dirty=false;const owner=localStorage.getItem('pushpull_indexeddb_owner');
  const keepClosed=()=>{try{if(id&&!localStorage.getItem(LOCAL_RESTORE_KEY))localStorage.setItem(LOCAL_RESTORE_KEY,id)}catch{}};
  const checkAnchor=()=>{if(localStorage.getItem('pushpull_skeleton_v1')!==null||localStorage.getItem('pushpull_indexeddb_owner')!==owner)throw Error('Zmieniono kotwicę lokalnego profilu.');};
  const changed=e=>{if(e.storageArea===localStorage&&(e.key===null||e.key.startsWith('pushpull')))dirty=true;};addEventListener('storage',changed);
  const stop=async(error,result)=>{clearTimeout(timer);w.terminate();removeEventListener('storage',changed);
   if(error){if(claimed)keepClosed();try{if(id&&!claimed&&!await pendingCanonicalRestore({databaseOnly:true})&&localStorage.getItem(LOCAL_RESTORE_KEY)===id)localStorage.removeItem(LOCAL_RESTORE_KEY);}catch{}reject(error);return;}
   try{checkAnchor();if(!id||localStorage.getItem(LOCAL_RESTORE_KEY)!==id||dirty)throw Error('Zmiana podczas aktywacji localStorage. Profil pozostaje pending.');const expected=result.buffers;const actual=localCanonicalBuffers(id);if(JSON.stringify(actual)!==JSON.stringify([...expected].sort((a,b)=>a.key<b.key?-1:a.key>b.key?1:0)))throw Error('Końcowy odczyt buforów różni się.');localStorage.removeItem(LOCAL_RESTORE_KEY);resolve(result.metrics);}catch(e){keepClosed();reject(e);}
  };
  const timer=setTimeout(()=>void stop(Error('Nie potwierdzono restore. Sprawdź stan pending.')),120000);
  w.onerror=()=>void stop(Error('Przerwano worker restore. Sprawdź stan pending.'));
  w.onmessage=({data})=>{
   if(data.reserve){try{if(localCanonicalBuffers().length||localStorage.getItem('pushpull_skeleton_v1')!==null)throw Error('Cel localStorage zmienił się.');id=data.reserve;localStorage.setItem(LOCAL_RESTORE_KEY,id);w.postMessage({reserveOK:true});}catch{w.postMessage({reserveOK:false});}return;}
   if(data.claimed){claimed=true;return;}
   if(data.local){try{checkAnchor();if(dirty||localStorage.getItem(LOCAL_RESTORE_KEY)!==id||localCanonicalBuffers(id).length)throw Error('Konflikt celu');for(const row of data.local){if(localStorage.getItem(row.key)!==null)throw Error('Konflikt bufora');localStorage.setItem(row.key,row.raw);}const actual=localCanonicalBuffers(id);if(JSON.stringify(actual)!==JSON.stringify([...data.local].sort((a,b)=>a.key<b.key?-1:a.key>b.key?1:0)))throw Error('Odczyt buforów różni się.');w.postMessage({localOK:true});}catch{w.postMessage({localOK:false});}return;}
   void stop(data.error?Error(data.error):null,data.result);
  };
  w.postMessage({file,baseline});
 });
}
