/** Foreground-only reminder; never infers cloud freshness from a missing token. */
export const REMINDER_KEY='pushpull-drive-reminder-shown-v1';
export const DAY=24*60*60*1000;
export function needsReminder(s){return !!(s?.automatic&&s.pending&&s.backupFailed&&!s.busy);}
export function reminderDue(last,now){return last===null||Number.isFinite(Number(last))&&now-Number(last)>=DAY;}
export function openDriveReminder({drive,safe,storage=localStorage,now=Date.now,doc=document,lock=fn=>navigator.locks?navigator.locks.request('pushpull-drive-reminder',fn):Promise.resolve().then(fn)}){
 let dialog=null,checking=false,running=false;
 const dismiss=()=>{dialog?.close();dialog?.remove();dialog=null;};
 async function refresh(){
  if(!needsReminder(drive.status)||!safe()||doc.visibilityState!=='visible'){dismiss();return;}
  if(dialog||checking)return;checking=true;
  try{await lock(()=>{
   if(!needsReminder(drive.status)||!safe()||doc.visibilityState!=='visible')return;
   const time=now();if(!reminderDue(storage.getItem(REMINDER_KEY),time))return;
   // Fail closed if the rate limit cannot survive a restart.
   storage.setItem(REMINDER_KEY,String(time));
   dialog=doc.createElement('dialog');dialog.className='card';dialog.style.cssText='position:relative;margin:12px auto;max-width:min(90vw,420px);background:#101010;color:#eee;border:1px solid #39FF74;border-radius:12px';
   dialog.setAttribute('aria-labelledby','drive-reminder-title');dialog.dataset.driveReminder='';
   dialog.innerHTML='<h2 id="drive-reminder-title">Kopia Google Drive nieaktualna</h2><p>Treningi są zapisane na tym urządzeniu, ale najnowsza kopia na Google Drive nie została wykonana.</p><p role="status" data-reminder-status></p><div class="row"><button class="btn primary" data-reminder-connect>Połącz z Google</button><button class="btn" data-reminder-later>Później</button></div>';
   const connect=dialog.querySelector('[data-reminder-connect]');
   if(drive.config.connected)connect.textContent='Ponów kopię';
   dialog.querySelector('[data-reminder-later]').onclick=dismiss;
   dialog.oncancel=e=>{e.preventDefault();dismiss();};
   connect.onclick=()=>{
    if(running)return;running=true;connect.disabled=true;
    // Invoke existing authorization synchronously from the user's click.
    const attempt=drive.config.connected?Promise.resolve():drive.connect();
    Promise.resolve(attempt).then(()=>drive.retryCanonical()).then(()=>{
     if(!drive.status.pending)dismiss();else if(dialog)dialog.querySelector('[data-reminder-status]').textContent=drive.status.detail;
    }).catch(error=>{if(dialog)dialog.querySelector('[data-reminder-status]').textContent=error.message;}).finally(()=>{running=false;if(dialog)connect.disabled=false;});
   };
   doc.body.prepend(dialog);dialog.show();
  });}catch{dismiss();}finally{checking=false;}
 }
 return {refresh};
}
