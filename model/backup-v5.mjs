/** Isolated v5 envelope. No storage, restore, DOM or network capability. */
import {decodeBackup as decodeV4,V4_LIMITS,boundedBackupJson,backupLimits} from './backup-v4.mjs';
import {exportBackupV4} from './backup-v4-export.mjs';
import {canonical,freeze,portable,record,requireThat as check} from './backup-json.mjs';
const utf8=new TextEncoder(),CHUNK=128*1024;
const sha=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',utf8.encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
const abort=signal=>{if(signal?.aborted)throw new DOMException('Backup cancelled','AbortError');};
const exact=(x,keys)=>check(record(x)&&Object.keys(x).length===keys.length&&keys.every(k=>Object.hasOwn(x,k)),'v5: fields');
const seal=d=>canonical({...d,integrity:{algorithm:'SHA-256'}});
export async function decodeBackup(text,{limits:overrides={},signal}={}){
 const limits=backupLimits(overrides);abort(signal);
 const d=boundedBackupJson(text,limits,limits.fileBytes);
 if(d?.version!==5)return decodeV4(text,{limits:overrides,signal});
 exact(d,['format','version','payload','archives','integrity']);
 check(d.format==='pushpull-backup'&&d.payload?.version===4&&Array.isArray(d.archives)&&d.archives.length<=limits.archives,'v5: header');
 exact(d.integrity,['algorithm','digest']);
 check(d.integrity.algorithm==='SHA-256'&&await sha(seal(d))===d.integrity.digest,'v5: manifest checksum');
 // Bound logical expansion even when many references share one compressed blob.
 const rows=d.payload.archives;check(Array.isArray(rows)&&rows.length<=limits.blobs,'v5: fragment count');
 const descriptors=new Map(d.payload.blobs.map(b=>[b.id,b]));
 let total=descriptors.get(d.payload.live.blobId)?.decodedBytes;
 check(Number.isSafeInteger(total)&&total>=0,'v5: live size');
 let ordinal=0;
 for(const a of d.archives){
  exact(a,['metadata','parts']);check(record(a.metadata)&&!Object.hasOwn(a.metadata,'raw')&&(a.parts===null||Array.isArray(a.parts)&&a.parts.length>0),'v5: archive');
  if(a.parts)for(const index of a.parts){
   abort(signal);check(index===ordinal++&&index<rows.length,'v5: ordered fragment reference');
   const b=descriptors.get(rows[index].blobId);
   check(b&&Number.isSafeInteger(b.decodedBytes)&&b.decodedBytes>=0,'v5: fragment descriptor');
   total+=b.decodedBytes;check(total<=limits.totalDecodedBytes,'v5: logical expansion limit');
  }
 }
 check(ordinal===rows.length,'v5: unused fragment');
 const stage=await decodeV4(JSON.stringify(d.payload),{limits:overrides,signal});
 const ids=new Set(),archives=[];
 for(const a of d.archives){
  abort(signal);const m=a.metadata;
  check(typeof m.id==='string'&&m.id.length&&!ids.has(m.id)&&typeof m.kind==='string'&&typeof m.createdAt==='string'&&Number.isFinite(Date.parse(m.createdAt)),'v5: archive metadata');ids.add(m.id);
  const raw=a.parts===null?null:a.parts.map(i=>{const value=stage.archives[i].raw;check(typeof value==='string','v5: fragment string');return value;}).join('');
  archives.push({...m,raw});
 }
 abort(signal);return freeze({formatVersion:5,createdAt:stage.createdAt,metadata:stage.metadata,live:stage.live,archives});
}
export async function exportBackupV5(snapshot,{createdAt,metadata,limits:overrides={},signal}={}){
 const limits=backupLimits(overrides);abort(signal);portable(snapshot);
 check(snapshot?.version===2&&snapshot.format==='pushpull-backup'&&Array.isArray(snapshot.archives)&&snapshot.archives.length<=limits.archives,'v5: complete v2 snapshot required');
 const archives=[],fragments=[],expected=[];let logical=0;
 for(const row of snapshot.archives){
  const {raw,...info}=row;check(raw===null||typeof raw==='string','v5: raw');
  const parts=raw===null?null:[];
  if(parts)for(let offset=0;offset<raw.length||offset===0;offset+=CHUNK){
   abort(signal);check(fragments.length<limits.blobs,'v5: fragment count');
   const value=raw.slice(offset,offset+CHUNK);
   logical+=utf8.encode(JSON.stringify(value)).length;check(logical<=limits.totalDecodedBytes,'v5: logical expansion limit');
   parts.push(fragments.length);fragments.push({id:'fragment-'+fragments.length,kind:'fragment',createdAt,raw:value});
  }
  const infoCopy=structuredClone(info);archives.push({metadata:infoCopy,parts});expected.push({...infoCopy,raw});
 }
 // B1 snapshots mutable live synchronously; archive strings are immutable.
 const inner=await exportBackupV4({...snapshot,archives:fragments},{createdAt,metadata,limits:overrides,signal});
 const payload=JSON.parse(inner.text),document={format:'pushpull-backup',version:5,payload,archives,integrity:{algorithm:'SHA-256'}};
 document.integrity.digest=await sha(seal(document));abort(signal);
 const text=JSON.stringify(document);check(utf8.encode(text).length<=limits.fileBytes,'v5: file size limit');
 const stage=await decodeBackup(text,{limits:overrides,signal});
 check(stage.archives.length===expected.length,'v5: self verification');
 for(let i=0;i<archives.length;i++)check(stage.archives[i].raw===expected[i].raw&&canonical(archives[i].metadata)===canonical((({raw,...m})=>m)(stage.archives[i])),'v5: self verification');
 return {text,diagnostics:Object.freeze({formatVersion:5,fileBytes:utf8.encode(text).length,archiveRecords:archives.length,fragments:fragments.length,logicalArchiveBytes:logical})};
}
