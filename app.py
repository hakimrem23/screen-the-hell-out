"""STHO Terminal V3 — mobile-first interface over existing V2 scan snapshots.

Keep metrics.py, scan_market.py, workflow and requirements.txt from V2 unchanged.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

from metrics import RULE_LABELS, screen_ticker

ROOT = Path(__file__).resolve().parent
RESULTS_FILE = ROOT / "data" / "market_results.csv"
STATUS_FILE = ROOT / "data" / "scan_status.json"
DEFAULT_TICKERS = "NVDA, MRVL, MU, BMRN, AVGO, AMD, CLSK, SOFI, RKLB, TSLA, AMZN, PLTR"
NAV = ["Discover", "My Watchlist", "Deep Dive", "About"]
RANKS = ["All", "9/9", "7–8/9", "6/9"]
METRIC_FIELDS = ["Score", "Close ($)", "ADR20 (%)", "1M (%)", "3M (%)", "6M (%)", "ADV60 ($M)"]

st.set_page_config(page_title="STHO Terminal", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """<style>
    .block-container {max-width: 1120px; padding-top: 0.8rem; padding-bottom: 2.4rem;}
    h1,h2,h3 {letter-spacing: -.035em;}
    [data-testid="stHeader"] {background: transparent;}
    [data-testid="stSidebar"] {background: #111925;}
    .stApp {background: #0b111b;}
    .stButton > button[kind="primary"] {background: #1ba88f; color: #031814; border: none;}
    .stButton > button {border-radius: 12px; min-height: 2.6rem;}
    [data-testid="stVerticalBlockBorderWrapper"] {border-color: #263344 !important; border-radius: 16px !important;}
    div[data-testid="stAlert"] {border-radius: 12px;}
    .stho-head {display:flex; align-items:center; justify-content:space-between; margin: 0 0 12px; gap:10px;}
    .stho-logo {color: #f0f5fb; font-size: 1.45rem; font-weight: 780; letter-spacing: -.06em;}
    .stho-logo span {color: #54dbbe;}
    .stho-sub {color: #8d9db0; font-size: .79rem; margin-top: -3px;}
    .stho-pill {color:#7be0c7; background:#14352f; border:1px solid #275748; border-radius:999px; padding:5px 10px; font-size:.72rem; white-space:nowrap;}
    .stho-grid {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:9px; margin:12px 0 16px;}
    .stho-kpi {background:#141e2b;border:1px solid #243144;border-radius:14px;padding:13px 10px;min-width:0;}
    .stho-num {font-size: clamp(1.15rem,3.8vw,1.85rem);font-weight:750;color:#edf5fb;line-height:1.25;}
    .stho-label {color:#8797ac;font-size:.72rem;margin-top:6px;}
    .stho-stock-head {display:flex;align-items:flex-start;justify-content:space-between;gap:10px;}
    .stho-ticker {font-size:1.17rem;font-weight:750;color:#f1f6ff;letter-spacing:-.02em;}
    .stho-company {color:#8999ad;font-size:.78rem;line-height:1.4;margin-top:2px;}
    .stho-score {font-size:1.22rem;font-weight:750;color:#6ce0c5;text-align:right;white-space:nowrap;}
    .stho-score.low {color:#c7d0db;}
    .stho-score small {display:block;font-weight:400;font-size:.66rem;color:#8b9bb0;}
    .stho-stats {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:12px 0 5px;}
    .stho-stat {padding:9px;background:#0e1621;border-radius:9px;min-width:0;}
    .stho-stat strong {display:block;font-size:.86rem;color:#eaf3fa;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .stho-stat span {font-size:.68rem;color:#8294a9;}
    .stho-note {color:#99a9ba;font-size:.78rem;line-height:1.5;margin-top:6px;}
    .stho-section {font-size:1.08rem;color:#eaf1fa;font-weight:730;margin:14px 0 8px;}
    .stho-empty {padding:23px 14px;border:1px dashed #334356;border-radius:14px;color:#acbbcd;text-align:center;}
    @media (max-width: 700px) {
      .block-container {padding-left: 1rem; padding-right: 1rem; padding-top: .6rem;}
      .stho-logo {font-size: 1.32rem;}
      .stho-kpi {padding: 10px 8px;}
      .stho-grid {gap:7px;}
      .stho-stat {padding:8px 6px;}
    }
    </style>""",
    unsafe_allow_html=True,
)


def clean_tickers(text: str) -> list[str]:
    return list(dict.fromkeys(
        token for token in re.split(r"[\s,]+", text.upper())
        if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", token)
    ))[:25]


@st.cache_data(ttl=1200, show_spinner=False)
def history(symbol: str) -> pd.DataFrame:
    frame = yf.Ticker(symbol).history(period="2y", interval="1d", auto_adjust=True, actions=False)
    if frame.empty:
        raise ValueError("No historical prices returned")
    return frame


@st.cache_data(ttl=600, show_spinner=False)
def snapshot(data_mtime: int, status_mtime: int) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(RESULTS_FILE)
    state = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    for col in METRIC_FIELDS:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    # Recent means recent checked row AND recent daily bar; it is not a live quote.
    now = pd.Timestamp.now(tz="UTC")
    bars = pd.to_datetime(frame["Date"], utc=True, errors="coerce")
    checked = pd.to_datetime(frame["Scanned at UTC"], utc=True, errors="coerce")
    bar_days = (now - bars).dt.total_seconds() / 86400
    scan_days = (now - checked).dt.total_seconds() / 86400
    frame["Recent"] = (bar_days.between(-1, 5) & scan_days.between(-1, 5)).fillna(False)
    return frame, state


def rules_for(row: dict) -> dict[str, bool]:
    if isinstance(row.get("Rule details"), dict):
        return row["Rule details"]
    raw = row.get("Rules JSON", "{}")
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else {}
        return {str(k): bool(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def score_of(row: dict) -> int:
    try:
        score = int(float(row.get("Score", -1)))
        return score if 0 <= score <= 9 else -1
    except (ValueError, TypeError, OverflowError):
        return -1


def fmt(row: dict, key: str, suffix: str = "", prefix: str = "") -> str:
    try:
        value = float(row[key])
        if pd.isna(value):
            return "—"
        return f"{prefix}{value:,.2f}{suffix}"
    except (TypeError, ValueError, KeyError):
        return "—"


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def small_kpis(pairs: list[tuple[str, str]]) -> None:
    contents = "".join(
        f'<div class="stho-kpi"><div class="stho-num">{esc(value)}</div><div class="stho-label">{esc(label)}</div></div>'
        for label, value in pairs
    )
    st.markdown(f'<div class="stho-grid">{contents}</div>', unsafe_allow_html=True)


def set_details(symbol: str, row: dict) -> None:
    # Callback runs before Streamlit reconstructs the nav widget on next rerun.
    st.session_state["detail_symbol"] = symbol
    st.session_state["detail_row"] = dict(row)
    st.session_state["nav_radio"] = "Deep Dive"
    st.session_state["chart_symbol"] = ""


def stock_card(row: dict, uid: str) -> None:
    sym = str(row.get("Ticker", "—"))
    score = score_of(row)
    rules = rules_for(row)
    failed = [k for k, value in rules.items() if not value]
    adv = row.get("ADV60 ($M)", 0)
    try:
        liquid = float(adv) >= 100
    except (TypeError, ValueError):
        liquid = False
    name = str(row.get("Name", sym))
    if len(name) > 58:
        name = name[:55].rstrip() + "…"
    summary = ("All nine momentum checks passed" if score == 9 else
               "; ".join(failed[:2]) if failed else "Open analysis for rule details")
    risk = " · Below $100M daily liquidity" if not liquid else ""
    content = f'''<div class="stho-stock-head">
      <div><div class="stho-ticker">{esc(sym)}</div><div class="stho-company">{esc(name)}</div></div>
      <div class="stho-score{'' if score >= 7 else ' low'}">{score if score >= 0 else '—'}/9<small>Momentum</small></div>
    </div><div class="stho-stats">
      <div class="stho-stat"><strong>{esc(fmt(row, 'Close ($)', prefix='$'))}</strong><span>Last close</span></div>
      <div class="stho-stat"><strong>{esc(fmt(row, '1M (%)', suffix='%'))}</strong><span>1M return</span></div>
      <div class="stho-stat"><strong>{esc(fmt(row, 'ADV60 ($M)', suffix='M', prefix='$'))}</strong><span>ADV60</span></div>
    </div><div class="stho-note">{esc(summary + risk)}</div>'''
    with st.container(border=True):
        st.markdown(content, unsafe_allow_html=True)
        st.button("View analysis  ↗", key=f"card_{uid}_{sym}", on_click=set_details,
                  args=(sym, row), use_container_width=True)


def get_market() -> tuple[pd.DataFrame, dict] | None:
    if not RESULTS_FILE.exists() or not STATUS_FILE.exists():
        st.info("First run needed: GitHub → Actions → US Market Momentum Scan → Run workflow. Data will appear after the first successful scan.")
        return None
    try:
        return snapshot(RESULTS_FILE.stat().st_mtime_ns, STATUS_FILE.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
        st.error(f"Could not read market snapshot: {type(exc).__name__}: {exc}")
        return None


def discover(market: tuple[pd.DataFrame, dict] | None) -> None:
    st.markdown('<div class="stho-section">Market overview</div>', unsafe_allow_html=True)
    if market is None:
        return
    frame, state = market
    total = int(state.get("universe_count", 0))
    count = int(state.get("ever_scanned", len(frame)))
    recent = int(frame["Recent"].sum())
    small_kpis([("Universe", f"{total:,}"), ("Ever scanned", f"{count:,}"), ("Recent rows", f"{recent:,}")])
    coverage = 100 * count / total if total else 0
    st.caption(f"Coverage {coverage:.1f}% · Partial US market scan · Last run {str(state.get('last_run_utc', 'unknown'))[:16]} UTC")
    st.progress(min(1.0, count / total) if total else 0.0)

    st.markdown('<div class="stho-section">Discover candidates</div>', unsafe_allow_html=True)
    category = st.radio("Momentum category", RANKS, horizontal=True, label_visibility="collapsed", key="rank_filter")
    c1, c2 = st.columns(2)
    with c1:
        only_liquid = st.checkbox("ADV ≥ $100M", value=True, help="Excludes thinly traded stocks from the main shortlist; scores themselves are unchanged.")
    with c2:
        recent_only = st.checkbox("Recent only", value=True, help="Daily bar and scan both within 5 calendar days; still not live data.")
    with st.expander("More filters"):
        sort = st.selectbox("Sort by", ["Momentum score", "1M performance", "Dollar volume"], key="market_sort")
        max_cards = st.slider("Candidates to display", 3, 30, 9, step=3)

    shown = frame.copy()
    if recent_only:
        shown = shown[shown["Recent"]]
    if only_liquid:
        shown = shown[shown["ADV60 ($M)"] >= 100]
    if category == "9/9":
        shown = shown[shown["Score"] == 9]
    elif category == "7–8/9":
        shown = shown[shown["Score"].between(7, 8)]
    elif category == "6/9":
        shown = shown[shown["Score"] == 6]
    sort_cols = {"Momentum score": ["Score", "1M (%)"],
                 "1M performance": ["1M (%)", "Score"],
                 "Dollar volume": ["ADV60 ($M)", "Score"]}[sort]
    shown = shown.sort_values(sort_cols, ascending=False, na_position="last")
    st.caption(f"{len(shown):,} candidates match your filters · Showing up to {max_cards}")
    if shown.empty:
        st.markdown('<div class="stho-empty">No matches in the scanned data. Try another category or turn off a filter.</div>', unsafe_allow_html=True)
    else:
        for index, row in enumerate(shown.head(max_cards).to_dict("records")):
            stock_card(row, f"discover_{index}")

    with st.expander("Advanced: full data table"):
        columns = ["Ticker", "Date", "Score", "Category", "Close ($)", "1M (%)", "3M (%)", "6M (%)", "ADR20 (%)", "ADV60 ($M)", "Recent"]
        st.dataframe(shown[[col for col in columns if col in shown.columns]], hide_index=True,
                     use_container_width=True, height=380)
    with st.expander("Data quality & scan coverage"):
        st.write("This is a progressive scan, not a daily full-market scan. Missing stocks have NOT failed the screener. Old scores can become invalid as prices move.")
        st.write(f"Latest batch: {state.get('batch_succeeded', '—')}/{state.get('batch_requested', '—')} succeeded · {state.get('batch_failed', '—')} failures")
        st.write(f"Universe source: {state.get('source_status', 'Unknown')}")
        st.write("Yahoo Finance via yfinance is an unofficial, best-effort source. Confirm current prices and volume with your broker before trading.")
        for error in state.get("failed_examples", [])[:6]:
            st.caption(str(error))


def my_watchlist() -> None:
    st.markdown('<div class="stho-section">Your tickers</div>', unsafe_allow_html=True)
    st.caption("On-demand scan · up to 25 US symbols · current browser session")
    raw = st.text_area("Tickers separated by commas", value=DEFAULT_TICKERS, key="watch_input", height=80)
    symbols = clean_tickers(raw)
    if not symbols:
        st.warning("Enter at least one valid ticker.")
        return
    if st.button("Scan my watchlist", type="primary", use_container_width=True):
        results, errors = [], []
        with st.spinner(f"Retrieving {len(symbols)} symbols..."):
            for symbol in symbols:
                try:
                    result = screen_ticker(symbol, history(symbol))
                    result["Name"] = symbol
                    results.append(result)
                except Exception as exc:
                    errors.append(f"{symbol}: {str(exc)[:115]}")
        st.session_state["watch_results"] = results
        st.session_state["watch_errors"] = errors
    rows = st.session_state.get("watch_results", [])
    if not rows:
        st.info("Tap 'Scan my watchlist' to calculate the latest completed daily-bar momentum scores.")
        return
    rows = sorted(rows, key=lambda r: (-score_of(r), -float(r.get("1M (%)", 0))))
    small_kpis([("9/9", str(sum(score_of(r) == 9 for r in rows))),
                ("7–8/9", str(sum(7 <= score_of(r) <= 8 for r in rows))),
                ("6/9", str(sum(score_of(r) == 6 for r in rows)))])
    for i, row in enumerate(rows):
        stock_card(row, f"watch_{i}")
    errors = st.session_state.get("watch_errors", [])
    if errors:
        with st.expander(f"{len(errors)} unavailable symbol(s)"):
            for error in errors:
                st.caption(error)


def deep_dive(market: tuple[pd.DataFrame, dict] | None) -> None:
    st.markdown('<div class="stho-section">Deep Dive</div>', unsafe_allow_html=True)
    st.caption("Open any candidate from Discover, or look up a ticker directly.")
    typed = st.text_input("Ticker lookup", placeholder="e.g. BMRN", key="lookup_ticker", max_chars=10)
    if st.button("Analyze ticker", use_container_width=True):
        syms = clean_tickers(typed)
        if len(syms) != 1:
            st.warning("Enter one valid US ticker.")
        else:
            symbol = syms[0]
            with st.spinner(f"Calculating {symbol}..."):
                try:
                    row = screen_ticker(symbol, history(symbol))
                    row["Name"] = symbol
                    st.session_state["detail_symbol"] = symbol
                    st.session_state["detail_row"] = row
                    st.session_state["chart_symbol"] = ""
                except Exception as exc:
                    st.error(f"Unable to analyze {symbol}: {type(exc).__name__}: {str(exc)[:180]}")

    row = st.session_state.get("detail_row")
    if row is None and market is not None and not market[0].empty:
        row = market[0].sort_values(["Score", "1M (%)"], ascending=False).iloc[0].to_dict()
    if row is None:
        st.info("Select a candidate from Discover to inspect its score, indicators and chart.")
        return
    symbol = str(row.get("Ticker", ""))
    score = score_of(row)
    with st.container(border=True):
        st.markdown(f'**{esc(symbol)}** · {esc(row.get("Name", symbol))}')
        small_kpis([("Momentum", f"{score}/9"),
                    ("Price", fmt(row, "Close ($)", prefix="$")),
                    ("ADR20", fmt(row, "ADR20 (%)", suffix="%"))])
        st.caption(f"Last completed bar: {row.get('Date', '—')} · 1M {fmt(row, '1M (%)', suffix='%')} · 3M {fmt(row, '3M (%)', suffix='%')} · 6M {fmt(row, '6M (%)', suffix='%')}")

    rules = rules_for(row)
    if rules:
        passed = [name for name, ok in rules.items() if ok]
        failed = [name for name, ok in rules.items() if not ok]
        st.markdown("#### What passed / failed")
        if failed:
            st.warning("Failed conditions: " + "; ".join(failed))
        else:
            st.success("All nine momentum rules passed on the recorded daily bar.")
        with st.expander(f"Show all {len(rules)} rule checks"):
            for name in RULE_LABELS:
                if name in rules:
                    st.write(("✅ " if rules[name] else "❌ ") + name)
    else:
        st.info("Rule breakdown unavailable for this saved row.")

    st.markdown("#### Price & moving averages")
    st.caption("Click only when needed to avoid unnecessary Yahoo Finance requests.")
    if st.button("Load interactive chart", type="primary", use_container_width=True):
        st.session_state["chart_symbol"] = symbol
    if st.session_state.get("chart_symbol") == symbol:
        try:
            hist = history(symbol)
            chart = pd.DataFrame(index=hist.index)
            chart["Close"] = hist["Close"]
            for span in (10, 21, 50, 200):
                chart[f"EMA{span}"] = hist["Close"].ewm(span=span, adjust=False, min_periods=span).mean()
            st.line_chart(chart.tail(260), use_container_width=True)
            st.caption("Chart can include an in-progress candle. Scores use the last completed US daily bar.")
        except Exception as exc:
            st.error(f"Chart unavailable: {type(exc).__name__}: {str(exc)[:140]}")
    with st.expander("Detailed indicators"):
        for label, key, suffix, prefix in [
            ("ADR20", "ADR20 (%)", "%", ""), ("ADV60", "ADV60 ($M)", "M", "$"),
            ("1M return", "1M (%)", "%", ""), ("3M return", "3M (%)", "%", ""),
            ("6M return", "6M (%)", "%", ""),
        ]:
            st.write(f"**{label}:** {fmt(row, key, suffix=suffix, prefix=prefix)}")


def about() -> None:
    st.markdown('<div class="stho-section">How this works</div>', unsafe_allow_html=True)
    st.write("**The same original nine rules** — no thresholds have been changed by the V3 interface upgrade.")
    for index, name in enumerate(RULE_LABELS, 1):
        st.write(f"{index}. {name}")
    st.write("**Classification:** 9/9 Perfect Momentum; 7–8/9 Near Miss; 6/9 Watch; 0–5/9 Below Watch.")
    st.info("'ADV ≥ $100M' on Discover is an additional viewing filter, not a change to the nine-rule score. Turn it off to inspect low-liquidity names.")
    st.write("**Data limitations:** Yahoo historical daily price data is unofficial, may lag, and can be rate-limited. The scanner covers a rotating subset of listed US equities, not every stock on every date. Historical results can become stale. This is research support, not a buy/sell recommendation.")
    st.write("**Automation:** The existing GitHub Actions scanner and data pipeline are unchanged. V3 changes presentation only.")


st.markdown('''<div class="stho-head"><div><div class="stho-logo">STHO<span>•</span>Terminal</div>
    <div class="stho-sub">US momentum · Clean signals, deeper research</div></div>
    <div class="stho-pill">EOD · Research</div></div>''', unsafe_allow_html=True)
st.session_state.setdefault("nav_radio", "Discover")
st.session_state.setdefault("detail_row", None)
st.session_state.setdefault("chart_symbol", "")
page = st.radio("Navigation", NAV, horizontal=True, key="nav_radio", label_visibility="collapsed")
market = get_market() if page in ("Discover", "Deep Dive") else None
if page == "Discover":
    discover(market)
elif page == "My Watchlist":
    my_watchlist()
elif page == "Deep Dive":
    deep_dive(market)
else:
    about()

st.divider()
st.caption("STHO Terminal V3 · Daily completed candles · Research only · Not financial advice")
