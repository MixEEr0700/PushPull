/** Manual, append-only Drive backups. Legacy files remain readable.
 * No timers, outbox execution, automatic upload or cloud-to-database restore.
 */
import {runIncremental} from './drive-incremental-client.mjs';
import {canonical} from './backup-json.mjs';
import {parseModelBackup,backupSummary} from './legacy-model.mjs';
import {readLegacyBackup} from './legacy-backup.mjs';
const uuid=x=>typeof x==='string'&&/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(x);
const sorted=x=>[...x].sort();
const same=(a,b)=>canonical(a)===canonical(b);
const hash=async x=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(x)))),b=>b.toString(16).padStart(2,'0')).join('');
export async function inspectBackup(text){
 const value=JSON.parse(text);
 if(value.version===3)return parseModelBackup(text);
 const legacy=readLegacyBackup(text);return legacy.formatVersion===2?legacy.original:{data:legacy.data};
}
export async function makeNode(backup,parents,inspect=inspectBackup){
 await inspect(backup);
 const node={format:'pushpull-drive-backup',version:1,id:crypto.randomUUID(),parents:sorted(parents),createdAt:new Date().toISOString(),backup};
 return {...node,digest:await hash(node)};
}
export function properties(node){
 // Drive private properties: <=30 total, each key+value <=124 bytes.
 if(node.parents.length>60)throw Error('Zbyt wiele rozbieżnych kopii. Pobierz je do ręcznego odzyskania.');
 const p={pushpull:'sync-v1',node:node.id,digest:node.digest};
 for(let i=0;i<node.parents.length;i+=3)p['p'+i/3]=node.parents.slice(i,i+3).join(',');
 return p;
}
export async function readNode(transport,row,inspect=inspectBackup){
 const node=JSON.parse(await transport.read(row.fileId));
 const {digest,...body}=node;
 if(node.format!=='pushpull-drive-backup'||node.version!==1||node.id!==row.id||!same(node.parents,row.parents)||digest!==row.digest||await hash(body)!==digest)throw Error('Kopia Drive nie przeszła weryfikacji integralności.');
 await inspect(node.backup);return node;
}
// Keep the existing metadata key and archive ALL legacy account/outbox fields.
const initial=()=>({clientId:'',enabled:false,selected:null,accounts:{}});
export async function openDriveBackup({database,transport,inspect=inspectBackup,online=()=>navigator.onLine,captureCanonical,withLock=fn=>globalThis.navigator?.locks?navigator.locks.request('pushpull-drive-sync',fn):fn()}={}){
 let state,serial=Promise.resolve(),changed=()=>{},notice='',busy=false,connectedAccount=null,connectedClient=null,closed=false;
 const emit=()=>changed();
 const deviceId=crypto.randomUUID();
 const refresh=async()=>{state=await database.readDriveState()??{...initial(),mode:'manual',deviceId};};
 async function save(){const saved=await database.writeDriveState(state,state.token??null);state=saved;emit();}
 function mutex(fn){const result=serial.then(()=>withLock(fn));serial=result.catch(()=>{});return result;}
 // Use the legacy worker lock: finish any already-running operation BEFORE the
 // cutover, then disable future legacy workers without deleting their evidence.
 await mutex(async()=>{await refresh();if(state.mode!=='manual'||state.enabled||!state.deviceId){state.mode='manual';state.enabled=false;state.deviceId??=crypto.randomUUID();await save();}});
 function requireConnection(){
  if(closed)throw Error('Otwórz aplikację ponownie.');
  if(!online())throw Error('Brak Internetu. Dane i szkice pozostają zapisane lokalnie.');
  if(!transport.authenticated||connectedAccount!==state.selected||connectedClient!==state.clientId)throw Error('Połącz Google, aby wykonać kopię lub ją pobrać.');
 }
 async function operation(fn,isCurrent=()=>true){return mutex(async()=>{if(!isCurrent())return;await refresh();if(!isCurrent())return;requireConnection();busy=true;notice='Trwa operacja Google Drive…';emit();try{return await fn();}finally{busy=false;if(notice==='Trwa operacja Google Drive…')notice='Brak aktywnej operacji Google Drive.';emit();}});}
 let incrementalRunning=null,queueing=null,retryTimer=null,retryDelay=1000;
 const api={
  set onchange(fn){changed=fn;},
  get config(){return {clientId:state.clientId,selected:state.selected,label:state.accounts[state.selected]?.label??'',connected:transport.authenticated&&connectedAccount===state.selected&&connectedClient===state.clientId};},
  get status(){return {busy,automatic:state.autoPPC1===true,connected:api.config.connected,pending:!!state.ppc1Queue,verified:state.accounts[state.selected]?.ppc1?.verified??null,detail:notice||('Automatyczne kopie '+(state.autoPPC1?'włączone':'wyłączone')+'. Trening i szkice są zapisywane lokalnie.')};},
  async configure(clientId){
   await mutex(async()=>{await refresh();state.clientId=clientId.trim();state.enabled=false;await save();});
   transport.clear();connectedAccount=null;connectedClient=null;notice='Konfiguracja zapisana. Połącz Google przy wykonywaniu kopii.';emit();
   void transport.load?.().catch(()=>{});
  },
  async connect(){
   const clientId=state.clientId,identity=await transport.connect(clientId);
   await mutex(async()=>{await refresh();if(state.clientId!==clientId){transport.clear();throw Error('Konfiguracja Google zmieniła się. Połącz ponownie.');}
    if(state.selected&&state.selected!==identity.id){transport.clear();throw Error('Wybrano inne konto. Odłącz poprzednie w opcjach zaawansowanych.');}
    state.selected=identity.id;state.accounts[identity.id]??={};state.accounts[identity.id].label=identity.label;state.enabled=false;await save();connectedAccount=identity.id;connectedClient=clientId;state.autoPPC1??=true;await save();notice='Połączono Google. Teraz wybierz zapis lub przywrócenie kopii.';emit();});
  },
  async disconnect(){transport.clear();connectedAccount=null;connectedClient=null;await mutex(async()=>{await refresh();state.selected=null;state.enabled=false;await save();});notice='Odłączono Google. Dane lokalne i kopie Drive pozostają.';emit();},
  get automatic(){return state.autoPPC1===true;},
  async setAutomatic(enabled){await mutex(async()=>{await refresh();state.autoPPC1=!!enabled;await save();});},
  queueCanonical({manual=false}={}){if(queueing)return queueing;queueing=mutex(async()=>{await refresh();if(!manual&&!state.autoPPC1)return;state.ppc1Queue??=crypto.randomUUID();await save();notice='Trening zapisany lokalnie / Oczekuje na wysłanie';emit();}).then(()=>api.retryCanonical()).finally(()=>{queueing=null});return queueing;},
  retryCanonical(){
   clearTimeout(retryTimer);let failed=false;
   if(incrementalRunning)return incrementalRunning;if(!state.ppc1Queue)return Promise.resolve();
   incrementalRunning=operation(async()=>{
    if(!state.ppc1Queue)return;
    let account=state.accounts[state.selected];const queue=state.ppc1Queue;
    account.ppc1??={};let pending=account.ppc1.pending;
    if(!pending){
     if(!captureCanonical)throw Error('Brak kolektora PPC1.');
     const value=await captureCanonical();
     const {packet}=await runIncremental('prepare',{file:value,parent:account.ppc1.last??null},transport);
     pending={fileId:await transport.reservePointId(),packet,queue};
     account.ppc1.pending=pending;await save();
    }
    notice='Trening zapisany lokalnie / Zapisywanie kopii na Drive';emit();
    const result=await runIncremental('upload',pending,transport);
    account=state.accounts[state.selected];account.ppc1.last=result.fileId;delete account.ppc1.pending;
    if(state.ppc1Queue===pending.queue)delete state.ppc1Queue;
    account.ppc1.verified=new Date().toISOString();await save();
    notice='Kopia zweryfikowana';emit();return result;
   }).catch(error=>{failed=true;notice=(error.auth||!transport.authenticated)?'Trening zapisany lokalnie / Wymagane logowanie':'Trening zapisany lokalnie / Oczekuje na wysłanie: '+error.message;emit();}).finally(()=>{incrementalRunning=null;if(!closed&&state.ppc1Queue&&transport.authenticated&&online()&&typeof window!=='undefined'){retryDelay=failed?Math.min(retryDelay*2,600000):1000;retryTimer=setTimeout(()=>void api.retryCanonical(),failed?retryDelay:0);}});return incrementalRunning;
  },
  async canonicalPoints(){return operation(async()=>{try{const rows=await transport.listPoints();notice=rows.length?'Wybierz punkt odzyskiwania PPC1.':'Brak punktów PPC1 na Drive.';return rows;}catch(e){notice='Nie pobrano listy punktów: '+e.message;throw e;}});},
  async canonicalPoint(fileId,{signal,isCurrent=()=>!signal?.aborted}={}){return operation(async()=>{try{const result=await runIncremental('restore',{fileId},transport,{signal});if(isCurrent())notice='Punkt PPC1 zweryfikowany. Sprawdź podgląd przed przywróceniem.';return result;}catch(e){if(isCurrent())notice='Nie zweryfikowano punktu PPC1: '+e.message;throw e;}},isCurrent);},
  async upload(){return operation(async()=>{
   if(database.error)throw Error('Najpierw odzyskaj lokalne dane. Nie wysłano pustej kopii.');
   const revision=database.revision,current=database.value;
   const backup=database.model?await database.exportModelBackup():JSON.stringify(database.export());
   const node=await makeNode(backup,[],inspect);
   if(database.error||database.revision!==revision)throw Error('Dane zmieniły się podczas przygotowania kopii. Kliknij zapis ponownie.');
   // Each click is an independent CURRENT snapshot, never the old sync outbox.
   const file=await transport.create(JSON.stringify(node),{...properties(node),mode:'manual',device:state.deviceId});
   if(!file?.id)throw Error('Google nie potwierdził pliku. Kopia mogła powstać; możesz zapisać kolejną.');
   const verified=await readNode(transport,{...node,fileId:file.id},inspect);
   // readNode already checks the whole returned body against node.digest.
   // Compare exact text without allocating two more escaped copies of a large backup.
   if(node.backup!==verified.backup||node.digest!==verified.digest)throw Error('Google zwrócił inną zawartość kopii. Nie potwierdzono zapisu.');
   const summary=backupSummary(current,{createdAt:node.createdAt});
   notice='Kopia zapisana i zweryfikowana na Google Drive. '+new Date(node.createdAt).toLocaleString('pl-PL',{timeZone:'Europe/Warsaw'})+' · Sesje: '+summary.sessions+' · Wyniki: '+summary.results+' · Kompletne wersje planów: '+summary.completePlans+'. Szkice pozostają lokalnie.'+(database.revision!==revision?' W międzyczasie zmieniono dane lokalne — zapisz kolejną kopię.':'');
   return {fileId:file.id,revision,summary};
  });},
  async download(fileId,{choose=false,forRestore=false,isCurrent=()=>true}={}){return operation(async()=>{
   const files=await transport.list(),valid=[];let skipped=0;
   for(const file of files){
    try{
     const p=file.appProperties;
     if(p?.pushpull!=='sync-v1'||!uuid(p.node))throw Error('Nieznany plik');
     const parents=Object.keys(p).filter(k=>/^p\d+$/.test(k)).sort((a,b)=>Number(a.slice(1))-Number(b.slice(1))).flatMap(k=>p[k].split(','));
     if(parents.some(id=>!uuid(id)||id===p.node)||new Set(parents).size!==parents.length)throw Error('Nieprawidłowe relacje');
     let parsed;
     const node=await readNode(transport,{id:p.node,digest:p.digest,parents:sorted(parents),fileId:file.id},async raw=>{parsed=await inspect(raw);});
     valid.push({fileId:file.id,node,origin:p.mode==='manual'&&uuid(p.device)?p.device:null,time:Date.parse(file.createdTime),date:file.createdTime,sessionCount:parsed.summary?.sessions??parsed.data.sessions.length,entryCount:parsed.summary?.results??parsed.data.entries.length});
    }catch(error){if(error.auth||error.status)throw error;skipped++;}
   }
   if(!valid.length)throw Error(files.length?'Nie znaleziono prawidłowej kopii. Istniejące pliki pozostają na Drive.':'Brak kopii w Google Drive.');
   // Dates come from Drive, never the phone clock in node.createdAt. Legacy
   // ancestry identifies superseded copies; independent devices need a choice.
   const parents=new Set(valid.flatMap(c=>c.node.parents));
   const tips=valid.filter(c=>!parents.has(c.node.id));
   const origins=new Set(tips.map(c=>c.origin??c.node.id));
   const candidates=tips.length?tips:valid;
   candidates.sort((a,b)=>(Number.isFinite(b.time)?b.time:0)-(Number.isFinite(a.time)?a.time:0));
   const ambiguous=!tips.length||origins.size>1||candidates.some(c=>!Number.isFinite(c.time))||candidates.some((c,i)=>i&&c.time===candidates[0].time&&!same(c.node.backup,candidates[0].node.backup));
   const warning=(skipped?'Pominięto nieprawidłowe lub niedostępne kopie. ':'')+(ambiguous?'Kopie mogą zawierać różne historie urządzeń. Data zapisu w Drive nie rozstrzyga, która historia jest pełniejsza. Wybierz plik; pobranie nie zmieni danych lokalnych.':'');
   if(!fileId&&(choose||ambiguous||skipped)){
    if(isCurrent())notice=forRestore?'Wybierz kopię do podglądu. Różne urządzenia mogą mieć różne historie; niczego nie przywrócono. '+(skipped?'Pominięto nieprawidłowe kopie.':''):warning;return {choices:(choose?valid.slice().sort((a,b)=>(b.time||0)-(a.time||0)):candidates).map(c=>({fileId:c.fileId,date:c.date,sessionCount:c.sessionCount,entryCount:c.entryCount})),warning};
   }
   const chosen=fileId?valid.find(c=>c.fileId===fileId):candidates[0];
   if(!chosen)throw Error('Wybrana kopia nie jest już dostępna lub jest nieprawidłowa. Wybierz ponownie.');
   if(isCurrent())notice=forRestore?'Kopia zweryfikowana. Sprawdź podgląd przed zastąpieniem lokalnej bazy.':'Kopia sprawdzona. Pobieramy JSON na telefon; baza lokalna pozostaje bez zmian.';
   return {backup:chosen.node.backup,date:chosen.date};
  },isCurrent);},
  pauseForRestore(){clearTimeout(retryTimer);transport.clear();connectedAccount=null;connectedClient=null;},
  report(error){notice='Błąd: '+error.message;busy=false;emit();},
  close(){closed=true;clearTimeout(retryTimer);transport.clear();},
  // Passive compatibility for older cached shells used during PWA upgrades.
  // These calls must NEVER resume the former automatic queue.
  localChanged(){},retryNow(){return Promise.resolve();},
 };
 return api;
}
export const openDriveSync=openDriveBackup;
