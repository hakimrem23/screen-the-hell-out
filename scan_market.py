"""Progressive US-listed equity scan, run by GitHub Actions (not on every app visit).

No paid provider or API key; best-effort Yahoo historical prices via yfinance.
Results are snapshots of *successfully screened* tickers, not a complete live market feed.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from metrics import screen_ticker

DATA_DIR = Path(__file__).resolve().parent / "data"
RESULTS_FILE = DATA_DIR / "market_results.csv"
STATUS_FILE = DATA_DIR / "scan_status.json"
UNIVERSE_FILE = DATA_DIR / "universe.csv"

LISTS = [
    ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "NASDAQ", "Symbol"),
    ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", "OTHER", "ACT Symbol"),
]

# Keep V1 favourites fresh. They are *not* an endorsement or trade signal.
FAVOURITES = ("NVDA", "MRVL", "MU", "BMRN", "AVGO", "AMD", "CLSK", "SOFI", "RKLB", "TSLA", "AMZN", "PLTR")
RESULT_COLUMNS = [
    "Ticker", "Name", "Exchange", "Date", "Close ($)", "Score", "Category",
    "ADR20 (%)", "1M (%)", "3M (%)", "6M (%)", "ADV60 ($M)",
    "Rules JSON", "Scanned at UTC",
]
BAD_NAMES = re.compile(
    r"\b(?:warrants?|rights?|units?|preferred|preference|senior notes?|subordinated notes?|"
    r"debentures?|convertible notes?|bonds?|ETFs?|ETNs?|closed.end funds?|"
    r"subscription rights?|depositary shares.*preferred|acquisition corp(?:oration)?\b.*(?:units?|warrants?))\b",
    re.IGNORECASE,
)


def symbol_ok(symbol: str, name: str) -> bool:
    """Best-effort equity filter; exchange flags aren't a perfect security-type taxonomy."""
    if not re.fullmatch(r"[A-Z]{1,5}(?:[.][A-Z])?", symbol):
        return False
    return not bool(BAD_NAMES.search(name))


def parse_listing(content: str, source: str, ticker_column: str) -> list[dict]:
    frame = pd.read_csv(io.StringIO(content), sep="|", dtype=str, on_bad_lines="skip").fillna("")
    required = {ticker_column, "Security Name", "ETF", "Test Issue"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Unexpected {source} file columns. Missing {required - set(frame.columns)}")
    rows = []
    for item in frame.to_dict(orient="records"):
        sym = str(item[ticker_column]).strip().upper()
        name = str(item["Security Name"]).strip()
        if item.get("ETF", "").strip().upper() != "N" or item.get("Test Issue", "").strip().upper() != "N":
            continue
        if not symbol_ok(sym, name):
            continue
        # YF uses hyphens for class shares such as BRK.B -> BRK-B.
        yf_symbol = sym.replace(".", "-")
        exchange = "NASDAQ" if source == "NASDAQ" else {"N": "NYSE", "A": "NYSE American", "P": "NYSE Arca", "Z": "Cboe", "V": "IEX"}.get(item.get("Exchange", ""), "Other US")
        rows.append({"Ticker": yf_symbol, "Name": name, "Exchange": exchange})
    return rows


def request_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; personal market researcher)"})
    with urllib.request.urlopen(req, timeout=35) as response:
        return response.read().decode("utf-8-sig", errors="replace")


def load_universe() -> tuple[pd.DataFrame, str]:
    batches = []
    failures = []
    for url, source, ticker_col in LISTS:
        try:
            batches.extend(parse_listing(request_text(url), source, ticker_col))
        except Exception as exc:
            failures.append(f"{source}: {type(exc).__name__}: {str(exc)[:150]}")
    new = pd.DataFrame(batches, columns=["Ticker", "Name", "Exchange"]).drop_duplicates("Ticker")
    if failures:
        # Never silently accept half the listing as if it were the whole universe.
        if UNIVERSE_FILE.exists():
            prior = pd.read_csv(UNIVERSE_FILE, dtype=str).fillna("")
            if not prior.empty:
                return prior, "Using previously saved universe. Listing fetch warning: " + "; ".join(failures)
        raise RuntimeError("Listing download unavailable: " + "; ".join(failures))
    if len(new) < 1000:
        raise RuntimeError(f"Universe only {len(new)} equities; refuse incomplete listing")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    new = new.sort_values("Ticker").reset_index(drop=True)
    new.to_csv(UNIVERSE_FILE, index=False)
    return new, "NASDAQ Trader symbol lists; equity exclusion is best effort"


