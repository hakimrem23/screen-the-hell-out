"""Research-only, end-of-day early-reversal logic; thresholds are hypotheses to backtest.

Not a complete swing strategy, trading system, earnings calendar, or Shariah assessment.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import numpy as np
from metrics import completed_daily_bars

BASE_COLS = ("Close", "High", "Low", "Volume")


def analyze_reversal(ticker: str, history: pd.DataFrame, now_et: datetime | None = None) -> dict:
    if not set(BASE_COLS).issubset(history.columns):
        raise ValueError("Missing OHLCV history")
    df = completed_daily_bars(history, now_et).sort_index().copy()
    for col in BASE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=list(BASE_COLS))
    df = df.loc[(df.Close > 0) & (df.High >= df.Low) & (df.Volume >= 0)]
    if len(df) < 240:
        raise ValueError("Need at least 240 completed daily candles")
    c, h, l, v = (df[k].astype(float) for k in BASE_COLS)
    e10 = c.ewm(span=10, adjust=False, min_periods=10).mean()
    e21 = c.ewm(span=21, adjust=False, min_periods=21).mean()
    e50 = c.ewm(span=50, adjust=False, min_periods=50).mean()
    e200 = c.ewm(span=200, adjust=False, min_periods=200).mean()
    price = float(c.iloc[-1])
    pivot = float(h.iloc[-21:-1].max())
    prior_below = int((c.iloc[-61:-1] < e200.iloc[-61:-1]).sum())
    adr = float((((h - l) / c) * 100).tail(20).mean())
    adv_m = float((c * v).tail(60).mean() / 1e6)
    vol20 = float(v.iloc[-21:-1].mean())
    rvol = float(v.iloc[-1] / vol20) if vol20 > 0 else float("nan")
    low_recent = float(l.iloc[-10:].min())
    low_prior = float(l.iloc[-20:-10].min())
    higher_low = low_recent > low_prior * 1.01
    base_width = (float(h.iloc[-21:-1].max()) / max(float(l.iloc[-21:-1].min()), 1e-12) - 1) * 100
    base = base_width <= 30
    ema10_rising = float(e10.iloc[-1]) > float(e10.iloc[-6])
    reclaim_200 = (float(c.iloc[-2]) <= float(e200.iloc[-2]) and price > float(e200.iloc[-1]))
    reclaim_50 = (float(c.iloc[-2]) <= float(e50.iloc[-2]) and price > float(e50.iloc[-1]))
    breakout_20 = price > pivot
    over_pivot = ((price / pivot) - 1) * 100 if pivot else float("nan")
    liquidity_ok = price >= 5 and adv_m >= 20 and 2.5 <= adr <= 8.0
    history_ok = prior_below >= 30
    # Reference levels, NOT executable order prices or guarantees.
    stop_ref = min(low_recent, float(e21.iloc[-1])) * .995
    target_ref = float(h.iloc[-100:-21].max())  # prior overhead, excludes breakout/base period
    risk = price - stop_ref
    reward = target_ref - price
    rr = reward / risk if risk > 0 and reward > 0 else float("nan")
    rr_ok = bool(np.isfinite(rr) and rr >= 2)
    forming = history_ok and price > float(e21.iloc[-1]) and ema10_rising and (higher_low or base or reclaim_50)
    breakout = (breakout_20 or reclaim_200) and rvol >= 1.5 and price > float(e21.iloc[-1])
    extended = breakout_20 and over_pivot > 5
    # 'Breakout review' only if all technical gates pass; no promise of future upside.
    if history_ok and liquidity_ok and breakout and (higher_low or base) and rr_ok and not extended:
        stage = "Breakout review"
    elif history_ok and liquidity_ok and extended:
        stage = "Extended"
    elif forming:
        stage = "Reversal watch"
    else:
        stage = "No setup"
    flags = {
        "Formerly below EMA200 ≥30/60": history_ok,
        "Last price ≥$5": price >= 5,
        "ADV60 ≥$20M": adv_m >= 20,
        "ADR20 2.5–8%": 2.5 <= adr <= 8,
        "Base or higher low": bool(base or higher_low),
        "EMA10 rising; close > EMA21": bool(ema10_rising and price > e21.iloc[-1]),
        "20D breakout or EMA200 reclaim": bool(breakout_20 or reclaim_200),
        "RVOL20 ≥1.5×": bool(np.isfinite(rvol) and rvol >= 1.5),
        "Reference RR ≥2": rr_ok,
        "Not extended >5% above pivot": bool(not extended),
    }
    return {
        "Reversal Stage": stage,
        "Reversal Score": int(sum(flags.values())),
        "Below EMA200 Days (60)": prior_below,
        "RVOL20": round(rvol, 2) if np.isfinite(rvol) else None,
        "Pivot ($)": round(pivot, 3),
        "Stop Ref ($)": round(stop_ref, 3),
        "Target Ref ($)": round(target_ref, 3),
        "RR Proxy": round(rr, 2) if np.isfinite(rr) else None,
        "Pivot Extension (%)": round(over_pivot, 2),
        "EMA200 Gap (%)": round((price / float(e200.iloc[-1]) - 1) * 100, 2),
        "Reversal Checks": flags,
    }
