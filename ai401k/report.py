"""Human-readable output: the monthly proposal in Markdown and a one-page HTML dashboard."""
from __future__ import annotations

import base64
import io
import json

from . import SLEEVES
from . import config as C


def money(x) -> str:
    return "-" if x is None else f"${round(x) + 0:,.0f}"


def pct(x, d: int = 1) -> str:
    return "-" if x is None else f"{x * 100:.{d}f}%"


def proposal_md(p: dict) -> str:
    t = p["trades"]
    L = [f"# {p['month']} rebalancing proposal ({p['mode']} mode)", "",
         f"Investor {p['investor']} | goal **{p['goal']}**" + (f" ({money(p['target_amount'])} today's $ = {money(p.get('target_nominal'))} nominal)" if p.get("target_amount") else "")
         + f" | {p['years_left']} years left | prices as of {min(v['date'] for v in p['prices'].values())} "
         f"| signals as of month-end {p['signals_month_end']}", "",
         f"**Status: {p['status'].upper()}**" + ("" if not p["validation_errors"] else " - " + "; ".join(p["validation_errors"])), "",
         "## Signals", "", "| sleeve | vs 10m avg | trend | 3m | 6m | 12m | blended mom. | beats cash |", "|---|---|---|---|---|---|---|---|"]
    for s in SLEEVES:
        g = p["signals"][s]
        L.append(f"| {s} | {pct(g['pct_vs_sma10'])} | {'up' if g['trend_up'] else 'DOWN'} | {pct(g['mom_3m'])} | {pct(g['mom_6m'])} "
                 f"| {pct(g['mom_12m'])} | {pct(g['mom_blend'])} | {'yes' if g['beats_cash'] else 'no'} |")
    L += ["", "Tactical rule says:"] + [f"- {n}" for n in p["tactical_notes"]]
    L += ["", "## Weights", "", "| sleeve | strategic | tactical | " + ("override | " if p.get("override") else "") + "**final** |",
          "|---|---|---|" + ("---|" if p.get("override") else "") + "---|"]
    for s in SLEEVES:
        ov = f"{p['override']['delta'].get(s, 0) * 100:+.1f} | " if p.get("override") else ""
        L.append(f"| {s} | {pct(p['strategic'][s])} | {pct(p['tactical'][s])} | {ov}**{pct(p['final'][s])}** |")
    if p.get("override"):
        L += ["", f"Discretionary override by {p['override']['by']}: {p['override']['reason']}"]
    L += ["", "## Orders", "", f"Mode: **{t['mode']}**. New money this month: {money(t['deposit'])}. "
          f"Turnover {pct(t['turnover'])}." + (f" Largest drift before trading {pct(t['max_drift_before'])}." if t["max_drift_before"] is not None else ""), "",
          "| sleeve | fund | now $ | now % | target % | trade $ | ~units @ price | after % |", "|---|---|---|---|---|---|---|---|"]
    for o in t["orders"]:
        tr = f"{o['trade_usd']:+,.0f}" if o["trade_usd"] else "-"
        un = f"{o['trade_units']:+,.3f} @ {o['price']:,.2f}" if o["trade_usd"] else ""
        L.append(f"| {o['sleeve']} | {o['ticker']} | {money(o['current_usd'])} | {pct(o['current_w'])} | {pct(o['target_w'])} | {tr} | {un} | {pct(o['post_w'])} |")
    L += ["", "Future-contribution election (whole %, for the plan website): "
          + ", ".join(f"{s} {v}%" for s, v in t["contribution_election_pct"].items())]
    pr = p["projection"]
    L += ["", "## Where this is heading (strategic mix, Monte Carlo)", "",
          f"Median at horizon {money(pr['median'])} (today's dollars {money(pr['median_real'])}); 10th pct {money(pr['p10'])}; 90th pct {money(pr['p90'])}."
          + (f" Probability of reaching {money(p.get('target_nominal'))}: **{pct(pr['prob_target'])}**." if "prob_target" in pr else "")]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- dashboard
