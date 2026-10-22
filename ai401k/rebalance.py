"""Turn target weights into 401k instructions.

A 401k gives you two levers, and the engine uses both:
  1. future-contribution election: whole percentages for new payroll money. Setting it to the target
     weights means new money rebalances you for free.
  2. exchange / rebalance of the existing balance: only when some sleeve drifts more than the band
     (default 3 points), capped by `max_turnover` so one month cannot churn the account.
"""
from __future__ import annotations

from . import SLEEVES


def integer_percent(w: dict) -> dict:
    """Largest-remainder rounding to whole percents that add up to exactly 100."""
    raw = {s: w[s] * 100 for s in SLEEVES}
    base = {s: int(raw[s]) for s in SLEEVES}
    for s in sorted(SLEEVES, key=lambda s: raw[s] - base[s], reverse=True)[: 100 - sum(base.values())]:
        base[s] += 1
    return base


def plan_trades(values: dict, target: dict, deposit: float, prices: dict, rcfg: dict) -> dict:
    """values: current $ per sleeve; deposit: new cash arriving this month (paper mode or initial funding)."""
    held = sum(values.values())
    total = held + deposit
    cur_w = {s: (values[s] / held if held else 0.0) for s in SLEEVES}
    drift = {s: cur_w[s] - target[s] for s in SLEEVES}
    full = {s: target[s] * total - values[s] for s in SLEEVES}  # trades for an exact rebalance

    # contribution-only: put new money where it is most underweight, no selling
    contrib_only = {s: 0.0 for s in SLEEVES}
    if deposit > 0:
        short = {s: max(full[s], 0.0) for s in SLEEVES}
        tot_short = sum(short.values())
        for s in SLEEVES:
            contrib_only[s] = deposit * (short[s] / tot_short if tot_short else target[s])
    post_w = {s: (values[s] + contrib_only[s]) / total for s in SLEEVES} if total else dict(target)
    max_drift_after = max(abs(post_w[s] - target[s]) for s in SLEEVES)

    if held == 0 or max_drift_after <= rcfg["drift_band_abs"]:
        trades, mode = contrib_only, ("initial funding" if held == 0 else
                                      "within band: invest new money only" if deposit else "within band: no trades")
    else:
        trades, mode = dict(full), "rebalance: drift exceeds band"
        turnover = sum(-t for t in trades.values() if t < 0) / total
        if turnover > rcfg["max_turnover"]:
            k = rcfg["max_turnover"] / turnover
            trades = {s: contrib_only[s] + k * (full[s] - contrib_only[s]) for s in SLEEVES}
            mode += f" (partial: turnover capped at {rcfg['max_turnover']:.0%})"

    # drop dust trades; park the residual in CASH so the books balance
    for s in SLEEVES:
        if s != "CASH" and abs(trades[s]) < rcfg["min_trade_usd"]:
            trades[s] = 0.0
    trades["CASH"] = deposit - sum(trades[s] for s in SLEEVES if s != "CASH")
    if abs(trades["CASH"]) < 0.005:
        trades["CASH"] = 0.0

    rows = []
    for s in SLEEVES:
        px = prices[s]["price"]
        post = values[s] + trades[s]
        rows.append({
            "sleeve": s, "ticker": prices[s]["ticker"], "price": round(px, 4),
            "current_usd": round(values[s], 2), "current_w": round(cur_w[s], 4),
            "target_w": round(target[s], 4), "drift": round(drift[s], 4),
            "trade_usd": round(trades[s], 2), "trade_units": round(trades[s] / px, 4),
            "post_usd": round(post, 2), "post_w": round(post / total, 4) if total else 0.0,
        })
    sells = sum(-r["trade_usd"] for r in rows if r["trade_usd"] < 0)
    return {
        "mode": mode, "deposit": round(deposit, 2), "total_after": round(total, 2),
        "turnover": round(sells / total, 4) if total else 0.0, "max_drift_before": round(max(abs(d) for d in drift.values()), 4) if held else None,
        "orders": rows, "contribution_election_pct": integer_percent(target),
    }
