"""Daily-bar screen criteria for a *watchlist*, not a whole-market scanner."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

RULE_LABELS = [
    "Price > EMA50",
    "Price > EMA200",
    "EMA10 > EMA21",
    "ADR20 > 5%",
    "Price > $1",
    "1M return > 30%",
    "3M return > 30%",
    "6M return > 30%",
    "ADV60 > $100M",
]


def completed_daily_bars(frame: pd.DataFrame, now_et: datetime | None = None) -> pd.DataFrame:
    """Drop the current ET session's daily candle while it may be incomplete."""
    df = frame.copy()
    if df.empty:
        return df
    df = df.sort_index()
    now_et = now_et or datetime.now(ZoneInfo("America/New_York"))
    if now_et.tzinfo is None:
        raise ValueError("now_et must be timezone aware")
    now_et = now_et.astimezone(ZoneInfo("America/New_York"))
    if now_et.hour < 16 or (now_et.hour == 16 and now_et.minute < 20):
        index_dates = pd.to_datetime(df.index).date
        df = df.loc[index_dates < now_et.date()]
    return df


def screen_ticker(symbol: str, frame: pd.DataFrame, now_et: datetime | None = None) -> dict:
    expected = {"Close", "High", "Low", "Volume"}
    if not expected.issubset(frame.columns):
        raise ValueError(f"Missing columns: {sorted(expected - set(frame.columns))}")
    df = completed_daily_bars(frame, now_et)
    df = df.copy()
    for col in expected:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=list(expected))
    df = df.loc[(df["Close"] > 0) & (df["High"] >= df["Low"]) & (df["Volume"] >= 0)]
    if len(df) < 201:
        raise ValueError("Insufficient valid daily candles (need at least 201)")

    close = df["Close"]
    ema10 = close.ewm(span=10, adjust=False, min_periods=10).mean()
    ema21 = close.ewm(span=21, adjust=False, min_periods=21).mean()
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    ema200 = close.ewm(span=200, adjust=False, min_periods=200).mean()
    adr20 = ((df["High"] - df["Low"]) / close * 100.0).tail(20).mean()
    ret1 = (close.iloc[-1] / close.iloc[-22] - 1) * 100
    ret3 = (close.iloc[-1] / close.iloc[-64] - 1) * 100
    ret6 = (close.iloc[-1] / close.iloc[-127] - 1) * 100
    adv60 = (close * df["Volume"]).tail(60).mean()
    last = float(close.iloc[-1])

    checks = [
        last > float(ema50.iloc[-1]),
        last > float(ema200.iloc[-1]),
        float(ema10.iloc[-1]) > float(ema21.iloc[-1]),
        float(adr20) > 5,
        last > 1,
        float(ret1) > 30,
        float(ret3) > 30,
        float(ret6) > 30,
        float(adv60) > 100_000_000,
    ]
    score = sum(bool(v) for v in checks)
    category = "Perfect Momentum" if score == 9 else ("Near Miss" if score >= 7 else ("Watch" if score == 6 else "Below Watch"))
    return {
        "Ticker": symbol,
        "Date": str(df.index[-1].date()),
        "Close ($)": round(last, 2),
        "Score": score,
        "Category": category,
        "ADR20 (%)": round(float(adr20), 2),
        "1M (%)": round(float(ret1), 2),
        "3M (%)": round(float(ret3), 2),
        "6M (%)": round(float(ret6), 2),
        "ADV60 ($M)": round(float(adv60) / 1_000_000, 2),
        "Rule details": dict(zip(RULE_LABELS, (bool(x) for x in checks))),
    }
