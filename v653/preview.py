"""Entirely invented four-stock preview. Never an archived or prospective result."""
from collections import Counter
import json
from .records import A_FILES,B_FILES,CATEGORIES,MODELS,sha,verify

def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def fixture(qualified=True):
    session='2000-01-03';source='1'*40;protocol='2'*64
    activation=dict(schema_version=1,source_sha=source,approval_method='GITHUB_OWNER_PR4_MERGE',approval_pr=4,
        approved_by='hakimrem23',approved_at_utc='2000-01-01T00:00:00+00:00',approval_merge_sha='3'*40,
        approved_dispatcher_sha256='4'*64,first_eligible_session=session)
    rows=[]
    for ticker,category in zip(['DEMOA','DEMOB','DEMOC','DEMOD'],CATEGORIES):
        if not qualified and category=='QUALIFIED SETUP':category='WATCHLIST'
        for model in MODELS:
            good=category=='QUALIFIED SETUP';missing=category=='DATA UNAVAILABLE'
            rows.append(dict(ticker=ticker,observation_date=session,strategy_model=model,setup_classification=category,
                pattern='FICTIONAL_PREVIEW_PATTERN',confirmation_date=session,decision_session=session,entry_session=session if good else None,
                trend_context=None if missing else dict(close=111,sma10=110,sma30=108,sma50=107,ema21=109,atr14=3),
                volume_context=None if missing else dict(current=100000,rvol1d=1.5,rvol5=1.4),
                entry_trigger=None if missing else 'Synthetic original-rule trigger example; not an actual signal',
                proposed_entry_plan='Fictional observed-open example' if good else 'Confirmation incomplete; no executable entry',
                entry_price=110 if good else None,initial_stop_loss=105 if good else None,reward_to_risk=2.0 if good else None,
                support=None if missing else 108,resistance=[] if missing else [dict(session=session,price=120)],
                reasons=['SYNTHETIC_ONLY: invented demonstration, not a market observation'],
                data_quality_status='FAILED' if missing else 'VALID',next_open_gates_pending=category=='WATCHLIST',
                price_basis='Synthetic adjusted-price illustration; not a broker price'))
    histories={t:dict(status='FAILED' if t=='DEMOD' else 'OK') for t in ['DEMOA','DEMOB','DEMOC','DEMOD','SPY']}
    manifest=dict(session=session,source_sha=source,activation_receipt=activation,histories=histories)
    b={n:b'\n' for n in B_FILES};b['data-manifest.json']=encode(manifest)
    daily=dict(session=session,mode='PROSPECTIVE',source_sha=source,protocol_sha256=protocol,activation_receipt=activation,
        no_live_orders=True,snapshot_sha256=sha(b['data-manifest.json']),observed_at='2000-01-03T22:00:00+00:00',
        integrity='DEGRADED',benchmark_ready=True,counts=dict(frozen_stock_universe=4,valid_stocks=3,new_confirmations=0,
        new_paper_entries=0,new_paper_exits=0,open_positions=0,closed_positions=0,pending_entries=0,unresolved_positions=0,unresolved_intents=0),
        errors=[dict(scope='DEMOD',error='SYNTHETIC missing-history example',expected=False)],portfolio_max_drawdown=None)
    b['daily.json']=encode(daily);b['state.json']=encode(dict(last_session=session))
    b['seal.json']=encode(dict(schema_version=1,session=session,protocol_sha256=protocol,previous_seal_sha256=None,files_sha256={n:sha(v) for n,v in b.items()}))
    screen=dict(schema_version=1,track='A_OPERATIONAL_SCREEN_ONLY',session=session,source_sha=source,
        activation_receipt=activation,mode='AS_OBSERVED_SNAPSHOT_NOT_VALIDATED_RECOMMENDATIONS',
        provider='SYNTHETIC — NO DATA PROVIDER',data_observed_at=daily['observed_at'],snapshot_manifest_sha256=daily['snapshot_sha256'],
        benchmark_status='VALID',universe_stocks=4,evaluated_tickers=4,rows=rows,live_orders=False,track_b_state_modified=False,accuracy_claim=None,
        category_rows=dict(Counter(r['setup_classification'] for r in rows)),
        categories_by_unique_ticker={c:len({r['ticker'] for r in rows if r['setup_classification']==c}) for c in CATEGORIES})
    binding=dict(screen_source_sha=source,activation_receipt=activation,strategy_state_unchanged=True,
        track_b_bundle_sha256='sha256:'+'5'*64,track_b_journal_commit='6'*40,track_b_seal_sha256=sha(b['seal.json']))
    a={n:b'\n' for n in A_FILES};a['screen.json']=encode(screen);a['binding.json']=encode(binding);a['accounting-audit.json']=encode(dict(track='B_ACCOUNTING_AUDIT_ONLY',positions=[]))
    a['SHA256SUMS.json']=encode({n:sha(v) for n,v in a.items()})
    proof=dict(status='BOTH_TRACKS_VERIFIED',all_source_receipt_session_and_inventory_checks_pass=True,session=session,
        source_sha=source,activation_receipt=activation,track_a_journal_commit='7'*40,track_b_journal_commit='6'*40,
        track_b_bundle_sha256=binding['track_b_bundle_sha256'],track_b_seal_sha256=sha(b['seal.json']),
        snapshot_manifest_sha256=daily['snapshot_sha256'],screen_files_sha256={n:sha(v) for n,v in a.items() if n!='SHA256SUMS.json'},
        coverage_stocks=4,verified_at_utc='2000-01-03T22:05:00+00:00')
    return proof,a,b,source,protocol

def preview(qualified=True):
    from datetime import datetime,timezone
    p,a,b,s,h=fixture(qualified)
    result=verify(p,a,b,s,h,datetime(2000,1,4,tzinfo=timezone.utc),'2000-01-03')
    result.update(synthetic=True,record_status='SYNTHETIC PREVIEW',freshness='NOT LIVE',expected_session=None,
        warnings=['All symbols, dates, prices and counts are invented. This preview is not prospective evidence.'],run_url=None)
    return result
