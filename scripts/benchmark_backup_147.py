import sys,json
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[1]/'tests'))
from test_browser import BrowserHarness
from pathlib import Path
class Probe(BrowserHarness):
 def runTest(self):
  self.page.wait_for_selector('[data-act=start]')
  for n in (40,400):
   self.page.evaluate("""async n=>{const {canonicalFixture}=await import('./tests/canonical-fixture.mjs'),p=await import('./model/journal-protocol.mjs'),{buildRuntime}=await import('./model/journal-runtime-index.mjs');const input=canonicalFixture(await(await fetch('./tests/fixtures/v1.json')).json(),n),source={...input.source,archives:[]},bundle=await p.createProtocol(source),rt=await buildRuntime(source,{sourceRoot:bundle.state.indexRoot});const records={...bundle.records,journalObjects:[...new Map([...bundle.records.journalObjects,...rt.objects].map(r=>[r.id,r])).values()],journalIndex:[...new Map([...bundle.records.journalIndex,...rt.nodes].map(r=>[r.id,r])).values()]};records.journalState=[await p.sealState({...bundle.state,allocation:await p.allocationFor(records),runtime:rt.runtime})];const db=await new Promise(r=>{const q=indexedDB.open('pushpull');q.onsuccess=()=>r(q.result)});await new Promise((r,j)=>{const tx=db.transaction([...db.objectStoreNames],'readwrite',{durability:'strict'});for(const name of db.objectStoreNames)tx.objectStore(name).clear();for(const [name,rows] of Object.entries(records))for(const row of rows)tx.objectStore(name).put(row);tx.objectStore('meta').put({key:'journal-protocol-v2',protocol:2,status:'active',epoch:bundle.state.epoch});tx.oncomplete=r;tx.onabort=()=>j(tx.error)});db.close();localStorage.clear();}""",n)
   self.page.reload();self.page.wait_for_selector('[data-act=start]')
   result=self.page.evaluate("""async()=>{const Original=Worker;window.Worker=class extends Original{constructor(url,opts){if(String(url).includes('canonical-export-worker')){const script='let early;onmessage=e=>early=e;let count=0;const tx=IDBDatabase.prototype.transaction;IDBDatabase.prototype.transaction=function(...a){count++;return tx.apply(this,a)};const send=postMessage;self.postMessage=x=>{if(x.result)x.result.metrics.transactions=count;send(x)};await import('+JSON.stringify(String(url))+');if(early)onmessage(early);';url=URL.createObjectURL(new Blob([script],{type:'text/javascript'}));}super(url,opts)}};const {exportCanonicalLocal}=await import('./model/canonical-export.mjs');const start=performance.now(),r=await exportCanonicalLocal({getRevision:()=>0});window.Worker=Original;return {...r.metrics,totalMs:performance.now()-start};}""")
   print(json.dumps({'sessions':n,**result}),flush=True)
import unittest
unittest.main(argv=['probe'])
