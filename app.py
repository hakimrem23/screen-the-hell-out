"""STHO V5: clean, compact, mobile-first early-reversal research terminal.

This UI consumes V4 snapshots; no market scanner or Shariah methodology changes.
Manual evidence records do NOT constitute independently verified compliance.
"""
from __future__ import annotations

import csv
import html
import io
import json
import re
from pathlib import Path
from datetime import date

import pandas as pd
import streamlit as st
import yfinance as yf

from metrics import screen_ticker
from reversal import analyze_reversal
from shariah_gate import COLUMNS, MAX_AGE_DAYS, read_reviews, review_status
from triage import CATEGORIES, REQUIRED_CHECKS, checks as parse_checks, classify, ready, technical_reasons

BASE = Path(__file__).resolve().parent
RESULTS = BASE / "data" / "market_results.csv"
STATUS = BASE / "data" / "scan_status.json"
REGISTRY = BASE / "data" / "shariah_reviews.csv"
DEFAULT_WATCH = "MU, MRVL, BMRN, NVDA, PLTR"
CATEGORY_KEYS = {
    "Watch": "Research Watch",
    "Ready": "Technically Ready · Syariah Pending",
    "Reviewed": "Shariah-cleared Review (manual record)",
    "Excluded": "Rejected / Blocked",
}

