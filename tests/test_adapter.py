import base64
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from v653.github_readonly import Access,GitHub,REPO,authorize,load_latest,proof_from_logs
from v653.preview import fixture,encode
from v653.records import Unverified,read_json

class User(dict):is_logged_in=True

def settings():
    return dict(mode='private',owner_approved_private_access=True,audience='authenticated_private',approval_reference='TEST OWNER APPROVAL',allowed_emails=['reviewer@example.test'],github_token='SYNTHETIC_TEST_TOKEN',approved_source_sha='1'*40,approved_protocol_sha256='2'*64,oidc_issuer='https://identity.example.test',oidc_client_id='synthetic-client',credential_generation='test-1',session_generation='test-1',auth_not_before_utc='2000-01-01T00:00:00Z')

def user():
    now=datetime.now(timezone.utc).timestamp()
    return User(email='reviewer@example.test',email_verified=True,iss='https://identity.example.test',aud='synthetic-client',sub='synthetic-user',iat=now-60,exp=now+3600)

class AuthTests(unittest.TestCase):
    def test_explicit_owner_approval_auth_identity_and_token_required(self):
        a=authorize(settings(),user());self.assertEqual(a.subject,'reviewer@example.test');self.assertNotIn('SYNTHETIC_TEST_TOKEN',repr(a))
    def test_default_preview_cannot_authorize_private_calls(self):
        with self.assertRaises(Unverified):authorize({},user())
    def test_token_alone_cannot_authorize(self):
        with self.assertRaises(Unverified):authorize({'github_token':'SYNTHETIC_TEST_TOKEN'},user())
    def test_missing_approval_and_public_audience_blocked(self):
        for k,v in [('owner_approved_private_access',False),('audience','public'),('approval_reference',''),('github_token',''),('approved_source_sha','main'),('approved_protocol_sha256','missing')]:
            cfg=settings();cfg[k]=v
            with self.subTest(k=k),self.assertRaises(Unverified):authorize(cfg,user())
    def test_anonymous_and_unverified_email_blocked(self):
        for u in [None,{},User(email='reviewer@example.test',email_verified=False),User(email='stranger@example.test',email_verified=True)]:
            with self.subTest(u=u),self.assertRaises(Unverified):authorize(settings(),u)
    def test_empty_allowlist_blocked(self):
        cfg=settings();cfg['allowed_emails']=[]
        with self.assertRaises(Unverified):authorize(cfg,user())

class Response:
    status=200
    def __init__(self,body):self.body=body
    def read(self,limit):return self.body[:limit]
    def __enter__(self):return self
    def __exit__(self,*args):return None
class Opener:
    def __init__(self,body=b'{}',redirect=None):self.body=body;self.redirect=redirect;self.requests=[]
    def open(self,request,timeout):
        self.requests.append(request)
        if self.redirect and len(self.requests)==1:raise HTTPError(request.full_url,302,'redirect',{'Location':self.redirect},None)
        return Response(self.body)

class TransportTests(unittest.TestCase):
    def client(self,opener):return GitHub(Access('SYNTHETIC_TEST_TOKEN','1'*40,'2'*64,'TEST'),opener)
    def test_only_get_to_fixed_github_repository(self):
        op=Opener();self.client(op).get('/actions/workflows/test');self.assertEqual(op.requests[0].method,'GET');self.assertTrue(op.requests[0].full_url.startswith('https://api.github.com/repos/'+REPO+'/'))
    def test_external_api_path_rejected(self):
        for path in ['https://attacker.example.test/','//attacker.example.test/']:
            op=Opener()
            with self.assertRaises(Unverified):self.client(op).get(path)
            self.assertFalse(op.requests)
    def test_redirect_never_leaks_authorization(self):
        op=Opener(b'logs',redirect='https://unit.blob.core.windows.net/logs?synthetic=signed')
        self.assertEqual(self.client(op).get('/actions/jobs/1/logs',logs=True),b'logs')
        self.assertIsNotNone(op.requests[0].get_header('Authorization'));self.assertIsNone(op.requests[1].get_header('Authorization'))
    def test_redirect_to_untrusted_domain_rejected(self):
        op=Opener(redirect='https://attacker.example.test/logs')
        with self.assertRaises(Unverified):self.client(op).get('/actions/jobs/1/logs',logs=True)
        self.assertEqual(len(op.requests),1)
    def test_regular_api_redirect_is_not_followed(self):
        op=Opener(redirect='https://unit.blob.core.windows.net/logs')
        with self.assertRaises(Unverified):self.client(op).get('/contents/a')
        self.assertEqual(len(op.requests),1)
    def test_oversized_body(self):
        with self.assertRaises(Unverified):self.client(Opener(b'123456')).get('',limit=5)
    def test_transport_errors_do_not_echo_credentials(self):
        op=Opener();op.open=lambda *a,**kw:(_ for _ in ()).throw(OSError('SYNTHETIC_TEST_TOKEN'))
        with self.assertRaises(Unverified) as caught:self.client(op).get('')
        self.assertNotIn('SYNTHETIC_TEST_TOKEN',str(caught.exception))
    def test_git_read_is_pinned_and_hash_checked(self):
        body=b'example';blob=hashlib.sha1(b'blob 7\0'+body).hexdigest();obj=dict(type='file',size=len(body),sha=blob,encoding='base64',content=base64.b64encode(body).decode())
        gh=self.client(Opener(encode(obj)));self.assertEqual(gh.file('1'*40,'safe/file'),body)
        with self.assertRaises(Unverified):gh.file('main','safe/file')
        with self.assertRaises(Unverified):gh.file('1'*40,'../file')
    def test_bad_git_blob_hash_is_rejected(self):
        obj=dict(type='file',size=1,sha='1'*40,encoding='base64',content='YQ==')
        with self.assertRaises(Unverified):self.client(Opener(encode(obj))).file('1'*40,'a')
    def test_large_contents_api_uses_git_blob_api(self):
        body=b'example';blob=hashlib.sha1(b'blob 7\0'+body).hexdigest();gh=self.client(Opener());calls=[]
        def js(path):
            calls.append(path)
            return dict(type='file',size=7,sha=blob,encoding='none') if path.startswith('/contents') else dict(encoding='base64',content=base64.b64encode(body).decode())
        gh.json=js;self.assertEqual(gh.file('1'*40,'a'),body);self.assertTrue(calls[1].startswith('/git/blobs/'))
    def test_missing_or_ambiguous_final_proof_rejected(self):
        p,*_=fixture()
        for b in [b'no finalized session',encode(p)+encode(p)]:
            with self.subTest(body=b[:10]),self.assertRaises(Unverified):proof_from_logs(b)

