from datetime import datetime

from playwright.sync_api import expect

from test_browser import BrowserHarness, open_result_panel
import test_v2_training as v2


class ActiveResultChange(BrowserHarness):
    activate = v2.V2Training.activate
    prepare = v2.V2Training.prepare
    ready = v2.V2Training.ready
    save_form = v2.V2Training.save_form

    def test_result_changes_in_active_session_and_history(self):
        self.activate()
        page = self.page
        exercise = 'PULL-A-1'
        header = page.locator(f'[data-expand="{exercise}"]')
        card = page.locator('.exercise-card').filter(has=header)
        label = header.locator('[data-result-change]')

        def clock(day):
            page.clock.set_fixed_time(datetime.fromisoformat(f'2026-10-{day:02d}T08:00:00+02:00'))

        def open_form(*, details=False):
            if header.get_attribute('aria-expanded') == 'false':
                header.click()
            open_result_panel(card)
            form = card.locator('.performanceForm')
            if details and not form.locator('[data-rich-details]').is_visible():
                form.locator('[data-rich-action=toggle]').click()
            return form

        def start(day):
            clock(day)
            page.locator('[data-type="PULL A"]').click()
            self.start(f'2026-10-{day:02d}')
            return self.state()['activeId']

        def finish():
            page.locator('[data-act=finish]').click()
            expect(page.locator('[data-act=start]')).to_be_visible()

        def entry(sid):
            return next((e for e in self.state()['entries'] if e['sessionId'] == sid and e['exerciseId'] == exercise), None)

        def quick(form, field, value):
            form.locator(f'[data-quick={field}]').fill(value)

        for day, kg in [(19, '95'), (20, '100')]:
            start(day)
            form = open_form()
            form.locator('[data-load-basis]').select_option('per-implement')
            quick(form, 'kg', kg)
            quick(form, 'reps', '10')
            self.save_form(form)
            finish()

        sid = start(21)
        expect(label).to_contain_text('1 sesję temu')
        form = open_form()
        self.save_form(form)
        self.assertNotIn('resultChangedOn', entry(sid))
        expect(label).to_contain_text('1 sesję temu')

        form = open_form()
        quick(form, 'kg', '107')
        quick(form, 'kg', '100.00')
        self.save_form(form)
        self.assertNotIn('resultChangedOn', entry(sid))
        expect(label).to_contain_text('1 sesję temu')

        before = entry(sid)
        form = open_form()
        quick(form, 'kg', '105')
        page.evaluate("""() => {
          window.realPut = IDBObjectStore.prototype.put;
          IDBObjectStore.prototype.put = function(row, ...args) {
            if (this.name === 'journalState' && row.id === 'active') this.transaction.abort();
            return window.realPut.call(this, row, ...args);
          };
        }""")
        with page.expect_event('dialog', predicate=lambda d: d.type == 'alert'):
            form.locator('[type=submit]').click()
        expect(label).to_contain_text('1 sesję temu')
        self.assertEqual(entry(sid), before)
        page.evaluate('() => { IDBObjectStore.prototype.put = window.realPut; }')

        form = open_form()
        quick(form, 'kg', '105')
        self.save_form(form)
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        saved = entry(sid)
        self.assertEqual((str(saved['kg']), str(saved['reps']), saved['resultChangedOn']), ('105', '10', '2026-10-21'))
        self.assertEqual(self.state()['changes'].get(exercise, []), [])
        page.reload()
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        self.assertEqual(entry(sid), saved)

        # Resaving the same values on a later local day must not move the date.
        clock(22)
        self.save_form(open_form())
        self.assertEqual(entry(sid)['resultChangedOn'], '2026-10-21')
        expect(label).to_have_text('· Ostatnia zmiana: wczoraj')
        clock(21)
        form = open_form()
        quick(form, 'kg', '100')
        self.save_form(form)
        finish()
        self.assertEqual(sum(e['id'] == saved['id'] for e in self.state()['entries']), 1)

        sid = start(22)
        expect(label).to_contain_text('2 sesje temu')
        form = open_form()
        quick(form, 'reps', '11')
        self.save_form(form)
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        self.assertEqual((str(entry(sid)['kg']), str(entry(sid)['reps'])), ('100', '11'))
        finish()

        sid = start(23)
        form = open_form(details=True)
        form.locator('[data-field=kg][data-segment="0"]').nth(1).fill('107')
        self.save_form(form)
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        before_count = len(entry(sid)['performance']['rows'])

        clock(24)
        form = open_form(details=True)
        form.locator('[data-rich-action=add-set]').click()
        form.locator('[data-field=kg][data-segment="0"]').last.fill('100')
        form.locator('[data-field=reps][data-segment="0"]').last.fill('11')
        self.save_form(form)
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        self.assertEqual(len(entry(sid)['performance']['rows']), before_count + 1)

        clock(25)
        form = open_form(details=True)
        form.locator('[data-rich-action=remove-set]').last.click()
        self.save_form(form)
        expect(label).to_have_text('· Ostatnia zmiana: dziś')
        self.assertEqual(len(entry(sid)['performance']['rows']), before_count)
        finish()

        page.locator('[data-tab=calendar]').click()
        page.locator('[data-day="2026-10-23"]').click()
        page.locator(f'[data-act=openSession][data-id="{sid}"]').click()
        form = open_form(details=True)
        form.locator('[data-field=kg][data-segment="0"]').nth(1).fill('109')
        self.save_form(form)
        self.assertEqual(entry(sid)['resultChangedOn'], '2026-10-23')
        self.assertEqual(self.state()['changes'].get(exercise, []), [])
