"""Walk-forward monthly back-test with contributions. Only data up to month t is used to trade at month t.

Caveats (say these out loud in an interview):
  * capital market assumptions in config/cma.yaml are today's, so the `target` goal solver has a mild
    look-ahead; signals and correlations do not.
  * proxies (SPY, EFA, AGG, GLD, BIL, T-bill yield) stand in for the trade ETFs before they existed.
  * no taxes or commissions (a 401k has neither); fund expense ratios are charged monthly.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from . import SLEEVES
from .config import guardrails, profiles, universe
from .data import sleeve_index, sleeve_returns
from .guardrails import project
from .plan import strategic
from .rebalance import plan_trades
from .tactical import signals, tactical

BENCHMARKS = {
    "60/40 US stocks/bonds": {"US_EQ": 0.6, "INTL_EQ": 0.0, "BONDS": 0.4, "GOLD": 0.0, "CASH": 0.0},
    "100% US stocks": {"US_EQ": 1.0, "INTL_EQ": 0.0, "BONDS": 0.0, "GOLD": 0.0, "CASH": 0.0},
}


def run(prof: dict, rets: pd.DataFrame | None = None, policy: dict | None = None, start: str | None = None,
        target_paths: int = 1000) -> tuple[pd.DataFrame, dict]:
    """policy=None -> the investor's full strategy; policy=dict of weights -> static benchmark (always rebalanced)."""
    rets = sleeve_returns() if rets is None else rets
    rets = rets[SLEEVES].dropna()
    uni = universe()
    fee = pd.Series({s: uni[s].get("expense_ratio", 0) / 12 for s in SLEEVES})
    net = rets - fee
    idx = sleeve_index(rets)
    goal = prof["goal"]
    g = guardrails(goal)
    tcfg = profiles()["profiles"][goal]["tactical"]
    months = rets.index
    i0 = 12 if start is None else max(12, months.searchsorted(pd.Timestamp(start)))
    dummy_px = {s: {"ticker": s, "price": 1.0} for s in SLEEVES}
    rcfg = g["rebalance"] if policy is None else {**g["rebalance"], "drift_band_abs": 0.0, "max_turnover": 1.0}

    vals = {s: 0.0 for s in SLEEVES}
    saa, saa_year = None, None
    rows, flows = [], []
    t0 = months[i0]
    for i in range(i0, len(months) - 1):
        t = months[i]
        elapsed = (t - t0).days / 365.25
        yl = max(0.0, prof["horizon_years"] - elapsed)
        yi = int(elapsed)
        deposit = prof["initial_balance"] if i == i0 else prof["annual_contribution"] * (1 + prof.get("contribution_growth", 0)) ** yi / 12
        wealth = sum(vals.values())
        if policy is not None:
            target = policy
        else:
            if goal != "target" or saa is None or saa_year != yi:
                saa = strategic(prof, wealth + deposit, yl, yi, g, rets.iloc[: i + 1], paths=target_paths)["weights"]
                saa_year = yi
            sig = signals(idx.iloc[: i + 1])
            tw, _ = tactical(saa, sig, tcfg)
            target = project(tw, g, yl, saa)
        tr = plan_trades(vals, target, deposit, dummy_px, rcfg)
        vals = {o["sleeve"]: o["post_usd"] for o in tr["orders"]}
        post = sum(vals.values())
        r_next = net.iloc[i + 1]
        vals = {s: vals[s] * (1 + r_next[s]) for s in SLEEVES}
        flows.append(deposit)
        rows.append({"date": months[i + 1], "wealth": sum(vals.values()), "deposit": deposit,
                     "port_return": sum(vals.values()) / post - 1,
                     "traded": tr["mode"].startswith("rebalance"), "turnover": tr["turnover"],
                     **{f"w_{s}": o["post_w"] for s, o in zip(SLEEVES, tr["orders"])}})
    df = pd.DataFrame(rows).set_index("date")
    return df, metrics(df, flows)


def metrics(df: pd.DataFrame, flows: list[float]) -> dict:
    r = df["port_return"]
    twr = (1 + r).cumprod()
    years = len(r) / 12
    dd = twr / twr.cummax() - 1
    cf = np.array([-f for f in flows] + [0.0])
    cf[-1] += df["wealth"].iloc[-1]
    npv = lambda m: sum(c / (1 + m) ** k for k, c in enumerate(cf))
    try:
        irr = (1 + brentq(npv, -0.05, 0.1)) ** 12 - 1
    except ValueError:
        irr = float("nan")
    return {
        "start": df.index[0].date().isoformat(), "end": df.index[-1].date().isoformat(), "years": round(years, 1),
        "final_wealth": round(float(df["wealth"].iloc[-1])), "contributed": round(float(sum(flows))),
        "cagr_twr": float(twr.iloc[-1] ** (1 / years) - 1), "irr_money_weighted": float(irr),
        "vol": float(r.std() * np.sqrt(12)), "max_drawdown": float(dd.min()),
        "worst_12m": float(((1 + r).rolling(12).apply(np.prod, raw=True) - 1).min()),
        "sharpe_vs_0": float(r.mean() / r.std() * np.sqrt(12)),
        "months_rebalanced_pct": float(df["traded"].mean()), "avg_turnover": float(df["turnover"].mean()),
    }


def compare(prof: dict, rets: pd.DataFrame | None = None, goals: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """The investor's strategy, the other goals with the same cash flows, and benchmarks."""
    rets = sleeve_returns() if rets is None else rets
    curves, table = {}, {}
    for gname in goals or [prof["goal"]]:
        p = {**prof, "goal": gname}
        if gname == "target" and not p.get("target_amount"):
            continue
        df, m = run(p, rets)
        label = f"{gname} (your plan)" if gname == prof["goal"] else gname
        curves[label], table[label] = df["wealth"], m
    for name, w in BENCHMARKS.items():
        df, m = run({**prof, "goal": "max_wealth"}, rets, policy=w)
        curves[name], table[name] = df["wealth"], m
    return pd.DataFrame(curves), table
