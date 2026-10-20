"""Presentation-only candidate triage for STHO V4.1.

This module never certifies Shariah compliance and never recommends a trade.
Only a recent, technically complete breakout with MANUALLY_REVIEWED evidence
can appear in the manually source-reviewed shortlist. Research-only technical
matches are deliberately separated from that shortlist.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

CATEGORIES = [
    "Research Watch",
    "Technically Ready · Syariah Pending",
    "Shariah-cleared Review (manual record)",
    "Rejected / Blocked",
]
REQUIRED_CHECKS = (
    "Formerly below EMA200 ≥30/60",
    "Last price ≥$5",
    "ADV60 ≥$20M",
    "ADR20 2.5–8%",
    "Base or higher low",
    "EMA10 rising; close > EMA21",
    "20D breakout or EMA200 reclaim",
    "RVOL20 ≥1.5×",
    "Reference RR ≥2",
    "Not extended >5% above pivot",
)


def _float(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _is_recent(row: dict) -> bool:
    if "Recent" in row:
        v = row["Recent"]
        return v is True or str(v).lower() == "true"
    raw = str(row.get("Date", ""))[:10]
    try:
        day = datetime.fromisoformat(raw).date()
        return -1 <= (datetime.now(timezone.utc).date() - day).days <= 4
    except ValueError:
        return False


def checks(row: dict) -> dict:
    value = row.get("Reversal Checks JSON", {})
    if isinstance(value, dict):
        data = value
    else:
        try:
            data = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return data if isinstance(data, dict) else {}


def technical_reasons(row: dict) -> list[str]:
    result = []
    stage = str(row.get("Reversal Stage", ""))
    if not _is_recent(row):
        result.append("Historical data or scan is stale; refresh before evaluating a setup")
    c = checks(row)
    if not c or any(key not in c or type(c[key]) is not bool for key in REQUIRED_CHECKS):
        result.append("Complete 10-rule checklist missing; new scan required")
    else:
        for key in REQUIRED_CHECKS:
            if c[key] is False:
                if key == "RVOL20 ≥1.5×":
                    n = _float(row.get("RVOL20"))
                    result.append(f"RVOL {n:.2f}× below 1.5×" if n is not None else "RVOL confirmation missing")
                elif key == "Reference RR ≥2":
                    n = _float(row.get("RR Proxy"))
                    result.append(f"R:R proxy {n:.2f}× below 2×" if n is not None else "R:R proxy not established")
                elif key == "ADV60 ≥$20M":
                    n = _float(row.get("ADV60 ($M)"))
                    result.append(f"ADV60 ${n:.1f}M below $20M" if n is not None else "Liquidity data missing")
                elif key == "ADR20 2.5–8%":
                    n = _float(row.get("ADR20 (%)"))
                    result.append(f"ADR20 {n:.2f}% outside 2.5–8%" if n is not None else "ADR20 unavailable")
                else:
                    result.append(key + " — not met")
    if stage == "Extended":
        result.insert(0, "Price extended beyond breakout pivot; avoid chasing")
    if stage == "No setup":
        result.insert(0, "No confirmed reversal pattern")
    return result


def ready(row: dict) -> bool:
    if row.get("Reversal Stage") != "Breakout review" or not _is_recent(row):
        return False
    c = checks(row)
    if any(c.get(k) is not True for k in REQUIRED_CHECKS):
        return False
    close = _float(row.get("Close ($)"))
    adv = _float(row.get("ADV60 ($M)"))
    adr = _float(row.get("ADR20 (%)"))
    rvol = _float(row.get("RVOL20"))
    rr = _float(row.get("RR Proxy"))
    extension = _float(row.get("Pivot Extension (%)"))
    return all([
        close is not None and close >= 5,
        adv is not None and adv >= 20,
        adr is not None and 2.5 <= adr <= 8,
        rvol is not None and rvol >= 1.5,
        rr is not None and rr >= 2,
        extension is not None and extension <= 5,
    ])


def classify(row: dict, gate: dict) -> str:
    """Distinct technical and user-reported Shariah decisions, never inferred."""
    stage = str(row.get("Reversal Stage", "No setup"))
    shariah_gate = gate.get("gate", "UNVERIFIED")
    if shariah_gate == "BLOCKED":
        return "Rejected / Blocked"
    if stage == "Extended":
        return "Rejected / Blocked"
    if stage not in {"Reversal watch", "Breakout review"}:
        return "Excluded / No setup"
    if not _is_recent(row):
        return "Rejected / Blocked"
    if ready(row):
        if shariah_gate == "MANUALLY_REVIEWED":
            return "Shariah-cleared Review (manual record)"
        return "Technically Ready · Syariah Pending"
    return "Research Watch"
