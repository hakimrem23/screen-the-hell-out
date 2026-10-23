"""Compact dark/mobile view. Never imports the screening engine or quotes API."""
from datetime import datetime,timezone
import html
import time
from zoneinfo import ZoneInfo
from shariah_gate import review_status
from .github_readonly import authorize,GitHub,load_latest
from .preview import preview
from .records import CATEGORIES,Unverified
from .session_security import clear_cached,clear_private,enforce_session,RECHECK_SECONDS


def settings(st):
    try:
        if 'v653' not in st.secrets:return {'mode':'synthetic_preview'}
        return dict(st.secrets['v653'])
    except FileNotFoundError:return {'mode':'synthetic_preview'}

def number(v):
    if v is None:return '—'
    if isinstance(v,(int,float)):return f'{v:,.2f}'
    return '—'

def text(st,label,value):
    # st.text avoids interpreting untrusted provider strings as HTML/Markdown.
    st.text(f'{label}: {value if value is not None else "Not available"}')

def render(st,reviews):
    # Public preview is unchanged and has no periodic/network side effects.
    if settings(st).get('mode')=='private':
        @st.fragment(run_every=RECHECK_SECONDS)
        def private_view():_render(st,reviews)
        private_view()
    else:_render(st,reviews)

def _render(st,reviews):
    st.subheader('V6.5.3 Screening')
    st.caption('Automatic end-of-day research · Track A shortlist · Track B stays independent')
    config=settings(st)
    if config.get('mode','synthetic_preview')=='synthetic_preview':
        st.session_state.pop('v653_private_record',None)
        st.info('SYNTHETIC PREVIEW · All examples are invented. No private results are loaded.')
        result=preview(qualified=not st.checkbox('Preview a day with zero qualified setups',key='v653_zero_preview'))
    elif config.get('mode')=='private':
        user=getattr(st,'user',None)
        if getattr(user,'is_logged_in',False) is True:
            if st.button('Sign out of private screening',key='v653_signout',use_container_width=True):
                clear_private(st.session_state)
                try:st.logout()
                except Exception:st.error('Sign-out could not complete. Close private tabs and contact the owner.')
                return
        try:
            access=authorize(config,user)
            identity=enforce_session(st.session_state,access)
        except Exception:
            clear_cached(st.session_state)
            st.warning('UNVERIFIED · Private results are locked. Approved server configuration and an authenticated allowlisted identity are required.')
            st.caption('Identity may be unauthorized, expired or invalidated by rotation. Sign out and sign in again; contact the owner if still locked. No credentials belong in browser inputs.')
            try:
                if config.get('owner_approved_private_access') is True and 'auth' in st.secrets and not getattr(getattr(st,'user',None),'is_logged_in',False):
                    if st.button('Sign in for private screening',key='v653_login'):st.login()
            except Exception:st.error('Authentication is unavailable; contact the owner.')
            return
        cached=st.session_state.get('v653_private_record')
        refresh=st.button('Refresh verified session',key='v653_refresh',use_container_width=True)
        if cached and cached['identity']!=identity:cached=None;st.session_state.pop('v653_private_record',None)
        if not cached or refresh or time.monotonic()-cached['loaded']>120:
            # Discard old data first: a failing refresh never appears CURRENT.
            st.session_state.pop('v653_private_record',None)
            try:
                with st.spinner('Checking completed run and both sealed tracks…'):result=load_latest(GitHub(access))
            except Exception:
                st.error('UNVERIFIED · The latest record could not be authenticated. Results are withheld. Check token permissions, approved pins, run logs and sealed evidence on the server.')
                return # Never print transport exceptions, URLs, tokens or raw private payloads.
            try:
                # A network read may outlive identity expiry or a settings update.
                current=authorize(settings(st),getattr(st,'user',None))
                current_identity=enforce_session(st.session_state,current)
                if current_identity!=identity:raise Unverified('ACCESS_CHANGED_DURING_READ')
            except Exception:
                clear_cached(st.session_state);st.warning('UNVERIFIED · Identity or credentials changed during retrieval. Results are withheld.');return
            st.session_state['v653_private_record']={'identity':identity,'loaded':time.monotonic(),'result':result}
        else:
            # Recompute calendar freshness on every render, even while data is cached.
            from .records import latest_ready
            result=dict(cached['result'])
            try:
                result['expected_session']=latest_ready(datetime.now(timezone.utc))
                result['freshness']='STALE' if result['screen']['session']<result['expected_session'] else 'CURRENT'
            except Exception:
                st.error('UNVERIFIED · Exchange-calendar freshness could not be established.');return
    else:
        st.session_state.pop('v653_private_record',None)
        st.warning('UNVERIFIED · Unsupported server mode. Results are withheld.');return
    screen=result['screen'];daily=result['daily']
    if result['freshness']=='STALE':st.warning('STALE · A newer completed US exchange session is expected. These are older records.')
    st.caption(result['record_status']+' · '+result['freshness']+' · Record integrity does not certify market prices or trading accuracy.')
    text(st,'US screening session',screen['session'])
    if result.get('read_at_utc'):
        read=datetime.fromisoformat(result['read_at_utc']).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
        st.caption('Fetched '+read.strftime('%Y-%m-%d %H:%M MYT')+' · data timestamp '+screen['data_observed_at'])
    categories=screen['categories_by_unique_ticker']
    kpis=[('Stocks accounted for',screen['evaluated_tickers']),('Valid histories',daily['counts']['valid_stocks']),
          ('Qualified setups',categories['QUALIFIED SETUP']),('Watchlist',categories['WATCHLIST']),('Data unavailable',categories['DATA UNAVAILABLE'])]
    st.markdown('<div class="stho-kpis">'+''.join('<div class="stho-kpi"><b>'+html.escape(str(v))+'</b><span>'+html.escape(k)+'</span></div>' for k,v in kpis)+'</div>',unsafe_allow_html=True)
    st.caption('Counts are unique tickers within each category; models can overlap. Accounted-for stocks include rejected and unavailable histories.')
    st.warning('Technical research only. A qualified setup is not a BUY or Shariah clearance. Adjusted reference prices are not broker order levels.')
    for warning in result['warnings']:st.warning(warning)
    group=st.selectbox('Setup category',CATEGORIES,key='v653_category')
    candidates=[r for r in screen['rows'] if r['setup_classification']==group]
    if not candidates:
        st.info('No qualified setups.' if group=='QUALIFIED SETUP' else 'No records in this category.')
    else:
        symbols=sorted({r['ticker'] for r in candidates})
        ticker=st.selectbox('Stock details',symbols,key='v653_ticker')
        for r in [r for r in candidates if r['ticker']==ticker]:
            with st.container(border=True):
                text(st,'Ticker',r['ticker']);text(st,'Model',r['strategy_model']);text(st,'Classification',r['setup_classification'])
                # Unchanged V5 fail-closed manual review; no technical result bypasses it.
                gate=review_status(r['ticker'],{} if result['synthetic'] else reviews)
                text(st,'Shariah evidence',gate['gate']);text(st,'Shariah review note',gate['why'])
                text(st,'Data quality',r['data_quality_status']);text(st,'Pattern',r.get('pattern'))
                text(st,'Entry trigger',r.get('entry_trigger'));text(st,'Entry plan',r.get('proposed_entry_plan'))
                text(st,'Observed entry reference',number(r.get('entry_price')));text(st,'Initial stop reference',number(r.get('initial_stop_loss')))
                risk=None
                if isinstance(r.get('entry_price'),(int,float)) and isinstance(r.get('initial_stop_loss'),(int,float)):risk=r['entry_price']-r['initial_stop_loss']
                text(st,'Initial per-share reference risk',number(risk));text(st,'Reference reward/risk',number(r.get('reward_to_risk')))
                text(st,'Support',number(r.get('support')));text(st,'Price basis',r.get('price_basis'))
                text(st,'Confirmation date',r.get('confirmation_date'));text(st,'Next-open gates pending',r['next_open_gates_pending'])
                for reason in r['reasons']:text(st,'Reason',reason)
                with st.expander('Trend, volume and resistance context'):
                    st.json({'trend':r.get('trend_context'),'volume':r.get('volume_context'),'resistance':r.get('resistance')})
        with st.expander('Category rows · technical research only'):
            st.dataframe([{k:r.get(k) for k in ['ticker','strategy_model','setup_classification','data_quality_status','confirmation_date','entry_price','initial_stop_loss','reward_to_risk']} for r in candidates],hide_index=True,use_container_width=True)
    with st.expander('Data-quality exceptions'):
        st.json(daily['errors'])
    with st.expander('Track B · independent paper journal'):
        st.caption('Track A categories do not create, approve or modify Track B trades. Historical fixtures are not prospective outcomes.')
        for k in ['new_paper_entries','new_paper_exits','pending_entries','open_positions','closed_positions','unresolved_positions','unresolved_intents']:
            text(st,k.replace('_',' '),daily['counts'].get(k))
        st.caption('Performance estimates are outside Integration V1; no win rate or portfolio drawdown is inferred.')
    if result.get('run_url'):st.link_button('Verified engine run · authorized access required',result['run_url'],use_container_width=True)
