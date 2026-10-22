"""Monthly tactical layer: market signals and the rule that turns them into tilts around the SAA.

Rules are deliberately simple, published and testable:
  trend          Faber (2007) 10-month moving-average filter. A sleeve trading below its 10-month
                 average has `trend_cut` of its strategic weight moved to cash until it recovers.
  dual_momentum  Antonacci (2014). Rank US, international, bonds, gold by blended 3/6/12-month
                 return (relative momentum); a sleeve that does not beat T-bills (absolute
                 momentum) gives its slot to cash.
  none           strategic weights only (pure rebalancing).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import SLEEVES

RISKY = ["US_EQ", "INTL_EQ", "BONDS", "GOLD"]


def signals(index: pd.DataFrame, lookbacks=(3, 6, 12), sma_months: int = 10) -> pd.DataFrame:
    """One row per sleeve, computed on the last COMPLETED month."""
    idx = index[SLEEVES].dropna()
    last = idx.iloc[-1]
    sma = idx.tail(sma_months).mean()
    rows = {
        "month_end": idx.index[-1].date().isoformat(),
        "level": last,
        "sma10": sma,
        "trend_up": last > sma,
        "pct_vs_sma10": last / sma - 1,
    }
    for k in lookbacks:
        rows[f"mom_{k}m"] = last / idx.iloc[-1 - k] - 1
    rows["mom_blend"] = sum(rows[f"mom_{k}m"] for k in lookbacks) / len(lookbacks)
    rows["vol_12m"] = idx.pct_change().tail(12).std() * np.sqrt(12)
    df = pd.DataFrame(rows)
    df["beats_cash"] = df["mom_blend"] > df.loc["CASH", "mom_blend"]
    return df


def tactical(saa: dict, sig: pd.DataFrame, tcfg: dict) -> tuple[dict, list[str]]:
    mode = tcfg.get("mode", "none")
    w = dict(saa)
    notes: list[str] = []
    if mode == "trend":
        cut = tcfg.get("trend_cut", 0.5)
        for s in RISKY:
            if not sig.loc[s, "trend_up"] and saa[s] > 0:
                move = saa[s] * cut
                w[s] -= move
                w["CASH"] += move
                notes.append(f"{s} is {sig.loc[s, 'pct_vs_sma10']:+.1%} vs its 10-month average (downtrend): "
                             f"move {move:.1%} to CASH")
        if not notes:
            notes.append("all risky sleeves are above their 10-month averages: hold strategic weights")
    elif mode == "dual_momentum":
        ranked = sig.loc[RISKY, "mom_blend"].sort_values(ascending=False)
        rw = tcfg.get("rank_weights", [0.4, 0.3, 0.15, 0.05])
        w = {s: 0.0 for s in SLEEVES}
        w["CASH"] = 1 - sum(rw)
        for s, wt in zip(ranked.index, rw):
            if sig.loc[s, "beats_cash"]:
                w[s] = wt
                notes.append(f"rank {list(ranked.index).index(s) + 1}: {s} momentum {ranked[s]:+.1%} -> {wt:.0%}")
            else:
                w["CASH"] += wt
                notes.append(f"{s} momentum {ranked[s]:+.1%} does not beat cash -> its {wt:.0%} goes to CASH")
    elif mode == "none":
        notes.append("no tactical rule for this goal: strategic weights only")
    else:
        raise ValueError(f"unknown tactical mode {mode}")
    return w, notes
