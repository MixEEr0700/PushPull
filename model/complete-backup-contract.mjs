/** Isolated persistent-state contract. No database/localStorage access or restore. */
import {STORES,materialize,equalJSON} from './journal-protocol.mjs';
import {validateCompactSource} from './compact-backup-preview.mjs';
import {portable,freeze} from './backup-json.mjs';
import {writeCompactModel,readCompactModel} from './compact-backup-writer.mjs';
export const COMPLETE_STORES=Object.freeze(['meta','plans','planVersions','exercises','sessions','entries','sets','notes','changes','backups',...STORES]);
export const LOCAL_SOURCES=Object.freeze(['pushpull_skeleton_v1','pushpull_indexeddb_owner','pushpull_skeleton_v1_backup_','pushpull_workout_draft_v1:','pushpull-note-ui-v1:']);
const check=(v,m)=>{if(!v)throw Error('PPC1 contract: '+m);};
const exact=(v,keys)=>check(v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k)),'sections');
const abort=signal=>{if(signal?.aborted)throw new DOMException('Cancelled','AbortError');};
export async function validateCompleteContract(input,{signal}={}){
 abort(signal);portable(input);
 exact(input,['format','version','capture','source','indexedDB','localStorage']);check(input.format==='pushpull-complete-contract'&&input.version===1,'version');
 exact(input.capture,['before','after','scope','otherTabs','counts','localKeys']);
 check(typeof input.capture.before==='string'&&input.capture.before.length>0&&input.capture.before.length<=256&&input.capture.before===input.capture.after,'unstable capture');
 check(input.capture.scope==='supplied-persistent-snapshot'&&input.capture.otherTabs==='unknown','coverage claim');
 exact(input.indexedDB,['name','version','stores']);check(input.indexedDB.name==='pushpull'&&input.indexedDB.version===2,'database');exact(input.indexedDB.stores,COMPLETE_STORES);
 exact(input.capture.counts,COMPLETE_STORES);check(Array.isArray(input.capture.localKeys),'local inventory');let records=0;
 for(const name of COMPLETE_STORES){const rows=input.indexedDB.stores[name];check(Array.isArray(rows)&&input.capture.counts[name]===rows.length,'store inventory');const ids=new Set();for(const row of rows){check(row&&typeof row==='object'&&!Array.isArray(row),'record');const id=row[name==='meta'?'key':'id'];check(typeof id==='string'&&id.length>0&&!ids.has(id),'record identity');ids.add(id);check(++records<=10000,'record limit');}}
 check(Array.isArray(input.localStorage),'localStorage');const keys=new Set();for(const row of input.localStorage){exact(row,['key','raw']);check(typeof row.key==='string'&&typeof row.raw==='string'&&!keys.has(row.key),'local key');check(LOCAL_SOURCES.some(k=>k.endsWith(':')||k.endsWith('_')?row.key.startsWith(k):row.key===k),'unclassified local key');keys.add(row.key);check(++records<=10000,'record limit');}
 check(input.capture.localKeys.length===keys.size&&new Set(input.capture.localKeys).size===keys.size&&input.capture.localKeys.every(k=>keys.has(k)),'local inventory');
 abort(signal);validateCompactSource(input.source,()=>abort(signal));
 const ledger=input.indexedDB.stores,state=ledger.journalState.find(r=>r.id==='active');
 const marker=ledger.meta.find(r=>r.key==='journal-protocol-v2');check(marker&&marker.protocol===2&&marker.status==='active'&&marker.epoch===state?.epoch,'protocol marker');check(state&&input.capture.before===state.root,'capture root');
 const restored=await materialize({state,records:Object.fromEntries(STORES.map(k=>[k,ledger[k]]))},{signal});
 check(equalJSON(restored,input.source),'source/ledger mismatch');abort(signal);return input;
}
export async function writeCompleteContract(input,options={}){
 // Snapshot before awaits. All supplied records/extensions remain intact.
 abort(options.signal);portable(input);const snapshot=structuredClone(input);freeze(snapshot);await validateCompleteContract(snapshot,options);
 return writeCompactModel(snapshot,options);
}
export async function readCompleteContract(file,options={}){const result=await readCompactModel(file,options);await validateCompleteContract(result,options);return result;}
export function contractCoverage(){return freeze({stores:COMPLETE_STORES.map(store=>({store,section:'indexedDB.stores.'+store,capture:'caller-supplied',ppc1:'isolated-roundtrip',productionRestore:'not-integrated',readback:'synthetic-only'})),localStorage:LOCAL_SOURCES.map(key=>({key,section:'localStorage',capture:'caller-supplied',ppc1:'isolated-roundtrip',productionRestore:'not-integrated',readback:'synthetic-only'})),productionComplete:false});}
