"""Fail-closed, manual-only Shariah evidence registry. No automated fatwa or verification.

A recorded compliant result is explicitly a USER-REVIEWED claim, NOT an independent
Shariah certification by this program. Duplicates, missing evidence and stale
records are blocked; unknown is never interpreted as non-compliant or compliant.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

COLUMNS = ["Ticker", "Reported_Status", "Business_Screen", "Financial_Screen",
           "Methodology", "Provider", "Evidence_URL", "Checked_On", "Reviewed_By", "Notes"]
MAX_AGE_DAYS = 90  # Our conservative *recheck policy*, not an official Shariah rule.


def read_reviews(path: str | Path) -> dict[str, list[dict]]:
    path = Path(path)
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or any(k not in reader.fieldnames for k in COLUMNS):
            raise ValueError("Shariah CSV has missing columns; see the V4 template")
        grouped: dict[str, list[dict]] = {}
        for line in reader:
            ticker = str(line.get("Ticker") or "").strip().upper()
            if ticker:
                grouped.setdefault(ticker, []).append({col: str(line.get(col) or "").strip() for col in COLUMNS})
        return grouped


def review_status(ticker: str, reviews: dict[str, list[dict]], today: date | None = None) -> dict:
    """Status labels refer only to recorded *manual* assessments.

    'Manual clearance recorded' is deliberately distinct from independently
    certified/guaranteed compliant. No ticker is pre-approved in the code.
    """
    records = reviews.get(str(ticker).upper(), [])
    if len(records) != 1:
        return {"gate": "UNVERIFIED", "why": "No review record" if not records else "Duplicate records: reconcile first", "evidence": ""}
    rec = records[0]
    reported = rec["Reported_Status"].upper()
    if reported in {"NON_COMPLIANT", "QUESTIONABLE", "UNRATED"}:
        return {"gate": "BLOCKED", "why": f"Source reports {reported}", "evidence": rec["Evidence_URL"]}
    if reported != "COMPLIANT":
        return {"gate": "UNVERIFIED", "why": "Unrecognized or missing status", "evidence": ""}
    if rec["Methodology"].upper() != "AAOIFI":
        return {"gate": "UNVERIFIED", "why": "Expected AAOIFI methodology", "evidence": ""}
    if not (rec["Business_Screen"].upper() == "PASS" and rec["Financial_Screen"].upper() == "PASS"):
        return {"gate": "UNVERIFIED", "why": "Business and financial screen must both be documented PASS", "evidence": ""}
    if not rec["Provider"] or not rec["Reviewed_By"]:
        return {"gate": "UNVERIFIED", "why": "Provider or manual reviewer missing", "evidence": ""}
    url = urlparse(rec["Evidence_URL"])
    if url.scheme != "https" or not url.hostname or (url.path in {"", "/"} and not url.query):
        return {"gate": "UNVERIFIED", "why": "Link to specific HTTPS source report missing", "evidence": ""}
    today = today or datetime.now(timezone.utc).date()
    try:
        checked = date.fromisoformat(rec["Checked_On"])
    except (TypeError, ValueError):
        return {"gate": "UNVERIFIED", "why": "Invalid review date (YYYY-MM-DD)", "evidence": ""}
    age = (today - checked).days
    if age < 0:
        return {"gate": "UNVERIFIED", "why": "Review date is in the future", "evidence": ""}
    if age > MAX_AGE_DAYS:
        return {"gate": "EXPIRED", "why": f"Manual evidence {age} days old; recheck required", "evidence": rec["Evidence_URL"]}
    return {"gate": "MANUALLY_REVIEWED", "why": f"Recorded AAOIFI review {age} days ago; not independently verified by the app", "evidence": rec["Evidence_URL"]}
