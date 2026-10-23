"""GET-only fixed-repository adapter. No write, dispatch or provider API exists."""
from __future__ import annotations
import base64
from dataclasses import dataclass,field
from datetime import datetime,timezone
import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request
from .records import A_FILES,B_FILES,Unverified,read_json,require,sha40,sha64,latest_ready,verify,sha

REPO='hakimrem23/stho-moomoo-test'
ORIGIN='https://api.github.com'
WORKFLOW='stho-paper-dispatch.yml'
MAX_BYTES=12_000_000
@dataclass(frozen=True)
class Access:
    token:str=field(repr=False)
    source_sha:str
    protocol_sha256:str
    approval_reference:str
    subject:str=field(default="",repr=False)

def authorize(settings,user):
    """Read server secrets + Streamlit OIDC identity; never browser arguments.

    V1 permits authenticated private disclosure only, including when V5 is public.
    A public-display approval requires a later reviewed implementation.
    """
    require(settings.get('mode')=='private','PRIVATE_MODE_NOT_ENABLED')
    require(settings.get('owner_approved_private_access') is True and settings.get('audience')=='authenticated_private','OWNER_APPROVAL_REQUIRED')
    require(isinstance(settings.get('approval_reference'),str) and bool(settings['approval_reference'].strip()),'APPROVAL_REFERENCE_REQUIRED')
    require(getattr(user,'is_logged_in',False) is True,'AUTHENTICATION_REQUIRED')
    try:
        email=user.get('email');verified=user.get('email_verified');allowed=settings.get('allowed_emails')
    except Exception:raise Unverified('AUTHENTICATION_REQUIRED') from None
    require(verified is True and isinstance(email,str) and isinstance(allowed,(list,tuple)) and len(allowed)>0,'VERIFIED_IDENTITY_ALLOWLIST_REQUIRED')
    require(all(isinstance(e,str) and '@' in e for e in allowed) and email.casefold() in {e.casefold() for e in allowed},'IDENTITY_NOT_AUTHORIZED')
    token=settings.get('github_token');require(isinstance(token,str) and bool(token.strip()) and '\n' not in token and '\r' not in token,'SERVER_CREDENTIAL_REQUIRED')
    require(sha40(settings.get('approved_source_sha')) and sha64(settings.get('approved_protocol_sha256')),'APPROVED_PINS_REQUIRED')
    return Access(token,settings['approved_source_sha'],settings['approved_protocol_sha256'],settings['approval_reference'],email.casefold())

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

class GitHub:
    def __init__(self,access,opener=None):
        self.access=access
        self._opener=opener or urllib.request.build_opener(NoRedirect())
    def _request(self,url,authenticated=True):
        headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'STHO-Streamlit-read-only'}
        if authenticated:headers['Authorization']='Bearer '+self.access.token
        return urllib.request.Request(url,headers=headers,method='GET')
    def get(self,path,limit=MAX_BYTES,logs=False):
        require(isinstance(path,str) and (path=='' or path.startswith('/')) and not path.startswith('//') and '#' not in path and '\\' not in path and '..' not in path.split('/'),'API_PATH_INVALID')
        # Repository is fixed in code; no arbitrary URL or user-controlled remote.
        url=ORIGIN+'/repos/'+REPO+path
        try:
            try:
                response=self._opener.open(self._request(url),timeout=20)
            except urllib.error.HTTPError as exc:
                if exc.code not in (301,302,303,307,308) or not logs:raise
                target=exc.headers.get('Location','');u=urllib.parse.urlsplit(target)
                host=u.hostname or ''
                require(u.scheme=='https' and u.port in (None,443) and not u.username and not u.password and not u.fragment,'LOG_REDIRECT_REJECTED')
                require(host.endswith('.blob.core.windows.net') or host.endswith('.actions.githubusercontent.com'),'LOG_REDIRECT_REJECTED')
                # Signed log URLs get NO GitHub bearer token; no second redirect.
                response=self._opener.open(self._request(target,authenticated=False),timeout=20)
            with response:
                require(response.status==200,'GITHUB_RESPONSE_NOT_OK');body=response.read(limit+1)
            require(len(body)<=limit,'GITHUB_RESPONSE_TOO_LARGE');return body
        except Unverified:raise
        except Exception:raise Unverified('GITHUB_READ_FAILED') from None
    def json(self,path):return read_json(self.get(path))
    def file(self,commit,path):
        require(sha40(commit) and isinstance(path,str) and '..' not in path.split('/') and not path.startswith('/'),'UNPINNED_OR_UNSAFE_GIT_READ')
        obj=self.json('/contents/'+urllib.parse.quote(path,safe='/')+'?ref='+commit)
        require(isinstance(obj,dict) and obj.get('type')=='file' and sha40(obj.get('sha')),'GIT_FILE_INVALID')
        require(type(obj.get('size')) is int and 0<=obj['size']<=6_000_000,'GIT_FILE_TOO_LARGE')
        blob=obj if obj.get('encoding')=='base64' else self.json('/git/blobs/'+obj['sha'])
        require(blob.get('encoding')=='base64' and isinstance(blob.get('content'),str),'GIT_BLOB_ENCODING_INVALID')
        try:body=base64.b64decode(''.join(blob['content'].split()),validate=True)
        except Exception:raise Unverified('GIT_BLOB_ENCODING_INVALID') from None
        require(len(body)==obj['size'] and hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==obj['sha'],'GIT_BLOB_HASH_MISMATCH')
        return body

