/** Append-only PPC1 recovery points in Drive appDataFolder. */
import {runIncremental} from './drive-incremental-client.mjs';
import {canonical} from './backup-json.mjs';
// Keep the existing metadata key and archive ALL legacy account/outbox fields.
const initial=()=>({clientId:'',enabled:false,selected:null,accounts:{}});
async function driveLock(fn){
 if(!globalThis.navigator?.locks)return fn();
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(Error('Inna karta nadal korzysta z Google Drive. Ponów operację.')),30000);
 try{return await navigator.locks.request('pushpull-drive-sync',{signal:controller.signal},()=>{clearTimeout(timer);return fn();});}
 finally{clearTimeout(timer);}
}
const withoutIntent=({token,ppc1Queue,ppc1Failure,...rest})=>rest;
export async function openDriveBackup({database,transport,online=()=>navigator.onLine,captureCanonical,withLock=driveLock}={}){
 let state,serial=Promise.resolve(),changed=()=>{},notice='',busy=false,connectedAccount=null,connectedClient=null,closed=false;
 const emit=()=>changed();
 const deviceId=crypto.randomUUID();
 const refresh=async()=>{state=await database.readDriveState()??{...initial(),mode:'manual',deviceId};};
 async function save(){const saved=await database.writeDriveState(state,state.token??null);state=saved;emit();}
 // A native finish can write a fresh intent during network I/O. Merge only
 // that change. Never retry over a changed account, checkpoint or settings.
 async function saveProgress(change){
  const baseline=state;
  for(let i=0;i<3;i++){
   await refresh();
   if(state.token!==baseline.token&&canonical(withoutIntent(state))!==canonical(withoutIntent(baseline)))throw Error('Stan Google Drive zmienił się w innej karcie. Ponów operację.');
   const current=state;state=structuredClone(current);change(state);
   try{await save();return;}catch(error){
    await refresh();
    if(state.token===current.token||i===2)throw error;
   }
  }
 }
 function mutex(fn){const result=serial.then(()=>withLock(fn));serial=result.catch(()=>{});return result;}
 // Use the legacy worker lock: finish any already-running operation BEFORE the
 // cutover, then disable future legacy workers without deleting their evidence.
 await refresh();
 if(state.mode!=='manual'||state.enabled||!state.deviceId)await mutex(async()=>{await refresh();if(state.mode!=='manual'||state.enabled||!state.deviceId){state.mode='manual';state.enabled=false;state.deviceId??=crypto.randomUUID();await save();}});
 function requireConnection(){
  if(closed)throw Error('Otwórz aplikację ponownie.');
  if(!online())throw Error('Brak Internetu. Dane i szkice pozostają zapisane lokalnie.');
  if(!transport.authenticated||connectedAccount!==state.selected||connectedClient!==state.clientId)throw Object.assign(Error('Połącz Google, aby wykonać kopię lub ją pobrać.'),{auth:true});
 }
 async function operation(fn,isCurrent=()=>true,ready=()=>true){return mutex(async()=>{if(!isCurrent())return;await refresh();if(!isCurrent()||!ready())return;requireConnection();busy=true;notice='Trwa operacja Google Drive…';emit();try{return await fn();}finally{busy=false;if(notice==='Trwa operacja Google Drive…')notice='Brak aktywnej operacji Google Drive.';emit();}});}
 let incrementalRunning=null,queueing=null,manualRequested=false,retryTimer=null,retryDelay=1000;
 const api={
  set onchange(fn){changed=fn;},
  get config(){return {clientId:state.clientId,selected:state.selected,label:state.accounts[state.selected]?.label??'',connected:transport.authenticated&&connectedAccount===state.selected&&connectedClient===state.clientId};},
  get status(){return {busy,automatic:state.autoPPC1===true,connected:api.config.connected,pending:!!state.ppc1Queue,backupFailed:!!state.ppc1Queue&&state.ppc1Failure===state.ppc1Queue,verified:state.accounts[state.selected]?.ppc1?.verified??null,detail:notice||('Automatyczne kopie '+(state.autoPPC1?'włączone':'wyłączone')+'. Trening i szkice są zapisywane lokalnie.')};},
  async configure(clientId){
   await mutex(async()=>{await refresh();state.clientId=clientId.trim();state.enabled=false;await save();});
   transport.clear();connectedAccount=null;connectedClient=null;notice='Konfiguracja zapisana. Połącz Google przy wykonywaniu kopii.';emit();
   void transport.load?.().catch(()=>{});
  },
  async connect(){
   // Changing the token during an upload could send its next request to a
   // different account. Keep the user gesture, but refuse while Drive is busy.
   if(busy)throw Error('Trwa operacja Google Drive. Połącz ponownie po jej zakończeniu.');
   connectedAccount=null;connectedClient=null;
   const clientId=state.clientId,identity=await transport.connect(clientId);
   await mutex(async()=>{await refresh();if(state.clientId!==clientId){transport.clear();throw Error('Konfiguracja Google zmieniła się. Połącz ponownie.');}
    if(state.selected&&state.selected!==identity.id){transport.clear();throw Error('Wybrano inne konto. Odłącz poprzednie w opcjach zaawansowanych.');}
    await saveProgress(current=>{
     current.selected=identity.id;current.accounts[identity.id]??={};current.accounts[identity.id].label=identity.label;
     current.enabled=false;current.autoPPC1??=true;
    });
    connectedAccount=identity.id;connectedClient=clientId;notice='Połączono Google. Teraz wybierz zapis lub przywrócenie kopii.';emit();
   });
  },
  async disconnect(){transport.clear();connectedAccount=null;connectedClient=null;await mutex(async()=>{await refresh();state.selected=null;state.enabled=false;await save();});notice='Odłączono Google. Dane lokalne i kopie Drive pozostają.';emit();},
  get automatic(){return state.autoPPC1===true;},
  async setAutomatic(enabled){await mutex(async()=>{await refresh();state.autoPPC1=!!enabled;await save();});},
  queueCanonical({manual=false}={}){
   manualRequested||=manual;
   if(!queueing){
    queueing=mutex(async()=>{
     await refresh();if(!manualRequested&&!state.autoPPC1)return;
     const pending=state.accounts[state.selected]?.ppc1?.pending;
     const newerManual=manualRequested&&pending&&pending.queue===state.ppc1Queue&&pending.sourceRevision!==database.revision;
     if(!state.ppc1Queue||newerManual)await saveProgress(current=>{
      if(newerManual&&current.ppc1Queue===pending.queue)current.ppc1Queue=crypto.randomUUID();
      else current.ppc1Queue??=crypto.randomUUID();
     });
     notice='Trening zapisany lokalnie / Oczekuje na wysłanie';emit();
    }).finally(()=>{queueing=null;manualRequested=false;});
   }
   return queueing.then(()=>api.retryCanonical());
  },
  retryCanonical(){
   clearTimeout(retryTimer);let failed=false,attemptedQueue=state.ppc1Queue;
   if(incrementalRunning)return incrementalRunning;
   incrementalRunning=operation(async()=>{
    if(!state.ppc1Queue)return;
    const accountId=state.selected,queue=state.ppc1Queue;
    let pending=state.accounts[accountId].ppc1?.pending;
    const controller=new AbortController(),{signal}=controller;
    const timer=setTimeout(()=>controller.abort(Error('Przekroczono czas zapisu kopii na Google Drive. Ponów kopię.')),150000);
    try{
     if(!pending){
      if(!captureCanonical)throw Error('Brak kolektora PPC1.');
      const sourceRevision=database.revision;
      const value=await captureCanonical({signal});
      signal.throwIfAborted();
      const {packet}=await runIncremental('prepare',{file:value,parent:state.accounts[accountId].ppc1?.last??null},transport,{signal});
      pending={fileId:await transport.reservePointId({signal}),packet,queue,...(sourceRevision!=null?{sourceRevision}:{})};
      signal.throwIfAborted();
      await saveProgress(current=>{(current.accounts[accountId].ppc1??={}).pending=pending;});
     }
     notice='Trening zapisany lokalnie / Zapisywanie kopii na Drive';emit();
     const result=await runIncremental('upload',pending,transport,{signal});
     signal.throwIfAborted();
     await saveProgress(current=>{
      const checkpoint=current.accounts[accountId].ppc1;
      checkpoint.last=result.fileId;delete checkpoint.pending;
      if(current.ppc1Queue===pending.queue){delete current.ppc1Queue;delete current.ppc1Failure;}
      checkpoint.verified=new Date().toISOString();
     });
     notice='Kopia zweryfikowana';emit();return result;
    }finally{clearTimeout(timer);}
   },undefined,()=>{attemptedQueue=state.ppc1Queue;return !!attemptedQueue;}).catch(async error=>{
    failed=true;
    notice='Trening zapisany lokalnie / '+(error.auth?'Wymagane logowanie: ':'Nie udało się zapisać kopii: ')+error.message;emit();
    await mutex(async()=>{
     await refresh();
     if(state.ppc1Queue&&state.ppc1Queue===attemptedQueue)
      await saveProgress(current=>{if(current.ppc1Queue===attemptedQueue)current.ppc1Failure=attemptedQueue;});
    }).catch(()=>{});emit();
   }).finally(()=>{
    incrementalRunning=null;
    if(!closed&&state.ppc1Queue&&transport.authenticated&&online()&&typeof window!=='undefined'){
     retryDelay=failed?Math.min(retryDelay*2,600000):1000;
     retryTimer=setTimeout(()=>void api.retryCanonical(),failed?retryDelay:0);
    }
   });
   return incrementalRunning;
  },
  async canonicalPoints({signal,isCurrent=()=>!signal?.aborted}={}){
   return operation(async()=>{
    try{
     const rows=await transport.listPoints({signal});
     if(isCurrent())notice=rows.length?'Wybierz kopię do podglądu.':'Brak kopii zapasowych na Google Drive.';
     return [...rows].sort((a,b)=>(Date.parse(b.createdTime)||0)-(Date.parse(a.createdTime)||0)||a.id.localeCompare(b.id));
    }catch(error){if(isCurrent())notice='Nie pobrano listy kopii: '+error.message;throw error;}
   },isCurrent);
  },
  async canonicalPoint(fileId,{signal,isCurrent=()=>!signal?.aborted}={}){return operation(async()=>{try{const result=await runIncremental('restore',{fileId},transport,{signal});if(isCurrent())notice='Punkt PPC1 zweryfikowany. Sprawdź podgląd przed przywróceniem.';return result;}catch(e){if(isCurrent())notice='Nie zweryfikowano punktu PPC1: '+e.message;throw e;}},isCurrent);},
  pauseForRestore(){clearTimeout(retryTimer);transport.clear();connectedAccount=null;connectedClient=null;},
  report(error){notice='Błąd: '+error.message;busy=false;emit();},
  close(){closed=true;clearTimeout(retryTimer);transport.clear();},
 };
 return api;
}