def partition(universe: list[str], position: int, batch_size: int) -> tuple[list[str], int]:
    """Favourite symbols + reproducible pseudo-random round robin across other listings."""
    wanted = set(universe)
    priority = [s for s in FAVOURITES if s in wanted]
    rest = sorted((s for s in wanted if s not in priority), key=lambda s: hashlib.sha256(s.encode()).hexdigest())
    count = max(0, min(batch_size - len(priority), len(rest)))
    if not rest:
        return priority, 0
    start = position % len(rest)
    positions = [(start + i) % len(rest) for i in range(count)]
    chosen = priority + [rest[i] for i in positions]
    return chosen, (start + count) % len(rest)


def yield_price_frames(tickers: list[str], chunk_size: int = 12):
    """Yield (symbol, frame or None) without falsely counting failed downloads as scores."""
    for offset in range(0, len(tickers), chunk_size):
        chunk = tickers[offset:offset + chunk_size]
        try:
            prices = yf.download(
                chunk, period="2y", interval="1d", group_by="ticker", auto_adjust=True,
                progress=False, threads=False, timeout=20,
            )
            if prices is None or prices.empty:
                raise ValueError("Provider returned empty download")
        except Exception:
            for symbol in chunk:
                yield symbol, None
            time.sleep(1.5)
            continue
        for symbol in chunk:
            try:
                if isinstance(prices.columns, pd.MultiIndex):
                    frame = prices[symbol].copy()
                elif len(chunk) == 1:
                    frame = prices.copy()
                else:
                    raise KeyError(symbol)
                frame = frame.dropna(subset=["Close", "High", "Low", "Volume"])
                yield symbol, frame if not frame.empty else None
            except (KeyError, ValueError, TypeError):
                yield symbol, None
        time.sleep(1.0)


def run() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    universe_df, source_status = load_universe()
    universe = list(universe_df["Ticker"])
    info = universe_df.set_index("Ticker")[['Name', 'Exchange']].to_dict(orient='index')
    previous_status = {}
    if STATUS_FILE.exists():
        try:
            previous_status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    # 150 symbols/day default. You can increase it, but Yahoo may throttle requests.
    batch_size = max(15, min(500, int(os.getenv("MARKET_BATCH_SIZE", "150"))))
    picked, next_position = partition(universe, int(previous_status.get("cursor", 0)), batch_size)
    earlier = pd.read_csv(RESULTS_FILE, dtype={"Ticker": str}, keep_default_na=False) if RESULTS_FILE.exists() else pd.DataFrame(columns=RESULT_COLUMNS)
    earlier_rows = {row["Ticker"]: row for row in earlier.to_dict(orient="records") if row.get("Ticker") in info}
    utc_now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    checked = 0
    failures = []
    for ticker, frame in yield_price_frames(picked):
        try:
            if frame is None:
                raise ValueError("No valid historical candles")
            res = screen_ticker(ticker, frame)
            res["Name"] = info[ticker]["Name"]
            res["Exchange"] = info[ticker]["Exchange"]
            res["Rules JSON"] = json.dumps(res.pop("Rule details"), separators=(",", ":"))
            res["Scanned at UTC"] = utc_now
            earlier_rows[ticker] = res
            checked += 1
        except Exception as exc:
            failures.append(f"{ticker}: {str(exc)[:110]}")
    merged = pd.DataFrame(list(earlier_rows.values()), columns=RESULT_COLUMNS)
    if not merged.empty:
        merged = merged.sort_values(["Score", "Ticker"], ascending=[False, True])
    merged.to_csv(RESULTS_FILE, index=False)
    status = {
        "last_run_utc": utc_now,
        "universe_count": len(universe),
        "ever_scanned": len(earlier_rows),
        "batch_requested": len(picked),
        "batch_succeeded": checked,
        "batch_failed": len(failures),
        "cursor": next_position,
        "source_status": source_status,
        "failed_examples": failures[:12],
        "note": "Progressive partial coverage; old rows can be stale. Yahoo data unofficial.",
    }
    STATUS_FILE.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))
    if not checked and not earlier_rows:
        raise RuntimeError("First scan fetched zero valid tickers; check Actions logs for rate limits")
    return status


if __name__ == "__main__":
    run()
