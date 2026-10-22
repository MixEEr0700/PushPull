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
export function createGoogleDrive({fetcher=globalThis.fetch,now=Date.now}={}){
 let token=null,expires=0;
 const api={
  get authenticated(){return !!token&&now()<expires;},
  clear(){token=null;expires=0;},
  load:loadGoogle,
  async connect(clientId){
   if(!/^\d+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId))throw Error('Podaj identyfikator klienta OAuth aplikacji internetowej.');
   await loadGoogle();
   await new Promise((resolve,reject)=>{
    const client=google.accounts.oauth2.initTokenClient({client_id:clientId,scope:DRIVE_SCOPE,include_granted_scopes:false,
     callback:r=>{if(r.error||!r.access_token||!google.accounts.oauth2.hasGrantedAllScopes(r,DRIVE_SCOPE)){reject(Error('Brak zgody Google na kopie aplikacji.'));return;}token=r.access_token;expires=now()+Number(r.expires_in)*1000-30000;resolve();},
     error_callback:()=>reject(Error('Okno Google zamknięte lub zablokowane. Kliknij Połącz ponownie.'))});
    client.requestAccessToken({prompt:''});
   });
   const result=await request(API+'/about?fields=user(permissionId,displayName,emailAddress)');
   if(!/^[A-Za-z0-9_-]+$/.test(result.user?.permissionId??'')){api.clear();throw Error('Google nie potwierdził tożsamości konta.');}
   return {id:result.user.permissionId,label:result.user.emailAddress||result.user.displayName||'Google Drive'};
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
  read(fileId){return request(API+'/files/'+encodeURIComponent(fileId)+'?alt=media',{},true);},
  async create(text,properties){
   const boundary='pushpull_'+crypto.randomUUID();
   const metadata={name:'pushpull-'+properties.node+'.json',mimeType:'application/json',parents:['appDataFolder'],appProperties:properties};
   const body='--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+JSON.stringify(metadata)+'\r\n--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+text+'\r\n--'+boundary+'--';
   return request('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id',{method:'POST',headers:{'Content-Type':'multipart/related; boundary='+boundary},body});
  }
 };
 async function request(url,options={},raw=false){
  if(!api.authenticated)throw Object.assign(Error('Połącz Google, aby wznowić synchronizację.'),{auth:true});
  const usedToken=token;
  const response=await fetcher(url,{...options,headers:{...options.headers,Authorization:'Bearer '+usedToken},cache:'no-store',credentials:'omit',signal:AbortSignal.timeout(30000)});
  if(!response.ok){if(response.status===401&&token===usedToken)api.clear();throw Object.assign(Error(response.status===401?'Autoryzacja Google wygasła. Połącz ponownie.':'Błąd Google Drive ('+response.status+'). Dane pozostają lokalnie.'),{auth:response.status===401,status:response.status});}
  return raw?response.text():response.json();
 }
 return api;
}
