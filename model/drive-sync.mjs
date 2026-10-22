/** Full, immutable backup nodes: concurrent devices branch, never overwrite.
 * The official IDB revision IS the durable queue. Draft writes do not advance it.
 */
import {canonical} from './backup-json.mjs';
import {parseModelBackup} from './legacy-model.mjs';
import {readLegacyBackup} from './legacy-backup.mjs';
const uuid=x=>typeof x==='string'&&/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(x);
const sorted=x=>[...x].sort();
const same=(a,b)=>canonical(a)===canonical(b);
const hash=async x=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(x)))),b=>b.toString(16).padStart(2,'0')).join('');
export async function inspectBackup(text){
 const value=JSON.parse(text);
 if(value.version===3)return parseModelBackup(text);
 const legacy=readLegacyBackup(text);return legacy.original?.data?legacy.original:{data:legacy.data};
}
export async function makeNode(backup,parents){
 await inspectBackup(backup);
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
export function graph(files){
 const nodes=new Map();
 for(const f of files){
  const p=f.appProperties;if(p?.pushpull!=='sync-v1')throw Error('Nieznany protokół kopii Drive.');
  const keys=Object.keys(p).filter(k=>/^p\d+$/.test(k)).sort((a,b)=>Number(a.slice(1))-Number(b.slice(1)));
  const parents=keys.flatMap(k=>p[k].split(','));
  if(!uuid(p.node)||!/^[0-9a-f]{64}$/.test(p.digest??'')||parents.some(x=>!uuid(x)||x===p.node)||new Set(parents).size!==parents.length)throw Error('Nieprawidłowe powiązania kopii Drive.');
  const row={id:p.node,digest:p.digest,parents:sorted(parents),fileId:f.id,createdAt:f.createdTime};
  const old=nodes.get(row.id);
  if(old&&(old.digest!==row.digest||!same(old.parents,row.parents)))throw Error('Konflikt identyfikatora kopii Drive. Zachowano dane.');
  nodes.set(row.id,row); // An ambiguous POST retry may leave identical files, not duplicate results.
 }
 const visited=new Set(),visiting=new Set();
 function visit(id){if(visited.has(id))return;if(visiting.has(id)||!nodes.has(id))throw Error('Niekompletny lub cykliczny łańcuch kopii Drive.');visiting.add(id);nodes.get(id).parents.forEach(visit);visiting.delete(id);visited.add(id);}
 nodes.forEach(n=>visit(n.id));
 const parents=new Set([...nodes.values()].flatMap(n=>n.parents));
 return {nodes,heads:sorted([...nodes.keys()].filter(id=>!parents.has(id)))};
}
export async function readNode(transport,row){
 const node=JSON.parse(await transport.read(row.fileId));
 const {digest,...body}=node;
 if(node.format!=='pushpull-drive-backup'||node.version!==1||node.id!==row.id||!same(node.parents,row.parents)||digest!==row.digest||await hash(body)!==digest)throw Error('Kopia Drive nie przeszła weryfikacji integralności.');
 await inspectBackup(node.backup);return node;
}
const initial=()=>({clientId:'',enabled:false,selected:null,accounts:{}});
const account=()=>({base:[],ackRevision:0,outbox:null,lastSuccess:null,nextAttempt:0,failures:0});
export async function openDriveSync({database,transport,online=()=>navigator.onLine,now=Date.now,auto=true,withLock=fn=>globalThis.navigator?.locks?navigator.locks.request('pushpull-drive-sync',fn):fn()}={}){
 let state=await database.readDriveState()??initial(),timer=null,serial=Promise.resolve(),changed=()=>{},notice='',copies=[],closed=false,connectedAccount=null;
 const emit=()=>changed();
 const a=()=>state.selected?state.accounts[state.selected]:null;
 async function refresh(){state=await database.readDriveState()??initial();return state;}
 async function save(){const saved=await database.writeDriveState(state,state.token??null);state.token=saved.token;state.key=saved.key;emit();}
 function mutex(fn){
  const run=()=>withLock(fn);
  const result=serial.then(run);serial=result.catch(()=>{});return result;
 }
 function schedule(delay=0){if(!auto||closed)return;clearTimeout(timer);timer=setTimeout(()=>{void api.retry().catch(error=>api.report(error));},delay);}
 async function cloudGraph(){const g=graph(await transport.list());copies=[...g.nodes.values()].sort((a,b)=>(b.createdAt??'').localeCompare(a.createdAt??''));return g;}
 function requireConnection(){if(!state.enabled||!transport.authenticated||connectedAccount!==state.selected)throw Error('Połącz Google, aby odczytać kopie.');}
 async function work(){
  await refresh();const current=a();if(!state.enabled||!current||database.error)return;
  if(!online()||!transport.authenticated||connectedAccount!==state.selected){notice=!online()?'Offline — ponowimy po odzyskaniu połączenia.':'Połącz Google, aby wznowić synchronizację.';emit();return;}
  if(now()<current.nextAttempt){schedule(current.nextAttempt-now());return;}
  try{
   let g=await cloudGraph();
   // Finish the exact durable operation before considering a newer local revision.
   if(current.outbox){
    const pending=current.outbox,existing=g.nodes.get(pending.node.id);
    if(!existing&&!same(g.heads,current.base)){notice='Konflikt kopii. Wybierz wersję do odzyskania lub świadomie zachowaj lokalną.';emit();return;}
    if(!existing)await transport.create(JSON.stringify(pending.node),properties(pending.node));
    g=await cloudGraph();const stored=g.nodes.get(pending.node.id);
    if(!stored)throw Error('Google nie potwierdził obecności kopii. Ponowimy zapis.');
    const verified=await readNode(transport,stored);
    if(!same(verified,pending.node))throw Error('Google zwrócił inną zawartość kopii.');
    current.base=[verified.id];current.ackRevision=pending.revision;current.outbox=null;current.lastSuccess=new Date(now()).toISOString();current.failures=0;current.nextAttempt=0;notice='';await save();
   }
   if(!same(g.heads,current.base)){notice='Konflikt kopii. Wybierz wersję do odzyskania lub świadomie zachowaj lokalną.';emit();return;}
   if(current.ackRevision===database.revision){notice='';emit();return;}
   const revision=database.revision;
   const backup=database.model?await database.exportModelBackup():JSON.stringify(database.export());
   if(database.revision!==revision||database.error){schedule();return;}
   const node=await makeNode(backup,g.heads);
   if(database.revision!==revision||database.error){schedule();return;}
   current.outbox={node,revision};await save(); // Strict IDB completion BEFORE the POST.
   schedule();
  }catch(error){
   notice=error.message;current.failures++;current.nextAttempt=now()+Math.min(600000,10000*2**Math.min(current.failures,6));
   try{await save();}catch{notice+=' Nie zapisano stanu synchronizacji; lokalna historia nadal oczekuje.';}
   if(!error.auth)schedule(current.nextAttempt-now());emit();
  }
 }
 const api={
  set onchange(fn){changed=fn;},
  get config(){return {clientId:state.clientId,enabled:state.enabled,selected:state.selected,label:a()?.label??''};},
  get copies(){return structuredClone(copies);},
  get status(){
   const current=a(),pending=state.enabled&&(!current||current.ackRevision!==database.revision||!!current.outbox);
   const error=notice.startsWith('Błąd:')||notice.startsWith('Konflikt')||!!current?.failures;
   const label=error?'Błąd':pending?'Oczekuje na synchronizację':current?.lastSuccess?'Zsynchronizowano':'Zapisano lokalnie';
   return {label,detail:notice,lastSuccess:current?.lastSuccess??null,pending,connected:transport.authenticated&&connectedAccount===state.selected};
  },
  localChanged(){notice='';emit();schedule();},
  async configure(clientId){await mutex(async()=>{await refresh();state.clientId=clientId.trim();state.enabled=true;await save();});transport.clear();connectedAccount=null;void transport.load?.().catch(()=>{});},
  async connect(){
   const clientId=state.clientId,identity=await transport.connect(clientId);
   await mutex(async()=>{await refresh();if(state.clientId!==clientId){transport.clear();throw Error('Konfiguracja Google zmieniła się. Połącz ponownie.');}if(state.selected&&state.selected!==identity.id){transport.clear();throw Error('Wybrano inne konto Google. Odłącz poprzednie konto przed zmianą. Jego kolejka pozostanie zachowana.');}
    state.selected=identity.id;state.enabled=true;state.accounts[identity.id]??=account();a().label=identity.label;a().nextAttempt=0;notice='';await save();connectedAccount=identity.id;});schedule();emit();
  },
  async disconnect(){transport.clear();connectedAccount=null;await mutex(async()=>{await refresh();state.enabled=false;state.selected=null;await save();});clearTimeout(timer);notice='Rozłączono Google. Kopie i lokalne kolejki kont pozostają zachowane.';copies=[];emit();},
  retry(){return mutex(work);},
  async retryNow(){await mutex(async()=>{await refresh();if(a()){a().nextAttempt=0;await save();}});await api.retry();},
  async listCopies(){return mutex(async()=>{await refresh();requireConnection();const g=await cloudGraph();emit();return g.heads;});},
  async preview(id){return mutex(async()=>{await refresh();requireConnection();const g=await cloudGraph(),row=g.nodes.get(id);if(!row)throw Error('Kopia nie jest już dostępna.');const node=await readNode(transport,row),parsed=await inspectBackup(node.backup);
   return {node,parsed,heads:g.heads,account:state.selected,localRevision:database.revision};});},
  async restore(ticket,apply){return mutex(async()=>{
   await refresh();requireConnection();if(state.selected!==ticket.account||database.revision!==ticket.localRevision)throw Error('Konto lub lokalne dane zmieniły się od podglądu. Otwórz podgląd ponownie.');
   if((await database.readDrafts()).length)throw Error('Najpierw zapisz lub zabezpiecz i świadomie odrzuć lokalne szkice. Nie zastąpiono historii.');
   const g=await cloudGraph();if(!same(g.heads,ticket.heads))throw Error('Kopie Drive zmieniły się od podglądu. Otwórz podgląd ponownie.');
   const node=await readNode(transport,g.nodes.get(ticket.node.id));if(!same(node,ticket.node))throw Error('Kopia zmieniła się od podglądu.');
   await apply(node.backup); // Existing transactional import preserves a local preimage.
   a().base=g.heads;a().outbox=null;a().ackRevision=0;a().nextAttempt=0;notice='Zapisano lokalnie. Odtworzoną wersję zapiszemy jako nową kopię.';await save();schedule();emit();
  });},
  async keepLocal(expectedHeads){return mutex(async()=>{
   await refresh();requireConnection();const g=await cloudGraph();if(!same(g.heads,sorted(expectedHeads)))throw Error('Drive zmienił się. Odśwież listę kopii.');
   // Explicit conflict resolution retains all previous immutable branches.
   a().base=g.heads;a().outbox=null;a().ackRevision=0;a().nextAttempt=0;notice='';await save();schedule();
  });},
  report(error){notice='Błąd: '+error.message;emit();},
  close(){closed=true;clearTimeout(timer);transport.clear();},
 };
 if(state.clientId&&state.enabled)void transport.load?.().catch(()=>{});
 schedule();return api;
}