def _img(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def write_dashboard():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    from .data import latest_prices, sleeve_returns
    from .ledger import latest_proposal_month, load_holdings, load_proposal, read_ledger, values
    from .plan import projection

    prof = C.investor()
    from datetime import date
    today = date.today()
    prices = latest_prices()
    vals = values(load_holdings(), prices)
    wealth = sum(vals.values())
    month = latest_proposal_month()
    prop = load_proposal(month) if month else None
    saa = json.loads((C.PORTFOLIO / "saa.json").read_text())["weights"] if (C.PORTFOLIO / "saa.json").exists() else None
    colors = ["#2b6cb0", "#63b3ed", "#718096", "#d69e2e", "#a0aec0"]
    imgs = {}

    if prop:
        fig, ax = plt.subplots(figsize=(7, 3))
        x = range(len(SLEEVES))
        cur = [vals[s] / wealth if wealth else 0 for s in SLEEVES]
        ax.bar([i - 0.27 for i in x], cur, 0.27, label="now", color="#a0aec0")
        if saa:
            ax.bar(x, [saa[s] for s in SLEEVES], 0.27, label="strategic", color="#63b3ed")
        ax.bar([i + 0.27 for i in x], [prop["final"][s] for s in SLEEVES], 0.27, label=f"target {month}", color="#2b6cb0")
        ax.set_xticks(list(x), SLEEVES); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.legend(frameon=False)
        ax.set_title("Allocation"); ax.spines[["top", "right"]].set_visible(False)
        imgs["alloc"] = _img(fig); plt.close(fig)

    if saa:
        yl = C.years_left(prof, today)
        pr = projection(prof, saa, wealth or prof["initial_balance"], yl, int(C.years_elapsed(prof, today)), sleeve_returns())
        yrs = [today.year + i for i in range(len(pr["fan"][50]))]
        fig, ax = plt.subplots(figsize=(7, 3.2))
        ax.fill_between(yrs, pr["fan"][10], pr["fan"][90], color="#bee3f8", label="10th-90th pct")
        ax.fill_between(yrs, pr["fan"][25], pr["fan"][75], color="#90cdf4", label="25th-75th pct")
        ax.plot(yrs, pr["fan"][50], color="#2b6cb0", label="median")
        if prof.get("target_amount"):
            ax.axhline(C.nominal_target(prof), color="#c53030", ls="--", lw=1, label="target")
        ax.yaxis.set_major_formatter(lambda v, _: f"${v / 1e6:.1f}M"); ax.legend(frameon=False, fontsize=8)
        ax.set_title("Projected 401k value (Monte Carlo)"); ax.spines[["top", "right"]].set_visible(False)
        imgs["fan"] = _img(fig); plt.close(fig)

    bt = C.REPORTS / "backtest_wealth.csv"
    if bt.exists():
        curves = pd.read_csv(bt, index_col=0, parse_dates=True)
        fig, ax = plt.subplots(figsize=(7, 3.2))
        for i, c in enumerate(curves.columns):
            ax.plot(curves.index, curves[c], lw=2.2 if "your plan" in c else 1, label=c,
                    color="#2b6cb0" if "your plan" in c else None, alpha=1 if "your plan" in c else 0.7)
        ax.yaxis.set_major_formatter(lambda v, _: f"${v / 1e6:.1f}M"); ax.legend(frameon=False, fontsize=7)
        ax.set_title("Back-test: account value with the same contributions"); ax.spines[["top", "right"]].set_visible(False)
        imgs["bt"] = _img(fig); plt.close(fig)

    led = read_ledger()
    rows = "".join(f"<tr><td>{r['month']}</td><td>{r['action']}</td><td>{r['sleeve']}</td><td>{r['ticker']}</td>"
                   f"<td style='text-align:right'>{float(r['usd']):,.2f}</td><td>{r['note']}</td></tr>" for r in led[-40:])
    metrics = ""
    mfile = C.REPORTS / "backtest_metrics.json"
    if mfile.exists():
        m = json.loads(mfile.read_text())
        metrics = "<table><tr><th>strategy</th><th>final</th><th>IRR</th><th>vol</th><th>max DD</th><th>Sharpe</th></tr>" + "".join(
            f"<tr><td>{k}</td><td>{money(v['final_wealth'])}</td><td>{pct(v['irr_money_weighted'])}</td><td>{pct(v['vol'])}</td>"
            f"<td>{pct(v['max_drawdown'])}</td><td>{v['sharpe_vs_0']:.2f}</td></tr>" for k, v in m.items()) + "</table>"
    img = lambda k: f"<img src='{imgs[k]}' alt='{k} chart'>" if k in imgs else "<p class=muted>not available yet</p>"
    html = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>401k Dashboard</title><style>
:root{{--bg:#fff;--fg:#1a202c;--muted:#718096;--line:#e2e8f0;--card:#f7fafc}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1a202c;--fg:#edf2f7;--muted:#a0aec0;--line:#2d3748;--card:#232b3a}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:980px;margin:0 auto;padding:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}
.k{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px}}.k b{{font-size:22px;display:block}}
img{{max-width:100%;background:#fff;border-radius:6px}}table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}}.muted{{color:var(--muted)}}
.wrap{{overflow-x:auto}}</style></head><body>
<h1>{prof['name']}'s 401k</h1><p class=muted>goal {prof['goal']} · {prof.get('mode','paper')} mode · generated {today}</p>
<div class=grid><div class=k>value<b>{money(wealth)}</b></div><div class=k>years left<b>{C.years_left(prof, today):.1f}</b></div>
<div class=k>last proposal<b>{month or '-'}</b>{prop['status'] if prop else ''}</div>
<div class=k>P(target)<b>{pct(prop['projection'].get('prob_target')) if prop else '-'}</b></div></div>
<h2>Allocation</h2>{img('alloc')}<h2>Projection</h2>{img('fan')}<h2>Back-test</h2>{img('bt')}<div class=wrap>{metrics}</div>
<h2>Ledger (last 40 rows)</h2><div class=wrap><table><tr><th>month</th><th>action</th><th>sleeve</th><th>ticker</th><th>usd</th><th>note</th></tr>{rows}</table></div>
<p class=muted>Educational project, not investment advice.</p></body></html>"""
    C.REPORTS.mkdir(exist_ok=True)
    out = C.REPORTS / "dashboard.html"
    out.write_text(html)
    return out
