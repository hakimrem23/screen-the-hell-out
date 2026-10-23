"""Strict schema and cross-track checks. Verification concerns records, not prices."""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timedelta,timezone
import hashlib
import json
import math
import re

CATEGORIES=('QUALIFIED SETUP','WATCHLIST','REJECTED','DATA UNAVAILABLE')
MODELS=('LEGACY_7D_REFERENCE_RETEST','PULLBACK_15D_SMA_SUPPORT')
A_FILES={'screen.json','screen.csv','REPORT.md','binding.json','accounting-audit.json'}
B_FILES={'REPORT.md','coverage.csv','daily.json','data-manifest.json','events.json','events.jsonl','intents.csv','performance.csv','performance.json','positions.csv','setups.csv','state.json','watchlist.csv'}
class Unverified(ValueError):
    """Only fixed safe codes cross the UI boundary."""

def require(ok,code):
    if not ok:raise Unverified(code)
def sha(body):return hashlib.sha256(body).hexdigest()
def sha40(v):return isinstance(v,str) and re.fullmatch('[0-9a-f]{40}',v) is not None
def sha64(v):return isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) is not None
def utc(v):
    try:
        t=datetime.fromisoformat(v.replace('Z','+00:00'));require(t.tzinfo is not None,'TIMESTAMP_TIMEZONE_REQUIRED');return t.astimezone(timezone.utc)
    except (ValueError,AttributeError,TypeError):raise Unverified('INVALID_TIMESTAMP') from None

def read_json(body):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'DUPLICATE_JSON_KEY');out[k]=v
        return out
    def constant(_):raise Unverified('NONFINITE_JSON')
    try:return json.loads(body,object_pairs_hook=pairs,parse_constant=constant)
    except (ValueError,UnicodeError,TypeError,RecursionError):raise Unverified('INVALID_JSON') from None

def plain(v):
    if isinstance(v,float):require(math.isfinite(v),'NONFINITE_VALUE')
    elif isinstance(v,dict):
        for x in v.values():plain(x)
    elif isinstance(v,list):
        for x in v:plain(x)

def latest_ready(now):
    require(now.tzinfo is not None,'TIMESTAMP_TIMEZONE_REQUIRED')
    try:
        import exchange_calendars as xc
        cal=xc.get_calendar('XNYS',start=str(now.year-2)+'-01-01',end=str(now.year+1)+'-12-31')
        for day in reversed(cal.sessions_in_range((now-timedelta(days=15)).date(),now.date())):
            if cal.session_close(day).to_pydatetime()+timedelta(minutes=30)<=now:return str(day.date())
    except Exception:raise Unverified('EXCHANGE_CALENDAR_UNAVAILABLE') from None
    raise Unverified('NO_COMPLETED_EXCHANGE_SESSION')