st.set_page_config(
    page_title="STHO | Reversal Terminal V5",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""<style>
:root {color-scheme:dark;}
.stApp {background:#0b111b; color:#e8f0f7;}
.block-container {max-width:780px; padding: .55rem .85rem 3rem;}
[data-testid="stHeader"] {background:rgba(11,17,27,.93);}
[data-testid="stVerticalBlock"] {gap:.55rem;}
[data-testid="stVerticalBlockBorderWrapper"] {background:#111a27; border:1px solid #2a384a; border-radius:16px;}
.stButton>button {border-radius:12px; border:1px solid #36475a; min-height:2.5rem;}
.stButton>button[kind="primary"] {background:#55dcc0;color:#07131b;border:0;font-weight:700;}
.stho-brandline {display:flex;align-items:center;justify-content:space-between;gap:6px;margin:0 0 2px;}
.stho-brand {font-size:1.36rem;letter-spacing:-.05em;line-height:1.2;font-weight:820;color:#eff6ff;}
.stho-brand em {color:#59ddc3;font-style:normal;}
.stho-sub {color:#8ea1b6;font-size:.75rem;margin-top:4px;}
.stho-pill {display:inline-flex;border-radius:20px;padding:4px 8px;border:1px solid #23483f;background:#15332e;color:#91e8d4;font-size:.65rem;white-space:nowrap;}
.stho-hero {display:flex;align-items:center;justify-content:space-between;gap:8px;margin:10px 0 7px;}
.stho-h2 {font-size:1.14rem;font-weight:760;letter-spacing:-.035em;color:#f0f6fd;}
.stho-meta {color:#92a3b8;font-size:.72rem;line-height:1.45;}
.stho-kpis {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:3px 0 7px;}
.stho-kpi {padding:10px 8px;background:#121e2d;border:1px solid #29384b;border-radius:11px;min-width:0;}
.stho-kpi b {display:block;color:#f1f7ff;font-size:1.18rem;line-height:1.25;}
.stho-kpi span {font-size:.66rem;color:#9aafc4;}
.stho-stockhead {display:flex;align-items:flex-start;justify-content:space-between;gap:10px;}
.stho-ticker {font-size:1.12rem;font-weight:830;letter-spacing:-.025em;color:#f0f6fc;line-height:1.2;}
.stho-name {color:#879aae;font-size:.72rem;line-height:1.35;margin-top:4px;}
.stho-score {color:#65dec3;text-align:right;font-size:1.1rem;font-weight:800;line-height:1.1;white-space:nowrap;}
.stho-score small {display:block;font-size:.66rem;color:#9cb0c3;font-weight:500;margin-top:4px;}
.stho-numbers {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin:11px 0 6px;gap:6px;}
.stho-numbers div {background:#0d1724;border-radius:9px;padding:9px 7px;min-width:0;}
.stho-numbers b {font-size:.90rem;color:#eef5fb;line-height:1.2;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.stho-numbers small {color:#8ca0b4;font-size:.65rem;display:block;margin-top:5px;}
.stho-reason {font-size:.72rem;color:#d5c098;line-height:1.45;margin:6px 0 0;}
.stho-safe {color:#81dfc2;}
.stho-muted {color:#95a8b9;font-size:.76rem;line-height:1.4;}
.stho-divider {height:1px;background:#253447;margin:7px 0;}
.stho-tag {display:inline-block;padding:3px 7px;border:1px solid #46515d;border-radius:18px;color:#c7d4e0;font-size:.65rem;}
div[data-testid="stRadio"] div[role="radiogroup"] {gap:.25rem;}
div[data-testid="stRadio"] div[role="radiogroup"] label {padding:4px 7px;border-radius:10px;}
@media(max-width:480px){.block-container{padding: .55rem .7rem 2.5rem;}.stho-brand{font-size:1.24rem;}.stho-kpi{padding:8px 7px;}.stho-kpi b{font-size:1.03rem;}.stho-numbers b{font-size:.81rem;}}
</style>""", unsafe_allow_html=True)


def escape(value) -> str:
    return html.escape(str(value), quote=True)


def fmt(value, digits: int = 2, prefix: str = "", suffix: str = "") -> str:
    try:
        n = float(value)
        if pd.isna(n) or n in (float("inf"), float("-inf")):
            return "—"
        return f"{prefix}{n:,.{digits}f}{suffix}"
    except (TypeError, ValueError, OverflowError):
        return "—"


def clean_tickers(raw: str) -> list[str]:
    return list(dict.fromkeys(
        t for t in re.split(r"[,\s]+", raw.upper()) if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", t)
    ))[:25]


def short_name(value: object, max_len: int = 47) -> str:
    name = re.sub(r"\s*-\s*(?:Class [A-Z] )?Common Stock.*$", "", str(value), flags=re.I)
    return name[:max_len].rstrip() + ("…" if len(name) > max_len else "")


@st.cache_data(ttl=180, show_spinner=False)
def read_market(result_mtime: int, status_mtime: int):
    data = pd.read_csv(RESULTS, dtype={"Ticker": str})
    meta = json.loads(STATUS.read_text(encoding="utf-8"))
    if "Reversal Stage" not in data or "Reversal Checks JSON" not in data:
        raise ValueError("V4+ market results missing. Run your GitHub Actions scanner again.")
    number_cols = ["Close ($)", "Reversal Score", "RVOL20", "RR Proxy", "ADV60 ($M)",
                   "ADR20 (%)", "Pivot ($)", "Stop Ref ($)", "Target Ref ($)", "Pivot Extension (%)"]
    for field in number_cols:
        if field in data:
            data[field] = pd.to_numeric(data[field], errors="coerce")
    for field in ("Date", "Scanned at UTC"):
        if field not in data:
            data[field] = pd.NaT
    now = pd.Timestamp.now(tz="UTC")
    bar = pd.to_datetime(data["Date"], utc=True, errors="coerce")
    scan = pd.to_datetime(data["Scanned at UTC"], utc=True, errors="coerce")
    data["Recent"] = (((now - bar).dt.total_seconds() / 86400).between(-1, 4) &
                      ((now - scan).dt.total_seconds() / 86400).between(-1, 4)).fillna(False)
    data["Reversal Stage"] = data["Reversal Stage"].fillna("No setup")
    return data, meta


@st.cache_data(ttl=180, show_spinner=False)
def read_registry(modified_ns: int):
    return read_reviews(REGISTRY)


@st.cache_data(ttl=900, show_spinner=False)
def load_price_history(ticker: str):
    frame = yf.Ticker(ticker).history(period="2y", interval="1d", auto_adjust=True, actions=False)
    if frame.empty:
        raise ValueError("No price history from provider")
    return frame


def registry():
    try:
        return read_registry(REGISTRY.stat().st_mtime_ns if REGISTRY.exists() else 0)
    except Exception as exc:
        st.error(f"Syariah registry cannot be read; fail-closed. {type(exc).__name__}: {exc}")
        return {}


def snapshot():
    if not RESULTS.exists() or not STATUS.exists():
        st.info("No results yet. Run **GitHub Actions → US Market Momentum Scan** first.")
        return None
    try:
        return read_market(RESULTS.stat().st_mtime_ns, STATUS.stat().st_mtime_ns)
    except Exception as exc:
        st.error(f"Snapshot unavailable: {type(exc).__name__}: {exc}")
        return None


def go_to_detail(row: dict):
    st.session_state["detail_row_v5"] = row
    st.session_state["nav_v5"] = "Deep Dive"
    st.session_state["plot_ticker_v5"] = ""


def card(row: dict, reg: dict, idx: int, origin="d"):
    sym = str(row.get("Ticker", ""))
    gate = review_status(sym, reg)
    bucket = classify(row, gate)
    issues = technical_reasons(row)
    # A score measures checked flags, not likelihood of making money.
    score = fmt(row.get("Reversal Score"), 0)
    label = "Manual source record · verify report" if gate["gate"] == "MANUALLY_REVIEWED" else (
        "Source status blocks shortlist" if gate["gate"] == "BLOCKED" else "Syariah not cleared")
    hint = " · ".join(issues[:2]) if issues else "Recorded numeric technical checks met; validate earnings and price"
    tip_class = "stho-safe" if bucket == CATEGORY_KEYS["Reviewed"] else ""
    title = f'''<div class="stho-stockhead"><div><div class="stho-ticker">{escape(sym)}</div>
        <div class="stho-name">{escape(short_name(row.get('Name',sym)))}</div></div>
        <div class="stho-score">{escape(score)}/10<small>{escape(str(row.get('Reversal Stage','—')))}</small></div></div>
        <div class="stho-numbers">
        <div><b>{escape(fmt(row.get('Close ($)'), prefix='$'))}</b><small>Last close</small></div>
        <div><b>{escape(fmt(row.get('RVOL20'),suffix='×'))}</b><small>RVOL</small></div>
        <div><b>{escape(fmt(row.get('RR Proxy'),suffix='×'))}</b><small>R:R proxy</small></div>
        </div><div class="stho-reason {tip_class}">{escape(label)} · {escape(hint)}</div>'''
    with st.container(border=True):
        st.markdown(title, unsafe_allow_html=True)
        st.button("Details & chart  ↗", key=f"v5_{origin}_{idx}_{sym}",
                  use_container_width=True, on_click=go_to_detail, args=(row,))


def kpis(stats):
    st.markdown('<div class="stho-kpis">' + "".join(
        f'<div class="stho-kpi"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
        for label, value in stats
    ) + '</div>', unsafe_allow_html=True)


def discoveries(reg: dict):
    item = snapshot()
    if item is None:
        return
    df, meta = item
    active = df[df["Reversal Stage"].isin(["Reversal watch", "Breakout review", "Extended"])].copy()
    if not active.empty:
        active["Bucket"] = [classify(row, review_status(str(row["Ticker"]), reg))
                            for row in active.to_dict("records")]
    else:
        active["Bucket"] = pd.Series(dtype="object")
    recent = active[active["Recent"]]
    ready_count = int((recent["Bucket"] == CATEGORY_KEYS["Ready"]).sum())
    reviewed_count = int((recent["Bucket"] == CATEGORY_KEYS["Reviewed"]).sum())
    watch_count = int((recent["Bucket"] == CATEGORY_KEYS["Watch"]).sum())

    st.markdown('<div class="stho-hero"><div class="stho-h2">Discover the turn</div>'
                '<span class="stho-pill">EOD · research only</span></div>', unsafe_allow_html=True)
    kpis([("Research", watch_count), ("Tech ready", ready_count), ("Manual record", reviewed_count)])
    universe = int(meta.get("universe_count") or 0)
    scanned = int(meta.get("ever_scanned") or len(df))
    coverage = scanned / universe * 100 if universe else 0.
    st.markdown(f'<div class="stho-meta">{coverage:.1f}% historical coverage · '
                f'{scanned:,}/{universe:,} tickers · Not a complete live-market scan</div>',
                unsafe_allow_html=True)

    st.radio("Candidate category", list(CATEGORY_KEYS), horizontal=True,
             label_visibility="collapsed", key="bucket_short_v5")
    current = CATEGORY_KEYS[st.session_state["bucket_short_v5"]]
    candidates = active[active["Bucket"] == current].copy()
    with st.expander("Search / filters / scan health", expanded=False):
        query = st.text_input("Ticker contains", placeholder="e.g. MU", key="filter_symbol_v5")
        only_recent = st.checkbox("Completed recent bars only", value=True, key="only_recent_v5",
                                  help="Old results are never promoted to technical readiness")
        min_adv = st.number_input("Minimum ADV60 ($ million)", min_value=0., max_value=5000.,
                                  value=0., step=10., key="min_adv_v5")
        limit = st.slider("Maximum cards", 4, 30, 10, key="limit_v5")
        st.caption(f"Last run (UTC): {meta.get('last_run_utc','—')} · Most recent batch: "
                   f"{meta.get('batch_succeeded','—')}/{meta.get('batch_requested','—')} processed")
        st.progress(min(max(coverage / 100, 0.), 1.))
        st.caption("Repeated favourites and provider limits reduce unique daily coverage. "
                   "The results can become stale before the scanner finishes the universe.")
        st.caption("Shariah source records are typed manually and not independently authenticated.")
    if st.session_state.get("only_recent_v5", True) and current != CATEGORY_KEYS["Excluded"]:
        candidates = candidates[candidates["Recent"]]
    query = st.session_state.get("filter_symbol_v5", "").strip().upper()
    if query:
        candidates = candidates[candidates["Ticker"].str.contains(re.escape(query), na=False, regex=True)]
    adv = pd.to_numeric(candidates.get("ADV60 ($M)", pd.Series(index=candidates.index, dtype=float)), errors="coerce")
    candidates = candidates[adv >= st.session_state.get("min_adv_v5", 0.)]
    candidates = candidates.sort_values(["Reversal Score", "RVOL20", "ADV60 ($M)"],
                                        ascending=[False, False, False], na_position="last")
    st.caption(f"{len(candidates)} matched · {current} · Not a trading signal")
    if current == CATEGORY_KEYS["Reviewed"]:
        st.warning("A manual screening record is not a verified certification. Read the linked report before trading.")
    elif current == CATEGORY_KEYS["Ready"]:
        st.warning("Technically qualified only. Syariah is pending; no buy shortlist.")
    elif current == CATEGORY_KEYS["Excluded"]:
        st.info("This includes stale/extended signals or blocked source statuses; unrated does not mean non-compliant.")
    if candidates.empty:
        st.info("No matching stocks in this scanned subset. Try **Watch** or broaden filters. "
                "The Syariah-reviewed list starts empty until manual evidence is recorded.")
    for i, row in enumerate(candidates.head(st.session_state.get("limit_v5", 10)).to_dict("records")):
        card(row, reg, i)
    with st.expander("Full results table"):
        columns = ["Ticker", "Bucket", "Reversal Stage", "Reversal Score", "Close ($)",
                   "RVOL20", "RR Proxy", "ADV60 ($M)", "Date", "Recent"]
        st.dataframe(candidates[[c for c in columns if c in candidates]],
                     hide_index=True, use_container_width=True)


def on_demand_ticker(symbol: str) -> dict:
    frame = load_price_history(symbol)
    stats = screen_ticker(symbol, frame)
    rev = analyze_reversal(symbol, frame)
    stats.update({k: v for k, v in rev.items() if k != "Reversal Checks"})
    stats["Reversal Checks JSON"] = json.dumps(rev["Reversal Checks"])
    stats["Name"] = symbol
    # Evaluate on most recently completed US session only; on-demand is not intraday.
    day = pd.to_datetime(stats.get("Date"), utc=True, errors="coerce")
    age = (pd.Timestamp.now(tz="UTC") - day).total_seconds() / 86400 if pd.notna(day) else 999
    stats["Recent"] = -1 <= age <= 4
    return stats


def watchlist(reg: dict):
    st.markdown('<div class="stho-h2">My Watchlist</div>', unsafe_allow_html=True)
    st.caption("Analyze completed daily candles for selected tickers. Not an automatic alert or persistent portfolio.")
    raw = st.text_area("Ticker symbols", DEFAULT_WATCH, height=74, key="watch_v5")
    if st.button("Analyze", type="primary", use_container_width=True, key="analyze_v5"):
        rows, errors = [], []
        with st.spinner("Checking price history (unofficial feed)…"):
            for symbol in clean_tickers(raw):
                try:
                    rows.append(on_demand_ticker(symbol))
                except Exception as exc:
                    errors.append(f"{symbol}: {type(exc).__name__}: {str(exc)[:120]}")
        st.session_state["watch_results_v5"] = rows
        st.session_state["watch_errors_v5"] = errors
    for i, row in enumerate(st.session_state.get("watch_results_v5", [])):
        card(row, reg, i, "watch")
    for warning in st.session_state.get("watch_errors_v5", []):
        st.warning(warning)


def deep_dive(reg: dict):
    st.markdown('<div class="stho-h2">Deep Dive</div>', unsafe_allow_html=True)
    st.caption("Inspect what passed, what failed, and whether a manual Syariah record exists.")
    with st.form("ticker_lookup_v5"):
        typed = st.text_input("Search by ticker", placeholder="e.g. BMRN", max_chars=10)
        submitted = st.form_submit_button("Load analysis", use_container_width=True)
    if submitted:
        values = clean_tickers(typed)
        if len(values) != 1:
            st.warning("Enter exactly one valid ticker.")
        else:
            try:
                st.session_state["detail_row_v5"] = on_demand_ticker(values[0])
                st.session_state["plot_ticker_v5"] = ""
            except Exception as exc:
                st.error(f"Could not load {values[0]}: {type(exc).__name__}: {str(exc)[:160]}")
    row = st.session_state.get("detail_row_v5")
    if not row:
        st.info("Choose a stock from Discover or enter a ticker above.")
        return
    sym = str(row.get("Ticker", ""))
    gate = review_status(sym, reg)
    bucket = classify(row, gate)
    st.markdown(f'<div class="stho-stockhead"><div><div class="stho-ticker">{escape(sym)}</div>'
                f'<div class="stho-name">{escape(short_name(row.get("Name",sym)))}</div></div>'
                f'<div class="stho-score">{fmt(row.get("Reversal Score"),0)}/10<small>'
                f'{escape(row.get("Reversal Stage", "—"))}</small></div></div>', unsafe_allow_html=True)
    st.caption(f"{bucket} · Completed daily bar: {row.get('Date','—')}")
    if gate["gate"] != "MANUALLY_REVIEWED":
        st.warning(f"**Syariah NOT cleared.** {gate['why']}. Research only; not eligible for buy shortlist.")
    else:
        st.warning("A user-recorded AAOIFI source review exists, but this app has NOT authenticated "
                   "the report or independently certified the security.")
        if gate.get("evidence"):
            st.link_button("Open source record ↗", gate["evidence"])
    kpis([("Last close", fmt(row.get("Close ($)"), prefix="$")),
          ("RVOL", fmt(row.get("RVOL20"), suffix="×")),
          ("R:R proxy", fmt(row.get("RR Proxy"), suffix="×"))])
    reasons = technical_reasons(row)
    with st.expander(f"Entry blockers ({len(reasons)})", expanded=bool(reasons)):
        if reasons:
            for reason in reasons:
                st.write("• " + reason)
        else:
            st.write("Numeric conditions passed in the recorded dataset, but this is NOT a buy signal.")
    st.markdown('<div class="stho-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="stho-h2">Reference levels</div>', unsafe_allow_html=True)
    st.caption(f"Pivot {fmt(row.get('Pivot ($)'),prefix='$')} · Stop ref {fmt(row.get('Stop Ref ($)'),prefix='$')} "
               f"· Prior overhead {fmt(row.get('Target Ref ($)'),prefix='$')}")
    st.caption("These are algorithmic reference levels, NOT tested entry/exit prices or guaranteed targets.")
    with st.expander("All 10 reversal conditions"):
        current_checks = parse_checks(row)
        if not current_checks:
            st.warning("No recorded technical checklist. Refresh scanner before evaluating this stock.")
        else:
            for field in REQUIRED_CHECKS:
                check = current_checks.get(field)
                icon = "✅" if check is True else ("❌" if check is False else "❔")
                st.write(f"{icon} {field}")
    st.markdown('<div class="stho-h2">Trend chart</div>', unsafe_allow_html=True)
    period = st.radio("Show", ["3M", "6M", "1Y"], horizontal=True, key="chart_window_v5")
    if st.button("Load chart", use_container_width=True, key="load_chart_v5"):
        st.session_state["plot_ticker_v5"] = sym
    if st.session_state.get("plot_ticker_v5") == sym:
        try:
            history = load_price_history(sym)
            from metrics import completed_daily_bars
            frame = completed_daily_bars(history)
            plot = pd.DataFrame(index=frame.index)
            plot["Close"] = frame["Close"]
            for n in (10, 21, 50, 200):
                plot[f"EMA{n}"] = frame["Close"].ewm(span=n, adjust=False, min_periods=n).mean()
            st.line_chart(plot.tail({"3M": 65, "6M": 130, "1Y": 260}[period]), use_container_width=True)
        except Exception as exc:
            st.error(f"Chart download failed: {type(exc).__name__}: {str(exc)[:140]}")
    st.caption("Before any trade: independently verify stock-specific Shariah status, earnings timing, "
               "catalysts, spreads, market regime and fees. Pattern not backtested.")


def build_review_csv(existing: dict, record: dict) -> str:
    """Generate a file for user review/download. NEVER submits claims to a provider."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    # A replacement is deliberate, not a duplicate append.
    for ticker, rows in sorted(existing.items()):
        if ticker != record["Ticker"]:
            for item in rows:
                writer.writerow({key: item.get(key, "") for key in COLUMNS})
    writer.writerow({key: record.get(key, "") for key in COLUMNS})
    return buffer.getvalue()


def shariah_center(reg: dict):
    st.markdown('<div class="stho-h2">Syariah Review Center</div>', unsafe_allow_html=True)
    st.warning("**Default = Unverified.** No stock is automatically classified as Syariah-compliant. "
               "A completed CSV record is a *manual claim*, not independent certification.")
    st.caption("Only enter results from a current **stock-specific** report you personally read. "
               "Confirm both the business and financial tests, source methodology and the date.")
    with st.expander("Prepare a manual review record", expanded=False):
        with st.form("manual_review_v5"):
            ticker = st.text_input("Ticker", placeholder="e.g. EXAMPLE", max_chars=10).strip().upper()
            reported = st.selectbox("What does the report state?", ["Choose report status…", "COMPLIANT", "NON_COMPLIANT", "QUESTIONABLE", "UNRATED"])
            business = st.selectbox("Business screen in source", ["Not checked", "PASS", "FAIL"])
            financial = st.selectbox("Financial screen in source", ["Not checked", "PASS", "FAIL"])
            provider = st.text_input("Source provider", placeholder="Source actually used")
            evidence = st.text_input("Direct HTTPS link to ticker-specific report", placeholder="https://...")
            reviewed_on = st.date_input("Date you checked the report", value=date.today())
            alias = st.text_input("Reviewer alias (not real name)", value="self")
            notes = st.text_input("Optional notes (avoid personal data)", max_chars=140)
            replace_existing = st.checkbox("Replace an earlier record for the same ticker (if present)")
            acknowledged = st.checkbox("I actually checked this ticker-specific report; this app did not verify it")
            submit = st.form_submit_button("Prepare CSV for GitHub", use_container_width=True)
        if submit:
            if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker):
                st.error("Use one valid ticker symbol.")
            elif reported == "Choose report status…":
                st.error("Select the EXACT status shown in your source report.")
            elif not acknowledged:
                st.error("Confirm you actually checked the ticker-specific source, or leave it unverified.")
            elif ticker in reg and not replace_existing:
                st.error("A record exists for this ticker. Check the replacement box to avoid duplicates.")
            else:
                record = {
                    "Ticker": ticker, "Reported_Status": reported,
                    "Business_Screen": business, "Financial_Screen": financial,
                    "Methodology": "AAOIFI", "Provider": provider.strip(),
                    "Evidence_URL": evidence.strip(), "Checked_On": reviewed_on.isoformat(),
                    "Reviewed_By": alias.strip(), "Notes": notes.strip(),
                }
                status = review_status(ticker, {ticker: [record]})
                # Reject malformed or incomplete forms. Non-compliant/questionable source
                # statuses remain BLOCKED, never treated as eligible.
                if status["gate"] not in {"MANUALLY_REVIEWED", "BLOCKED"}:
                    st.error(f"Incomplete/invalid source record: {status['why']}")
                elif not provider.strip() or not evidence.startswith("https://") or not alias.strip():
                    st.error("Source provider, full HTTPS report link and reviewer alias are required.")
                elif reported != "COMPLIANT" and (business == "Not checked" or financial == "Not checked"):
                    st.error("Document what the source reports for both screening categories.")
                else:
                    st.session_state["prepared_registry_csv_v5"] = build_review_csv(reg, record)
                    st.success("CSV prepared locally. No external report was automatically checked.")
        if st.session_state.get("prepared_registry_csv_v5"):
            st.download_button("Download shariah_reviews.csv", data=st.session_state["prepared_registry_csv_v5"],
                               file_name="shariah_reviews.csv", mime="text/csv", use_container_width=True)
            st.caption("Replace ONLY `data/shariah_reviews.csv` in GitHub and commit. "
                       "Inspect the downloaded rows first; this does not certify any company.")
    if not reg:
        st.info("No manual source review records yet. The main reviewed shortlist correctly stays empty.")
    else:
        rows = []
        for ticker in sorted(reg):
            gate = review_status(ticker, reg)
            rows.append({"Ticker": ticker, "Record status": gate["gate"], "Note": gate["why"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    with st.expander("Manual CSV fields & methodology"):
        st.code(",".join(COLUMNS), language="text")
        st.markdown("[Zoya methodology explanation](https://help.zoya.finance/en/articles/4189798-how-does-zoya-screen-stocks-for-shariah-compliance)")
        st.caption(f"The {MAX_AGE_DAYS}-day recheck window is this app's policy, not a religious ruling. "
                   "Recheck on earnings or material changes. Do not put sensitive information in public GitHub.")
    st.caption("This app validates user-entered record format/recency; it cannot read the report or independently certify Shariah compliance.")


st.markdown('<div class="stho-brandline"><div><div class="stho-brand">STHO <em>Terminal</em></div>'
            '<div class="stho-sub">Early reversal · 1–2-week swing research</div></div>'
            '<span class="stho-pill">V5 · beta</span></div>', unsafe_allow_html=True)
st.session_state.setdefault("nav_v5", "Discover")
st.session_state.setdefault("bucket_short_v5", "Watch")
st.session_state.setdefault("detail_row_v5", None)
st.session_state.setdefault("plot_ticker_v5", "")
st.radio("Navigate", ["Discover", "Watchlist", "Deep Dive", "Syariah"],
         horizontal=True, label_visibility="collapsed", key="nav_v5")
manual_reviews = registry()
section = st.session_state["nav_v5"]
if section == "Discover":
    discoveries(manual_reviews)
elif section == "Watchlist":
    watchlist(manual_reviews)
elif section == "Deep Dive":
    deep_dive(manual_reviews)
else:
    shariah_center(manual_reviews)
with st.expander("About / data quality / safety"):
    st.write("STHO V5 is an EOD, partially covered US stock research dashboard. "
             "Research Watch is not technically ready; Technically Ready does not mean Syariah cleared; "
             "a manually recorded report is not independently authenticated. No trading orders or alerts are placed.")
    st.write("The scan uses historical Yahoo Finance data in rotating batches. Rankings are incomplete and "
             "can be stale. Earnings dates and major corporate news are not checked, and 1–2-week returns "
             "have not been backtested. Review all inputs before any decision.")
st.caption("STHO V5 · End-of-day research · No automated Syariah certification or trade recommendation")
