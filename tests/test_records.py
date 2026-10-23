"""Only invented payloads. No private repository samples or credentials."""
from copy import deepcopy
from datetime import datetime,timezone
import unittest
from v653.preview import fixture,encode
from v653.records import verify,Unverified,sha,read_json,latest_ready

NOW=datetime(2000,1,4,tzinfo=timezone.utc)

def rehash(p,a,b):
    seal=read_json(b['seal.json']);seal['files_sha256']={n:sha(v) for n,v in b.items() if n!='seal.json'};b['seal.json']=encode(seal)
    p['track_b_seal_sha256']=sha(b['seal.json']);binding=read_json(a['binding.json']);binding['track_b_seal_sha256']=p['track_b_seal_sha256'];a['binding.json']=encode(binding)
    hashes={n:sha(v) for n,v in a.items() if n!='SHA256SUMS.json'};a['SHA256SUMS.json']=encode(hashes);p['screen_files_sha256']=hashes

class RecordsTests(unittest.TestCase):
    def setUp(self):self.p,self.a,self.b,self.source,self.protocol=fixture()
    def result(self,expected='2000-01-03'):
        return verify(self.p,self.a,self.b,self.source,self.protocol,NOW,expected)
    def test_verified_records_are_not_price_certification(self):
        r=self.result();self.assertEqual(r['record_status'],'VERIFIED RECORDS');self.assertEqual(r['freshness'],'CURRENT');self.assertTrue(r['warnings'])
    def test_stale_when_newer_exchange_session_expected(self):self.assertEqual(self.result('2000-01-04')['freshness'],'STALE')
    def test_future_session_not_exposed(self):
        with self.assertRaises(Unverified):self.result('1999-12-31')
    def test_hash_tamper(self):
        self.a['screen.json']+=b' '
        with self.assertRaisesRegex(Unverified,'HASH'):self.result()
    def test_journal_tamper(self):
        self.b['events.json']=b'corrupt'
        with self.assertRaisesRegex(Unverified,'HASH'):self.result()
    def test_missing_track_a_file(self):
        del self.a['screen.csv']
        with self.assertRaisesRegex(Unverified,'INVENTORY'):self.result()
    def test_missing_track_b_file(self):
        del self.b['state.json']
        with self.assertRaisesRegex(Unverified,'INVENTORY'):self.result()
    def test_uninventoried_data_rejected(self):
        self.a['extra.json']=b'{}'
        with self.assertRaisesRegex(Unverified,'INVENTORY'):self.result()
    def test_cross_track_session_mismatch(self):
        d=read_json(self.b['daily.json']);d['session']='1999-12-31';self.b['daily.json']=encode(d);rehash(self.p,self.a,self.b)
        with self.assertRaisesRegex(Unverified,'SESSION'):self.result()
    def test_source_mismatch(self):
        s=read_json(self.a['screen.json']);s['source_sha']='9'*40;self.a['screen.json']=encode(s);rehash(self.p,self.a,self.b)
        with self.assertRaisesRegex(Unverified,'SOURCE'):self.result()
    def test_source_not_owner_pinned(self):
        self.source='9'*40
        with self.assertRaisesRegex(Unverified,'UNAPPROVED_SOURCE'):self.result()
    def test_mismatched_activation_receipt(self):
        d=read_json(self.b['daily.json']);d['activation_receipt']['approved_by']='someone';self.b['daily.json']=encode(d);rehash(self.p,self.a,self.b)
        with self.assertRaisesRegex(Unverified,'ACTIVATION'):self.result()
    def test_snapshot_mismatch(self):
        self.b['data-manifest.json']+=b' ';rehash(self.p,self.a,self.b)
        with self.assertRaisesRegex(Unverified,'SNAPSHOT'):self.result()
    def test_category_counts_must_come_from_rows(self):
        s=read_json(self.a['screen.json']);s['categories_by_unique_ticker']['QUALIFIED SETUP']=99;self.a['screen.json']=encode(s);rehash(self.p,self.a,self.b)
        with self.assertRaisesRegex(Unverified,'CATEGORY_COUNT'):self.result()
    def test_missing_model_cannot_claim_complete_coverage(self):
        s=read_json(self.a['screen.json']);s['rows'].pop();self.a['screen.json']=encode(s);rehash(self.p,self.a,self.b)
        with self.assertRaisesRegex(Unverified,'MODEL_COVERAGE'):self.result()
    def test_pending_setup_cannot_be_qualified(self):
        s=read_json(self.a['screen.json']);s['rows'][0]['next_open_gates_pending']=True;self.a['screen.json']=encode(s);rehash(self.p,self.a,self.b)
        with self.assertRaisesRegex(Unverified,'UNCONFIRMED'):self.result()
    def test_qualified_missing_or_negative_risk_is_not_presented(self):
        for entry,stop in [(None,None),(100,101),(True,0.5)]:
            p,a,b,source,protocol=fixture();s=read_json(a['screen.json']);s['rows'][0].update(entry_price=entry,initial_stop_loss=stop);a['screen.json']=encode(s);rehash(p,a,b)
            with self.subTest(entry=entry),self.assertRaisesRegex(Unverified,'RISK'):verify(p,a,b,source,protocol,NOW,'2000-01-03')
    def test_zero_qualified_is_valid(self):
        p,a,b,s,h=fixture(False);r=verify(p,a,b,s,h,NOW,'2000-01-03');self.assertEqual(r['screen']['categories_by_unique_ticker']['QUALIFIED SETUP'],0)
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(Unverified):read_json(b'{"x":1,"x":2}')
    def test_nonfinite_json_rejected(self):
        for value in [b'NaN',b'Infinity',b'-Infinity']:
            with self.subTest(value=value),self.assertRaises(Unverified):read_json(value)
    def test_byte_identical_repeat_and_no_mutation(self):
        before=deepcopy((self.p,self.a,self.b));self.assertEqual(self.result(),self.result());self.assertEqual((self.p,self.a,self.b),before)
    def test_observation_after_verification_rejected(self):
        self.p['verified_at_utc']='2000-01-03T21:00:00Z'
        with self.assertRaisesRegex(Unverified,'TIME'):self.result()
    def test_calendar_holiday_weekend_early_close_dst(self):
        cases=[('2025-07-04T23:00:00+00:00','2025-07-03'),('2025-07-05T23:00:00+00:00','2025-07-03'),
               ('2025-11-28T18:29:00+00:00','2025-11-26'),('2025-11-28T18:30:00+00:00','2025-11-28'),
               ('2025-03-10T20:29:00+00:00','2025-03-07'),('2025-03-10T20:30:00+00:00','2025-03-10')]
        for now,expected in cases:
            with self.subTest(now=now):self.assertEqual(latest_ready(datetime.fromisoformat(now)),expected)
