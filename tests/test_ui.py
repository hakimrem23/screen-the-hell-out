"""Real Streamlit AppTest; all remote calls blocked, all V6.5.3 data invented."""
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from v653.preview import preview
from v653.records import Unverified
from tests.test_adapter import settings,user

APP=str(Path(__file__).resolve().parents[1]/'app.py')
class UITests(unittest.TestCase):
    def setUp(self):
        self.network=patch('v653.ui.load_latest',side_effect=AssertionError('private network forbidden'));self.network.start();self.addCleanup(self.network.stop)
        self.quotes=patch('yfinance.Ticker',side_effect=AssertionError('quotes forbidden'));self.quotes.start();self.addCleanup(self.quotes.stop)
    def app(self):return AppTest.from_file(APP,default_timeout=20).run()
    def v6(self):
        at=self.app();at.radio(key='nav_v5').set_value('V6.5.3 Screening').run();self.assertFalse(at.exception);return at
    def test_v5_navigation_and_no_network_on_existing_sections(self):
        at=self.app()
        for name in ['Discover','Watchlist','Deep Dive','Syariah']:
            at.radio(key='nav_v5').set_value(name).run();self.assertFalse(at.exception)
    def test_default_synthetic_preview_uses_no_token_or_engine_calls(self):
        at=self.v6();self.assertTrue(any('SYNTHETIC PREVIEW' in i.value for i in at.info));self.assertEqual(at.selectbox(key='v653_ticker').options,['DEMOA'])
    def test_zero_qualified_day_is_honest(self):
        at=self.v6();at.checkbox(key='v653_zero_preview').check().run();self.assertTrue(any(i.value=='No qualified setups.' for i in at.info));self.assertFalse(at.exception)
    def test_all_categories_and_incomplete_data_render(self):
        at=self.v6()
        for category in ['WATCHLIST','REJECTED','DATA UNAVAILABLE']:
            at.selectbox(key='v653_category').set_value(category).run();self.assertFalse(at.exception)
        self.assertTrue(any('DEMOD' in x.value for x in at.text));self.assertTrue(any('UNVERIFIED' in x.value for x in at.text))
    def test_repeat_render_is_consistent(self):
        at=self.v6();before=[x.value for x in at.text];at.run();self.assertEqual([x.value for x in at.text],before)
    def test_pending_entry_has_no_invented_price(self):
        at=self.v6();at.selectbox(key='v653_category').set_value('WATCHLIST').run()
        self.assertTrue(any('Observed entry reference: —'==x.value for x in at.text));self.assertTrue(any('Initial stop reference: —'==x.value for x in at.text))
    def test_private_config_without_login_is_locked_before_network(self):
        with patch('v653.ui.settings',return_value=settings()):
            at=self.v6();self.assertTrue(any('Private results are locked' in x.value for x in at.warning));self.assertFalse(at.selectbox)
    def test_approved_private_view_renders_only_after_authorization(self):
        # Still synthetic; no real credentials, records or private access in this test.
        p=preview();p.update(synthetic=False,freshness='STALE',record_status='VERIFIED RECORDS')
        from v653.github_readonly import authorize
        access=authorize(settings(),user())
        with patch('v653.ui.settings',return_value=settings()),patch('v653.ui.authorize',return_value=access),patch('v653.ui.load_latest',return_value=p):
            at=self.v6();self.assertTrue(any('STALE' in x.value for x in at.warning));self.assertFalse(at.exception)
    def test_private_load_failure_does_not_display_secret_or_old_result(self):
        from v653.github_readonly import authorize
        with patch('v653.ui.settings',return_value=settings()),patch('v653.ui.authorize',return_value=authorize(settings(),user())),patch('v653.ui.load_latest',side_effect=RuntimeError('SYNTHETIC_TEST_TOKEN')):
            at=self.v6();self.assertTrue(any('UNVERIFIED' in x.value for x in at.error));self.assertFalse(at.selectbox);self.assertFalse(at.exception)
            self.assertNotIn('SYNTHETIC_TEST_TOKEN',' '.join(x.value for x in at.error))
    def test_html_like_reasons_are_not_unsafe_markdown(self):
        p=preview();p['screen']['rows'][0]['reasons']=['<script>synthetic()</script>']
        with patch('v653.ui.preview',return_value=p):
            at=self.v6();self.assertTrue(any('<script>synthetic()</script>' in x.value for x in at.text));self.assertFalse(at.exception)

    def test_failing_refresh_removes_previously_displayed_private_data(self):
        from v653.github_readonly import authorize
        p=preview();p.update(synthetic=False,freshness='STALE',record_status='VERIFIED RECORDS')
        with patch('v653.ui.settings',return_value=settings()),patch('v653.ui.authorize',return_value=authorize(settings(),user())),patch('v653.ui.load_latest',side_effect=[p,RuntimeError('SYNTHETIC_TEST_TOKEN')]):
            at=self.v6();self.assertTrue(at.selectbox);at.button(key='v653_refresh').click().run()
            self.assertFalse(at.selectbox);self.assertTrue(at.error);self.assertNotIn('v653_private_record',at.session_state)
    def test_access_revocation_removes_cached_data_before_any_network(self):
        from v653.github_readonly import authorize
        p=preview();p.update(synthetic=False,freshness='STALE',record_status='VERIFIED RECORDS')
        with patch('v653.ui.settings',return_value=settings()),patch('v653.ui.authorize',side_effect=[authorize(settings(),user()),Unverified('IDENTITY_NOT_AUTHORIZED')]),patch('v653.ui.load_latest',return_value=p) as fetch:
            at=self.v6();at.run();self.assertFalse(at.selectbox);self.assertEqual(fetch.call_count,1);self.assertNotIn('v653_private_record',at.session_state)
