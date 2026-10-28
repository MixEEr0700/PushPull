"""PR97 owner decision: userNotes only, explicit preparation, no source migration."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_notes,wait_for_service_worker_controller
import test_plan_import as imported
import test_journal as observed

class UserNotes(BrowserHarness):
    prepare=imported.PlanImport.prepare
    ready=imported.PlanImport.ready
    preview=imported.PlanImport.preview
    store=imported.PlanImport.store
    settings=imported.PlanImport.settings
    activate=imported.PlanImport.activate

    def plan_note(self,eid='TEST-1'):
        unit=self.page.locator('[data-selected-plan] [data-plan-unit]').first
        if not unit.evaluate('(e)=>e.open'):unit.locator(':scope > summary').click()
        note=unit.locator(f'[data-plan-exercise="{eid}"] [data-personal-note]')
        if not note.evaluate('(e)=>e.open'):note.locator('summary').click()
        return note

    def save_note(self,note,text):
        note.locator('textarea').fill(text);note.locator('[type=submit]').click()
        expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        expect(self.page.locator('[data-training-pending]')).to_have_count(0)

    def test_initial_note_before_activation_restart_offline_and_training_use_same_record(self):
        # Actual service worker, no network dependency once installed.
        self.context=self.new_context(service_workers='allow');self.page=self.context.new_page()
        self.page.on('dialog',self.dialog);self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.url);wait_for_service_worker_controller(self.page)
        self.prepare();self.ready();before=self.state();self.preview();self.store()
        stored=self.state();text='Własna notatka przed treningiem Ł 😀\nDruga linia'
        note=self.plan_note();expect(note.locator('textarea')).to_have_value('');self.save_note(note,text)
        saved=self.state();j=saved['trainingJournal']
        self.assertNotIn('activePlanVersionId',j)
        self.assertEqual(j['importedPlans'],stored['trainingJournal']['importedPlans'])
        self.assertEqual(j['model']['coachInstructions'],stored['trainingJournal']['model']['coachInstructions'])
        self.assertEqual(saved['exercises'],stored['exercises'])
        self.assertEqual(saved['sessions'],before['sessions']);self.assertEqual(saved['entries'],before['entries'])
        self.assertEqual(j['sessionSnapshots'],stored['trainingJournal']['sessionSnapshots'])
        self.assertEqual(j['model']['userNotes'][0]['id'],'user:synthetic-v3:TEST-1')
        self.assertEqual(j['model']['userNotes'][0]['revision'],1)
        self.context.set_offline(True);self.page.reload();self.ready();self.plans('synthetic-v3')
        note=self.plan_note();expect(note.locator('textarea')).to_have_value(text)
        self.save_note(note,text+' offline');self.activate()
        self.page.locator('[data-tab=training]').click()
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.page.locator('[data-expand="TEST-1"]').click();open_notes(self.page)
        card=self.page.locator('.exercise-card').first
        expect(card.locator('.exercise-notes [data-instructions]')).to_have_count(0)
        expect(card.locator('[data-personal-note] summary')).to_contain_text(text+' offline')
        self.page.reload();self.ready();self.page.locator('[data-expand="TEST-1"]').click()
        expect(card.locator('.exercise-notes')).not_to_be_visible();open_notes(card)
        expect(card.locator('[data-personal-note] summary')).to_contain_text(text+' offline')
        final=self.state();self.assertEqual(final['trainingJournal']['model']['userNotes'][0]['revision'],2)
        self.assertEqual(final['entries'],before['entries'])
        self.assertEqual(final['trainingJournal']['model']['coachInstructions'],stored['trainingJournal']['model']['coachInstructions'])

    def test_same_exercise_in_new_plan_does_not_borrow_note_and_clearing_is_an_own_revision(self):
        self.prepare();self.ready();self.preview();self.store();self.save_note(self.plan_note(),'V3 only')
        before=self.state();self.preview(imported.v4());self.store()
        n=self.plan_note();expect(n.locator('textarea')).to_have_value('');self.save_note(n,'V4 only')
        both=self.state();self.page.reload();self.ready();self.plans('synthetic-v3')
        expect(self.plan_note().locator('textarea')).to_have_value('V3 only')
        self.page.locator('#importedPlanId').select_option('synthetic-v4')
        n=self.plan_note();expect(n.locator('textarea')).to_have_value('V4 only');self.save_note(n,'')
        final=self.state();notes=final['trainingJournal']['model']['userNotes']
        self.assertEqual([(n['id'],n['text'],n['revision']) for n in notes],[('user:synthetic-v3:TEST-1','V3 only',1),('user:synthetic-v4:TEST-1','',2)])
        for k in ['sessions','entries','changes']:self.assertEqual(final[k],before[k])
        self.assertEqual(final['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertEqual(final['trainingJournal']['importedPlans'][0],before['trainingJournal']['importedPlans'][0])
        self.assertEqual(final['trainingJournal']['importedPlans'][1],imported.v4())
        self.assertEqual(both['trainingJournal']['model']['coachInstructions'],final['trainingJournal']['model']['coachInstructions'])

    def test_unversioned_source_text_is_not_shown_or_editable_and_remains_unchanged(self):
        self.prepare();self.ready()
        self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{const d=h.value;d.exercises['PUSH A'][0].notes='SOURCE owner/historical not an own note';await h.commit(d,{importing:true})}finally{h.close()}}""")
        self.page.reload();self.ready();before=self.state()
        draft=self.page.evaluate('''()=>{const context='pushpull-note-ui-v1:'+JSON.stringify(['local','source','PUSH-A-1']),d={key:context+':old-tab',context,base:'SOURCE owner/historical not an own note',text:'Nieutracony szkic',token:'old-legacy-note-token'};localStorage.setItem(d.key,JSON.stringify(d));return d}''')
        self.page.locator('[data-expand="PUSH-A-1"]').click();open_notes(self.page)
        expect(self.page.locator('[data-note-unbound]')).to_be_visible()
        expect(self.page.locator('.exercise-notes textarea')).to_have_count(0)
        expect(self.page.locator('.exercise-notes')).not_to_contain_text('SOURCE owner/historical')
        self.assertEqual(self.state(),before)
        with self.page.expect_download() as download:self.page.locator('[data-unbound-note-download]').click()
        evidence=json.loads(Path(download.value.path()).read_text())
        self.assertEqual(evidence['sources'],[draft])
        self.assertEqual(self.page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))',draft['key']),draft)
        # An arbitrary historical userNotes record is evidence, never a default for a new plan.
        self.preview();self.store()
        self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{const d=h.value;d.trainingJournal.model.userNotes.push({id:'old-arbitrary-note',exerciseId:'TEST-1',sessionId:null,origin:'user',text:'unbound own evidence',revision:7,source:{kind:'owner',reference:'synthetic',recordedAt:null}});await h.commit(d,{importing:true})}finally{h.close()}}""")
        self.page.reload();self.ready();self.plans('synthetic-v3');n=self.plan_note()
        expect(n.locator('textarea')).to_have_value('');self.save_note(n,'new explicit note')
        final=self.state();self.assertEqual(final['trainingJournal']['model']['userNotes'][0]['text'],'unbound own evidence')
        self.assertEqual(final['trainingJournal']['model']['userNotes'][0]['revision'],7)
        self.assertEqual(final['exercises']['PUSH A'][0]['notes'],before['exercises']['PUSH A'][0]['notes'])
        self.assertEqual(final['sessions'],before['sessions']);self.assertEqual(final['entries'],before['entries'])

class ObservedUserNotes(BrowserHarness):
    prepare=observed.JournalFlow.prepare
    ready=observed.JournalFlow.ready
    settings=observed.JournalFlow.settings
    enable=observed.JournalFlow.enable

    def test_legacy_observed_version_uses_own_notes_and_never_edits_source_or_snapshot(self):
        self.enable();self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        before=self.state();self.page.locator('[data-expand="PUSH-A-1"]').click();open_notes(self.page)
        note=self.page.locator('[data-personal-note]');note.locator('summary').click()
        expect(note.locator('textarea')).to_have_value('');note.locator('textarea').fill('Notatka własna szkieletu Ł 😀')
        note.locator('[type=submit]').click();expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        after=self.state();self.assertEqual(after['exercises'],before['exercises'])
        self.assertEqual(after['entries'],before['entries']);self.assertEqual(after['sessions'],before['sessions'])
        self.assertEqual(after['trainingJournal']['sessionSnapshots'],before['trainingJournal']['sessionSnapshots'])
        self.assertEqual(after['trainingJournal']['model']['coachInstructions'],before['trainingJournal']['model']['coachInstructions'])
        own=after['trainingJournal']['model']['userNotes'][-1]
        self.assertEqual(own['text'],'Notatka własna szkieletu Ł 😀');self.assertIn('observed:PUSH A:',own['id'])
        self.page.reload();self.ready();self.page.locator('[data-expand="PUSH-A-1"]').click();open_notes(self.page)
        expect(self.page.locator('[data-personal-note] summary')).to_contain_text(own['text'])
        self.assertEqual(self.state(),after)
