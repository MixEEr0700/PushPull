/** Future-data canonical model. Isolated PPC1 codec, no storage/migration/restore. */
import {portable,freeze,immutableJSON} from './backup-json.mjs';
import {validateCompactSource} from './compact-backup-preview.mjs';
import {writeCompactModel,readCompactModel} from './compact-backup-writer.mjs';
import {openCompactBackup} from './compact-backup-reader.mjs';
import {JSON_OBJECT,writeCanonicalJSON,readCanonicalJSON} from './canonical-json-transport.mjs';
const check=(v,m)=>{if(!v)throw Error('Canonical PPC1: '+m);};
const exact=(v,keys)=>check(v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k)),'fields');
export function validateCanonicalBackup(input,{signal}={}){
 signal?.throwIfAborted();portable(input);if(!immutableJSON(input))input=freeze(intern(input));
 exact(input,['format','version','source','drafts','buffers','preferences','drive']);
 check(input.format==='pushpull-canonical'&&input.version===1,'version');
 exact(input.source,['format','version','data','catalog']);
 validateCompactSource({...input.source,archives:[]},()=>signal?.throwIfAborted());
 check(Array.isArray(input.drafts)&&Array.isArray(input.buffers),'draft collections');
 const ids=new Set();for(const d of input.drafts){exact(d,['key','value']);check(typeof d.key==='string'&&d.key.startsWith('workout-draft:')&&!ids.has(d.key),'draft identity');ids.add(d.key);check(d.value&&typeof d.value==='object'&&!Array.isArray(d.value),'draft value');}
 const keys=new Set();for(const b of input.buffers){exact(b,['key','raw']);check(typeof b.key==='string'&&['pushpull_workout_draft_v1:','pushpull-note-ui-v1:'].some(p=>b.key.startsWith(p))&&typeof b.raw==='string'&&!keys.has(b.key),'buffer identity');keys.add(b.key);}
 check(input.preferences&&typeof input.preferences==='object'&&!Array.isArray(input.preferences),'preferences');
 exact(input.drive,['clientId']);check(typeof input.drive.clientId==='string','Drive config');
 check(input.drafts.length+input.buffers.length<=10000,'collection limit');signal?.throwIfAborted();return input;
}
/** Input is already canonical future data: no implicit destructive conversion
 * from the old complete ledger or arbitrary archive stripping. */
export function createCanonicalBackup({source,drafts,buffers,preferences,drive},{signal}={}){
 signal?.throwIfAborted();const input={format:'pushpull-canonical',version:1,source,drafts,buffers,preferences,drive};
 return validateCanonicalBackup(input,{signal});
}
export async function writeCanonicalBackup(input,options={}){const owned=validateCanonicalBackup(input,options);try{return await writeCanonicalJSON(owned,options);}catch(error){if(error.name==='AbortError'||!/v4: (token|nesting) limit/.test(error.message))throw error;return writeCompactModel(owned,options);}}
export async function readCanonicalBackup(file,options={}){const reader=await openCompactBackup(file,options);const value=reader.manifest.objects.some(o=>o.id===JSON_OBJECT)?await readCanonicalJSON(reader,options):await readCompactModel(file,options);validateCanonicalBackup(value,options);return value;}

// Intern equal subtrees before the transport traversal budget: identical copied
// snapshots become shared immutable values; ordered arrays/keys stay intact.
function intern(root){
 const seen=new WeakMap(),pool=new Map();let next=0;
 function visit(v){
  if(v&&typeof v==='object'&&seen.has(v))return seen.get(v);
  const object=v&&typeof v==='object',array=Array.isArray(v),keys=object?Object.keys(v):[];
  const children=keys.map(k=>visit(v[k]));
  const signature=object?JSON.stringify([array?'array':'object',keys,children.map(c=>c.id)]):JSON.stringify(['value',v]);
  let entry=pool.get(signature);
  if(!entry){entry={id:next++,value:object?(array?children.map(c=>c.value):Object.fromEntries(keys.map((k,i)=>[k,children[i].value]))):v};pool.set(signature,entry);}
  if(object)seen.set(v,entry);return entry;
 }
 return visit(root).value;
}
