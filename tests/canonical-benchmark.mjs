// Manual synthetic evidence, not a timing assertion or a device benchmark.
import {readFileSync} from 'node:fs';import {canonicalFixture} from './canonical-fixture.mjs';
import {createCanonicalBackup,writeCanonicalBackup,readCanonicalBackup} from '../model/canonical-backup.mjs';
import assert from 'node:assert/strict';
const old=JSON.parse(readFileSync('tests/fixtures/v1.json'));
for(const n of [0,4,40,400]){const c=createCanonicalBackup(canonicalFixture(old,n)),jsonBytes=Buffer.byteLength(JSON.stringify(c)),start=performance.now(),file=await writeCanonicalBackup(c),written=performance.now(),out=await readCanonicalBackup(file);assert.deepStrictEqual(out,c);console.log(JSON.stringify({sessions:n,jsonBytes,ppc1Bytes:file.size,writeMs:+(written-start).toFixed(2),readMs:+(performance.now()-written).toFixed(2)}));}
