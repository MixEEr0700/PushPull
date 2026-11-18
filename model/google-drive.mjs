/** Browser-only Google Identity Services + append-only appDataFolder transport.
 * Access tokens stay in memory; no client secret, refresh token or user backend.
 */
export const DRIVE_SCOPE='https://www.googleapis.com/auth/drive.appdata';
const API='https://www.googleapis.com/drive/v3';
let sdk;
export function loadGoogle(){
 if(globalThis.google?.accounts?.oauth2)return Promise.resolve();
 if(!sdk)sdk=new Promise((resolve,reject)=>{
  const script=document.createElement('script');script.src='https://accounts.google.com/gsi/client';script.async=true;
  const timer=setTimeout(()=>{script.remove();sdk=null;reject(Error('Nie udało się załadować Google. Połącz ponownie.'));},15000);
  script.onload=()=>{clearTimeout(timer);resolve();};script.onerror=()=>{clearTimeout(timer);sdk=null;reject(Error('Google niedostępne. Dane pozostają lokalnie.'));};document.head.append(script);
 });
 return sdk;
}
export function createGoogleDrive({fetcher=globalThis.fetch,now=Date.now,timeoutMs=30000,oauthTimeoutMs=90000}={}){
 let token=null,expires=0,connecting=false,generation=0;
 const api={
  get authenticated(){return !!token&&now()<expires;},
  clear(){generation++;token=null;expires=0;},
  load:loadGoogle,
  async connect(clientId){
   if(!/^\d+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId))throw Error('Podaj identyfikator klienta OAuth aplikacji internetowej.');
   if(connecting)throw Error('Połączenie z Google jest już w toku.');
   connecting=true;api.clear();const attempt=generation;
   try{
    await loadGoogle();
    await new Promise((resolve,reject)=>{
     let settled=false;
     const finish=(error)=>{if(settled)return;settled=true;clearTimeout(timer);error?reject(error):resolve();};
     const timer=setTimeout(()=>finish(Error('Przekroczono czas logowania Google. Połącz ponownie.')),oauthTimeoutMs);
     try{
      const client=google.accounts.oauth2.initTokenClient({client_id:clientId,scope:DRIVE_SCOPE,include_granted_scopes:false,
       callback:r=>{if(settled)return;if(attempt!==generation||r.error||!r.access_token||!google.accounts.oauth2.hasGrantedAllScopes(r,DRIVE_SCOPE)){finish(Error('Nie potwierdzono zgody Google na kopie aplikacji.'));return;}token=r.access_token;expires=now()+Number(r.expires_in)*1000-30000;finish();},
       error_callback:()=>finish(Error('Okno Google zamknięte lub zablokowane. Kliknij Połącz ponownie.'))});
      client.requestAccessToken({prompt:''});
     }catch(error){finish(error);}
    });
    const result=await request(API+'/about?fields=user(permissionId,displayName,emailAddress)');
    if(attempt!==generation||!/^[A-Za-z0-9_-]+$/.test(result.user?.permissionId??''))throw Error('Google nie potwierdził tożsamości konta.');
    return {id:result.user.permissionId,label:result.user.emailAddress||result.user.displayName||'Google Drive'};
   }catch(error){if(attempt===generation)api.clear();throw error;}
   finally{connecting=false;}
  },
  async reservePointId({signal}={}){const r=await request(API+'/files/generateIds?count=1&space=appDataFolder&type=files',{signal});if(!r.ids?.[0])throw Error('Brak ID kopii Drive.');return r.ids[0];},
  async listPoints(){
   const files=[];let pageToken;
   do{const p=new URLSearchParams({spaces:'appDataFolder',q:"trashed = false and appProperties has { key='pushpull' and value='ppc1-incremental-v1' }",fields:'nextPageToken,files(id,appProperties,createdTime)',pageSize:'1000'});if(pageToken)p.set('pageToken',pageToken);const r=await request(API+'/files?'+p);files.push(...(r.files??[]));pageToken=r.nextPageToken;if(files.length>50000)throw Error('Limit katalogu Drive.');}while(pageToken);return files;
  },
  async createPoint(id,text,digest,{signal}={}){
   const boundary='pushpull_'+crypto.randomUUID(),metadata={id,name:'pushpull-'+id+'.json',mimeType:'application/json',parents:['appDataFolder'],appProperties:{pushpull:'ppc1-incremental-v1',digest}};
   const body='--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+JSON.stringify(metadata)+'\r\n--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+text+'\r\n--'+boundary+'--';
   return request('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id',{method:'POST',headers:{'Content-Type':'multipart/related; boundary='+boundary},body,signal});
  },
  async list(){
   const files=[];let pageToken;
   do{
    const params=new URLSearchParams({spaces:'appDataFolder',q:"trashed = false and appProperties has { key='pushpull' and value='sync-v1' }",pageSize:'1000',fields:'nextPageToken,files(id,appProperties,createdTime)'});
    if(pageToken)params.set('pageToken',pageToken);
    const page=await request(API+'/files?'+params);files.push(...(page.files??[]));pageToken=page.nextPageToken;
   }while(pageToken);
   return files;
  },
  readPoint(fileId,{signal}={}){return request(API+'/files/'+encodeURIComponent(fileId)+'?alt=media',{signal},128*1024*1024);},
  read(fileId){return request(API+'/files/'+encodeURIComponent(fileId)+'?alt=media',{},true);},
  async create(text,properties){
   const boundary='pushpull_'+crypto.randomUUID();
   const metadata={name:'pushpull-'+properties.node+'.json',mimeType:'application/json',parents:['appDataFolder'],appProperties:properties};
   const body='--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+JSON.stringify(metadata)+'\r\n--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+text+'\r\n--'+boundary+'--';
   return request('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id',{method:'POST',headers:{'Content-Type':'multipart/related; boundary='+boundary},body});
  }
 };
 async function request(url,options={},raw=false){
  if(!api.authenticated)throw Object.assign(Error('Połącz Google, aby wykonać kopię lub ją pobrać.'),{auth:true});
  const usedToken=token,controller=new AbortController();
  const signal=options.signal?AbortSignal.any([options.signal,controller.signal]):controller.signal;
  signal.throwIfAborted();
  const timer=setTimeout(()=>controller.abort(Error('Przekroczono czas odpowiedzi Google Drive. Ponów kopię.')),timeoutMs);
  let abort;
  const cancelled=new Promise((_,reject)=>{abort=()=>reject(signal.reason);signal.addEventListener('abort',abort,{once:true});});
  try{return await Promise.race([cancelled,readResponse()]);}
  finally{clearTimeout(timer);signal.removeEventListener('abort',abort);}
  async function readResponse(){
   const response=await fetcher(url,{...options,headers:{...options.headers,Authorization:'Bearer '+usedToken},cache:'no-store',credentials:'omit',signal});
   signal.throwIfAborted();
   if(!response.ok){if(response.status===401&&token===usedToken)api.clear();throw Object.assign(Error(response.status===401?'Autoryzacja Google wygasła. Połącz ponownie.':'Błąd Google Drive ('+response.status+'). Dane pozostają lokalnie.'),{auth:response.status===401,status:response.status});}
   if(typeof raw==='number'){
    const reader=response.body.getReader(),chunks=[];let size=0;
    const cancel=()=>void reader.cancel().catch(()=>{});
    signal.addEventListener('abort',cancel,{once:true});
    try{
     while(true){const {done,value}=await reader.read();signal.throwIfAborted();if(done)break;size+=value.byteLength;if(size>raw)throw Error('Limit rozmiaru pliku Drive.');chunks.push(value);}
     const bytes=new Uint8Array(size);let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.byteLength;}
     return new TextDecoder('utf-8',{fatal:true}).decode(bytes);
    }catch(error){if(!signal.aborted)cancel();throw error;}
    finally{signal.removeEventListener('abort',cancel);}
   }
   return raw?response.text():response.json();
  }
 }
 return api;
}
