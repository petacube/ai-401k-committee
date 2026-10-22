"""The books: holdings (units per sleeve), an append-only ledger of every cash flow and trade, monthly proposals."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from . import SLEEVES
from .config import PORTFOLIO, PROPOSALS

HOLDINGS = PORTFOLIO / "holdings.csv"
LEDGER = PORTFOLIO / "ledger.csv"
LEDGER_COLS = ["timestamp", "month", "sleeve", "ticker", "action", "usd", "price", "units", "note"]


def load_holdings() -> dict:
    units = {s: 0.0 for s in SLEEVES}
    if HOLDINGS.exists():
        with open(HOLDINGS) as fh:
            for row in csv.DictReader(fh):
                units[row["sleeve"]] = float(row["units"])
    return units


def save_holdings(units: dict, prices: dict) -> None:
    PORTFOLIO.mkdir(parents=True, exist_ok=True)
    with open(HOLDINGS, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["sleeve", "ticker", "units"])
        for s in SLEEVES:
            w.writerow([s, prices[s]["ticker"], f"{units[s]:.6f}"])


def values(units: dict, prices: dict) -> dict:
    return {s: units[s] * prices[s]["price"] for s in SLEEVES}


def append_ledger(rows: list[dict]) -> None:
    new = not LEDGER.exists()
    with open(LEDGER, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_COLS)
        if new:
            w.writeheader()
        ts = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            w.writerow({"timestamp": ts, **r})


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    with open(LEDGER) as fh:
        return list(csv.DictReader(fh))


def total_deposits() -> float:
    return sum(float(r["usd"]) for r in read_ledger() if r["action"] == "deposit")


def proposal_path(month: str) -> Path:
    return PROPOSALS / f"{month}.json"


def save_proposal(p: dict) -> Path:
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    path = proposal_path(p["month"])
    path.write_text(json.dumps(p, indent=2, default=str))
    return path


def load_proposal(month: str) -> dict:
    path = proposal_path(month)
    if not path.exists():
        raise SystemExit(f"No proposal for {month}. Run `ai401k propose` first.")
    return json.loads(path.read_text())


def latest_proposal_month() -> str | None:
    files = sorted(PROPOSALS.glob("*.json")) if PROPOSALS.exists() else []
    return files[-1].stem if files else None


def approved_months() -> list[str]:
    out = []
    for f in sorted(PROPOSALS.glob("*.json")) if PROPOSALS.exists() else []:
        if json.loads(f.read_text()).get("status") == "approved":
            out.append(f.stem)
    return out
