import {readFileSync} from 'node:fs';import assert from 'node:assert/strict';
import {canonicalFixture} from './canonical-fixture.mjs';import {createCanonicalBackup,writeCanonicalBackup,readCanonicalBackup} from '../model/canonical-backup.mjs';import {writeCompactModel,readCompactModel} from '../model/compact-backup-writer.mjs';
const old=JSON.parse(readFileSync('tests/fixtures/v1.json'));
for(const n of [0,4,40,400,4000])for(const snapshots of ['repeated','unique']){
 const input=canonicalFixture(old,n);input.preferences.snapshots=Array.from({length:n},(_,i)=>({instructions:'Synthetic training instructions '.repeat(20),version:snapshots==='unique'?i:1,load:snapshots==='unique'?i/4:20}));
 const at=performance.now(),c=createCanonicalBackup(input),prepareMs=performance.now()-at,out={n,snapshots,prepareMs:+prepareMs.toFixed(2)};
 for(const variant of ['json','gzip','graph','jsonPPC1']){try{
  const start=performance.now();let file;if(variant==='json')file=new Blob([JSON.stringify(c)]);else if(variant==='gzip')file=await new Response(new Blob([JSON.stringify(c)]).stream().pipeThrough(new CompressionStream('gzip'))).blob();else file=await (variant==='graph'?writeCompactModel:writeCanonicalBackup)(c);
  const writeMs=performance.now()-start,readStart=performance.now();let restored;if(variant==='json')restored=JSON.parse(await file.text());else if(variant==='gzip')restored=JSON.parse(await new Response(file.stream().pipeThrough(new DecompressionStream('gzip'))).text());else restored=await (variant==='graph'?readCompactModel:readCanonicalBackup)(file);assert.deepStrictEqual(restored,c);
  const stats={bytes:file.size,writeMs:+writeMs.toFixed(2),readMs:+(performance.now()-readStart).toFixed(2)};if(variant==='graph'||variant==='jsonPPC1'){const h=new DataView(await file.slice(0,40).arrayBuffer()),length=h.getUint32(4),m=JSON.parse(await file.slice(40,40+length).text());Object.assign(stats,{header:40,manifest:length,objects:m.objects.length,chunks:m.chunks.length,payload:file.size-40-length});}out[variant]=stats;
 }catch(e){out[variant]={refused:e.message};}}console.log(JSON.stringify(out));
}