def verify(proof,a,b,source,protocol,now,expected_session):
    """Inputs are bytes from immutable Git commits selected by completed-run proof.

    Entire committed A/B record inventories are checked. Raw provider archives,
    economic accuracy and vendor lineage are outside this frontend verifier.
    """
    require(isinstance(proof,dict) and proof.get('status')=='BOTH_TRACKS_VERIFIED','FINAL_VERIFICATION_MISSING')
    require(proof.get('all_source_receipt_session_and_inventory_checks_pass') is True,'FINAL_CHECKS_FAILED')
    require(sha40(source) and sha64(protocol) and proof.get('source_sha')==source,'UNAPPROVED_SOURCE')
    session=proof.get('session');require(isinstance(session,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',session),'SESSION_INVALID')
    try:date.fromisoformat(session)
    except ValueError:raise Unverified('SESSION_INVALID') from None
    require(session<=expected_session,'FUTURE_OR_INCOMPLETE_SESSION')
    require(set(a)==A_FILES|{'SHA256SUMS.json'},'TRACK_A_INVENTORY_MISMATCH')
    ah=read_json(a['SHA256SUMS.json']);require(isinstance(ah,dict) and set(ah)==A_FILES,'TRACK_A_HASH_INVENTORY')
    require(ah==proof.get('screen_files_sha256'),'TRACK_A_PROOF_HASH_MISMATCH')
    for name in A_FILES:require(sha64(ah[name]) and sha(a[name])==ah[name],'TRACK_A_HASH_MISMATCH')
    require(set(b)==B_FILES|{'seal.json'},'TRACK_B_INVENTORY_MISMATCH')
    seal=read_json(b['seal.json']);require(isinstance(seal,dict) and seal.get('schema_version')==1 and seal.get('session')==session,'TRACK_B_SEAL_SCHEMA')
    require(sha(b['seal.json'])==proof.get('track_b_seal_sha256'),'TRACK_B_SEAL_HASH')
    bh=seal.get('files_sha256');require(isinstance(bh,dict) and set(bh)==B_FILES,'TRACK_B_HASH_INVENTORY')
    for name in B_FILES:require(sha64(bh[name]) and sha(b[name])==bh[name],'TRACK_B_HASH_MISMATCH')
    require(seal.get('protocol_sha256')==protocol,'PROTOCOL_MISMATCH')
    previous=seal.get('previous_seal_sha256');require(previous is None or sha64(previous),'PREVIOUS_SEAL_INVALID')
    screen,binding,daily=read_json(a['screen.json']),read_json(a['binding.json']),read_json(b['daily.json'])
    require(all(isinstance(x,dict) for x in [screen,binding,daily]),'REPORT_OBJECT_REQUIRED');plain(screen);plain(daily)
    require(screen.get('schema_version')==1 and screen.get('track')=='A_OPERATIONAL_SCREEN_ONLY','TRACK_A_SCHEMA')
    require(screen.get('mode')=='AS_OBSERVED_SNAPSHOT_NOT_VALIDATED_RECOMMENDATIONS','NONPROSPECTIVE_SCREEN')
    require(daily.get('mode')=='PROSPECTIVE' and daily.get('no_live_orders') is True,'TRACK_B_MODE')
    require(screen.get('live_orders') is False and screen.get('track_b_state_modified') is False and screen.get('accuracy_claim') is None,'SCREEN_SAFETY_SCHEMA')
    require(screen.get('session')==daily.get('session')==session,'CROSS_TRACK_SESSION_MISMATCH')
    require(screen.get('source_sha')==daily.get('source_sha')==binding.get('screen_source_sha')==source,'CROSS_TRACK_SOURCE_MISMATCH')
    require(binding.get('strategy_state_unchanged') is True,'STRATEGY_STATE_CHANGED')
    require(daily.get('protocol_sha256')==protocol,'PROTOCOL_MISMATCH')
    manifest=sha(b['data-manifest.json'])
    require(screen.get('snapshot_manifest_sha256')==daily.get('snapshot_sha256')==proof.get('snapshot_manifest_sha256')==manifest,'SNAPSHOT_BINDING_MISMATCH')
    m=read_json(b['data-manifest.json']);require(m.get('session')==session and m.get('source_sha')==source,'MANIFEST_IDENTITY_MISMATCH')
    require(binding.get('track_b_seal_sha256')==proof.get('track_b_seal_sha256'),'BINDING_SEAL_MISMATCH')
    require(binding.get('track_b_journal_commit')==proof.get('track_b_journal_commit') and sha40(proof.get('track_a_journal_commit')) and sha40(proof.get('track_b_journal_commit')),'JOURNAL_COMMIT_MISMATCH')
    require(binding.get('track_b_bundle_sha256')==proof.get('track_b_bundle_sha256') and re.fullmatch(r'sha256:[0-9a-f]{64}',proof.get('track_b_bundle_sha256','')),'BUNDLE_BINDING_MISMATCH')
    activation=proof.get('activation_receipt')
    require(isinstance(activation,dict) and all(x.get('activation_receipt')==activation for x in [screen,binding,daily,m]),'ACTIVATION_RECEIPT_MISMATCH')
    require(activation.get('schema_version')==1 and activation.get('source_sha')==source and activation.get('approval_method')=='GITHUB_OWNER_PR4_MERGE' and activation.get('approved_by')=='hakimrem23' and activation.get('approval_pr')==4,'ACTIVATION_NOT_OWNER_APPROVED')
    require(sha40(activation.get('approval_merge_sha')) and sha64(activation.get('approved_dispatcher_sha256')),'ACTIVATION_IDENTITY_INVALID')
    require(isinstance(activation.get('first_eligible_session'),str) and activation['first_eligible_session']<=session,'BEFORE_ACTIVATION_SESSION')
    require(utc(activation['approved_at_utc'])<utc(daily['observed_at'])<=utc(proof['verified_at_utc'])<=now,'OBSERVATION_TIME_INVALID')
    require(screen.get('data_observed_at')==daily.get('observed_at'),'OBSERVATION_TIME_MISMATCH')
    require(read_json(b['state.json']).get('last_session')==session,'STATE_SESSION_MISMATCH')
    rows=screen.get('rows');require(isinstance(rows,list) and 0<len(rows)<=40000,'ROWS_MISSING_OR_OVERSIZED')
    counts=Counter();tickers={c:set() for c in CATEGORIES};pairs=set()
    required={'ticker','observation_date','strategy_model','setup_classification','data_quality_status','reasons','trend_context','volume_context','entry_trigger','proposed_entry_plan','entry_price','initial_stop_loss','support','resistance','reward_to_risk','next_open_gates_pending','price_basis'}
    for r in rows:
        require(isinstance(r,dict) and required<=set(r),'ROW_SCHEMA_INVALID')
        require(isinstance(r['ticker'],str) and re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,19}',r['ticker']),'TICKER_INVALID')
        c=r['setup_classification'];require(c in CATEGORIES and r['strategy_model'] in MODELS and r['observation_date']==session,'ROW_IDENTITY_INVALID')
        require(isinstance(r['reasons'],list) and all(isinstance(x,str) for x in r['reasons']),'REASONS_INVALID')
        require(isinstance(r['data_quality_status'],str) and type(r['next_open_gates_pending']) is bool,'QUALITY_SCHEMA_INVALID')
        if c=='QUALIFIED SETUP':
            require(r['data_quality_status']=='VALID' and not r['next_open_gates_pending'] and r.get('entry_session')==session,'UNCONFIRMED_QUALIFIED_ROW')
            entry,stop=r['entry_price'],r['initial_stop_loss']
            require(type(entry) in (int,float) and type(stop) in (int,float) and 0<stop<entry,'QUALIFIED_REFERENCE_RISK_INVALID')
        counts[c]+=1;tickers[c].add(r['ticker']);pairs.add((r['ticker'],r['strategy_model']))
    all_tickers=set.union(*tickers.values());n=len(all_tickers)
    require(type(screen.get('evaluated_tickers')) is int and screen['evaluated_tickers']==screen.get('universe_stocks')==n==proof.get('coverage_stocks'),'COVERAGE_MISMATCH')
    require(pairs=={(t,model) for t in all_tickers for model in MODELS},'MODEL_COVERAGE_MISMATCH')
    require(screen.get('categories_by_unique_ticker')=={c:len(tickers[c]) for c in CATEGORIES},'CATEGORY_COUNT_MISMATCH')
    reported=screen.get('category_rows');require(isinstance(reported,dict) and set(reported)<=set(CATEGORIES) and all(reported.get(c,0)==counts[c] for c in CATEGORIES),'ROW_COUNT_MISMATCH')
    dc=daily.get('counts',{});require(dc.get('frozen_stock_universe')==n and type(dc.get('valid_stocks')) is int and 0<=dc['valid_stocks']<=n,'TRACK_B_COVERAGE_MISMATCH')
    histories=m.get('histories');require(isinstance(histories,dict) and set(histories)==all_tickers|{'SPY'},'HISTORY_INVENTORY_MISMATCH')
    require(sum(histories[t].get('status')=='OK' for t in all_tickers)==dc['valid_stocks'],'VALID_HISTORY_COUNT_MISMATCH')
    errors=daily.get('errors');require(isinstance(errors,list),'ERRORS_UNAVAILABLE')
    warnings=[]
    if daily.get('integrity')!='OK':warnings.append('Track B reports degraded data integrity; preserved exceptions remain unresolved.')
    if screen.get('benchmark_status')!='VALID' or daily.get('benchmark_ready') is not True:warnings.append('Benchmark unavailable: screening reliability is limited.')
    missing=n-dc['valid_stocks']
    if missing:warnings.append(f'{missing} stock histories unavailable; no prices have been filled or replaced.')
    if tickers['DATA UNAVAILABLE']:warnings.append('Indicator-context gaps can add DATA UNAVAILABLE tickers beyond raw-history failures.')
    return dict(screen=screen,daily=daily,proof=proof,freshness='STALE' if session<expected_session else 'CURRENT',
        expected_session=expected_session,record_status='VERIFIED RECORDS',warnings=warnings,synthetic=False)
