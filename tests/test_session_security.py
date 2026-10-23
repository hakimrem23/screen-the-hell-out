"""Synthetic identities, no live OIDC, tokens or private observations."""
from dataclasses import replace
from datetime import datetime,timezone
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from pathlib import Path
from tests.test_adapter import settings,user,User
from v653.github_readonly import authorize
from v653.session_security import enforce_session,clear_private,RECHECK_SECONDS
from v653.records import Unverified
from v653.preview import preview

class IdentitySecurityTests(unittest.TestCase):
    def setUp(self):
        self.cfg=settings();self.u=user();self.now=datetime.now(timezone.utc).timestamp()
    def test_fresh_approved_identity_accepted(self):self.assertGreater(authorize(self.cfg,self.u,now=self.now).expires_at,self.now)
    def test_missing_expiry_and_issued_at_denied(self):
        for field in ['iat','exp']:
            u=User(self.u);del u[field]
            with self.subTest(field=field),self.assertRaises(Unverified):authorize(self.cfg,u,now=self.now)
    def test_bad_claim_numeric_types_denied(self):
        for field in ['iat','exp']:
            for v in [None,True,'123',float('inf'),float('nan')]:
                u=User(self.u);u[field]=v
                with self.subTest(field=field,value=str(v)),self.assertRaises(Unverified):authorize(self.cfg,u,now=self.now)
    def test_expired_identity_denied_at_boundary(self):
        self.u['exp']=self.now
        with self.assertRaises(Unverified):authorize(self.cfg,self.u,now=self.now)
    def test_future_issuance_denied(self):
        self.u['iat']=self.now+1
        with self.assertRaises(Unverified):authorize(self.cfg,self.u,now=self.now)
    def test_inverted_lifetime_denied(self):
        self.u.update(iat=self.now-1,exp=self.now-2)
        with self.assertRaises(Unverified):authorize(self.cfg,self.u,now=self.now)
    def test_max_age_denied_even_if_idp_cookie_lives(self):
        self.u['iat']=self.now-3601
        with self.assertRaises(Unverified):authorize(self.cfg,self.u,now=self.now)
    def test_invalid_max_age_policy_denied(self):
        for v in [True,0,59,86401,'3600']:
            cfg=dict(self.cfg,max_session_age_seconds=v)
            with self.subTest(value=v),self.assertRaises(Unverified):authorize(cfg,self.u,now=self.now)
    def test_wrong_issuer_audience_authorized_party_denied(self):
        for k,v in [('iss','https://attacker.example.test'),('aud','wrong'),('azp','wrong'),('sub','')]:
            u=User(self.u);u[k]=v
            with self.subTest(field=k),self.assertRaises(Unverified):authorize(self.cfg,u,now=self.now)
    def test_multiple_audiences_require_reviewed_client_and_party(self):
        self.u.update(aud=['synthetic-client','other'],azp='synthetic-client');self.assertTrue(authorize(self.cfg,self.u,now=self.now))
    def test_missing_trust_configuration_denied(self):
        for k in ['oidc_issuer','oidc_client_id','credential_generation','session_generation','auth_not_before_utc']:
            cfg=dict(self.cfg);del cfg[k]
            with self.subTest(field=k),self.assertRaises(Unverified):authorize(cfg,self.u,now=self.now)
    def test_old_cookie_denied_after_rotation_cutoff_in_new_session(self):
        self.cfg['auth_not_before_utc']=datetime.fromtimestamp(self.now-10,timezone.utc).isoformat()
        with self.assertRaises(Unverified):authorize(self.cfg,self.u,now=self.now)
    def test_future_rotation_cutoff_denied(self):
        self.cfg['auth_not_before_utc']=datetime.fromtimestamp(self.now+60,timezone.utc).isoformat()
        with self.assertRaises(Unverified):authorize(self.cfg,self.u,now=self.now)
    def test_token_rotation_immediately_invalidates_cached_record(self):
        a=authorize(self.cfg,self.u,now=self.now);state={};enforce_session(state,a,now=self.now)
        state['v653_private_record']={'sensitive':'synthetic only'};self.cfg['github_token']='SYNTHETIC_ROTATED_TOKEN'
        with self.assertRaisesRegex(Unverified,'REAUTHENTICATION'):enforce_session(state,authorize(self.cfg,self.u,now=self.now),now=self.now)
        self.assertNotIn('v653_private_record',state)
    def test_same_token_generation_rotation_also_invalidates_session(self):
        for field in ['credential_generation','session_generation']:
            state={};a=authorize(self.cfg,self.u,now=self.now);enforce_session(state,a,now=self.now);cfg=dict(self.cfg);cfg[field]='rotated'
            with self.subTest(field=field),self.assertRaises(Unverified):enforce_session(state,authorize(cfg,self.u,now=self.now),now=self.now)
    def test_old_identity_cannot_retry_through_rotation_gate(self):
        state={};a=authorize(self.cfg,self.u,now=self.now);enforce_session(state,a,now=self.now);rotated=replace(a,credential_key='changed')
        for _ in range(2):
            with self.assertRaises(Unverified):enforce_session(state,rotated,now=self.now)
    def test_fresh_login_after_rotation_is_accepted(self):
        state={};a=authorize(self.cfg,self.u,now=self.now);enforce_session(state,a,now=self.now);rotated=replace(a,credential_key='changed')
        with self.assertRaises(Unverified):enforce_session(state,rotated,now=self.now)
        self.assertTrue(enforce_session(state,replace(rotated,issued_at=self.now+1),now=self.now+2))
    def test_already_fresh_login_after_rotation_does_not_loop(self):
        state={};a=authorize(self.cfg,self.u,now=self.now);enforce_session(state,a,now=self.now)
        fresh=replace(a,credential_key='rotated',issued_at=self.now-1)
        self.assertTrue(enforce_session(state,fresh,now=self.now))
    def test_identity_switch_clears_previous_viewer_cache(self):
        state={};a=authorize(self.cfg,self.u,now=self.now);enforce_session(state,a,now=self.now);state['v653_private_record']={'private':'synthetic'}
        enforce_session(state,replace(a,identity_key='different-allowed-user'),now=self.now)
        self.assertNotIn('v653_private_record',state)
    def test_cache_digest_contains_no_raw_credential_or_email(self):
        a=authorize(self.cfg,self.u,now=self.now);state={};enforce_session(state,a,now=self.now)
        self.assertNotIn('SYNTHETIC_TEST_TOKEN',str(state));self.assertNotIn(self.u['email'],str(state))
    def test_expired_receipt_cannot_access_cache(self):
        a=authorize(self.cfg,self.u,now=self.now)
        with self.assertRaises(Unverified):enforce_session({},a,now=a.expires_at)
    def test_logout_clears_private_fields_but_preserves_v5(self):
        state={k:'fixture' for k in ['v653_private_record','v653_private_session','v653_reauth_boundary','v653_ticker','v653_category','nav_v5','detail_row_v5']};clear_private(state)
        self.assertEqual(set(state),{'nav_v5','detail_row_v5'})
    def test_periodic_private_recheck_interval(self):self.assertEqual(RECHECK_SECONDS,30)

