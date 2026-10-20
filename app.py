"""STHO V4 Early Reversal Swing — research dashboard for phones.

Shariah gate is based ONLY on manually supplied dated, source-linked records.
There are NO pre-approved securities and NO automated religious determination.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

from reversal import analyze_reversal
from metrics import screen_ticker
from shariah_gate import read_reviews, review_status, COLUMNS, MAX_AGE_DAYS

ROOT = Path(__file__).resolve().parent
RESULTS_FILE = ROOT / "data/market_results.csv"
STATUS_FILE = ROOT / "data/scan_status.json"
SHARIAH_FILE = ROOT / "data/shariah_reviews.csv"
DEFAULT_WATCH = "MU, MRVL, BMRN, NVDA, PLTR"
PAGES = ["Discover", "My Watchlist", "Deep Dive", "Shariah Reviews", "About"]
STAGES = ["Breakout review", "Reversal watch", "Extended", "All setups"]

st.set_page_config(page_title="STHO | Early Reversal V4", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
st.markdown('''<style>
.stApp {background:#0b111b;color:#e9f2f8;}
.block-container {max-width:950px;padding-top:.35rem;padding-bottom:2.8rem;}
h1,h2,h3 {letter-spacing:-.025em;}
[data-testid="stHeader"] {background:transparent;}
.stButton>button {min-height:2.45rem;border-radius:12px;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px!important;border-color:#263344!important;}
.stho-head {display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px;}
.stho-brand {font-weight:800;font-size:1.35rem;color:#f3f6fc;letter-spacing:-.05em;}
.stho-brand span {color:#54ddbf;}
.stho-sub {font-size:.76rem;color:#95a5b8;}
.stho-chip {color:#72d8bb;font-size:.69rem;border:1px solid #23483f;background:#13342e;border-radius:50px;padding:5px 8px;white-space:nowrap;}
.stho-kpis {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:8px 0 14px;}
.stho-kpi {background:#141e2b;border:1px solid #263444;padding:11px 8px;border-radius:12px;}
.stho-kpi strong {display:block;font-size:1.25rem;line-height:1.25;color:#eff7ff;}
.stho-kpi span {display:block;font-size:.68rem;color:#9aabc0;margin-top:4px;}
.stho-card {display:flex;align-items:flex-start;justify-content:space-between;gap:10px;}
.stho-ticker {font-size:1.2rem;font-weight:800;color:#f7f9ff;}
.stho-name {font-size:.73rem;color:#94a7ba;line-height:1.4;}
.stho-stage {font-size:.82rem;font-weight:750;color:#69dec2;text-align:right;max-width:45%;}
.stho-statgrid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:11px 0;}
.stho-stat {background:#101927;border-radius:9px;padding:8px;min-width:0;}
.stho-stat b {display:block;color:#eaf4fb;font-size:.91rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.stho-stat span {font-size:.69rem;color:#9aaabe;}
.stho-warn {font-size:.77rem;color:#f0c982;padding-top:6px;line-height:1.6;}
.stho-ok {font-size:.77rem;color:#77ddbd;padding-top:6px;line-height:1.6;}
.stho-muted {font-size:.78rem;color:#9aaabe;line-height:1.5;}
@media(max-width:680px){.block-container{padding-left:1rem;padding-right:1rem;}.stho-statgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.stho-kpi strong{font-size:1.1rem}.stho-stat{padding:7px 8px;}}
</style>''', unsafe_allow_html=True)


def esc(obj) -> str:
    return html.escape(str(obj), quote=True)


def number(value, digits=2, prefix="", suffix="") -> str:
    try:
        n = float(value)
        return f"{prefix}{n:,.{digits}f}{suffix}" if pd.notna(n) else "—"
    except (TypeError, ValueError):
        return "—"


def clean_tickers(raw: str) -> list[str]:
    return list(dict.fromkeys(
        t for t in re.split(r"[,\s]+", raw.upper()) if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", t)
    ))[:25]


@st.cache_data(ttl=900, show_spinner=False)
def history(ticker: str) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(period="2y", interval="1d", auto_adjust=True, actions=False)
    if df.empty:
        raise ValueError("Price history not available")
    return df


@st.cache_data(ttl=180, show_spinner=False)
def load_data(result_mtime: int, status_mtime: int):
    data = pd.read_csv(RESULTS_FILE)
    status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    if "Reversal Stage" not in data.columns:
        return data, status, False
    for field in ["Close ($)", "ADR20 (%)", "ADV60 ($M)", "Reversal Score", "RVOL20", "RR Proxy", "Pivot ($)", "Stop Ref ($)", "Target Ref ($)", "Below EMA200 Days (60)"]:
        if field in data.columns:
            data[field] = pd.to_numeric(data[field], errors="coerce")
    now = pd.Timestamp.now(tz="UTC")
    last_bar = pd.to_datetime(data["Date"], utc=True, errors="coerce")
    last_scan = pd.to_datetime(data["Scanned at UTC"], utc=True, errors="coerce")
    data["Recent"] = (((now - last_bar).dt.total_seconds() / 86400).between(-1, 4) &
                       ((now - last_scan).dt.total_seconds() / 86400).between(-1, 4)).fillna(False)
    data["Reversal Stage"] = data["Reversal Stage"].fillna("No setup")
    return data, status, True


@st.cache_data(ttl=180, show_spinner=False)
def load_reviews(mtime: int):
    return read_reviews(SHARIAH_FILE)


def registry():
    try:
        return load_reviews(SHARIAH_FILE.stat().st_mtime_ns if SHARIAH_FILE.exists() else 0)
    except Exception as e:
        st.error(f"Manual registry invalid. Fail-closed: no Shariah clearance. {type(e).__name__}: {e}")
        return {}


def last_snapshot():
    if not RESULTS_FILE.exists() or not STATUS_FILE.exists():
        st.info("No market snapshots yet. Run GitHub Actions → US Market Momentum Scan.")
        return None
    try:
        snapshot = load_data(RESULTS_FILE.stat().st_mtime_ns, STATUS_FILE.stat().st_mtime_ns)
        if not snapshot[2]:
            st.warning("V4 technical results not generated yet. Run a NEW GitHub Actions scan after uploading scan_market.py and reversal.py.")
            return None
        return snapshot[0], snapshot[1]
    except Exception as exc:
        st.error(f"Could not load scan snapshot: {type(exc).__name__}: {exc}")
        return None


def review_label(gate: dict) -> str:
    return {"MANUALLY_REVIEWED": "Manual source review recorded", "BLOCKED": "Source status not compliant",
            "EXPIRED": "Manual review expired", "UNVERIFIED": "Syariah unverified"}.get(gate["gate"], "Syariah unverified")


def set_detail(row: dict):
    st.session_state["detail_row"] = row
    st.session_state["page"] = "Deep Dive"
    st.session_state["chart_symbol"] = ""


def card(row: dict, reg: dict, key: str):
    sym = str(row.get("Ticker", ""))
    gate = review_status(sym, reg)
    stage = str(row.get("Reversal Stage") or "No setup")
    name = re.sub(r"\s+-\s+(?:Class [A-Z] )?Common Stock.*$", "", str(row.get("Name", sym)), flags=re.I)[:64]
    tag_class = "stho-ok" if gate["gate"] == "MANUALLY_REVIEWED" else "stho-warn"
    details = f'''<div class="stho-card"><div><div class="stho-ticker">{esc(sym)}</div><div class="stho-name">{esc(name)}</div></div>
      <div class="stho-stage">{esc(stage)}<div class="stho-muted">{esc(number(row.get('Reversal Score'),0))}/10 signals</div></div></div>
    <div class="stho-statgrid">
      <div class="stho-stat"><b>{esc(number(row.get('Close ($)'),prefix='$'))}</b><span>Close</span></div>
      <div class="stho-stat"><b>{esc(number(row.get('RVOL20'),suffix='×'))}</b><span>RVOL</span></div>
      <div class="stho-stat"><b>{esc(number(row.get('RR Proxy'),suffix='×'))}</b><span>R:R proxy</span></div>
      <div class="stho-stat"><b>{esc(number(row.get('ADV60 ($M)'),prefix='$',suffix='M'))}</b><span>ADV60</span></div>
    </div><div class="{tag_class}">{esc(review_label(gate))} · {esc(gate['why'])}</div>'''
    with st.container(border=True):
        st.markdown(details, unsafe_allow_html=True)
        st.button("Open Deep Dive ↗", key=f"open_{key}_{sym}", on_click=set_detail, args=(row,), use_container_width=True)


def kpis(items):
    insides = "".join(f'<div class="stho-kpi"><strong>{esc(v)}</strong><span>{esc(k)}</span></div>' for k, v in items)
    st.markdown(f'<div class="stho-kpis">{insides}</div>', unsafe_allow_html=True)


def discover(reg: dict):
    result = last_snapshot()
    if result is None:
        return
    df, state = result
    total = int(state.get("universe_count", 0))
    n = int(state.get("ever_scanned", len(df)))
    valid_technical = df["Reversal Stage"].isin(["Reversal watch", "Breakout review", "Extended"]) & df["Recent"]
    screened = df[valid_technical].copy()
    gate_map = {t: review_status(t, reg) for t in screened["Ticker"].astype(str).unique()}
    screened["Shariah Gate"] = screened["Ticker"].map(lambda t: gate_map[str(t)]["gate"])
    manually = screened[screened["Shariah Gate"] == "MANUALLY_REVIEWED"]
    kpis([("Historical coverage", f"{n}/{total}"), ("Recent technical setups", str(len(screened))),
          ("Manual source reviewed", str(len(manually)))])
    st.caption(f"Batch run {str(state.get('last_run_utc', '—'))[:16]} UTC · Scans rotate; not a full-market daily feed")
    with st.expander("Coverage, scan quality & limitations"):
        st.progress(min(n / total, 1.) if total else 0.)
        st.write(f"{(100*n/total if total else 0):.1f}% ever scanned; stale history is not included in fresh shortlist.")
        st.caption(f"Latest batch: {state.get('batch_succeeded','—')}/{state.get('batch_requested','—')} successfully scored; {state.get('batch_failed','—')} failures")
        st.caption("No earnings-calendar check; confirm earnings and broker prices independently before any trade.")
    st.subheader("Early Reversal Discover")
    st.caption("Default: only tickers with valid MANUALLY RECORDED evidence. The app never verifies a source report for you.")
    include_uncleared = st.checkbox("Show research-only (Shariah not cleared)", value=False,
                                    help="Shows unverified, expired or blocked as research; these are NOT buy candidates.")
    stage = st.selectbox("Setup", STAGES, index=0)
    only_recent = st.checkbox("Recent bars only", value=True)
    with st.expander("Additional filters"):
        min_rvol = st.slider("Min relative volume", 0.0, 4.0, 0.0, step=.25)
        limit = st.slider("Maximum cards", 3, 40, 12, step=1)
    selected = df.copy()
    if only_recent:
        selected = selected[selected["Recent"]]
    if stage == "All setups":
        selected = selected[selected["Reversal Stage"].isin(["Breakout review", "Reversal watch", "Extended"])]
    else:
        selected = selected[selected["Reversal Stage"] == stage]
    selected = selected[pd.to_numeric(selected["RVOL20"], errors="coerce") >= min_rvol]
    selected["Shariah Gate"] = selected["Ticker"].map(lambda t: review_status(t, reg)["gate"])
    if not include_uncleared:
        selected = selected[selected["Shariah Gate"] == "MANUALLY_REVIEWED"]
    selected = selected.sort_values(["Reversal Score", "RVOL20"], ascending=False, na_position="last")
    st.caption(f"{len(selected)} result(s) from available data · Not live trade alerts")
    if not include_uncleared and selected.empty:
        st.info("No manually cleared matches. This is EXPECTED if data/shariah_reviews.csv is empty. Open Shariah Reviews for the manual evidence checklist.")
        st.caption(f"Technically interesting fresh rows in scanned subset: {len(screened)} (not Shariah-cleared).")
    elif selected.empty:
        st.info("No matches with current filters or data coverage. Try All setups.")
    for idx, row in enumerate(selected.head(limit).to_dict("records")):
        card(row, reg, f"discover_{idx}")
    with st.expander("Technical results table (not a Shariah certification)"):
        cols = ["Ticker", "Reversal Stage", "Shariah Gate", "Reversal Score", "RVOL20", "Close ($)", "RR Proxy", "Date", "Recent"]
        st.dataframe(selected[[c for c in cols if c in selected.columns]], hide_index=True, use_container_width=True)


def on_demand(reg: dict):
    st.subheader("My Watchlist")
    st.caption("Analyze up to 25 US symbols on demand, including Shariah status from YOUR manual registry.")
    raw = st.text_area("Tickers (comma separated)", DEFAULT_WATCH, height=70)
    if st.button("Analyze watchlist", type="primary", use_container_width=True):
        found, errors = [], []
        with st.spinner("Downloading completed daily candles..."):
            for sym in clean_tickers(raw):
                try:
                    frame = history(sym)
                    row = screen_ticker(sym, frame)
                    rev = analyze_reversal(sym, frame)
                    row.update({k:v for k,v in rev.items() if k != "Reversal Checks"})
                    row["Reversal Checks JSON"] = json.dumps(rev["Reversal Checks"])
                    row["Name"] = sym
                    found.append(row)
                except Exception as exc:
                    errors.append(f"{sym}: {type(exc).__name__}: {str(exc)[:120]}")
        st.session_state["watch_rows"] = found
        st.session_state["watch_errors"] = errors
    for i, row in enumerate(st.session_state.get("watch_rows", [])):
        card(row, reg, f"watch_{i}")
    for problem in st.session_state.get("watch_errors", []):
        st.warning(problem)


def deep_dive(reg: dict):
    st.subheader("Deep Dive")
    text = st.text_input("Research any ticker", placeholder="e.g. BMRN", max_chars=10)
    if st.button("Load ticker research", use_container_width=True):
        t = clean_tickers(text)
        if len(t) != 1:
            st.warning("Enter exactly one US ticker")
        else:
            sym = t[0]
            try:
                df = history(sym)
                row = screen_ticker(sym, df)
                rev = analyze_reversal(sym, df)
                row.update({k:v for k,v in rev.items() if k != "Reversal Checks"})
                row["Reversal Checks JSON"] = json.dumps(rev["Reversal Checks"])
                row["Name"] = sym
                st.session_state["detail_row"] = row
                st.session_state["chart_symbol"] = ""
            except Exception as exc:
                st.error(f"Could not analyze {sym}: {type(exc).__name__}: {str(exc)[:160]}")
    row = st.session_state.get("detail_row")
    if not row:
        st.info("Select a stock in Discover or enter its ticker.")
        return
    sym = str(row["Ticker"])
    gate = review_status(sym, reg)
    st.markdown(f"### {esc(sym)} · {esc(row.get('Reversal Stage', 'Unknown'))}")
    if gate["gate"] != "MANUALLY_REVIEWED":
        st.error(f"NOT SHARIAH-CLEARED. {gate['why']}. Technical research only; not eligible for buy shortlist.")
    else:
        st.success(f"Manual source review recorded, AAOIFI; checked within {MAX_AGE_DAYS} days. Status NOT independently verified by this app.")
        if gate.get("evidence"):
            st.link_button("Open manually cited source", gate["evidence"])
    kpis([("Close", number(row.get("Close ($)"),prefix="$")), ("RVOL20", number(row.get("RVOL20"),suffix="×")),
          ("Reference R:R", number(row.get("RR Proxy"),suffix="×"))])
    st.caption(f"Daily bar {row.get('Date','—')} · Pivot {number(row.get('Pivot ($)'),prefix='$')} · Stop reference {number(row.get('Stop Ref ($)'),prefix='$')} · Overhead reference {number(row.get('Target Ref ($)'),prefix='$')}")
    st.warning("Pivot, stop and overhead are algorithmic reference levels, NOT guaranteed 1–2 week targets. Earnings dates, gaps, spreads and news NOT checked.")
    try:
        checks = json.loads(row.get("Reversal Checks JSON", "{}"))
    except (TypeError, ValueError):
        checks = {}
    with st.expander("All reversal checks", expanded=True):
        if checks:
            for k, v in checks.items():
                st.write(("✅ " if v else "❌ ") + str(k))
        else:
            st.caption("Checks not recorded. Run latest scanner or research ticker on demand.")
    st.subheader("Price & EMAs")
    if st.button("Load interactive chart", use_container_width=True):
        st.session_state["chart_symbol"] = sym
    if st.session_state.get("chart_symbol") == sym:
        try:
            df = history(sym)
            plot = pd.DataFrame(index=df.index)
            plot["Close"] = df["Close"]
            for period in [10, 21, 50, 200]:
                plot[f"EMA{period}"] = df["Close"].ewm(span=period, adjust=False, min_periods=period).mean()
            st.line_chart(plot.tail(190), use_container_width=True)
        except Exception as exc:
            st.error(f"Chart error: {type(exc).__name__}: {str(exc)[:140]}")
    with st.expander("Why this is NOT a trade recommendation"):
        st.write("1. A pattern backtest is required. 2. The OHLCV feed is unofficial. 3. Earnings and catalysts are not checked. 4. Shariah reports are entered manually by the user. 5. The market scanner has only progressive partial coverage.")


def shariah_reviews(reg: dict):
    st.subheader("Shariah Reviews — manual only")
    st.warning("No stock is automatically labelled compliant. Empty or invalid reviews are blocked from the main shortlist.")
    st.write("Check a stock-specific screening report yourself using a consistent methodology (here: AAOIFI). Record BOTH business and financial screens as PASS, the report's stated status, direct HTTPS evidence link, date, provider and reviewer alias.")
    st.caption("The app validates that a complete source-linked record was entered; it cannot read the linked report or certify its accuracy.")
    st.markdown("**Edit:** `data/shariah_reviews.csv` in your GitHub repository → pencil → add a CSV row → Commit changes.")
    st.code(",".join(COLUMNS), language="text")
    st.caption(f"Our *operational* evidence recheck interval is {MAX_AGE_DAYS} days, not a religious ruling. Recheck when new financial reports or major business changes arise.")
    st.write("**Methodology guide:** [Zoya screening explanation](https://help.zoya.finance/en/articles/4189798-how-does-zoya-screen-stocks-for-shariah-compliance). Do not copy a homepage as evidence; use the particular ticker's report, and record your manual inspection.")
    if not reg:
        st.info("Registry currently has no reviewed tickers. This is safe and expected initially.")
        return
    records = []
    for ticker in sorted(reg):
        result = review_status(ticker, reg)
        records.append({"Ticker":ticker,"Gate":result["gate"],"Reason":result["why"]})
    st.dataframe(pd.DataFrame(records),hide_index=True,use_container_width=True)
    st.caption("If multiple rows exist for the same ticker, they are blocked until reconciled. Do not enter personal identity, passwords or API keys in a public repository.")


def about():
    st.subheader("STHO V4 — Early Reversal Swing")
    st.write("**Aim:** locate recent downtrend-to-base / EMA reclaim / volume breakout patterns that may warrant further research for a 1–2-week swing. No guaranteed price predictions.")
    st.write("**Technical stages:** Reversal watch, Breakout review, Extended, No setup. Breakout review includes risk/reward proxy >=2 and basic liquidity gates. Exact thresholds are experimental, not optimized.")
    st.write("**Shariah default:** no stock passed. Only manual AAOIFI reviews with business/financial PASS, report-specific HTTPS source, reviewer and recent date enter the shortlist. The app does not verify external report content.")
    st.write("**Data:** progressive US universe via Nasdaq Trader symbols, unofficial Yahoo Finance historical EOD pricing, rotated GitHub Actions. Does not check earnings, company announcements, corporate actions beyond data feed, or compliance changes.")
    st.write("**V4 migration:** replace app.py and scan_market.py; add reversal.py, shariah_gate.py and data/shariah_reviews.csv. Keep metrics.py, requirements.txt, workflow and theme. Trigger a NEW scan to calculate reversal fields.")


st.markdown('''<div class="stho-head"><div><div class="stho-brand">STHO<span>•</span>Reversal</div>
<div class="stho-sub">Shariah-first · Early reversal · 1–2 week research</div></div>
<div class="stho-chip">V4 · EOD</div></div>''', unsafe_allow_html=True)
st.session_state.setdefault("page", "Discover")
st.session_state.setdefault("detail_row", None)
st.session_state.setdefault("chart_symbol", "")
page = st.selectbox("Navigate", PAGES, key="page", label_visibility="collapsed")
reviews = registry()
if page == "Discover":
    discover(reviews)
elif page == "My Watchlist":
    on_demand(reviews)
elif page == "Deep Dive":
    deep_dive(reviews)
elif page == "Shariah Reviews":
    shariah_reviews(reviews)
else:
    about()
st.divider()
st.caption("STHO V4 · Research-only EOD snapshots · Manual evidence ≠ independent Shariah certification · Not investment advice")
