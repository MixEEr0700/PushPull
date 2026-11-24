"""Mobile viewport geometry for the existing Matrix workout cards."""
from playwright.sync_api import expect
from test_browser import BrowserHarness, open_result_panel
import test_v2_training as versioned


class ExerciseScroll174(BrowserHarness):
    activate = versioned.V2Training.activate
    prepare = versioned.V2Training.prepare
    ready = versioned.V2Training.ready

    def new_context(self, **options):
        return super().new_context(is_mobile=True, has_touch=True, **options)

    def toggle_at(self, header, offset, expanded, *, touch=False):
        before = header.evaluate("""(button, offset) => {
            window.scrollBy(0, button.getBoundingClientRect().top - offset);
            button.focus({preventScroll:true});
            return button.getBoundingClientRect().top;
        }""", offset)
        if touch:header.tap()
        else:header.press('Enter')
        expect(header).to_have_attribute('aria-expanded', str(expanded).lower())
        after = header.evaluate("""button => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => {
            const top = button.getBoundingClientRect().top;
            resolve({top, pageTop:top + scrollY, max:document.scrollingElement.scrollHeight - innerHeight});
        })))""")
        expected = after['pageTop'] - max(0, min(after['max'], after['pageTop'] - before))
        self.assertAlmostEqual(after['top'], expected, delta=2, msg=(before, after, offset))
        if not touch:expect(header).to_be_focused()

    def test_legacy_long_card_switch_and_document_end_at_three_widths(self):
        self.start()
        headers = self.page.locator('[data-expand]')
        for width in (360, 390, 412):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width':width,'height':680})
                a,b = headers.nth(3),headers.nth(4)
                for offset in (110, 405):
                    self.toggle_at(a,offset,True)
                    editor = self.page.locator('.seriesResultForm')
                    if not editor.locator('[data-series-add]').is_visible():
                        editor.locator('[data-series-toggle]').click()
                    for _ in range(max(0, 11-editor.locator('[data-series-remove]').count())):
                        editor.locator('[data-series-add]').click()
                    self.toggle_at(b,offset,True)
                    expect(a).to_have_attribute('aria-expanded','false')
                    self.toggle_at(b,offset,False)
                self.toggle_at(a,150,True,touch=True)
                self.toggle_at(a,150,False,touch=True)
                self.toggle_at(headers.last,475,True)
                self.toggle_at(headers.last,210,False)

    def test_versioned_input_draft_style_and_saved_result(self):
        self.activate()
        self.start()
        self.page.set_viewport_size({'width':390,'height':820})
        header = self.page.locator('[data-expand]').nth(2)
        card = header.locator('xpath=ancestor::section[1]')
        colors = lambda: card.evaluate("(el)=>{const s=getComputedStyle(el);return [s.backgroundColor,s.borderTopColor,s.borderTopWidth]}")
        closed, height = colors(), header.bounding_box()['height']
        self.toggle_at(header,180,True)
        opened = colors()
        self.assertNotEqual(closed[:2],opened[:2])
        self.assertEqual(closed[2],opened[2])
        self.assertEqual(header.bounding_box()['height'],height)
        open_result_panel(card)
        editor = card.locator('.performanceForm')
        kg = editor.locator('[data-quick=kg]')
        editor.locator('[data-quick=reps]').fill('8')
        kg.fill('41')
        expect(kg).to_be_focused()
        # A shorter viewport models reduced space while editing. Android IME
        # behavior itself needs verification on a physical device.
        self.page.set_viewport_size({'width':390,'height':460})
        expect(kg).to_be_focused()
        self.toggle_at(header,95,False)
        self.assertEqual(colors(),closed)
        self.toggle_at(header,135,True)
        expect(kg).to_have_value('41')
        pk = header.get_attribute('data-expand')
        editor.locator('[type=submit]').focus()
        before = header.evaluate('(el)=>el.getBoundingClientRect().top')
        editor.locator('[type=submit]').press('Enter')
        expect(self.page.get_by_text('Wynik zapisany',exact=True)).to_be_visible()
        expect(header).to_be_focused()
        after = header.evaluate('(el)=>el.getBoundingClientRect().top')
        self.assertAlmostEqual(before,after,delta=2)
        self.assertTrue(any(e['exerciseId']==pk and e['kg']=='41' for e in self.state()['entries']))
        self.toggle_at(header,90,False)
        self.toggle_at(header,120,True)
        expect(card.locator('.last-result').first).to_contain_text('41')