class SecurityUITests(unittest.TestCase):
    def setUp(self):
        self.u=user();self.cfg=settings();self.p=preview();self.p.update(synthetic=False,freshness='STALE',record_status='VERIFIED RECORDS')
    def app(self):
        app=Path(__file__).resolve().parents[1]/'app.py';at=AppTest.from_file(str(app),default_timeout=20).run();at.radio(key='nav_v5').set_value('V6.5.3 Screening').run();return at
    def test_expired_user_never_fetches_or_renders_private_rows(self):
        self.u['exp']=1
        with patch('v653.ui.settings',return_value=self.cfg),patch('streamlit.user',self.u),patch('v653.ui.load_latest') as fetch:
            at=self.app();self.assertFalse(at.exception);self.assertFalse(at.selectbox);fetch.assert_not_called();self.assertTrue(any('locked' in x.value for x in at.warning))
    def test_explicit_signout_clears_records_and_calls_logout(self):
        with patch('v653.ui.settings',return_value=self.cfg),patch('streamlit.user',self.u),patch('v653.ui.load_latest',return_value=self.p),patch('streamlit.logout') as logout:
            at=self.app();self.assertTrue(at.selectbox);at.button(key='v653_signout').click().run();logout.assert_called_once();self.assertFalse(at.selectbox);self.assertNotIn('v653_private_record',at.session_state)
    def test_expiry_during_network_read_withholds_retrieved_data(self):
        a=authorize(self.cfg,self.u)
        with patch('v653.ui.settings',return_value=self.cfg),patch('streamlit.user',self.u),patch('v653.ui.authorize',side_effect=[a,Unverified('IDENTITY_EXPIRED_OR_INVALID')]),patch('v653.ui.load_latest',return_value=self.p):
            at=self.app();self.assertFalse(at.selectbox);self.assertNotIn('v653_private_record',at.session_state)
    def test_live_token_change_denies_old_session_before_refetch(self):
        with patch('v653.ui.settings',side_effect=lambda *_:dict(self.cfg)),patch('streamlit.user',self.u),patch('v653.ui.load_latest',return_value=self.p) as fetch:
            at=self.app();self.assertTrue(at.selectbox);self.cfg['github_token']='SYNTHETIC_ROTATED_TOKEN';at.run();self.assertFalse(at.selectbox);self.assertEqual(fetch.call_count,1)
    def test_unauthorized_user_has_signout_but_no_fetch(self):
        self.u['email']='unauthorized@example.test'
        with patch('v653.ui.settings',return_value=self.cfg),patch('streamlit.user',self.u),patch('v653.ui.load_latest') as fetch:
            at=self.app();self.assertFalse(at.selectbox);fetch.assert_not_called();self.assertTrue(at.button(key='v653_signout'))
