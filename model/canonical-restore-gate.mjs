/** Startup-only readonly gate; never creates/upgrades a database. */
export const LOCAL_RESTORE_KEY='pushpull_canonical_restore_pending';
export const RESTORE_KEY='canonical-restore-pending';
export async function pendingCanonicalRestore({databaseOnly=false}={}){
 if(!databaseOnly&&localStorage.getItem(LOCAL_RESTORE_KEY))return {status:'pending'};
 return new Promise((resolve,reject)=>{const q=indexedDB.open('pushpull');let absent=false;q.onupgradeneeded=()=>{absent=true;q.transaction.abort()};q.onerror=()=>absent?resolve(null):reject(q.error);q.onsuccess=()=>{const db=q.result;if(!db.objectStoreNames.contains('meta')){db.close();resolve(null);return;}const tx=db.transaction('meta'),r=tx.objectStore('meta').get(RESTORE_KEY);let value;r.onsuccess=()=>value=r.result;tx.oncomplete=()=>{db.close();resolve(value??null)};tx.onabort=()=>{db.close();reject(tx.error)}};});
}
export function showCanonicalPending(detail=''){document.getElementById('app').innerHTML='<main class="app"><h1>Przywracanie nie zostało zakończone</h1><p role="alert">Dane pozostają zablokowane. Nie uruchomiono częściowo przywróconej aplikacji. Zachowaj plik PPC1 i ponów import w nowym, czystym profilu przeglądarki. Nie usunięto danych tego profilu.</p><p data-pending-detail></p></main>';document.querySelector('[data-pending-detail]').textContent=detail;}
