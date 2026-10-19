"""Screen The Hell Out V2: mobile watchlist + progressive US-market snapshot."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

from metrics import screen_ticker

ROOT = Path(__file__).resolve().parent
RESULTS_FILE = ROOT / "data" / "market_results.csv"
STATUS_FILE = ROOT / "data" / "scan_status.json"
DEFAULTS = "NVDA, MRVL, MU, BMRN, AVGO, AMD, CLSK, SOFI, RKLB, TSLA, AMZN, PLTR"
CATEGORIES = ["All", "Perfect Momentum", "Near Miss", "Watch", "Below Watch"]
SHOW_COLS = ["Ticker", "Name", "Exchange", "Date", "Close ($)", "Score", "Category", "ADR20 (%)", "1M (%)", "3M (%)", "6M (%)", "ADV60 ($M)"]

st.set_page_config(page_title="Screen The Hell Out · V2", page_icon="📈", layout="wide")
st.markdown("""<style>
.block-container {padding-top:1.05rem; padding-bottom:2rem;}
[data-testid='stMetricValue'] {font-size:1.45rem;}
</style>""", unsafe_allow_html=True)
st.title("📈 Screen The Hell Out · V2")
st.caption("US equities · daily EOD momentum · research only · best-effort provider data")


def parse_tickers(raw: str) -> list[str]:
    symbols = re.split(r"[,\s]+", raw.upper())
    return list(dict.fromkeys(s for s in symbols if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", s)))[:25]


@st.cache_data(ttl=1800, show_spinner=False)
def get_history(symbol: str) -> pd.DataFrame:
    df = yf.Ticker(symbol).history(period="2y", interval="1d", auto_adjust=True, actions=False)
    if df.empty:
        raise ValueError("Provider returned no daily prices")
    return df


@st.cache_data(ttl=900, show_spinner=False)
def read_snapshot(results_mtime: int, status_mtime: int) -> tuple[pd.DataFrame, dict]:
    try:
        df = pd.read_csv(RESULTS_FILE)
        status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        return df, status
    except (OSError, ValueError, json.JSONDecodeError, pd.errors.ParserError) as exc:
        raise ValueError(f"Snapshot unavailable: {exc}") from exc


def show_rule_details(row: pd.Series | dict) -> None:
    encoded = row.get("Rules JSON", "{}")
    try:
        checks = json.loads(encoded) if isinstance(encoded, str) else {}
    except json.JSONDecodeError:
        checks = {}
    for label, passed in checks.items():
        st.write(f"{'✅' if passed else '❌'} {label}")


def show_chart(symbol: str, key: str) -> None:
    if st.button(f"📉 Load chart for {symbol}", key=key, use_container_width=True):
        with st.spinner(f"Loading {symbol} chart..."):
            try:
                raw = get_history(symbol)
                chart = pd.DataFrame(index=raw.index)
                chart["Close"] = raw["Close"]
                for span in (10, 21, 50, 200):
                    chart[f"EMA{span}"] = raw["Close"].ewm(span=span, adjust=False, min_periods=span).mean()
                st.line_chart(chart.tail(300), use_container_width=True)
                st.caption("Chart may show an in-progress candle; scores use completed bars.")
            except Exception as exc:
                st.error(f"Price feed unavailable: {str(exc)[:180]}")


def market_mode() -> None:
    if not (RESULTS_FILE.exists() and STATUS_FILE.exists()):
        st.info("Market-wide scan belum dijalankan. Pergi ke GitHub → Actions → US Market Momentum Scan → Run workflow. Selepas berjaya, kembali ke sini.")
        st.caption("Tiada ranking market-wide dipaparkan sehingga data sebenar berjaya dikumpulkan. Watchlist V1 masih boleh digunakan di mod sebelah.")
        return

    try:
        df, status = read_snapshot(RESULTS_FILE.stat().st_mtime_ns, STATUS_FILE.stat().st_mtime_ns)
    except ValueError as exc:
        st.error(str(exc))
        return

    for col in ("Score", "Close ($)", "ADR20 (%)", "1M (%)", "3M (%)", "6M (%)", "ADV60 ($M)"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # A fresh technical signal requires both a recently completed price bar and a recent scan.
    day_age = (pd.Timestamp.now(tz="UTC").tz_localize(None) - pd.to_datetime(df.get("Date"), errors="coerce")).dt.days
    scan_age = (pd.Timestamp.now(tz="UTC") - pd.to_datetime(df.get("Scanned at UTC"), utc=True, errors="coerce")).dt.days
    df["Fresh"] = ((day_age <= 10) & (day_age >= -1) & (scan_age <= 10) & (scan_age >= 0)).fillna(False)

    total = int(status.get("universe_count", 0))
    scanned = int(status.get("ever_scanned", len(df)))
    fresh = int(df["Fresh"].sum())
    st.subheader("🌎 US Market Scanner")
    m1, m2, m3 = st.columns(3)
    m1.metric("Universe", f"{total:,}")
    m2.metric("Ever scanned", f"{scanned:,}")
    m3.metric("Fresh rows", f"{fresh:,}")
    pct = min(1., scanned / total) if total else 0.
    st.progress(pct, text=f"Historical coverage: {pct:.1%} · not a complete fresh-market scan")
    st.caption(f"Last run (UTC): {status.get('last_run_utc', 'unknown')} · latest batch successful: {status.get('batch_succeeded', 0)}/{status.get('batch_requested', 0)} · failures: {status.get('batch_failed', 0)}")
    if status.get("batch_failed"):
        st.warning("Some tickers failed to download or lacked 200+ completed bars. These are **not** scored zero.")
    if scanned < total:
        st.info("Progressive coverage: results only include tickers successfully checked so far. Each scheduled run rotates through more symbols; the list is NOT the whole market yet.")
    if status.get("source_status", "").startswith("Using previously saved"):
        st.warning(status["source_status"])

    fresh_only = st.checkbox("Fresh results only (last 10 days: scan + price bar)", value=True)
    category = st.selectbox("Category", CATEGORIES)
    shown = df[df["Fresh"]] if fresh_only else df
    if category != "All":
        shown = shown[shown["Category"] == category]
    shown = shown.sort_values(["Score", "1M (%)"], ascending=[False, False]) if not shown.empty else shown
    st.caption(f"Showing {len(shown):,} rows; old snapshots can misrepresent today's technical setup. Verify in broker before trading.")
    st.dataframe(shown[[c for c in SHOW_COLS if c in shown.columns]], hide_index=True, use_container_width=True, height=430)

    if not shown.empty:
        ticker = st.selectbox("Inspect candidate", shown["Ticker"].tolist(), key="market_inspect")
        found = shown[shown["Ticker"] == ticker].iloc[0]
        st.write(f"**{ticker}** · {found.get('Name', '')} · latest bar: {found.get('Date', '')}")
        show_rule_details(found)
        show_chart(ticker, "market_chart")
    with st.expander("⚠️ Coverage and data limitations"):
        st.write("Universe = Nasdaq Trader listings filtered for ETFs, test securities and obvious non-common-share instruments. This is a best-effort approximation, not a certified list of all US common shares.")
        st.write("Yahoo historical data is unofficial and can be delayed, inaccurate or rate-limited. The free scanner gradually rotates across the universe: never treat non-listed or non-fresh tickers as failed signals.")
        st.write(f"Provider/listing status: {status.get('source_status', 'unknown')}")
        for error in status.get("failed_examples", []):
            st.caption(error)


def watchlist_mode() -> None:
    st.subheader("⭐ Personal Watchlist")
    raw = st.text_area("Tickers (comma separated; up to 25)", value=DEFAULTS, height=86)
    tickers = parse_tickers(raw)
    if not tickers:
        st.warning("Enter at least one ticker.")
        return
    if st.button("🔄 Refresh watchlist", type="primary", use_container_width=True):
        get_history.clear()
    results, errors = [], []
    with st.spinner(f"Scanning {len(tickers)} symbols..."):
        for symbol in tickers:
            try:
                results.append(screen_ticker(symbol, get_history(symbol)))
            except Exception as exc:
                errors.append(f"{symbol}: {str(exc)[:140]}")
    if not results:
        st.warning("No valid tickers. Check Yahoo availability and tickers.")
        for error in errors:
            st.caption(error)
        return
    results = sorted(results, key=lambda r: (-r["Score"], -r["1M (%)"]))
    m1, m2, m3 = st.columns(3)
    m1.metric("Perfect", sum(r["Score"] == 9 for r in results))
    m2.metric("Near Miss", sum(7 <= r["Score"] <= 8 for r in results))
    m3.metric("Watch", sum(r["Score"] == 6 for r in results))
    category = st.selectbox("Filter", CATEGORIES, key="watch_category")
    visible = [r for r in results if category == "All" or r["Category"] == category]
    cols = ["Ticker", "Date", "Close ($)", "Score", "Category", "ADR20 (%)", "1M (%)", "3M (%)", "6M (%)", "ADV60 ($M)"]
    st.dataframe(pd.DataFrame(visible, columns=cols), hide_index=True, use_container_width=True)
    chosen = st.selectbox("Inspect rule details", [r["Ticker"] for r in results], key="watch_inspect")
    row = next(r for r in results if r["Ticker"] == chosen)
    for label, passed in row["Rule details"].items():
        st.write(f"{'✅' if passed else '❌'} {label}")
    show_chart(chosen, "watch_chart")
    if errors:
        with st.expander(f"⚠️ {len(errors)} data errors"):
            for error in errors:
                st.caption(error)


mode = st.radio("Mode", ["🌎 Market-wide", "⭐ My watchlist", "ℹ️ Method"], horizontal=True, label_visibility="collapsed")
if mode == "🌎 Market-wide":
    market_mode()
elif mode == "⭐ My watchlist":
    watchlist_mode()
else:
    st.markdown("""**Nine rules, calculated on last completed daily US bar:**

1. Close > EMA50
2. Close > EMA200
3. EMA10 > EMA21
4. Mean 20-day (High−Low)/Close > 5%
5. Close > $1
6. Return (21 sessions) > 30%
7. Return (63 sessions) > 30%
8. Return (126 sessions) > 30%
9. 60-session average Close × Volume > $100 million

**9/9** Perfect Momentum · **7–8/9** Near Miss · **6/9** Watch · **0–5/9** Below Watch.

Universe listings are broad but imperfect; scans process only a rotating subset each day. The dashboard shows real coverage and data timestamps. No buy/sell recommendations, intraday scan, catalyst validation, or alert automation. Validate with broker and check market-data provider terms before redistribution.
""")
