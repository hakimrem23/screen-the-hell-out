"""Server-only identity/session boundaries. No market data or trading policy."""
from datetime import datetime,timezone
import hashlib
import json
import math
from .records import require,utc

DEFAULT_MAX_AGE=3600
RECHECK_SECONDS=30

def epoch():return datetime.now(timezone.utc).timestamp()
def numeric(v):return type(v) in (int,float) and math.isfinite(v)
def claims(settings,user,now=None):
    now=epoch() if now is None else now
    issuer=settings.get('oidc_issuer');client=settings.get('oidc_client_id')
    require(isinstance(issuer,str) and issuer.startswith('https://') and isinstance(client,str) and bool(client),'OIDC_TRUST_CONFIG_REQUIRED')
    require(user.get('iss')==issuer,'IDENTITY_ISSUER_MISMATCH')
    aud=user.get('aud');require(aud==client or isinstance(aud,list) and client in aud,'IDENTITY_AUDIENCE_MISMATCH')
    if isinstance(aud,list) and len(aud)>1:require(user.get('azp')==client,'IDENTITY_AUTHORIZED_PARTY_MISMATCH')
    else:require(user.get('azp',client)==client,'IDENTITY_AUTHORIZED_PARTY_MISMATCH')
    subject=user.get('sub');require(isinstance(subject,str) and bool(subject),'IDENTITY_SUBJECT_REQUIRED')
    issued,expires=user.get('iat'),user.get('exp')
    require(numeric(issued) and numeric(expires) and issued<=now<expires and issued<expires,'IDENTITY_EXPIRED_OR_INVALID')
    maximum=settings.get('max_session_age_seconds',DEFAULT_MAX_AGE)
    require(type(maximum) is int and 60<=maximum<=86400,'SESSION_POLICY_INVALID')
    require(now-issued<maximum,'IDENTITY_MAX_AGE_EXCEEDED')
    cutoff=settings.get('auth_not_before_utc');require(isinstance(cutoff,str),'AUTH_CUTOFF_REQUIRED')
    boundary=utc(cutoff).timestamp();require(boundary<=now and issued>=boundary,'IDENTITY_BEFORE_ROTATION_CUTOFF')
    generation=settings.get('credential_generation');sessions=settings.get('session_generation')
    require(all(isinstance(x,str) and bool(x.strip()) for x in [generation,sessions]),'ROTATION_GENERATIONS_REQUIRED')
    identity=hashlib.sha256(json.dumps([issuer,client,subject,user.get('email')],separators=(',',':')).encode()).hexdigest()
    # Digest only is retained server-side; never rendered, logged or sent to a client.
    key=hashlib.sha256(json.dumps([settings['github_token'],generation,sessions,cutoff],separators=(',',':')).encode()).hexdigest()
    return identity,key,issued,min(expires,issued+maximum)

def clear_cached(state):
    for key in ['v653_private_record','v653_ticker','v653_category']:state.pop(key,None)

def clear_private(state):
    clear_cached(state)
    for key in ['v653_private_session','v653_reauth_boundary']:state.pop(key,None)

def enforce_session(state,access,now=None):
    now=epoch() if now is None else now
    require(access.identity_key and access.credential_key and access.expires_at>now,'PRIVATE_SESSION_EXPIRED')
    previous=state.get('v653_private_session')
    if previous and previous['credential_key']!=access.credential_key:
        clear_cached(state);state.pop('v653_private_session',None)
        if access.issued_at<=previous.get('issued_at',0):state['v653_reauth_boundary']=now
    boundary=state.get('v653_reauth_boundary')
    if boundary is not None:
        require(access.issued_at>boundary,'CREDENTIAL_ROTATED_REAUTHENTICATION_REQUIRED')
        state.pop('v653_reauth_boundary',None)
    if previous and previous['identity_key']!=access.identity_key:clear_cached(state)
    state['v653_private_session']={'credential_key':access.credential_key,'identity_key':access.identity_key,'issued_at':access.issued_at}
    return (access.source_sha,access.protocol_sha256,access.approval_reference,access.identity_key,access.credential_key)
