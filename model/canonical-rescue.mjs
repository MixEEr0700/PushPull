/** Independent immutable recovery files; never part of the active journal. */
import {readCanonicalBackup,assertCanonicalRestoreKeys} from './canonical-backup.mjs';
import {portable} from './backup-json.mjs';
import {evidenceProof,boundedJSONStringify} from './evidence-proof.mjs';
import {sha as shaText} from './journal-index.mjs';
const MAX=128*1024*1024;
const sha=async file=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('');
function open(){return new Promise((resolve,reject)=>{const q=indexedDB.open('pushpull-canonical-rescue',1);q.onupgradeneeded=()=>q.result.createObjectStore('points',{keyPath:'id'}).createIndex('createdAt','createdAt');q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);q.onblocked=()=>reject(Error('Baza punktów cofnięcia jest zajęta.'));});}
async function access(mode,work){const db=await open();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('points',mode,mode==='readwrite'?{durability:'strict'}:undefined);let result,failure;const get=q=>new Promise((r,j)=>{q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error)});Promise.resolve().then(()=>work(tx.objectStore('points'),get)).then(v=>result=v,e=>{failure=e;tx.abort()});tx.oncomplete=()=>resolve(result);tx.onabort=()=>reject(failure??tx.error);});}finally{db.close()}}
export async function readRescue(id){const p=await access('readonly',(s,get)=>get(s.get(id)));if(p)portable(p.evidence);if(!p||p.file.size>MAX||await sha(p.file)!==p.sha||(p.evidenceEncoding==='merkle-v1'?(await evidenceProof(p.evidence)).sha256:await shaText(boundedJSONStringify(p.evidence,MAX)))!==p.evidenceSHA)throw Error('Punkt ratunkowy nie przeszedł weryfikacji.');assertCanonicalRestoreKeys(await readCanonicalBackup(p.file));return p;}
export async function saveRescue(id,file,evidence){
 portable(evidence);if(!(file instanceof Blob)||file.size>MAX)throw Error('Limit pamięci punktu ratunkowego. Nie zastąpiono danych.');
 assertCanonicalRestoreKeys(await readCanonicalBackup(file));const point={id,file,evidence,sha:await sha(file),evidenceSHA:(await evidenceProof(evidence)).sha256,evidenceEncoding:'merkle-v1',createdAt:new Date().toISOString()};
 await access('readwrite',async(s,get)=>{s.add(point);const r=await get(s.get(id));if(!r||r.sha!==point.sha||r.evidenceSHA!==point.evidenceSHA)throw Error('Odczyt punktu ratunkowego różni się.');});return readRescue(id);
}
export async function listRescues(){return access('readonly',s=>new Promise((resolve,reject)=>{const rows=[],q=s.index('createdAt').openKeyCursor(null,'prev');q.onerror=()=>reject(q.error);q.onsuccess=()=>{const c=q.result;if(!c){resolve(rows);return;}if(rows.length>=1000){reject(Error('Limit listy punktów cofnięcia.'));return;}rows.push({id:c.primaryKey,createdAt:c.key});c.continue();};}));}
export function loadRescueFile(id){return new Promise((resolve,reject)=>{const w=new Worker(new URL('./canonical-restore-worker.mjs',import.meta.url),{type:'module'});const finish=(e,v)=>{clearTimeout(timer);w.terminate();e?reject(e):resolve(v)};const timer=setTimeout(()=>finish(Error('Nie potwierdzono punktu ratunkowego.')),120000);w.onerror=()=>finish(Error('Przerwano weryfikację punktu.'));w.onmessage=({data})=>finish(data.error?Error(data.error):null,data.result);w.postMessage({action:'read-rescue',id});});}
