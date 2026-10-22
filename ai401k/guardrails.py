"""Hard limits. `project` moves any weight vector to the nearest compliant one; `check` lists violations.

The same code guards the strategic optimiser, the tactical signals and Claude's discretionary
override, so no layer can push the portfolio outside the investment policy.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from . import SLEEVES
from .config import universe

TOL = 1e-4  # weights are stored to 4 decimals (0.01%)


def equity_mask() -> np.ndarray:
    uni = universe()
    return np.array([bool(uni[s].get("equity")) for s in SLEEVES])


def equity_range(g: dict, years_left: float) -> tuple[float, float]:
    lo, hi = g["total_equity"]
    for rule in sorted(g.get("equity_by_years_left", []), key=lambda r: r["years_left_below"]):
        if years_left < rule["years_left_below"]:
            hi = min(hi, rule["max_equity"])
            break
    return min(lo, hi), hi


def sleeve_bounds(g: dict, saa: dict | None = None, use_tilt: bool = True) -> list[tuple[float, float]]:
    out = []
    t = g.get("max_tilt_from_saa", 1.0)
    for s in SLEEVES:
        lo, hi = g["weights"][s]
        if saa is not None and use_tilt:
            lo, hi = max(lo, saa[s] - t), min(hi, saa[s] + t)
        out.append((lo, max(lo, hi)))
    return out


def project(w: dict, g: dict, years_left: float, saa: dict | None = None) -> dict:
    """Closest weights (least squares) that satisfy bounds, the equity range, the tilt band and sum to 1.
    If the tilt band conflicts with the equity cap, the cap wins (it is the safety rule)."""
    x0 = np.array([w[s] for s in SLEEVES], dtype=float)
    eq = equity_mask()
    elo, ehi = equity_range(g, years_left)
    for use_tilt in (True, False):
        bnds = sleeve_bounds(g, saa, use_tilt)
        cons = [
            {"type": "eq", "fun": lambda x: x.sum() - 1.0},
            {"type": "ineq", "fun": lambda x: x[eq].sum() - elo},
            {"type": "ineq", "fun": lambda x: ehi - x[eq].sum()},
        ]
        start = np.clip(x0, [b[0] for b in bnds], [b[1] for b in bnds])
        res = minimize(lambda x: ((x - x0) ** 2).sum(), start, method="SLSQP", bounds=bnds,
                       constraints=cons, options={"ftol": 1e-12, "maxiter": 500})
        out = {s: float(round(v, 4)) for s, v in zip(SLEEVES, res.x)}
        big = max(out, key=out.get)  # absorb the rounding residual in the largest sleeve
        out[big] = round(1.0 - sum(v for k, v in out.items() if k != big), 4)
        if not check(out, g, years_left, saa if use_tilt else None):
            return out
    raise ValueError("guardrails are infeasible; review config/guardrails.yaml")


def check(w: dict, g: dict, years_left: float, saa: dict | None = None) -> list[str]:
    errs = []
    if abs(sum(w.values()) - 1) > 1e-3:
        errs.append(f"weights sum to {sum(w.values()):.4f}, not 1")
    for s, (lo, hi) in zip(SLEEVES, sleeve_bounds(g)):
        if not lo - TOL <= w[s] <= hi + TOL:
            errs.append(f"{s} weight {w[s]:.1%} outside policy range [{lo:.0%}, {hi:.0%}]")
    eq = sum(w[s] for s, m in zip(SLEEVES, equity_mask()) if m)
    elo, ehi = equity_range(g, years_left)
    if not elo - 1e-3 <= eq <= ehi + 1e-3:
        errs.append(f"total equity {eq:.1%} outside [{elo:.0%}, {ehi:.0%}] for {years_left:.1f} years left")
    if saa is not None:
        t = g.get("max_tilt_from_saa", 1.0)
        for s in SLEEVES:
            if abs(w[s] - saa[s]) > t + 1e-3:
                errs.append(f"{s} tilt {w[s] - saa[s]:+.1%} vs strategic exceeds +/-{t:.0%}")
    return errs


def check_override(delta: dict, reason: str, g: dict) -> list[str]:
    o = g["ai_override"]
    errs = []
    for s, d in delta.items():
        if s not in SLEEVES:
            errs.append(f"unknown sleeve {s}")
        elif abs(d) > o["max_per_sleeve"] + 1e-9:
            errs.append(f"override {s} {d:+.1%} exceeds +/-{o['max_per_sleeve']:.0%} per sleeve")
    if sum(abs(d) for d in delta.values()) > o["max_total"] + 1e-9:
        errs.append(f"override total |change| {sum(abs(d) for d in delta.values()):.1%} exceeds {o['max_total']:.0%}")
    if abs(sum(delta.values())) > 1e-9:
        errs.append(f"override changes must net to zero (got {sum(delta.values()):+.2%})")
    if len(reason.strip()) < o["reason_min_chars"]:
        errs.append(f"override reason must be at least {o['reason_min_chars']} characters and cite evidence")
    return errs
