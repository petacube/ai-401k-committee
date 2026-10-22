"""Unit tests on synthetic data: no network needed."""
import numpy as np
import pandas as pd
import pytest

from ai401k import SLEEVES
from ai401k import config as C
from ai401k.backtest import run
from ai401k.data import sleeve_index
from ai401k.guardrails import check, check_override, project
from ai401k.plan import cma_inputs, frontier, glide, simulate
from ai401k.rebalance import integer_percent, plan_trades
from ai401k.tactical import signals, tactical

PX = {s: {"ticker": s, "price": 10.0} for s in SLEEVES}
RCFG = {"drift_band_abs": 0.03, "min_trade_usd": 100, "max_turnover": 0.40}
BAL = {"US_EQ": 0.38, "INTL_EQ": 0.20, "BONDS": 0.32, "GOLD": 0.06, "CASH": 0.04}


def synthetic_returns(months=240, seed=1, drift=None):
    rng = np.random.default_rng(seed)
    mu = drift or {"US_EQ": 0.007, "INTL_EQ": 0.006, "BONDS": 0.003, "GOLD": 0.003, "CASH": 0.002}
    vol = {"US_EQ": 0.045, "INTL_EQ": 0.05, "BONDS": 0.015, "GOLD": 0.045, "CASH": 0.0005}
    idx = pd.date_range("2005-01-31", periods=months, freq="ME")
    return pd.DataFrame({s: mu[s] + vol[s] * rng.standard_normal(months) for s in SLEEVES}, index=idx)


def test_integer_percent_sums_to_100():
    p = integer_percent({"US_EQ": 0.333, "INTL_EQ": 0.333, "BONDS": 0.334, "GOLD": 0.0, "CASH": 0.0})
    assert sum(p.values()) == 100


def test_initial_funding_hits_target():
    zero = {s: 0.0 for s in SLEEVES}
    t = plan_trades(zero, BAL, 100_000, PX, RCFG)
    assert t["mode"] == "initial funding"
    for o in t["orders"]:
        assert o["post_w"] == pytest.approx(BAL[o["sleeve"]], abs=1e-3)


def test_within_band_never_sells():
    vals = {s: BAL[s] * 100_000 for s in SLEEVES}
    vals["US_EQ"] += 1_500
    t = plan_trades(vals, BAL, 1_000, PX, RCFG)
    assert all(o["trade_usd"] >= 0 for o in t["orders"])
    assert sum(o["trade_usd"] for o in t["orders"]) == pytest.approx(1_000, abs=0.01)


def test_big_drift_rebalances_and_caps_turnover():
    vals = {"US_EQ": 90_000, "INTL_EQ": 0, "BONDS": 10_000, "GOLD": 0, "CASH": 0}
    t = plan_trades(vals, BAL, 0, PX, RCFG)
    assert t["mode"].startswith("rebalance")
    assert t["turnover"] <= 0.40 + 1e-9
    assert sum(o["trade_usd"] for o in t["orders"]) == pytest.approx(0, abs=0.01)


def test_project_respects_equity_glide_cap():
    g = C.guardrails("aggressive")
    w = project({"US_EQ": 0.7, "INTL_EQ": 0.3, "BONDS": 0, "GOLD": 0, "CASH": 0}, g, years_left=2)
    assert w["US_EQ"] + w["INTL_EQ"] <= 0.45 + 1e-4
    assert not check(w, g, 2)


def test_override_limits():
    g = C.guardrails()
    long_reason = "x" * 100
    assert not check_override({"US_EQ": -0.03, "BONDS": 0.03}, long_reason, g)
    assert check_override({"US_EQ": -0.06, "BONDS": 0.06}, long_reason, g)        # > 5 points
    assert check_override({"US_EQ": -0.03, "BONDS": 0.02}, long_reason, g)        # does not net to zero
    assert check_override({"US_EQ": -0.03, "BONDS": 0.03}, "because", g)          # reason too short


def test_trend_rule_moves_downtrend_to_cash():
    r = synthetic_returns()
    r.iloc[-6:, SLEEVES.index("GOLD")] = -0.05  # gold crashes
    sig = signals(sleeve_index(r))
    w, notes = tactical(BAL, sig, {"mode": "trend", "trend_cut": 0.5})
    assert w["GOLD"] == pytest.approx(BAL["GOLD"] / 2)
    assert sum(w.values()) == pytest.approx(1)
    assert any("GOLD" in n for n in notes)


def test_dual_momentum_goes_to_cash_when_everything_falls():
    r = synthetic_returns()
    for s in ["US_EQ", "INTL_EQ", "BONDS", "GOLD"]:
        r.iloc[-12:, SLEEVES.index(s)] = -0.02
    sig = signals(sleeve_index(r))
    w, _ = tactical(BAL, sig, {"mode": "dual_momentum", "rank_weights": [0.4, 0.3, 0.15, 0.05]})
    assert w["CASH"] == pytest.approx(1.0)


def test_simulation_without_risk_matches_annuity_formula():
    geo = np.full(5, 0.0)
    cov = np.zeros((5, 5))
    w = np.array([1, 0, 0, 0, 0.0])
    term = simulate(w, geo, cov, 1000.0, np.full(12, 100.0), paths=10)
    assert term == pytest.approx(np.full(10, 2200.0))


def test_frontier_obeys_policy():
    geo, cov, _ = cma_inputs(synthetic_returns())
    g = C.guardrails()
    pts = frontier(geo, cov, g, years_left=25, n=8)
    rets = [p["exp_return_arith"] for p in pts]
    assert rets == sorted(rets)
    for p in pts:
        assert sum(p["weights"].values()) == pytest.approx(1, abs=1e-3)
        assert p["weights"]["GOLD"] <= 0.15 + 1e-3


def test_glide_path_ends_at_conservative():
    end = C.profiles()["profiles"]["conservative"]["saa"]
    assert glide("aggressive", 0) == pytest.approx(end)
    assert glide("aggressive", 20) == C.profiles()["profiles"]["aggressive"]["saa"]


def test_backtest_runs_and_conserves_money():
    prof = {"name": "t", "initial_balance": 100_000, "annual_contribution": 12_000, "contribution_growth": 0.0,
            "horizon_years": 25, "goal": "balanced"}
    df, m = run(prof, synthetic_returns())
    assert m["contributed"] == pytest.approx(100_000 + 1_000 * (len(df) - 1), abs=1)
    assert df["wealth"].iloc[-1] > 0
    assert -1 < m["max_drawdown"] <= 0
