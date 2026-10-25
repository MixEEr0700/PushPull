"""Issue #12: source skeleton, read-only preview and approved V2 cards."""
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_indexeddb as legacy
import test_v2_training as flows

class V2Presentation(BrowserHarness):
    prepare=legacy.IndexedDBMigration.prepare
    ready=legacy.IndexedDBMigration.ready

    def test_source_preview_manual_activation_and_independent_cards(self):
        self.prepare();self.ready();before=self.state()
        expect(self.page.locator('.eyebrow')).to_have_text('PLAN ŹRÓDŁOWY · SZKIELET')
        expect(self.page.locator('[data-source-plan-hint]')).to_contain_text('nie jest pełnym planem V2')
        expect(self.page.locator('[data-source-plan-hint]')).to_contain_text('Dane → Plany treningowe → wybierz V2 → aktywuj')
        self.plans('v2-owner-2026-10-22')
        self.page.locator('[data-plan-unit="PULL B"] > summary').click()
        for eid,name in [('PULL-B-6-SKI','Narciarz'),('PULL-B-6-SHRUGS','Szrugsy')]:
            ex=self.page.locator(f'[data-plan-exercise="{eid}"]')
            expect(ex).to_contain_text(name)
            for text in ['Seria 1','8–10','RIR 0','tempo 2 0 1 0','15 s']:expect(ex).to_contain_text(text)
            expect(ex.locator('p.small').first).to_be_visible()
            expect(ex.locator('p.small').first).to_contain_text('C1: narciarz')
            expect(ex.locator('textarea')).to_have_count(0)
        self.page.locator('[data-plan-unit="PUSH A"] > summary').click()
        deferred=self.page.locator('[data-plan-exercise="PUSH-A-8"]')
        for text in ['Liczba serii nieokreślona','RIR nieokreślone','tempo nieokreślone']:expect(deferred).to_contain_text(text)
        self.assertEqual(self.state(),before) # Opening preview never activates/migrates.
        self.confirm=False;self.page.locator('[data-plan-activate]').click()
        self.assertEqual(self.state(),before)
        self.confirm=True
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click()
        # Activation does not relabel the already-started source session.
        expect(self.page.locator('[data-source-plan-hint]')).to_be_visible()
        self.assertEqual(self.state()['sessions'],before['sessions'])
        self.assertEqual(self.state()['entries'],before['entries'])
        self.page.locator('[data-act=finish]').click()
        self.page.locator('[data-type="PULL B"]').click()
        expect(self.page.locator('[data-source-plan-hint]')).to_have_count(0)
        expect(self.page.locator('.eyebrow')).to_have_text('DZIENNIK · V2')
        self.page.locator('[data-act=start]').click();self.ready()
        snapshot=self.state()['trainingJournal']['sessionSnapshots'][-1]
        self.assertEqual(self.page.locator('[data-expand="PULL-B-6"]').count(),0)
        self.assertEqual(self.page.locator('.exercise-card').count(),10) # 9 slots, pair A/B.
        for eid,label in [('PULL-B-6-SKI','Narciarz'),('PULL-B-6-SHRUGS','Szrugsy')]:
            card=self.page.locator('.exercise-card').filter(has=self.page.locator(f'[data-expand="{eid}"]'))
            expect(card.locator('.name')).to_have_text(label)
            expect(card.locator('.exercise-description')).to_have_count(0)
            expect(card).to_contain_text('2 serie · 8–10 / 8–10 powt. · Tempo 2 0 1 0 · RIR 0')
            card.locator('[data-expand]').click()
            card.locator('.expanded details > summary').click()
            expect(card.locator('.expanded p.small')).to_contain_text('C1: narciarz')
            expect(card.locator('.v2NoteForm textarea')).to_be_visible()
            expect(card.locator('.v2NoteForm textarea')).to_have_value('')
            card.locator('.v2NoteForm textarea').fill('Moja notatka '+eid)
            card.locator('.v2NoteForm button').click()
            expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
            expect(card.locator('.v2NoteForm textarea')).to_have_value('Moja notatka '+eid)
            card.locator('[data-panel=result]').click()
            form=card.locator('.performanceForm')
            expect(form).to_have_attribute('data-id',eid)
            form.locator('[data-rich-action=toggle]').click()
            self.assertEqual(form.locator('[data-field=kg]').count(),2)
            flows.V2Training.fill_rows(self,form,'20' if eid.endswith('SKI') else '10','8')
            expect(form.locator('[data-draft-status]')).to_have_text('Szkic zapisany lokalnie · wynik niezatwierdzony')
        drafts=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')
        self.assertEqual({d['exerciseId'] for d in drafts},{'PULL-B-6-SKI','PULL-B-6-SHRUGS'})
        self.assertEqual(self.state()['entries'],before['entries'])
        for eid in ['PULL-B-6-SKI','PULL-B-6-SHRUGS']:
            self.page.locator(f'[data-expand="{eid}"]').click()
            self.page.locator('[data-panel=result]').click()
            flows.V2Training.save_form(self,self.page.locator('.performanceForm'))
        entries=self.state()['entries'][-2:]
        self.assertEqual([e['exerciseId'] for e in entries],['PULL-B-6-SKI','PULL-B-6-SHRUGS'])
        self.assertTrue(all(len(e['performance']['rows'])==2 for e in entries))
        for eid,total in [('PULL-B-6-SKI','320'),('PULL-B-6-SHRUGS','160')]:
            self.page.locator(f'[data-expand="{eid}"]').click()
            self.page.locator('[data-panel=history]').click()
            self.assertEqual(self.page.locator('.panel .entry').count(),1)
            self.page.locator('[data-panel=stats]').click()
            expect(self.page.locator('.stat-tile').first).to_contain_text(total)
            expect(self.page.locator('.v2NoteForm textarea')).to_have_value('Moja notatka '+eid)
        self.assertEqual(self.state()['trainingJournal']['sessionSnapshots'][-1],snapshot)
        self.assertEqual(self.state()['entries'][:-2],before['entries'])
        self.assertEqual(self.local_raw(),legacy.RAW)
        self.page.locator('[data-tab=calendar]').click()
        self.page.locator(f'[data-act=openSession][data-id="{before["activeId"]}"]').click()
        expect(self.page.locator('.exercise-card .name').nth(3)).to_have_text('Dipy')
        self.assertEqual(self.page.locator('.exercise-card').count(),8)
        self.assertFalse(self.alerts,self.alerts)

    def test_active_v2_preview_and_stale_activation_handler_are_read_only(self):
        flows.V2Training.activate(self)
        before=self.state()
        self.plans('v2-owner-2026-10-22')
        expect(self.page.locator('[data-current-plan]')).to_be_visible()
        expect(self.page.locator('[data-plan-activate]')).to_have_count(0)
        for unit in ['PUSH A','PULL A','PUSH B','PULL B']:
            self.page.locator(f'[data-plan-unit="{unit}"] > summary').click()
            expect(self.page.locator(f'[data-plan-unit="{unit}"] [data-plan-exercise]').first).to_be_visible()
        # A queued/stale DOM action must be harmless even without a visible button.
        self.page.evaluate('''()=>{const b=document.createElement('button');b.dataset.planActivate='';b.dataset.planId='v2-owner-2026-10-22';b.id='staleActivation';document.querySelector('main').append(b)}''')
        self.page.locator('#staleActivation').click()
        expect(self.page.locator('.toast')).to_have_text('Ten plan jest aktywny')
        self.assertEqual(self.state(),before)
        self.page.reload();expect(self.page.locator('h1')).to_have_text('Trening')
        self.assertEqual(self.state(),before)
        # An imported active plan must never be labeled as active V2.
        from test_plan_import import PlanImport,PLAN
        self.settings=lambda:self.page.locator('[data-tab=settings]').click()
        PlanImport.preview(self,PLAN);PlanImport.store(self);PlanImport.activate(self)
        self.plans('v2-owner-2026-10-22')
        expect(self.page.locator('[data-current-plan]')).to_have_count(0)
        expect(self.page.locator('[data-plan-activate]')).to_be_visible()
        self.assertEqual(self.state()['trainingJournal']['activePlanVersionId'],PLAN['planVersion']['id'])

    def test_activation_setup_waits_for_session_finish_with_slow_hash(self):
        # A slow real history commit must finish before activate() returns.
        # Only the test's SHA call is delayed; DB writes/CAS stay real.
        self.context.add_init_script(r"""(() => {
          const digest=crypto.subtle.digest.bind(crypto.subtle);
          document.addEventListener('click',e=>{
            if(e.target.closest?.('[data-act=finish]'))window.__finishDelayArmed=true;
          },true);
          crypto.subtle.digest=async(...args)=>{
            if(window.__finishDelayArmed&&new TextDecoder().decode(args[1]).includes('"activeId":null')){
              window.__finishDelayArmed=false;window.__finishHashDelayed=true;
              await new Promise(resolve=>setTimeout(resolve,700));
            }
            return digest(...args);
          };
        })();""")
        flows.V2Training.activate(self)
        finished=self.state()
        self.assertIsNone(finished['activeId'])
        self.assertTrue(self.page.evaluate('window.__finishHashDelayed===true'))
        expected=[{**s,**({'status':'done'} if s['id']==self.before['activeId'] else {})} for s in self.before['sessions']]
        self.assertEqual(finished['sessions'],expected)
        self.assertEqual(finished['entries'],self.before['entries'])
        self.assertEqual(finished['changes'],self.before['changes'])
