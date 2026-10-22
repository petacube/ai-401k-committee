"""Strategic asset allocation (SAA): capital market assumptions, efficient frontier, Monte Carlo, goal solver."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize

from . import SLEEVES
from .config import cma, nominal_target, profiles, universe
from .guardrails import equity_mask, equity_range, project, sleeve_bounds


# ---------------------------------------------------------------- capital market assumptions
def cma_inputs(rets: pd.DataFrame | None = None) -> tuple[np.ndarray, np.ndarray, str]:
    """Expected geometric return net of fund fees, covariance matrix, and where correlations came from."""
    c, uni = cma(), universe()
    geo = np.array([c["sleeves"][s]["return"] - uni[s].get("expense_ratio", 0) for s in SLEEVES])
    vol = np.array([c["sleeves"][s]["vol"] for s in SLEEVES])
    corr, src = np.array([c["fallback_corr"][s] for s in SLEEVES], dtype=float), "fallback matrix in cma.yaml"
    if rets is not None:
        hist = rets[SLEEVES].dropna().tail(12 * c.get("corr_lookback_years", 15))
        if len(hist) >= 60:
            corr = hist.corr().values
            src = f"monthly history {hist.index[0]:%Y-%m}..{hist.index[-1]:%Y-%m}"
    return geo, np.outer(vol, vol) * corr, src


def stats(w: np.ndarray, geo: np.ndarray, cov: np.ndarray) -> dict:
    arith = float(w @ (geo + np.diag(cov) / 2))  # lognormal: arithmetic ~ geometric + var/2
    var = float(w @ cov @ w)
    return {"exp_return_arith": arith, "vol": var ** 0.5, "exp_return_geo": arith - var / 2}


# ---------------------------------------------------------------- efficient frontier
def _constraints(g: dict, years_left: float) -> list[dict]:
    eq = equity_mask()
    us, intl = SLEEVES.index("US_EQ"), SLEEVES.index("INTL_EQ")
    elo, ehi = equity_range(g, years_left)
    ilo, ihi = g.get("intl_share_of_equity", [0, 1])
    return [
        {"type": "eq", "fun": lambda x: x.sum() - 1},
        {"type": "ineq", "fun": lambda x: x[eq].sum() - elo},
        {"type": "ineq", "fun": lambda x: ehi - x[eq].sum()},
        {"type": "ineq", "fun": lambda x: x[intl] - ilo * (x[us] + x[intl])},
        {"type": "ineq", "fun": lambda x: ihi * (x[us] + x[intl]) - x[intl]},
    ]


def frontier(geo: np.ndarray, cov: np.ndarray, g: dict, years_left: float, n: int = 25) -> list[dict]:
    """Long-only minimum-variance portfolios for n target returns, under the policy guardrails."""
    a = geo + np.diag(cov) / 2
    bnds = sleeve_bounds(g)
    cons = _constraints(g, years_left)
    x0 = np.full(len(SLEEVES), 1 / len(SLEEVES))
    solve = lambda extra: minimize(lambda x: x @ cov @ x, x0, method="SLSQP", bounds=bnds,
                                   constraints=cons + extra, options={"ftol": 1e-12, "maxiter": 500})
    lo_ret = float(solve([]).x @ a)
    # highest feasible return: LP with the linear constraints
    eq = equity_mask().astype(float)
    us, intl = SLEEVES.index("US_EQ"), SLEEVES.index("INTL_EQ")
    ilo, ihi = g.get("intl_share_of_equity", [0, 1])
    elo, ehi = equity_range(g, years_left)
    r1 = np.zeros(5); r1[us], r1[intl] = ilo, ilo - 1
    r2 = np.zeros(5); r2[us], r2[intl] = -ihi, 1 - ihi
    lp = linprog(-a, A_ub=[eq, -eq, r1, r2], b_ub=[ehi, -elo, 0, 0], A_eq=[np.ones(5)], b_eq=[1], bounds=bnds)
    hi_ret = float(-lp.fun)
    out = []
    for r in np.linspace(lo_ret, hi_ret, n):
        res = solve([{"type": "eq", "fun": lambda x, r=r: x @ a - r}])
        if res.success:
            w = np.clip(res.x, 0, None); w /= w.sum()
            out.append({"weights": dict(zip(SLEEVES, w.round(4))), **stats(w, geo, cov)})
    return out


# ---------------------------------------------------------------- Monte Carlo
def contributions(annual: float, growth: float, months: int, start_year_index: int = 0) -> np.ndarray:
    yrs = start_year_index + np.arange(months) // 12
    return annual * (1 + growth) ** yrs / 12.0


def simulate(w: np.ndarray, geo: np.ndarray, cov: np.ndarray, wealth0: float, contrib: np.ndarray,
             paths: int = 5000, df: int = 5, seed: int = 401, keep_paths: bool = False):
    """Monthly portfolio wealth with contributions at the start of each month. Fat-tailed (Student-t) shocks.
    Returns terminal wealth (and the yearly wealth matrix if keep_paths)."""
    s = stats(w, geo, cov)
    mu = np.log1p(s["exp_return_geo"]) / 12
    sig = s["vol"] / np.sqrt(12)
    rng = np.random.default_rng(seed)
    z = rng.standard_t(df, size=(len(contrib), paths)) * np.sqrt((df - 2) / df)
    growth = np.exp(mu + sig * z)
    W = np.full(paths, float(wealth0))
    yearly = [W.copy()]
    for t, c in enumerate(contrib):
        W = (W + c) * growth[t]
        if keep_paths and (t + 1) % 12 == 0:
            yearly.append(W.copy())
    return (W, np.array(yearly)) if keep_paths else W


def summarize(terminal: np.ndarray, target: float | None, inflation: float, years: float) -> dict:
    deflate = (1 + inflation) ** years
    out = {
        "median": float(np.median(terminal)),
        "p10": float(np.percentile(terminal, 10)),
        "p90": float(np.percentile(terminal, 90)),
        "median_real": float(np.median(terminal) / deflate),
    }
    if target:
        out["prob_target"] = float((terminal >= target).mean())
    return out


# ---------------------------------------------------------------- strategic allocation per goal
def glide(goal: str, years_left: float) -> dict:
    p = profiles()
    w = p["profiles"][goal]["saa"]
    gcfg = p["glide"]
    if years_left >= gcfg["start_years"]:
        return dict(w)
    lam = years_left / gcfg["start_years"]
    end = p["profiles"][gcfg["toward"]]["saa"]
    return {s: lam * w[s] + (1 - lam) * end[s] for s in SLEEVES}


def solve_target(prof: dict, wealth0: float, years_left: float, year_index: int, g: dict,
                 rets: pd.DataFrame | None = None, paths: int | None = None) -> dict:
    """Goal-based choice on the efficient frontier.
    Among portfolios with P(wealth >= target) >= confidence, pick by `selection` (profile key):
      max_p10  (default) the best 10th-percentile outcome: still reaches the goal and hurts least if markets disappoint
      min_vol  the least volatile one (pure liability matching; tends to hold lots of cash when the goal is easy)
      max_median  the highest median (most aggressive that qualifies)
    If none qualifies, take the most likely one and report the contribution needed."""
    geo, cov, src = cma_inputs(rets)
    c = cma()
    sim = c["simulation"]
    paths = paths or sim["paths"]
    months = max(1, int(round(years_left * 12)))
    contrib = contributions(prof["annual_contribution"], prof.get("contribution_growth", 0), months, year_index)
    target, conf = nominal_target(prof), prof.get("confidence", 0.7)
    rows = []
    for pt in frontier(geo, cov, g, years_left):
        w = np.array([pt["weights"][s] for s in SLEEVES])
        term = simulate(w, geo, cov, wealth0, contrib, paths, sim["student_t_df"], sim["seed"])
        rows.append({**pt, **summarize(term, target, c["inflation"], years_left)})
    ok = [r for r in rows if r["prob_target"] >= conf]
    if ok:
        rule = prof.get("selection", "max_p10")
        pick = {"max_p10": lambda r: r["p10"], "min_vol": lambda r: -r["vol"], "max_median": lambda r: r["median"]}[rule]
        best, status = max(ok, key=pick), "on_track"
        need = None
    else:
        best, status = max(rows, key=lambda r: r["prob_target"]), "stretch"
        w = np.array([best["weights"][s] for s in SLEEVES])
        lo, hi = 1.0, 20.0
        for _ in range(30):  # bisection on a contribution multiplier
            mid = (lo + hi) / 2
            p = (simulate(w, geo, cov, wealth0, contrib * mid, paths, sim["student_t_df"], sim["seed"]) >= target).mean()
            lo, hi = (lo, mid) if p >= conf else (mid, hi)
        need = prof["annual_contribution"] * hi
    return {"weights": best["weights"], "status": status, "required_annual_contribution": need,
            "chosen": {k: v for k, v in best.items() if k != "weights"}, "frontier": rows, "corr_source": src}


def strategic(prof: dict, wealth: float, years_left: float, year_index: int, g: dict,
              rets: pd.DataFrame | None = None, paths: int | None = None) -> dict:
    """SAA for any goal, already projected onto the guardrails."""
    goal = prof["goal"]
    if goal == "target":
        res = solve_target(prof, wealth, years_left, year_index, g, rets, paths)
    else:
        res = {"weights": glide(goal, years_left), "status": "policy"}
    res["weights"] = project(res["weights"], g, years_left)
    return res


def projection(prof: dict, w: dict, wealth0: float, years_left: float, year_index: int,
               rets: pd.DataFrame | None = None) -> dict:
    """Fan chart data and goal probability for a given allocation (held constant)."""
    geo, cov, _ = cma_inputs(rets)
    c = cma()
    sim = c["simulation"]
    months = max(1, int(round(years_left * 12)))
    contrib = contributions(prof["annual_contribution"], prof.get("contribution_growth", 0), months, year_index)
    x = np.array([w[s] for s in SLEEVES])
    term, yearly = simulate(x, geo, cov, wealth0, contrib, sim["paths"], sim["student_t_df"], sim["seed"], keep_paths=True)
    fan = {q: np.percentile(yearly, q, axis=1).tolist() for q in (10, 25, 50, 75, 90)}
    out = summarize(term, nominal_target(prof), c["inflation"], years_left)
    out.update(stats(x, geo, cov))
    out["fan"] = fan
    out["total_contributions"] = float(contrib.sum())
    return out
