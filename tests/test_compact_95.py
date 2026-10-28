"""Issue95 actual individual results, only synthetic isolated native databases."""
import re
from pathlib import Path
from playwright.sync_api import expect
from test_browser import BrowserHarness,open_result_panel,open_notes
import test_v2_training as v2

class Compact95(BrowserHarness):
    activate=v2.V2Training.activate
    prepare=v2.V2Training.prepare
    ready=v2.V2Training.ready
    fill_rows=v2.V2Training.fill_rows
    save_form=v2.V2Training.save_form
    records=v2.V2Training.records

    def form(self,eid='PUSH-A-1'):
        card=self.page.locator('.exercise-card').filter(has=self.page.locator(f'[data-expand="{eid}"]'))
        if card.locator('[data-expand]').get_attribute('aria-expanded')!='true':card.locator('[data-expand]').click()
        open_result_panel(card)
        return card.locator('.performanceForm')

    def test_actual_10_10_9_prefill_individual_edits_restart_and_confirmation(self):
        self.activate();self.page.locator('[data-type="PUSH A"]').click();self.page.locator('[data-act=start]').click()
        f=self.form();f.locator('[data-rich-action=toggle]').click();self.fill_rows(f,'80','10')
        f.locator('[data-row="2"][data-field=reps]').fill('9');self.save_form(f)
        first=self.state();sid=first['activeId'];source=first['entries'][-1];card=self.page.locator('.exercise-card').first
        expect(card.locator('.last-series-row')).to_have_text(['Seria 1: 10 × 80 kg','Seria 2: 10 × 80 kg','Seria 3: 9 × 80 kg'])
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-type="PUSH A"]').click();self.page.locator('[data-act=start]').click();f=self.form()
        expect(f.locator('[data-quick=reps]')).to_have_value('10');expect(f.locator('[data-quick=kg]')).to_have_value('80')
        f.locator('[data-rich-action=toggle]').click()
        self.assertEqual(f.locator('[data-field=reps]').evaluate_all('(els)=>els.map(e=>e.value)'),['10','10','9'])
        self.confirm=False;f.locator('[data-quick=kg]').fill('90')
        expect(f.locator('[data-quick=kg]')).to_have_value('80');expect(f.locator('[data-row="2"][data-field=reps]')).to_have_value('9')
        f.locator('[data-rich-action=add-set]').click();f.locator('[data-row="3"][data-field=reps]').fill('7');f.locator('[data-row="3"][data-field=kg]').fill('70');expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        f.locator('[data-rich-action=toggle]').click();expect(f.locator('[data-rich-details]')).not_to_be_visible()
        self.page.locator('[data-tab=settings]').click();self.page.locator('[data-tab=training]').click()
        f=self.page.locator('.performanceForm');expect(f.locator('[data-quick=kg]')).to_have_value('80')
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        if not f.locator('[data-rich-details]').is_visible():f.locator('[data-rich-action=toggle]').click()
        self.assertEqual(f.locator('[data-field=reps]').evaluate_all('(els)=>els.map(e=>e.value)'),['10','10','9','7'])
        f.locator('[data-rich-action=remove-set][data-row="1"]').click()
        self.assertEqual(f.locator('[data-field=reps]').evaluate_all('(els)=>els.map(e=>e.value)'),['10','9','7'])
        self.confirm=True;self.save_form(f);after=self.state()
        old=next(e for e in after['entries'] if e['sessionId']==sid and e['exerciseId']=='PUSH-A-1');self.assertEqual(old,source)
        self.assertEqual([r['segments'][0]['reps'] for r in after['entries'][-1]['performance']['rows']],['10','9','7'])
        # Unchanged prefills can be saved directly; individual values never expand to a fake 10/10/10.
        self.page.locator('[data-act=finish]').click();expect(self.page.locator('[data-act=start]')).to_be_visible()
        self.page.locator('[data-type="PUSH A"]').click();self.page.locator('[data-act=start]').click();f=self.form();self.save_form(f)
        self.assertEqual([r['segments'][0]['reps'] for r in self.state()['entries'][-1]['performance']['rows']],['10','9','7'])
        self.assertFalse(self.alerts,self.alerts)

    def test_mobile_notes_provenance_controls_icons_and_collapsed_actual_summary(self):
        self.activate()
        self.page.evaluate("""async()=>{const db=await PushPullDB.open(()=>{});try{const d=db.value,r=d.trainingJournal.model.coachInstructions.find(x=>x.positionId?.endsWith('PUSH-A-1'));r.source.kind='trainer';r.text='Instrukcja trenera Ł 😀 '+ 'długi tekst '.repeat(25);r.confirmation='confirmed';await db.commit(d,{importing:true})}finally{db.close()}}""")
        self.page.reload();expect(self.page.locator('[data-act=start]')).to_be_visible();self.page.locator('[data-act=start]').click();f=self.form();f.locator('[data-rich-action=toggle]').click();self.fill_rows(f,'80','10');self.save_form(f)
        original=self.state()['trainingJournal']['model']['coachInstructions']
        output=Path('/tmp/pushpull-95-review');output.mkdir(exist_ok=True)
        for width in [360,390,412]:
            self.page.set_viewport_size({'width':width,'height':844});card=self.page.locator('.exercise-card').first
            if card.locator('[data-expand]').get_attribute('aria-expanded')=='true':card.locator('[data-expand]').click()
            expect(card.locator('.detail').first).to_be_visible();expect(card.locator('.last-result')).to_have_text('10 × 80 kg')
            self.assertGreaterEqual(card.locator('.name').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)'),18)
            self.assertGreaterEqual(card.locator('.num').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)'),20)
            card.locator('[data-expand]').click();f=self.form()
            expect(card.locator('.panel h3')).to_have_count(0)
            open_notes(card);expect(card.locator('.exercise-notes h3')).to_have_text('Notatki')
            expect(card.locator('[data-instructions]')).to_have_count(0)
            expect(card.locator('.exercise-notes')).not_to_contain_text('Instrukcja trenera Ł 😀')
            expect(card.locator('[data-instructions]').locator('textarea,input,[contenteditable]')).to_have_count(0)
            expect(card.locator('.exercise-notes')).not_to_contain_text('Wskazówki źródłowe')
            self.assertEqual(f.locator('.quick-result input').count(),2)
            self.assertFalse(re.search(r'Seria 1|Wszystkie serie|Nowy wynik',f.inner_text()))
            buttons=f.locator('.result-buttons button');boxes=[b.bounding_box() for b in buttons.all()]
            self.assertEqual(len(boxes),2);self.assertEqual(boxes[0]['y'],boxes[1]['y'])
            self.assertTrue(all(b['height']>=44 for b in boxes))
            for tab in ['training','calendar','settings']:expect(self.page.locator(f'[data-tab={tab}] svg')).to_be_visible()
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.page.screenshot(path=str(output/f'{width}.png'),full_page=True)
        note=card.locator('[data-personal-note]');note.locator('summary').click();note.locator('textarea').fill('Własne Ł 😀\n'+'więcej '*20)
        note.locator('[type=submit]').click();expect(self.page.get_by_text('Notatka zapisana',exact=True)).to_be_visible()
        self.assertEqual(self.state()['trainingJournal']['model']['coachInstructions'],original)
        expect(card.locator('[data-personal-note] summary')).to_contain_text('Własne Ł 😀')
        expect(card.locator('[data-personal-note] summary')).not_to_contain_text('Moja notatka')

    def test_quick_confirm_preserves_other_individual_field_and_does_not_need_new_confirmation_per_keystroke(self):
        self.activate();self.page.locator('[data-act=start]').click();f=self.form();f.locator('[data-rich-action=toggle]').click();self.fill_rows(f,'80','10');f.locator('[data-row="2"][data-field=reps]').fill('9')
        self.confirm=True;f.locator('[data-quick=kg]').fill('90');self.confirm=False;f.locator('[data-quick=reps]').fill('12')
        expect(f.locator('[data-row="2"][data-field=reps]')).to_have_value('9');expect(f.locator('[data-row="0"][data-field=kg]')).to_have_value('90')
        self.confirm=True;f.locator('[data-quick=reps]').press_sequentially('2')
        expect(f.locator('[data-row="2"][data-field=reps]')).to_have_value('102')
        self.save_form(f);self.assertEqual([r['segments'][0]['reps'] for r in self.state()['entries'][-1]['performance']['rows']],['102']*3)

    def test_legacy_quick_typing_preserves_individual_reps_and_asks_once_per_edit(self):
        self.start();self.result('80','10');f=self.page.locator('.seriesResultForm')
        f.locator('[data-series-toggle]').click();f.locator('[data-series-index="2"][data-field=reps]').fill('9')
        confirmations=[];self.page.on('dialog',lambda d:confirmations.append(d.message) if d.type=='confirm' else None)
        f.locator('[data-main=kg]').fill('');f.locator('[data-main=kg]').press_sequentially('90')
        self.assertEqual(len(confirmations),1)
        self.confirm=False;f.locator('[data-main=reps]').fill('12')
        self.assertEqual(len(confirmations),2)
        expect(f.locator('[data-main=reps]')).to_have_value('10')
        self.assertEqual(f.locator('[data-field=reps]').evaluate_all('(els)=>els.map(e=>e.value)'),['10','10','9'])
        f.locator('[data-series-toggle]').click();self.save()
        self.assertEqual([r['reps'] for r in self.state()['entries'][-1]['series']],['10','10','9'])
        self.assertEqual([r['kg'] for r in self.state()['entries'][-1]['series']],['90']*3)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible()
        self.assertEqual([r['reps'] for r in self.state()['entries'][-1]['series']],['10','10','9'])

    def test_structural_series_edits_are_durable_drafts_without_a_followup_keystroke(self):
        self.activate();self.page.locator('[data-act=start]').click();f=self.form()
        f.locator('[data-quick=kg]').fill('80');f.locator('[data-quick=reps]').fill('10')
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        f.locator('[data-rich-action=toggle]').click();f.locator('[data-rich-action=remove-set][data-row="1"]').click()
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        drafts=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')
        self.assertEqual(len(drafts[0]['value']['performance']['rows']),2)
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        self.assertEqual(f.locator('[data-field=reps]').count(),2)
        f.locator('[data-rich-action=add-set]').click()
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.reload();self.ready();self.page.locator('[data-draft-resume]').click();f=self.page.locator('.performanceForm')
        self.assertEqual(f.locator('[data-field=reps]').count(),3)
        expect(f.locator('[data-row="2"][data-field=reps]')).to_have_value('')
        expect(f.locator('[data-row="2"][data-field=kg]')).to_have_value('')

    def test_legacy_add_remove_without_typing_survives_restart_without_approving_a_result(self):
        self.start();self.result('80','10');f=self.page.locator('.seriesResultForm');f.locator('[data-series-toggle]').click()
        f.locator('[data-series-remove="0"]').click()
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        drafts=self.page.evaluate('async()=>{const db=await PushPullDB.open(()=>{});try{return await db.readDrafts()}finally{db.close()}}')
        self.assertEqual(len(drafts[0]['value']['series']),2)
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.page.locator('[data-draft-resume]').click()
        f=self.page.locator('.seriesResultForm');self.assertEqual(f.locator('[data-field=reps]').count(),2)
        f.locator('[data-series-add]').click()
        expect(f.locator('[data-draft-status]')).to_contain_text('Szkic zapisany lokalnie')
        self.page.reload();expect(self.page.locator('[data-act=finish]')).to_be_visible();self.page.locator('[data-draft-resume]').click()
        f=self.page.locator('.seriesResultForm');self.assertEqual(f.locator('[data-field=reps]').count(),3)
        self.assertEqual(f.locator('[data-field=reps]').evaluate_all('(els)=>els.map(e=>e.value)'),['10']*3)
        self.assertEqual(self.state()['entries'],[])
