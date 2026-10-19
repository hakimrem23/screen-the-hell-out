"""Mobile-friendly, end-of-day US *watchlist* momentum screener."""
from __future__ import annotations

import re
import pandas as pd
import streamlit as st
import yfinance as yf
from metrics import screen_ticker

st.set_page_config(page_title="Screen The Hell Out", page_icon="📈", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.65rem;}
</style>""", unsafe_allow_html=True)
st.title("📈 Screen The Hell Out")
st.caption("US stock watchlist screener · daily candles · research only · data may be delayed")

DEFAULTS = "NVDA, MRVL, MU, BMRN, AVGO, AMD, CLSK, SOFI, RKLB, TSLA, AMZN, PLTR"

def parse_tickers(raw: str) -> list[str]:
    candidates = re.split(r"[,\n\s]+", raw.upper())
    valid = []
    for symbol in candidates:
        if symbol and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol) and symbol not in valid:
            valid.append(symbol)
    return valid[:25]

@st.cache_data(ttl=900, show_spinner=False)
def get_history(ticker: str) -> pd.DataFrame:
    # Yahoo Finance is an unofficial source: requests can fail or be rate-limited.
    df = yf.Ticker(ticker).history(period="2y", interval="1d", auto_adjust=True, actions=False)
    if df.empty:
        raise ValueError("No data returned by provider")
    return df

with st.expander("⚙️ Watchlist settings", expanded=True):
    raw = st.text_area("Tickers (US; comma/newline separated; max 25)", value=DEFAULTS, height=85)
    st.caption("Price data via Yahoo Finance/yfinance (unofficial; may be delayed or temporarily unavailable).")
    refresh = st.button("🔄 Scan / refresh watchlist", type="primary", use_container_width=True)

tickers = parse_tickers(raw)
if not tickers:
    st.warning("Enter at least one valid US ticker.")
    st.stop()

if refresh:
    get_history.clear()

records = []
errors = []
frames = {}
with st.spinner(f"Checking {len(tickers)} tickers..."):
    for ticker in tickers:
        try:
            df = get_history(ticker)
            result = screen_ticker(ticker, df)
            records.append(result)
            frames[ticker] = df
        except Exception as exc:
            errors.append(f"{ticker}: {str(exc)[:170]}")

if not records:
    st.error("No tickers returned sufficient valid data. Do not treat data failures as failed screening signals.")
    for err in errors:
        st.caption(err)
    st.stop()

results = sorted(records, key=lambda x: (-x["Score"], -x["1M (%)"], x["Ticker"]))
metrics = st.columns(3)
metrics[0].metric("Perfect (9/9)", sum(x["Score"] == 9 for x in results))
metrics[1].metric("Near Miss (7–8)", sum(7 <= x["Score"] <= 8 for x in results))
metrics[2].metric("Watch (6/9)", sum(x["Score"] == 6 for x in results))

scan_tab, chart_tab, help_tab = st.tabs(["📋 Results", "📉 Chart", "ℹ️ Rules"])
with scan_tab:
    category = st.selectbox("Filter", ["All", "Perfect Momentum", "Near Miss", "Watch", "Below Watch"])
    rows = [r for r in results if category == "All" or r["Category"] == category]
    cols = ["Ticker", "Date", "Close ($)", "Score", "Category", "ADR20 (%)", "1M (%)", "3M (%)", "6M (%)", "ADV60 ($M)"]
    st.dataframe(pd.DataFrame(rows, columns=cols), hide_index=True, use_container_width=True)
    st.caption("Scores use the last completed US trading-day bar (not intraday triggers). 9/9 is a filter result, not a buy recommendation.")
    choices = [r["Ticker"] for r in results]
    selected = st.selectbox("Inspect rule-by-rule score", choices)
    info = next(x for x in results if x["Ticker"] == selected)
    st.markdown("  ".join([f"{'✅' if ok else '❌'} {rule}" for rule, ok in info["Rule details"].items()]))
    if errors:
        with st.expander(f"⚠️ Data unavailable for {len(errors)} ticker(s)"):
            for err in errors:
                st.write(err)

with chart_tab:
    choice = st.selectbox("Ticker chart", [r["Ticker"] for r in results], key="chart_choice")
    df = frames[choice].copy()
    p = df[["Close"]].dropna().tail(300).copy()
    for length in [10, 21, 50, 200]:
        # Warm up from all available history before selecting last 300 bars.
        p[f"EMA{length}"] = df["Close"].ewm(span=length, adjust=False, min_periods=length).mean().reindex(p.index)
    st.line_chart(p, use_container_width=True)
    st.caption("Indicator chart is indicative; today's unfinished candle may appear here. Screening scores exclude an unfinished daily candle.")

with help_tab:
    st.markdown("""**9 strict criteria:**
    1. Close > EMA50
    2. Close > EMA200
    3. EMA10 > EMA21
    4. ADR(20) > 5%, defined here as the mean of `(High−Low)/Close × 100` over 20 completed sessions
    5. Close > $1
    6. 1-month change > 30% (21 trading sessions)
    7. 3-month change > 30% (63 trading sessions)
    8. 6-month change > 30% (126 trading sessions)
    9. ADV(60) > $100 million, using average daily `Close × Volume` over 60 sessions

    **Categories:** Perfect = 9/9 · Near Miss = 7–8/9 · Watch = 6/9 · Below Watch = 0–5/9.

    **Limitations:** This scans only the tickers you enter, not the whole US market. Market data can be delayed, rate-limited, or wrong. No news or catalysts, alerts, entries, trading, stop-losses, or guarantees are included in v1. Validate any result against your broker before trading. Personal watchlist research only. Check data-provider terms before redistributing data.
    """)
