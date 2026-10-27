"""Approved F UI, native storage, test-only data. No schema migration."""
import json
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness
import test_v2_training

class CompactMatrix(BrowserHarness):
    activate=test_v2_training.V2Training.activate
    prepare=test_v2_training.V2Training.prepare
    ready=test_v2_training.V2Training.ready

    def open_note(self,page=None):
        p=page or self.page
        p.locator('[data-expand="PUSH-A-1"]').click()
        note=p.locator('[data-personal-note]').first
        if not note.evaluate('(e)=>e.open'):note.locator('summary').click()
        return note

    def test_note_draft_survives_card_navigation_reload_and_native_failure(self):
        self.activate();self.page.locator('[data-act=start]').click()
        note=self.open_note();note.locator('textarea').fill('Łopatki 😀\nbez zmiany instrukcji')
        self.page.locator('[data-expand="PUSH-A-1"]').click();self.page.reload();self.ready()
        note=self.open_note();expect(note.locator('textarea')).to_have_value('Łopatki 😀\nbez zmiany instrukcji')
        before=self.state()['trainingJournal']['model']
        self.page.evaluate("""()=>{window.__oldAdd=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(...a){if(this.name==='journalObjects')throw new DOMException('synthetic','QuotaExceededError');return __oldAdd.apply(this,a)}}""")
        with self.page.expect_event('dialog'):note.locator('[type=submit]').click()
        expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_have_count(0)
        expect(self.page.locator('[data-personal-note] textarea')).to_have_value('Łopatki 😀\nbez zmiany instrukcji')
        self.page.evaluate('()=>{IDBObjectStore.prototype.add=__oldAdd}')
        self.assertEqual(self.state()['trainingJournal']['model'],before)
        self.page.locator('[data-personal-note] [type=submit]').click()
        expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        after=self.state()['trainingJournal']['model']
        self.assertEqual(after['coachInstructions'],before['coachInstructions'])
        self.assertEqual(after['userNotes'][-1]['text'],'Łopatki 😀\nbez zmiany instrukcji')
        self.assertIn('v2-owner-2026-10-22',after['userNotes'][-1]['id'])
        # A second edit updates the same scoped record, not the source instruction.
        note=self.page.locator('[data-personal-note]').first;note.locator('summary').click()
        note.locator('textarea').fill('poprawiona notatka')
        note.locator('[type=submit]').click()
        expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        edited=self.state()['trainingJournal']['model']
        self.assertEqual(len(edited['userNotes']),len(after['userNotes']))
        self.assertEqual(edited['userNotes'][-1]['text'],'poprawiona notatka')
        self.assertEqual(edited['coachInstructions'],before['coachInstructions'])
        self.page.locator('[data-personal-note] summary').first.click()
        self.page.locator('[data-personal-note] textarea').fill('anulowana zmiana')
        self.page.locator('[data-note-cancel]').click()
        self.page.reload();self.ready();note=self.open_note()
        expect(note.locator('textarea')).to_have_value('poprawiona notatka')

    def test_two_note_sources_are_preserved_without_selecting_a_winner(self):
        self.activate();self.page.locator('[data-act=start]').click()
        self.open_note().locator('textarea').fill('pierwsza wersja')
        other=self.context.new_page();other.on('dialog',self.dialog);other.goto(self.url)
        self.open_note(other).locator('textarea').fill('druga wersja')
        self.page.reload();self.ready();note=self.open_note()
        expect(note.locator('[data-note-conflict]')).to_be_visible()
        expect(note.locator('textarea')).to_have_attribute('readonly','')
        with self.page.expect_download() as d:note.locator('[data-note-download]').click()
        evidence=json.loads(Path(d.value.path()).read_text())
        self.assertEqual({s['text'] for s in evidence['sources']},{'pierwsza wersja','druga wersja'})
        self.assertFalse(self.state()['trainingJournal']['model']['userNotes'])

    def test_header_order_coach_provenance_and_reps_first_at_mobile_widths(self):
        self.activate()
        self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{const d=h.value,r=d.trainingJournal.model.coachInstructions.find(x=>x.positionId?.endsWith('PUSH-A-1'));r.source.kind='trainer';r.text='Oryginalna instrukcja testowa trenera';r.confirmation='confirmed';await h.commit(d,{importing:true})}finally{h.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-act=start]').click()
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844})
            card=self.page.locator('.exercise-card').first
            if card.locator('[data-expand]').get_attribute('aria-expanded')=='true':card.locator('[data-expand]').click()
            expect(card.locator('.detail').first).not_to_be_visible()
            card.locator('[data-expand]').click();expect(card.locator('.performanceForm')).to_be_visible()
            self.assertEqual(card.locator('[data-quick]').evaluate_all('(els)=>els.map(e=>e.dataset.quick)'),['reps','kg'])
            coach=card.locator('[data-instructions=coach]');coach.locator('summary').click()
            expect(coach.locator('p')).to_have_text('Oryginalna instrukcja testowa trenera')
            expect(coach.locator('textarea,input')).to_have_count(0)
            expect(card.locator('[data-personal-note] textarea')).not_to_be_visible()
            self.assertGreaterEqual(card.locator('[data-expand]').bounding_box()['height'],44)
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

        # An explicitly empty trainer record is absence, not a blank block.
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.evaluate("""async()=>{const h=await PushPullDB.open(()=>{});try{const d=h.value;d.trainingJournal.model.coachInstructions.find(x=>x.positionId?.endsWith('PUSH-A-1')).text='';await h.commit(d,{importing:true})}finally{h.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-type="PUSH A"]').click()
        self.page.locator('[data-expand="PUSH-A-1"]').click()
        expect(self.page.locator('.exercise-card').first.locator('[data-instructions=coach]')).to_have_count(0)
