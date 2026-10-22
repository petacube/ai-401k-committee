"""Command line: `ai401k <command>`. Run `ai401k --help` for the list.

Monthly loop:  data -> status -> propose -> (override) -> validate -> approve -> report
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime

from . import SLEEVES, __version__
from . import config as C
from .data import latest_prices, load_daily, refresh, sleeve_index, sleeve_returns
from .guardrails import check, check_override, project
from .ledger import (append_ledger, approved_months, latest_proposal_month, load_holdings, load_proposal,
                     read_ledger, save_holdings, save_proposal, total_deposits, values)
from .plan import projection, strategic
from .rebalance import plan_trades
from .report import money, pct, proposal_md, write_dashboard
from .tactical import signals, tactical

SAA_FILE = C.PORTFOLIO / "saa.json"


# ---------------------------------------------------------------- helpers
def _today(args) -> date:
    return date.fromisoformat(args.as_of) if getattr(args, "as_of", None) else date.today()


def _target_txt(prof) -> str:
    if not prof.get("target_amount"):
        return "-"
    nom = C.nominal_target(prof)
    return money(nom) if nom == prof["target_amount"] else f"{money(prof['target_amount'])} in today's dollars (= {money(nom)} nominal)"


def _parse_kv(text: str) -> dict:
    out = {}
    for part in text.replace(" ", "").split(","):
        if part:
            k, v = part.split("=")
            out[k.upper()] = float(v)
    return out


def _ask(prompt: str, default=None, cast=str):
    if not sys.stdin.isatty():
        if default is None:
            raise SystemExit(f"missing value for: {prompt} (pass it as a flag)")
        return default
    raw = input(f"{prompt}{f' [{default}]' if default is not None else ''}: ").strip()
    return cast(raw) if raw else default


def _wealth(prices) -> tuple[dict, dict, float]:
    units = load_holdings()
    vals = values(units, prices)
    return units, vals, sum(vals.values())


def _saa(prof, wealth, today, rets, force=False) -> dict:
    """Strategic weights. `target` goals are solved once a year (or on `ai401k plan`); presets follow the glide path."""
    g = C.guardrails(prof["goal"])
    yl, yi = C.years_left(prof, today), int(C.years_elapsed(prof, today))
    if prof["goal"] == "target" and SAA_FILE.exists() and not force:
        saved = json.loads(SAA_FILE.read_text())
        if saved.get("goal") == "target" and (today - date.fromisoformat(saved["as_of"])).days < 365:
            return saved
    res = strategic(prof, wealth if wealth > 0 else prof["initial_balance"], yl, yi, g, rets)
    saved = {"as_of": today.isoformat(), "goal": prof["goal"], "years_left": round(yl, 2), "weights": res["weights"],
             "status": res["status"], "required_annual_contribution": res.get("required_annual_contribution"),
             "chosen": res.get("chosen"), "corr_source": res.get("corr_source")}
    if res.get("frontier"):
        saved["frontier"] = [{"weights": r["weights"], "vol": r["vol"], "exp_return_geo": r["exp_return_geo"],
                              "prob_target": r["prob_target"], "median": r["median"], "p10": r["p10"]} for r in res["frontier"]]
    C.PORTFOLIO.mkdir(parents=True, exist_ok=True)
    SAA_FILE.write_text(json.dumps(saved, indent=2))
    return saved


# ---------------------------------------------------------------- commands
def cmd_init(a):
    path = C.profile_path()
    if path.exists() and not a.force:
        raise SystemExit(f"{path} already exists. Use --force to start over (your ledger is kept).")
    goal = a.goal or _ask("Goal (" + "|".join(C.GOALS) + ", or a dollar amount)", "target")
    target = a.target
    if goal.replace(",", "").replace("$", "").replace(".", "").isdigit():
        target, goal = float(goal.replace(",", "").replace("$", "")), "target"
    if goal.startswith("target:"):
        goal, target = "target", float(goal.split(":", 1)[1])
    if goal not in C.GOALS:
        raise SystemExit(f"unknown goal {goal}; choose from {C.GOALS}")
    if goal == "target" and not target:
        target = _ask("Target amount in dollars", 1_000_000, float)
    prof = {
        "name": a.name or _ask("Your name", "Student"),
        "initial_balance": a.initial if a.initial is not None else _ask("Current 401k balance ($)", 100_000, float),
        "annual_contribution": a.contribution if a.contribution is not None else _ask("Annual contribution incl. employer match ($)", 20_000, float),
        "contribution_growth": a.growth,
        "horizon_years": a.years if a.years is not None else _ask("Years until you need the money", 25, float),
        "goal": goal,
        "target_amount": target,
        "target_real": not a.nominal,
        "confidence": a.confidence,
        "selection": "max_p10",
        "mode": a.mode,
        "start_date": a.start_date or date.today().isoformat(),
    }
    C.save_yaml(prof, path)
    print(f"Saved {path}")
    print(json.dumps(prof, indent=2))


def cmd_data(a):
    _, msg = refresh(offline=a.offline)
    print(msg)
    lp = latest_prices()
    for s, p in lp.items():
        print(f"  {s:8s} {p['ticker']:6s} {p['price']:>10.2f}  ({p['date']})")
    rets = sleeve_returns()
    print(f"monthly sleeve history: {rets.dropna().index[0]:%Y-%m} .. {rets.index[-1]:%Y-%m} (complete months)")


def cmd_plan(a):
    prof, today = C.investor(), _today(a)
    prices = latest_prices()
    rets = sleeve_returns()
    _, _, wealth = _wealth(prices)
    wealth = wealth or prof["initial_balance"]
    saa = _saa(prof, wealth, today, rets, force=True)
    yl, yi = C.years_left(prof, today), int(C.years_elapsed(prof, today))
    proj = projection(prof, saa["weights"], wealth, yl, yi, rets)
    C.REPORTS.mkdir(exist_ok=True)
    lines = [f"# Strategic plan for {prof['name']} ({today})", "",
             f"Goal **{prof['goal']}**" + (f", target {_target_txt(prof)} at {prof.get('confidence', 0.7):.0%} confidence" if prof.get("target_amount") else ""),
             f"Wealth now {money(wealth)}, contributing {money(prof['annual_contribution'])}/yr growing {prof.get('contribution_growth', 0):.0%}/yr, {yl:.1f} years left.", "",
             "| sleeve | strategic weight |", "|---|---|"]
    lines += [f"| {s} | {pct(saa['weights'][s])} |" for s in SLEEVES]
    lines += ["", f"Expected return (geometric, after fees) **{pct(proj['exp_return_geo'], 2)}**, volatility **{pct(proj['vol'])}**", "",
              f"Monte Carlo ({C.cma()['simulation']['paths']} fat-tailed paths), wealth at horizon:", "",
              f"- 10th percentile (bad luck): {money(proj['p10'])}",
              f"- median: {money(proj['median'])} (= {money(proj['median_real'])} in today's dollars)",
              f"- 90th percentile (good luck): {money(proj['p90'])}"]
    if "prob_target" in proj:
        lines.append(f"- probability of reaching {_target_txt(prof)}: **{pct(proj['prob_target'])}**")
    if saa.get("status") == "stretch":
        lines += ["", f"**Goal is a stretch.** No allocation inside the guardrails reaches the target with "
                  f"{prof.get('confidence', 0.7):.0%} confidence. The best one needs about "
                  f"{money(saa['required_annual_contribution'])}/yr of contributions, or a longer horizon / lower target."]
    if saa.get("frontier"):
        lines += ["", "## Efficient frontier considered", "", "| exp. return | vol | P(target) | 10th pct | median | " + " | ".join(SLEEVES) + " |",
                  "|---|---|---|---|---|" + "---|" * len(SLEEVES)]
        for r in saa["frontier"]:
            mark = " **<- chosen**" if saa.get("chosen") and abs(r["vol"] - saa["chosen"]["vol"]) < 1e-9 else ""
            lines.append(f"| {pct(r['exp_return_geo'], 2)} | {pct(r['vol'])} | {pct(r['prob_target'])} | {money(r['p10'])} | {money(r['median'])} | "
                         + " | ".join(pct(r["weights"][s]) for s in SLEEVES) + f" |{mark}")
        rule = {"max_p10": "the row with the best 10th-percentile outcome", "min_vol": "the LEAST volatile row",
                "max_median": "the row with the highest median"}[prof.get("selection", "max_p10")]
        lines += ["", f"Rule: among rows whose P(target) clears {prof.get('confidence', 0.7):.0%}, pick {rule}; "
                  "if none clears it, pick the most likely row. Then apply guardrails."]
    lines += ["", f"Correlations from: {saa.get('corr_source')}. Assumptions: config/cma.yaml (as of {C.cma()['as_of']})."]
    out = C.REPORTS / "plan.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nSaved {SAA_FILE} and {out}")


def cmd_signals(a):
    sig = signals(sleeve_index(sleeve_returns()))
    cols = ["pct_vs_sma10", "trend_up", "mom_3m", "mom_6m", "mom_12m", "mom_blend", "beats_cash", "vol_12m"]
    print(f"Signals as of month-end {sig['month_end'].iloc[0]}")
    print(sig[cols].to_string(float_format=lambda x: f"{x:+.3f}"))


def _build(prof, month, today, prices, rets, vals, wealth, override=None):
    g = C.guardrails(prof["goal"])
    yl, yi = C.years_left(prof, today), int(C.years_elapsed(prof, today))
    paper = prof.get("mode", "paper") == "paper"
    first = wealth == 0
    if first and not paper:
        raise SystemExit("live mode: enter your current balances first with `ai401k sync --set US_EQ=...,BONDS=...`")
    deposit = prof["initial_balance"] if first else (C.monthly_contribution(prof, today) if paper else 0.0)
    saa_info = _saa(prof, wealth + deposit, today, rets)
    saa = saa_info["weights"]
    tcfg = C.profiles()["profiles"][prof["goal"]]["tactical"]
    sig = signals(sleeve_index(rets))
    tw, notes = tactical(saa, sig, tcfg)
    final = project(tw, g, yl, saa)
    if final != {s: round(tw[s], 4) for s in SLEEVES}:
        notes.append("guardrails adjusted the tactical weights (see final vs tactical)")
    if override:
        final = {s: round(final[s] + override["delta"].get(s, 0.0), 4) for s in SLEEVES}
    errors = check(final, g, yl, saa)
    trades = plan_trades(vals, final, deposit, prices, g["rebalance"])
    proj = projection(prof, saa, wealth + deposit, yl, yi, rets)
    return {
        "month": month, "created": datetime.now().isoformat(timespec="seconds"), "as_of": today.isoformat(),
        "investor": prof["name"], "goal": prof["goal"], "mode": prof.get("mode", "paper"),
        "target_amount": prof.get("target_amount"), "target_nominal": C.nominal_target(prof), "years_left": round(yl, 2),
        "prices": prices, "signals_month_end": sig["month_end"].iloc[0],
        "signals": sig.drop(columns=["month_end"]).round(4).to_dict(orient="index"),
        "strategic": saa, "strategic_status": saa_info.get("status"),
        "tactical": {s: round(tw[s], 4) for s in SLEEVES}, "tactical_notes": notes,
        "override": override, "final": final, "validation_errors": errors,
        "trades": trades,
        "projection": {k: proj[k] for k in ("median", "p10", "p90", "median_real", "prob_target", "exp_return_geo", "vol") if k in proj},
        "status": "draft" if not errors else "invalid",
    }


def _month(a, today) -> str:
    return a.month or today.strftime("%Y-%m")


def cmd_propose(a):
    prof, today = C.investor(), _today(a)
    month = _month(a, today)
    if month in approved_months():
        raise SystemExit(f"{month} is already approved. Next proposal is for next month.")
    prices = latest_prices()
    stale = (today - date.fromisoformat(min(p["date"] for p in prices.values()))).days
    rets = sleeve_returns()
    _, vals, wealth = _wealth(prices)
    p = _build(prof, month, today, prices, rets, vals, wealth)
    p["data_age_days"] = stale
    path = save_proposal(p)
    md = proposal_md(p)
    path.with_suffix(".md").write_text(md)
    print(md)
    if stale > 5:
        print(f"\nWARNING: newest price is {stale} days old. Run `ai401k data` first.")
    print(f"\nSaved {path}")
    return 0 if not p["validation_errors"] else 2


def cmd_override(a):
    prof, today = C.investor(), _today(a)
    month = a.month or latest_proposal_month()
    old = load_proposal(month)
    if old["status"] == "approved":
        raise SystemExit("already approved; overrides are closed for this month")
    delta = _parse_kv(a.set)
    delta = {s: v for s, v in delta.items() if v}
    g = C.guardrails(prof["goal"])
    errs = check_override(delta, a.reason, g)
    pre = old["override"]["pre_override"] if old.get("override") else old["final"]  # a new override replaces the old one
    if not errs:
        trial = {s: round(pre[s] + delta.get(s, 0.0), 4) for s in SLEEVES}
        errs = check(trial, g, old["years_left"], old["strategic"])
    if errs:
        print("OVERRIDE REJECTED:\n  - " + "\n  - ".join(errs))
        return 2
    prices = old["prices"]
    _, vals, _ = _wealth(prices)
    base = dict(old)
    ov = {"delta": delta, "reason": a.reason.strip(), "by": a.by, "at": datetime.now().isoformat(timespec="seconds"),
          "pre_override": pre}
    final = {s: round(pre[s] + delta.get(s, 0.0), 4) for s in SLEEVES}
    trades = plan_trades(vals, final, old["trades"]["deposit"], prices, g["rebalance"])
    base.update(final=final, override=ov, trades=trades, validation_errors=check(final, g, old["years_left"], old["strategic"]),
                status="draft")
    save_proposal(base)
    md = proposal_md(base)
    C.PROPOSALS.joinpath(f"{month}.md").write_text(md)
    print(md)
    print("\nOverride accepted and saved.")
    return 0


def cmd_validate(a):
    prof = C.investor()
    month = a.month or latest_proposal_month()
    p = load_proposal(month)
    g = C.guardrails(prof["goal"])
    errs = check(p["final"], g, p["years_left"], p["strategic"])
    if p.get("override"):
        errs += check_override(p["override"]["delta"], p["override"]["reason"], g)
    flow = sum(o["trade_usd"] for o in p["trades"]["orders"])
    if abs(flow - p["trades"]["deposit"]) > 0.05:
        errs.append(f"trades net to {flow:.2f} but deposit is {p['trades']['deposit']:.2f}")
    if p["trades"]["turnover"] > g["rebalance"]["max_turnover"] + 1e-6:
        errs.append(f"turnover {p['trades']['turnover']:.1%} exceeds cap")
    if errs:
        print(f"{month}: FAIL\n  - " + "\n  - ".join(errs))
        return 2
    print(f"{month}: PASS (weights within policy, override within limits, trades balance, turnover {pct(p['trades']['turnover'])})")
    return 0


def cmd_approve(a):
    prof = C.investor()
    month = a.month or latest_proposal_month()
    if cmd_validate(argparse.Namespace(month=month)) != 0:
        raise SystemExit("not approved: fix validation errors first")
    p = load_proposal(month)
    if p["status"] == "approved":
        raise SystemExit(f"{month} was already approved at {p.get('approved_at')}")
    if not a.yes:
        if not sys.stdin.isatty() or input(f"Type APPROVE to execute {month}: ").strip() != "APPROVE":
            raise SystemExit("not approved (pass --yes after the human has approved in the chat)")
    prices = p["prices"]
    units = load_holdings()
    rows = []
    if p["trades"]["deposit"]:
        rows.append({"month": month, "sleeve": "", "ticker": "", "action": "deposit", "usd": p["trades"]["deposit"],
                     "price": "", "units": "", "note": "initial funding" if not any(units.values()) else "monthly contribution (paper)"})
    paper = p["mode"] == "paper"
    for o in p["trades"]["orders"]:
        if o["trade_usd"]:
            if paper:
                units[o["sleeve"]] += o["trade_units"]
            rows.append({"month": month, "sleeve": o["sleeve"], "ticker": o["ticker"],
                         "action": ("buy" if o["trade_usd"] > 0 else "sell") if paper else "instruction",
                         "usd": o["trade_usd"], "price": o["price"], "units": o["trade_units"],
                         "note": "paper fill at proposal price" if paper else "execute on plan website, then `ai401k sync`"})
    if paper:
        save_holdings(units, prices)
    append_ledger(rows)
    p.update(status="approved", approved_at=datetime.now().isoformat(timespec="seconds"), approved_by=a.by)
    save_proposal(p)
    print(f"{month} approved by {a.by}. {len(rows)} ledger rows written.")
    if not paper:
        print("LIVE MODE: log in to your 401k website and (1) set future contributions to "
              + ", ".join(f"{s} {v}%" for s, v in p["trades"]["contribution_election_pct"].items())
              + " and (2) place the exchanges listed in the proposal. Then run `ai401k sync`.")
    return 0


def cmd_sync(a):
    """Live mode: overwrite holdings with the balances shown on your 401k website."""
    prices = latest_prices()
    bal = _parse_kv(a.set)
    units = load_holdings()
    rows = []
    for s, usd in bal.items():
        if s not in SLEEVES:
            raise SystemExit(f"unknown sleeve {s}")
        units[s] = usd / prices[s]["price"]
        rows.append({"month": date.today().strftime("%Y-%m"), "sleeve": s, "ticker": prices[s]["ticker"], "action": "sync",
                     "usd": usd, "price": prices[s]["price"], "units": units[s], "note": "balance from plan statement"})
    if a.deposit:
        rows.append({"month": date.today().strftime("%Y-%m"), "sleeve": "", "ticker": "", "action": "deposit",
                     "usd": a.deposit, "price": "", "units": "", "note": "contributions since last sync (live)"})
    save_holdings(units, prices)
    append_ledger(rows)
    print(f"holdings updated: {', '.join(f'{s}={money(v)}' for s, v in bal.items())}")


def cmd_status(a):
    prof, today = C.investor(), _today(a)
    prices = latest_prices()
    _, vals, wealth = _wealth(prices)
    month = latest_proposal_month()
    tgt = load_proposal(month)["final"] if month else None
    deposits = total_deposits()
    out = {"name": prof["name"], "goal": prof["goal"], "mode": prof.get("mode", "paper"), "as_of": today.isoformat(),
           "years_left": round(C.years_left(prof, today), 2), "value": round(wealth, 2), "deposits": round(deposits, 2),
           "gain": round(wealth - deposits, 2), "last_proposal": month,
           "last_proposal_status": load_proposal(month)["status"] if month else None,
           "approved_months": len(approved_months()),
           "positions": {s: {"ticker": prices[s]["ticker"], "value": round(vals[s], 2),
                             "weight": round(vals[s] / wealth, 4) if wealth else 0.0,
                             "target": tgt[s] if tgt else None} for s in SLEEVES}}
    if SAA_FILE.exists():
        saa = json.loads(SAA_FILE.read_text())
        out["strategic"] = saa["weights"]
        if wealth:
            pr = projection(prof, saa["weights"], wealth, C.years_left(prof, today), int(C.years_elapsed(prof, today)), sleeve_returns())
            out["projection"] = {k: round(v, 3) if isinstance(v, float) else v for k, v in pr.items() if k != "fan"}
    if a.json:
        print(json.dumps(out, indent=2))
        return
    print(f"{prof['name']} | goal {prof['goal']} | {out['mode']} mode | {out['years_left']} years left | as of {today}")
    print(f"value {money(wealth)}   contributed {money(deposits)}   gain {money(wealth - deposits)}")
    print(f"{'sleeve':8s} {'ticker':6s} {'value':>12s} {'weight':>7s} {'target':>7s}")
    for s, p in out["positions"].items():
        print(f"{s:8s} {p['ticker']:6s} {money(p['value']):>12s} {pct(p['weight']):>7s} {pct(p['target']) if p['target'] is not None else '-':>7s}")
    if "projection" in out:
        pr = out["projection"]
        line = f"projection at horizon: median {money(pr['median'])}, 10th pct {money(pr['p10'])}"
        if "prob_target" in pr:
            line += f", P(reach {_target_txt(prof)}) = {pct(pr['prob_target'])}"
        print(line)
    print(f"last proposal: {month} ({out['last_proposal_status']})")


def cmd_backtest(a):
    import pandas as pd

    prof = C.investor()
    goals = C.GOALS if a.all else [prof["goal"]]
    curves, table = __import__("ai401k.backtest", fromlist=["compare"]).compare(prof, goals=goals)
    C.REPORTS.mkdir(exist_ok=True)
    curves.to_csv(C.REPORTS / "backtest_wealth.csv", float_format="%.2f")
    df = pd.DataFrame(table).T
    (C.REPORTS / "backtest_metrics.json").write_text(json.dumps(table, indent=2))
    show = df[["final_wealth", "contributed", "irr_money_weighted", "cagr_twr", "vol", "max_drawdown", "worst_12m", "sharpe_vs_0", "months_rebalanced_pct"]]
    fmt = show.copy()
    for c in ["irr_money_weighted", "cagr_twr", "vol", "max_drawdown", "worst_12m", "months_rebalanced_pct"]:
        fmt[c] = show[c].map(lambda v: f"{v:.1%}")
    fmt["sharpe_vs_0"] = show["sharpe_vs_0"].map(lambda v: f"{v:.2f}")
    for c in ["final_wealth", "contributed"]:
        fmt[c] = show[c].map(money)
    first = next(iter(table.values()))
    md = (f"# Back-test {first['start']} .. {first['end']} ({first['years']} years), same deposits for every strategy\n\n"
          f"Initial {money(prof['initial_balance'])}, then {money(prof['annual_contribution'])}/yr growing {prof.get('contribution_growth', 0):.0%}/yr. "
          "Glide path counts down from your horizon.\n\n" + fmt.to_markdown() + "\n")
    (C.REPORTS / "backtest.md").write_text(md)
    print(md)
    print(f"Saved reports/backtest.md, backtest_wealth.csv, backtest_metrics.json")


def cmd_project(a):
    prof, today = C.investor(), _today(a)
    prices = latest_prices()
    _, _, wealth = _wealth(prices)
    wealth = wealth or prof["initial_balance"]
    rets = sleeve_returns()
    saa = _saa(prof, wealth, today, rets)
    yl = C.years_left(prof, today)
    pr = projection(prof, saa["weights"], wealth, yl, int(C.years_elapsed(prof, today)), rets)
    print(f"Projection from {money(wealth)} with strategic weights, {yl:.1f} years:")
    print(f"{'year':>4s} {'p10':>12s} {'p50':>12s} {'p90':>12s}")
    for y in range(0, len(pr["fan"][50]), max(1, len(pr["fan"][50]) // 10)):
        print(f"{y:>4d} {money(pr['fan'][10][y]):>12s} {money(pr['fan'][50][y]):>12s} {money(pr['fan'][90][y]):>12s}")
    if "prob_target" in pr:
        print(f"P(reach {_target_txt(prof)}) = {pct(pr['prob_target'])}")


def cmd_report(a):
    path = write_dashboard()
    print(f"Saved {path}  (open it in a browser)")


def cmd_doctor(a):
    ok = True
    print(f"ai401k {__version__}, Python {sys.version.split()[0]}, kit at {C.ROOT}")
    for mod in ["numpy", "pandas", "scipy", "matplotlib", "yaml", "yfinance"]:
        try:
            __import__(mod)
            print(f"  [ok] {mod}")
        except ImportError:
            ok = False
            print(f"  [!!] {mod} missing: rerun the installer")
    try:
        px = load_daily()
        age = (date.today() - px.index[-1].date()).days
        print(f"  [{'ok' if age <= 5 else '!!'}] price data ends {px.index[-1]:%Y-%m-%d} ({age} days old)" + ("" if age <= 5 else ": run `ai401k data`"))
    except SystemExit as e:
        ok = False
        print(f"  [!!] {e}")
    print(f"  [{'ok' if C.profile_path().exists() else '--'}] investor profile {'found' if C.profile_path().exists() else 'not created yet (ai401k init)'}")
    print(f"  [{'ok' if shutil.which('claude') else '--'}] Claude Code CLI {'found' if shutil.which('claude') else 'not on PATH (see INSTALL.md step 3)'}")
    try:
        g = C.guardrails()
        project({s: 0.2 for s in SLEEVES}, g, 25)
        print("  [ok] guardrails feasible")
    except ValueError as e:
        ok = False
        print(f"  [!!] {e}")
    return 0 if ok else 1


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ai401k", description="AI-assisted 401k allocation and monthly rebalancing")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create portfolio/profile.yaml (your inputs and goal)")
    p.add_argument("--name"); p.add_argument("--initial", type=float); p.add_argument("--contribution", type=float)
    p.add_argument("--growth", type=float, default=0.03, help="yearly growth of contributions (default 0.03)")
    p.add_argument("--years", type=float); p.add_argument("--goal", help="|".join(C.GOALS) + " or a dollar amount")
    p.add_argument("--target", type=float); p.add_argument("--confidence", type=float, default=0.70)
    p.add_argument("--nominal", action="store_true", help="target is in future dollars (default: today's dollars)")
    p.add_argument("--mode", choices=["paper", "live"], default="paper"); p.add_argument("--start-date")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("data", help="download/refresh prices"); p.add_argument("--offline", action="store_true")
    for name, hlp in [("plan", "solve the strategic allocation + Monte Carlo (yearly)"), ("project", "Monte Carlo fan chart"),
                      ("signals", "show trend/momentum signals"), ("propose", "build this month's proposal"),
                      ("status", "holdings, drift, progress to goal")]:
        p = sub.add_parser(name, help=hlp); p.add_argument("--as-of"); p.add_argument("--month")
        if name == "status":
            p.add_argument("--json", action="store_true")
    p = sub.add_parser("override", help="bounded discretionary change to the proposal (AI or human)")
    p.add_argument("--month"); p.add_argument("--set", required=True, help="e.g. US_EQ=-0.03,BONDS=0.03")
    p.add_argument("--reason", required=True); p.add_argument("--by", default="claude"); p.add_argument("--as-of")
    p = sub.add_parser("validate", help="check the proposal against the guardrails"); p.add_argument("--month")
    p = sub.add_parser("approve", help="execute (paper) or record (live) the proposal")
    p.add_argument("--month"); p.add_argument("--yes", action="store_true"); p.add_argument("--by", default="owner")
    p = sub.add_parser("sync", help="live mode: enter balances from your 401k website")
    p.add_argument("--set", required=True, help="e.g. US_EQ=52000,INTL_EQ=26000,BONDS=18000,GOLD=5000,CASH=2000")
    p.add_argument("--deposit", type=float, default=0.0, help="contributions received since the last sync")
    p = sub.add_parser("backtest", help="walk-forward back-test vs benchmarks"); p.add_argument("--all", action="store_true")
    sub.add_parser("report", help="HTML dashboard in reports/dashboard.html")
    sub.add_parser("doctor", help="check the installation")
    return ap


COMMANDS = {"init": cmd_init, "data": cmd_data, "plan": cmd_plan, "signals": cmd_signals, "propose": cmd_propose,
            "override": cmd_override, "validate": cmd_validate, "approve": cmd_approve, "sync": cmd_sync,
            "status": cmd_status, "backtest": cmd_backtest, "project": cmd_project, "report": cmd_report, "doctor": cmd_doctor}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.cmd](args) or 0
