"""Linux isolated-process RSS measurements; no hosted/OIDC/throughput claim.

Default public mode is entirely synthetic. Optional --sealed-folder reads an
owner-authorized LOCAL copy outside the repo; payloads/identities never emitted.
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

def profile(viewers,private=None):
    start=time.monotonic()
    from datetime import datetime,timezone
    import base64,hashlib
    from unittest.mock import patch
    from streamlit.testing.v1 import AppTest
    from tests.test_adapter import settings,user
    from v653.preview import preview
    from v653.github_readonly import proof_from_logs
    from v653.records import verify,read_json,latest_ready
    def inventory():
        return {p.relative_to(private).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in private.rglob('*') if p.is_file()}
    before=inventory() if private else None
    cfg=settings()
    if private:
        proof=proof_from_logs((private/'log.txt').read_bytes());cfg['approved_source_sha']=proof['source_sha']
        cfg['approved_protocol_sha256']=read_json((private/'b/seal.json').read_bytes())['protocol_sha256']
    def load(*args,**kwargs):
        if not private:
            r=preview();r.update(synthetic=False,freshness='STALE',record_status='VERIFIED RECORDS');return r
        # Simulate GitHub JSON/base64 decoding allocations, without HTTP or token.
        def decoded(path):
            body=path.read_bytes();envelope=json.dumps({'content':base64.b64encode(body).decode()}).encode()
            return base64.b64decode(json.loads(envelope)['content'])
        a={p.name:decoded(p) for p in (private/'a').iterdir() if p.is_file()}
        b={p.name:decoded(p) for p in (private/'b').iterdir() if p.is_file()}
        now=datetime.now(timezone.utc)
        return verify(proof,a,b,cfg['approved_source_sha'],cfg['approved_protocol_sha256'],now,latest_ready(now))
    retained=[]
    with patch('v653.ui.settings',return_value=cfg),patch('streamlit.user',user()),patch('v653.ui.load_latest',side_effect=load),patch('yfinance.Ticker',side_effect=AssertionError('market requests forbidden')):
        for _ in range(viewers):
            at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
            at.radio(key='nav_v5').set_value('V6.5.3 Screening').run()
            for category in ['QUALIFIED SETUP','WATCHLIST','REJECTED','DATA UNAVAILABLE']:
                at.selectbox(key='v653_category').set_value(category).run()
                if at.exception:raise RuntimeError('APPTEST_PROFILE_FAILURE')
            for _ in range(3):
                at.button(key='v653_refresh').click().run()
                if at.exception:raise RuntimeError('APPTEST_PROFILE_FAILURE')
            retained.append(at)
    if private and inventory()!=before:raise RuntimeError('INPUT_CHANGED')
    return dict(resident_sessions=viewers,peak_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),elapsed_seconds=round(time.monotonic()-start,2),input_kind='AUTHORIZED_LOCAL_SEALED_RECORDS' if private else 'SYNTHETIC',input_bytes_unchanged=True,
        scope='AppTest + imports + XNYS + retained session records + category dataframes + three refreshes + base64 simulation; sequential requests, no HTTP/TLS/OIDC server/browser, no memory cap',
        market_requests=0,private_payloads_emitted=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);p.add_argument('--sealed-folder',type=Path);p.add_argument('--viewers',default='1,3,5');p.add_argument('--repeats',type=int,default=2);p.add_argument('--child',type=int);a=p.parse_args()
    if a.sealed_folder and a.output:
        source=a.sealed_folder.resolve();target=a.output.resolve()
        if source==target or source in target.parents:raise SystemExit('OUTPUT_MUST_BE_OUTSIDE_INPUT')
    if not sys.platform.startswith('linux'):raise SystemExit('LINUX_RSS_UNITS_REQUIRED')
    if a.child:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):r=profile(a.child,a.sealed_folder)
        print(json.dumps(r));return
    rows=[]
    for n in [int(v) for v in a.viewers.split(',')]:
        if not 1<=n<=10:raise SystemExit('INVALID_SESSION_COUNT')
        for repeat in range(a.repeats):
            cmd=[sys.executable,'-B','-m','tools.memory_profile','--child',str(n)]
            if a.sealed_folder:cmd+=['--sealed-folder',str(a.sealed_folder)]
            r=subprocess.run(cmd,capture_output=True,text=True,timeout=240)
            if r.returncode:raise SystemExit('PROFILE_FAILED_NO_PRIVATE_LOG_PUBLISHED')
            row=json.loads(r.stdout);row['repeat']=repeat+1;rows.append(row)
    out=dict(schema_version=1,mode='LOCAL_MEASUREMENTS_NOT_HOSTED_CAPACITY_CERTIFICATION',measurements=rows,linux_peak_rss_units='MiB (KiB / 1024)',
        comparison=dict(nominal_binary_tier_mib=[512,2048],conservative_decimal_tier_mib=[488.28,1907.35],conservative_25_percent_headroom_budget_mib=[366.21,1430.51],provider_actual_units_verified=False),
        limitations=['Linux peak process RSS, not full-container memory or cgroup memory.peak','No server/WebSocket/TLS/OIDC process or parallel fetch burst; platform overhead and network buffers unmeasured','No hosting purchased or deployed; synthetic measurements do not replace sealed-record measurements'])
    if not a.output:raise SystemExit('OUTPUT_REQUIRED')
    with a.output.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
    print(json.dumps({'cases':len(rows),'max_rss_mib':max(x['peak_rss_mib'] for x in rows),'output_written':True}))
if __name__=='__main__':main()
