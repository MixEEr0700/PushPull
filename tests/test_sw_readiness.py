"""Native readiness requires a real controller, not merely an active registration."""
from test_browser import BrowserHarness,wait_for_service_worker_controller

class ServiceWorkerReadiness(BrowserHarness):
    def uncontrolled_probe(self):
        context=self.new_context(service_workers='allow')
        page=context.new_page();page.goto(self.url+'tests/fixtures/')
        page.evaluate("async()=>{await navigator.serviceWorker.register('./controller-claim-probe.js');await navigator.serviceWorker.ready}")
        self.assertFalse(page.evaluate('!!navigator.serviceWorker.controller'))
        session=context.new_cdp_session(page)
        session.send('Emulation.setVirtualTimePolicy',{'policy':'pause'})
        return page

    def test_active_registration_without_controller_is_rejected(self):
        page=self.uncontrolled_probe()
        # A fulfilled ready promise is deliberately insufficient. The helper
        # must fail rather than claim the page or accept activation alone.
        with self.assertRaisesRegex(AssertionError,'did not control'):
            wait_for_service_worker_controller(page,timeout=100)
        self.assertFalse(page.evaluate('!!navigator.serviceWorker.controller'))
        self.assertEqual(page.evaluate('async()=>(await navigator.serviceWorker.getRegistration()).active.state'),'activated')

    def test_native_poll_waits_for_real_claim_with_paused_page_clock(self):
        page=self.uncontrolled_probe()
        page.evaluate("navigator.serviceWorker.ready.then(r=>r.active.postMessage('claim'))")
        wait_for_service_worker_controller(page)
        self.assertTrue(page.evaluate('!!navigator.serviceWorker.controller'))
        self.assertEqual(page.evaluate('async()=>(await navigator.serviceWorker.getRegistration()).active.state'),'activated')