class FakeEngine:
    def __init__(self):
        self.p,self.a,self.b,self.source,self.protocol=fixture();self.access=Access('SYNTHETIC_TEST_TOKEN',self.source,self.protocol,'TEST')
        self.run=dict(id=100,workflow_id=9,path='.github/workflows/stho-paper-dispatch.yml',head_branch='main',status='completed',conclusion='success',event='schedule',head_sha='8'*40,
            run_started_at='2000-01-03T21:30:00Z',updated_at='2000-01-03T22:10:00Z',referenced_workflows=[dict(path=REPO+'/.github/workflows/phase31-daily.yml@'+self.source,sha=self.source)])
        self.dispatcher=('uses: '+REPO+'/.github/workflows/phase31-daily.yml@'+self.source+'\nsource_ref: '+self.source+'\n').encode()
        from v653.records import sha
        self.p['activation_receipt']['approved_dispatcher_sha256']=sha(self.dispatcher)
        # Fixture receipts live in independently encoded bytes; update every binding.
        from tests.test_records import rehash
        for n in ['screen.json','binding.json']:
            d=read_json(self.a[n]);d['activation_receipt']=deepcopy(self.p['activation_receipt']);self.a[n]=encode(d)
        for n in ['daily.json','data-manifest.json']:
            d=read_json(self.b[n]);d['activation_receipt']=deepcopy(self.p['activation_receipt']);self.b[n]=encode(d)
        mh=sha(self.b['data-manifest.json']);self.p['snapshot_manifest_sha256']=mh
        s=read_json(self.a['screen.json']);s['snapshot_manifest_sha256']=mh;self.a['screen.json']=encode(s)
        d=read_json(self.b['daily.json']);d['snapshot_sha256']=mh;self.b['daily.json']=encode(d);rehash(self.p,self.a,self.b)
        self.calls=[];self.proof_present=True;self.failed_newer=False;self.log_missing=False
    def json(self,path):
        self.calls.append(path)
        if path=='':return dict(full_name=REPO,private=True)
        if path=='/actions/workflows/stho-paper-dispatch.yml':return dict(id=9,path=self.run['path'],state='active')
        if '/runs?status=completed' in path:
            runs=[self.run]
            if self.failed_newer:runs=[dict(self.run,id=101,conclusion='failure')]+runs
            return dict(workflow_runs=runs)
        if path.endswith('/jobs?per_page=100'):
            return dict(total_count=1,jobs=[dict(id=1,run_id=100,status='completed',conclusion='success',steps=[dict(name='Verify both committed tracks and receipt binding',conclusion='success' if self.proof_present else 'skipped')])])
        raise AssertionError(path)
    def get(self,path,**kwargs):
        self.calls.append(path)
        if self.log_missing:raise Unverified('GITHUB_READ_FAILED')
        return b'2000-01-03T22:05:00Z '+encode(self.p)
    def file(self,commit,path):
        self.calls.append(path+'@'+commit)
        if path.startswith('.github/'):return self.dispatcher
        if path.startswith('operations/'):assert commit==self.p['track_a_journal_commit'];return self.a[path.split('/')[-1]]
        assert commit==self.p['track_b_journal_commit'];return self.b[path.split('/')[-1]]

class LifecycleTests(unittest.TestCase):
    def load(self,engine):return load_latest(engine,datetime(2000,1,4,tzinfo=timezone.utc))
    def test_complete_completed_run_to_dual_track_verified_model(self):
        r=self.load(FakeEngine());self.assertEqual(r['freshness'],'CURRENT');self.assertEqual(r['screen']['evaluated_tickers'],4);self.assertTrue(r['run_url'].endswith('/100'))
    def test_idempotent_reads(self):
        e=FakeEngine();self.assertEqual(self.load(e),self.load(e))
    def test_newer_failed_run_disclosed(self):
        e=FakeEngine();e.failed_newer=True;r=self.load(e);self.assertTrue(any('newer' in x for x in r['warnings']))
    def test_waiting_run_does_not_fabricate_session(self):
        e=FakeEngine();e.proof_present=False
        with self.assertRaisesRegex(Unverified,'NO_FINALIZED'):self.load(e)
    def test_expired_logs_withhold_data(self):
        e=FakeEngine();e.log_missing=True
        with self.assertRaises(Unverified):self.load(e)
    def test_wrong_run_source_blocks_records(self):
        e=FakeEngine();e.run['referenced_workflows']=[]
        with self.assertRaisesRegex(Unverified,'RUN_SOURCE'):self.load(e)
    def test_immutable_read_tamper_fails_without_fallback(self):
        e=FakeEngine();e.a['screen.json']+=b' '
        with self.assertRaisesRegex(Unverified,'HASH'):self.load(e)
