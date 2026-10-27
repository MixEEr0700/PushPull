"""Stage A uses a separate named database; the production writer stays v1."""
from test_browser import BrowserHarness

class JournalProtocol(BrowserHarness):
    def test_lossless_protocol_persists_and_reopens_in_isolated_idb_without_touching_live_database(self):
        result=self.page.evaluate("""async()=>{
          const {createProtocol,materialize,STORES}=await import('./model/journal-protocol.mjs');
          const live=await PushPullDB.open(()=>{throw Error('missing live database')});
          try{
            const before=JSON.stringify(live.export()),revision=live.revision,bundle=await createProtocol(live.export());
            const request=r=>new Promise((ok,no)=>{r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});
            const opening=indexedDB.open('issue82-a-isolated',2);opening.onupgradeneeded=()=>{for(const name of STORES)opening.result.createObjectStore(name,{keyPath:'id'})};
            let db=await request(opening);await new Promise((ok,no)=>{const tx=db.transaction(STORES,'readwrite',{durability:'strict'});tx.oncomplete=ok;tx.onabort=()=>no(tx.error);for(const name of STORES)for(const row of bundle.records[name])tx.objectStore(name).add(row)});db.close();
            db=await request(indexedDB.open('issue82-a-isolated',2));const tx=db.transaction(STORES),records=Object.fromEntries(await Promise.all(STORES.map(async name=>[name,await request(tx.objectStore(name).getAll())])));db.close();
            const source=await materialize({state:records.journalState[0],records});
            return {identical:JSON.stringify(source)===before,liveUnchanged:JSON.stringify(live.export())===before&&live.revision===revision,version:PushPullDB.VERSION};
          }finally{live.close()}
        }""")
        self.assertEqual(result,{'identical':True,'liveUnchanged':True,'version':1})
