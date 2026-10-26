"""Storage/read invariants for the P0 optimizations; isolated synthetic origins."""
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy


class ResponsivenessSafety(BrowserHarness):
    records=legacy.IndexedDBMigration.records
    def archives(self):
        return self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return db.export().archives}finally{db.close()}}')

    def test_large_history_roundtrip_start_edit_and_reopen_preserve_archives_and_other_records(self):
        expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.evaluate("""async()=>{
         const db=await PushPullDB.open(()=>{}),d=db.value;
         for(let i=0;i<64;i++){
          const id='history-'+i,type=['PUSH A','PULL A','PUSH B','PULL B'][i%4];
          d.sessions.push({id,seq:i+1,type,date:'2026-01-01',status:'done'});
          for(const ex of d.exercises[type])d.entries.push({id:id+'-'+ex.id,sessionId:id,exerciseId:ex.id,kg:'20',reps:'8',series:[{kg:'20',reps:'8'},{kg:'19.5',reps:'10'}],extension:{text:'Ł😀'}});
         }
         await db.commit(d,{importedArchives:[{id:'large-raw',kind:'recovery',createdAt:'2026-01-01T00:00:00.000Z',raw:'Ł😀'.repeat(128*1024)}]});db.close();
        }""")
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        before=self.state();archive=self.archives();local=self.local_raw()
        self.assertTrue(any(a['id']=='large-raw' for a in archive))
        self.start();self.result('31,5','7')
        # The existing app adds default display descriptions on first commit.
        # Compare against the persisted start, then verify the edit changes only
        # its intended result (not any historic source or exercise metadata).
        started=self.state()
        expect(self.page.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.reload();expect(self.page.locator('[data-draft-resume]')).to_be_visible()
        self.page.locator('[data-draft-resume]').click()
        expect(self.page.locator('[data-main=kg]')).to_have_value('31,5')
        self.save()
        after=self.state()
        self.assertEqual(after['entries'][:-1],before['entries'])
        self.assertEqual(after['sessions'][:-1],before['sessions'])
        self.assertEqual(after['exercises'],started['exercises'])
        self.assertEqual(after['changes'],before['changes'])
        self.assertEqual(after['nextType'],before['nextType'])
        self.assertEqual(after['entries'][-1]['kg'],'31.5')
        self.assertEqual(after['entries'][-1]['reps'],'7')
        self.assertEqual(self.archives(),archive)
        self.assertEqual(self.local_raw(),local)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual(self.state(),after)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
