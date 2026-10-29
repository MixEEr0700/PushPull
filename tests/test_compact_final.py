"""Final compact polish: isolated native data, own notes only, protected sources."""
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_notes,ROOT
import test_v2_training as v2

class CompactFinal(BrowserHarness):
    activate=v2.V2Training.activate
    prepare=v2.V2Training.prepare
    ready=v2.V2Training.ready

    def card(self):return self.page.locator('.exercise-card').first

    def test_mobile_colour_controls_order_and_note_toggle_preserve_results(self):
        self.activate();self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        output=Path('/tmp/pushpull-final-review');output.mkdir(exist_ok=True)
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844});card=self.card()
            if card.locator('[data-expand]').get_attribute('aria-expanded')=='true':card.locator('[data-expand]').click()
            expect(card.locator('[data-note-toggle]')).to_have_count(0)
            expect(card.locator('.num')).to_have_css('background-color','rgb(23, 107, 69)')
            expect(card.locator('.num')).to_have_css('color','rgb(255, 255, 255)')
            expect(card.locator('.name')).to_have_css('font-size','20.5px')
            before=self.state();card.locator('[data-expand]').click()
            expect(card.locator('[data-note-toggle]')).to_be_visible()
            if card.locator('[data-note-toggle]').get_attribute('aria-expanded')=='true':card.locator('[data-note-toggle]').click()
            expect(card.locator('.exercise-notes')).not_to_be_visible()
            f=card.locator('.performanceForm');expect(f).to_be_visible()
            f.locator('[data-quick=kg]').fill('80');f.locator('[data-quick=reps]').fill('10')
            expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
            f.locator('[data-rich-action=toggle]').click()
            expect(f.locator('[data-rich-details]')).to_be_visible()
            f.locator('[data-row="2"][data-field=reps]').fill('9')
            self.assertLess(f.locator('.quick-result').bounding_box()['y'],f.locator('[data-rich-details]').bounding_box()['y'])
            self.assertLess(f.locator('[data-rich-details]').bounding_box()['y'],f.locator('.result-controls').bounding_box()['y'])
            expect(f.locator('.result-controls button')).to_have_text(['Zapisz korektę','✎ Zwiń serie','Historia','Statystyki'])
            rows=[b.bounding_box() for b in f.locator('.result-controls button').all()]
            self.assertEqual(rows[0]['y'],rows[1]['y']);self.assertEqual(rows[2]['y'],rows[3]['y']);self.assertGreater(rows[2]['y'],rows[0]['y'])
            self.assertTrue(all(b['height']>=44 for b in rows))
            expect(card.locator('.expanded>.actions')).not_to_be_visible()
            expect(card.locator('[data-panel=history]')).to_have_count(1);expect(card.locator('[data-panel=stats]')).to_have_count(1)
            self.assertNotIn('Szybki wpis zmienia',f.inner_text());self.assertNotIn('Wskazanie maszyny lub wyciągu',f.inner_text())
            open_notes(card);expect(card.locator('.exercise-notes')).to_be_visible()
            expect(card.locator('.exercise-notes small')).to_have_count(0)
            expect(card.locator('.exercise-notes textarea')).not_to_be_visible()
            card.locator('[data-note-toggle]').click();expect(card.locator('.exercise-notes')).not_to_be_visible()
            expect(f.locator('[data-row="2"][data-field=reps]')).to_have_value('9')
            f.locator('[data-rich-action=toggle]').click()
            expect(f.locator('.result-controls button')).to_have_text(['Zapisz wynik','✎ Edytuj serie','Historia','Statystyki'])
            self.assertEqual(self.state(),before)
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.page.screenshot(path=str(output/f'{width}.png'),full_page=True)
        f.locator('[type=submit]').click();expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        self.assertEqual([r['reps'] for r in self.state()['entries'][-1]['series']],['10','10','9'])
        self.assertEqual(card.locator('.adaptive-result').evaluate('(e)=>getComputedStyle(e).color'),'rgb(57, 255, 116)')
        expect(card.locator('.idle-controls button')).to_have_count(4)
        before=self.state();card.locator('[data-open-series]').click();expect(card.locator('[data-rich-details]')).to_be_visible();self.assertEqual(self.state(),before)
        self.page.reload();self.ready();card=self.card();card.locator('[data-expand]').click()
        expect(card.locator('.exercise-notes')).not_to_be_visible()

    def test_source_bytes_and_user_note_survive_closed_notes_restart_and_plan_roundtrip(self):
        self.activate();self.page.locator('[data-act=start]').click();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.card().locator('[data-expand]').click()
        before=self.state()['trainingJournal']['model'];open_notes(self.card())
        note=self.card().locator('[data-personal-note]');note.locator('summary').click()
        expect(self.card().locator('[data-instructions],[data-note-scope]')).to_have_count(0)
        expect(note.locator('textarea')).to_have_value('')
        text='Dopisek Ł 😀\n'+'Długi tekst '*40;note.locator('textarea').fill(text)
        self.card().locator('[data-note-toggle]').click();expect(self.card().locator('.exercise-notes')).not_to_be_visible()
        self.page.reload();self.ready();self.card().locator('[data-expand]').click()
        expect(self.card().locator('.exercise-notes')).not_to_be_visible();open_notes(self.card())
        note=self.card().locator('[data-personal-note]');expect(note.locator('textarea')).to_have_value(text)
        self.assertGreaterEqual(note.locator('textarea').evaluate('(e)=>e.clientHeight'),note.locator('textarea').evaluate('(e)=>e.scrollHeight'))
        note.locator('[type=submit]').click();expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        after=self.state();self.assertEqual(after['trainingJournal']['model']['coachInstructions'],before['coachInstructions'])
        self.assertEqual(after['trainingJournal']['model']['userNotes'][-1]['text'],text)
        self.page.reload();self.ready();self.card().locator('[data-expand]').click();open_notes(self.card())
        expect(self.card().locator('[data-personal-note] summary')).to_contain_text(text)
        expect(self.card().locator('[data-instructions]')).to_have_count(0)
        self.assertEqual(self.state(),after)
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.plans();self.page.locator('#planFile').set_input_files(ROOT/'tests/fixtures/plan-v3.json')
        self.page.locator('[data-plan-save]').click();expect(self.page.get_by_text('Plan zapisany bez aktywacji',exact=True)).to_be_visible()
        with self.page.expect_download():self.page.locator('[data-plan-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.card().locator('[data-expand]').click();open_notes(self.card())
        expect(self.card().locator('[data-personal-note] textarea')).to_have_value('')
        expect(self.card().locator('.exercise-notes')).not_to_contain_text(text)
        self.plans();self.page.locator('[data-plan-switch]').click();self.page.locator('#switchPlanId').select_option('v2-owner-2026-10-22')
        with self.page.expect_download():self.page.locator('[data-switch-activate]').click()
        expect(self.page.get_by_text('Plan aktywny dla przyszłych treningów',exact=True)).to_be_visible()
        self.page.locator('[data-tab=training]').click();self.page.locator('[data-type="PUSH A"]').click();self.card().locator('[data-expand]').click();open_notes(self.card())
        expect(self.card().locator('[data-personal-note] summary')).to_contain_text(text)
        final=self.state()['trainingJournal']['model']
        self.assertEqual([r for r in final['coachInstructions'] if r['planVersionId']=='v2-owner-2026-10-22'],before['coachInstructions'])
        self.assertEqual([n for n in final['userNotes'] if n['exerciseId']=='PUSH-A-1'],after['trainingJournal']['model']['userNotes'])

    def test_four_buttons_stay_below_legacy_rows(self):
        self.start();self.result('80','10');f=self.page.locator('.seriesResultForm')
        f.locator('[data-series-toggle]').click();f.locator('[data-series-index="2"][data-field=reps]').fill('9')
        self.assertLess(f.locator('.series-details').bounding_box()['y'],f.locator('.result-controls').bounding_box()['y'])
        expect(f.locator('.result-controls button')).to_have_text(['Zapisz korektę','✎ Zwiń serie','Historia','Statystyki'])
        f.locator('[data-series-toggle]').click();expect(f.locator('[data-main=kg]')).to_have_value('80')
        f.locator('[type=submit]').click();expect(f).to_have_count(0)
        self.assertEqual([r['reps'] for r in self.state()['entries'][-1]['series']],['10','10','9'])