def proof_from_logs(body):
    try:text=body.decode('utf-8')
    except UnicodeError:raise Unverified('VERIFICATION_LOG_ENCODING') from None
    found=[]
    for line in text.splitlines():
        if 'BOTH_TRACKS_VERIFIED' not in line:continue
        at=line.find('{')
        if at<0:continue
        try:obj=read_json(line[at:])
        except Unverified:continue
        if isinstance(obj,dict) and obj.get('status')=='BOTH_TRACKS_VERIFIED':found.append(obj)
    require(len(found)==1,'FINAL_VERIFICATION_LOG_MISSING_OR_AMBIGUOUS')
    return found[0]

def load_latest(client,now=None):
    """Latest completed approved dispatcher run with a successful finalize step.

    Waiting/holiday runs have no finalized session and are skipped. Failed newer
    executions are disclosed. A selected successful finalize with corrupt/missing
    evidence fails closed; it never silently falls back to an older fresh label.
    Logs expire: missing logs mean UNVERIFIED until separately approved proof exists.
    """
    now=now or datetime.now(timezone.utc);expected=latest_ready(now)
    repo=client.json('');require(repo.get('full_name')==REPO and repo.get('private') is True,'EXPECTED_PRIVATE_ENGINE_REPOSITORY')
    wf=client.json('/actions/workflows/'+WORKFLOW)
    require(wf.get('path')=='.github/workflows/'+WORKFLOW and type(wf.get('id')) is int,'WORKFLOW_IDENTITY_INVALID')
    runset=client.json('/actions/workflows/'+WORKFLOW+'/runs?status=completed&per_page=20')
    runs=runset.get('workflow_runs');require(isinstance(runs,list),'WORKFLOW_RUNS_UNAVAILABLE')
    warnings=[]
    for run in sorted(runs,key=lambda r:r.get('id',0),reverse=True):
        require(run.get('workflow_id')==wf['id'] and run.get('path')==wf['path'] and run.get('head_branch')=='main' and run.get('status')=='completed','RUN_IDENTITY_INVALID')
        if run.get('conclusion')!='success':warnings.append('A newer completed dispatcher run did not succeed.');continue
        require(run.get('event') in ('schedule','workflow_dispatch'),'RUN_EVENT_INVALID')
        rid=run.get('id');require(type(rid) is int and rid>0 and sha40(run.get('head_sha')),'RUN_IDENTITY_INVALID')
        require(any(x.get('sha')==client.access.source_sha and x.get('path')==REPO+'/.github/workflows/phase31-daily.yml@'+client.access.source_sha for x in run.get('referenced_workflows',[])),'RUN_SOURCE_NOT_APPROVED')
        jobs=client.json(f'/actions/runs/{rid}/jobs?per_page=100')
        candidates=[j for j in jobs.get('jobs',[]) if any(s.get('name')=='Verify both committed tracks and receipt binding' and s.get('conclusion')=='success' for s in j.get('steps',[]))]
        if not candidates:continue # completed holiday/waiting run; no session fabricated
        require(len(candidates)==1,'FINALIZE_JOB_AMBIGUOUS');job=candidates[0]
        require(job.get('status')=='completed' and job.get('conclusion')=='success' and job.get('run_id')==rid and type(job.get('id')) is int,'FINALIZE_JOB_INVALID')
        require(jobs.get('total_count',len(jobs.get('jobs',[])))<=100,'JOBS_PAGE_TRUNCATED')
        proof=proof_from_logs(client.get(f'/actions/jobs/{job["id"]}/logs',logs=True))
        require(sha40(proof.get('track_a_journal_commit')) and sha40(proof.get('track_b_journal_commit')),'JOURNAL_COMMIT_INVALID')
        session=proof.get('session');require(isinstance(session,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',session),'SESSION_INVALID')
        a={name:client.file(proof['track_a_journal_commit'],f'operations/screens/{session}/{name}') for name in sorted(A_FILES|{'SHA256SUMS.json'})}
        b={name:client.file(proof['track_b_journal_commit'],f'paper/journal/{session}/{name}') for name in sorted(B_FILES|{'seal.json'})}
        result=verify(proof,a,b,client.access.source_sha,client.access.protocol_sha256,now,expected)
        dispatcher=client.file(run['head_sha'],'.github/workflows/'+WORKFLOW)
        text=dispatcher.decode('utf-8');pins=re.findall(r'(?:phase31-daily\.yml@|source_ref:\s*)([0-9a-f]{40})',text)
        require(pins==[client.access.source_sha]*2 and sha(dispatcher)==proof['activation_receipt']['approved_dispatcher_sha256'],'DISPATCHER_APPROVAL_MISMATCH')
        require(utc_run(run['run_started_at'])<=utc_run(proof['verified_at_utc'])<=utc_run(run['updated_at']),'RUN_VERIFICATION_TIME_INVALID')
        result['warnings']+=list(dict.fromkeys(warnings))
        if wf.get('state')!='active':result['warnings'].append('Dispatcher is not active; this is the last verified record.')
        result['run_url']=f'https://github.com/{REPO}/actions/runs/{rid}'
        result['read_at_utc']=now.isoformat();return result
    raise Unverified('NO_FINALIZED_SESSION_IN_LAST_20_COMPLETED_RUNS')

def utc_run(v):
    from .records import utc
    return utc(v)
