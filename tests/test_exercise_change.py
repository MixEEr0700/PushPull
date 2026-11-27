from datetime import datetime
from playwright.sync_api import expect
from test_browser import BrowserHarness, open_result_panel, wait_for_service_worker_controller


class ExerciseChange(BrowserHarness):
    def test_changes_survive_saves_restart_and_historical_edit_offline(self):
        self.context.close()
        self.context = self.new_context(service_workers='allow')
        self.page = self.context.new_page()
        self.page.on('dialog',self.dialog)
        self.page.goto(self.url)
        self.page.clock.set_fixed_time(datetime.fromisoformat('2026-10-21T10:00:00+02:00'))
        wait_for_service_worker_controller(self.page)
        self.context.set_offline(True)
        self.start()
        page=self.page
        header=page.locator('[data-expand="PUSH-A-1"]')
        label=header.locator('[data-result-change]')
        header.click()
        open_result_panel(page)
        form=page.locator('.seriesResultForm')
        form.locator('[data-main=kg]').fill('40')
        form.locator('[data-main=reps]').fill('8')
        self.save()

        def changes():
            return self.state()['changes'].get('PUSH-A-1',[])

        def stats():
            page.locator('[data-panel=stats][data-id="PUSH-A-1"]').click()

        def mark(text, intermediate=None):
            panel=page.locator('.changeForm')
            if not panel.is_visible():page.get_by_text('＋ Oznacz zmianę',exact=True).click()
            if intermediate:panel.locator('textarea').fill(intermediate)
            panel.locator('textarea').fill(text)
            panel.locator('button').click()

        stats()
        self.assertEqual(changes(),[])
        mark('Łokcie bliżej')
        expect(page.get_by_text('Zmiana oznaczona',exact=True)).to_be_visible()
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        self.assertEqual(len(changes()),1)
        for text,temp in [('  Łokcie  bliżej  ',None),('Łokcie bliżej','Tymczasowy opis'),('Łokcie bliżej',None)]:
            mark(text,temp)
            expect(page.get_by_text('Brak nowej zmiany',exact=True)).to_be_visible()
            self.assertEqual(len(changes()),1)
        mark('Łokcie bliżej ławki')
        expect(page.get_by_text('Zmiana oznaczona',exact=True)).to_be_visible()
        self.assertEqual(len(changes()),2)
        expect(page.locator('.stat-chart line[stroke="#dfa44d"]')).to_have_count(2)
        page.locator('[data-panel=result][data-id="PUSH-A-1"]').click()
        form.locator('[data-main=kg]').fill('42')
        form.locator('[data-main=reps]').fill('9')
        self.save()
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        self.assertEqual(len(changes()),2)
        page.reload()
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        page.locator('[data-act=finish]').click()
        expect(page.locator('[data-act=start]')).to_be_visible()
        self.assertEqual(len(changes()),2)

        page.clock.set_fixed_time(datetime.fromisoformat('2026-10-22T10:00:00+02:00'))
        page.locator('[data-type="PUSH A"]').click()
        self.start('2026-10-22')
        expect(label).to_have_text('· Ostatnia zmiana: wczoraj')
        header.click()
        # Close the default editor by saving an unchanged result.
        self.save()
        stats()
        before=changes()
        page.evaluate("""()=>{window.originalPut=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(row,...rest){
          if(this.name==='journalState')this.transaction.abort();
          return originalPut.call(this,row,...rest);
        }}""")
        with page.expect_event('dialog',predicate=lambda d:d.type=='alert'):
            mark('Zapis nieudany')
        self.assertEqual(changes(),before)
        expect(label).to_have_text('· Ostatnia zmiana: wczoraj')
        page.evaluate('() => { IDBObjectStore.prototype.put=window.originalPut }')

        page.locator('[data-tab=calendar]').click()
        page.locator('[data-day="2026-10-21"]').click()
        page.locator('[data-act=openSession]').click()
        if header.get_attribute('aria-expanded')=='false':header.click()
        if page.locator('.historicalResultForm,.seriesResultForm').is_visible():
            form.locator('[data-main=kg]').fill('43')
            self.save()
        self.assertEqual(changes(),before)
        stats()
        page.get_by_text('＋ Oznacz zmianę',exact=True).click()
        expect(page.locator('.changeForm input[name=date]')).to_have_value('2026-10-21')
        mark('Doprecyzowanie z poprzedniego treningu')
        expect(page.get_by_text('Zmiana oznaczona',exact=True)).to_be_visible()
        expect(page.locator('.stat-chart line[stroke="#dfa44d"]')).to_have_count(3)
        self.assertEqual([c['date'] for c in changes()],['2026-10-21']*3)
        page.locator('[data-tab=training]').click()
        expect(label).to_have_text('· Ostatnia zmiana: wczoraj')
