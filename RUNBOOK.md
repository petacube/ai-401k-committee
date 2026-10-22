# Runbook: running your AI-assisted 401k

What to do, when, and what to type. Time needed: **one hour once**, then **about 15 minutes a month**.
Everything happens in a terminal inside this folder, talking to Claude Code in plain English.

```
cd student2        # this folder
claude             # start Claude Code; then type the slash commands below
```

---

## 1. Calendar

| When | What you type | Time | Output |
|---|---|---|---|
| Once, after installing | `/onboard` | 45-60 min | `portfolio/profile.yaml`, `reports/plan.md`, `reports/backtest.md`, `journal/IPS.md`, first memo, first allocation |
| **First business day of every month** | `/rebalance` | 10-15 min | `portfolio/proposals/YYYY-MM.md`, `journal/YYYY-MM.md`, updated ledger and dashboard |
| Any time | `/status` | 1 min | value, drift, probability of reaching the goal |
| Each January (or after a raise, job change, marriage, etc.) | `/annual-review` | 30-45 min | `journal/YYYY-annual-review.md`, new strategic plan |
| Whenever a number puzzles you | `/explain <topic>` | 2 min | interview-ready explanation |

Tip: put a recurring reminder in your calendar: *"401k committee: open terminal, `claude`, `/rebalance`"*.

## 2. One-time setup: `/onboard`

Prerequisite: the kit is installed (INSTALL.md) and `./ai401k.sh doctor` shows `[ok]` for the
packages and prices.

Claude will:
1. check the installation and refresh prices;
2. **interview you**: balance, yearly contribution including the employer match, expected raises,
   years to goal, the goal itself, confidence level, paper or live mode, and two risk-tolerance questions;
3. create your profile (`./ai401k.sh init ...`; you'll get a permission prompt, so press *Yes*);
4. build the strategic plan and explain it: weights, expected return, the median and the bad-luck
   outcome in today's dollars, and the probability of reaching your goal. **If the goal is a stretch,
   it shows the contribution you would need**;
5. run the back-test of every goal against 60/40 and 100% US stocks (a few minutes);
6. run the first monthly cycle: the initial allocation of your balance;
7. write your one-page Investment Policy Statement `journal/IPS.md` and ask for your approval.

**Paper or live?**

| | paper (recommended to start) | live |
|---|---|---|
| Money | simulated, ETFs at real market prices | your actual 401k |
| Contributions | added automatically each month | arrive by payroll; you report balances each month |
| Execution | `approve` fills the trades at the proposal's prices | `approve` records the instructions; **you** click them on the plan website |
| Good for | building a 6-12 month track record to show employers | managing your real retirement money |

You can run paper first and switch later: `./ai401k.sh init --force ... --mode live`, then `sync`.

### 2a. Live mode: map the kit to your plan's fund menu

Most 401k plans offer a short menu of mutual funds, not ETFs. Do this once before the first live
`/rebalance` (Claude can do it with you during `/onboard`; each config edit asks for your permission):

1. **Find the funds.** On the plan website, list the funds with their ticker symbols (5 letters, e.g.
   FXAIX). For each sleeve pick the cheapest broad **index** fund:

   | Sleeve | Look for | Example (Fidelity plan) |
   |---|---|---|
   | US_EQ | total US market or S&P 500 index | FXAIX, FSKAX |
   | INTL_EQ | total international or developed-markets index | FTIHX, FSPSX |
   | BONDS | US aggregate / total bond index | FXNAX |
   | GOLD | usually not offered (see step 3) | — |
   | CASH | stable value, money market or short Treasury fund | SPAXX |

   Avoid target-date funds here: they already mix stocks and bonds and would double-count.
2. **Edit `config/universe.yaml`.** Set `ticker` to the plan fund's symbol and `plan_fund` to its name
   exactly as the website shows it. Leave the `history` lists alone (they feed the back-test). Then run
   `./ai401k.sh data` and check that every sleeve shows a price. A fund Yahoo Finance doesn't know
   (some "collective investment trusts" have no ticker) shows `DOWNLOAD FAILED`. In that case use the
   closest public index fund or ETF as the ticker, and use the real fund's balance in `sync`.
3. **No gold in the plan?** Set `GOLD: [0.00, 0.00]` in `config/guardrails.yaml` (you edit this file;
   Claude can't). If your goal is `momentum`, also change `GOLD: [0, 0.40]` to `GOLD: [0, 0]` under
   `momentum: guardrail_overrides` in `config/profiles.yaml`, because that line replaces the
   guardrail for that goal. Then run `./ai401k.sh plan`: gold's weight is redistributed automatically.
   If the plan offers a brokerage window, you can hold GLDM there instead.
4. **Check the plan's frequent-trading rules.** Search the plan documents for "excessive trading" or
   "round trip". Many plans block buying back a fund within 30-90 days of selling it. The trend filter
   and especially the `momentum` goal can switch a fund in and out within weeks. If your plan has such
   a rule, prefer `balanced`, `aggressive` or `max_wealth`, or raise `drift_band_abs` in
   `config/guardrails.yaml` (e.g. to 0.05), and tell Claude, who will flag any proposal that buys back
   a fund sold less than 90 days ago.
5. **Enter your balances:** `./ai401k.sh sync --set US_EQ=...,INTL_EQ=...,BONDS=...,GOLD=0,CASH=...`

## 3. Monthly: `/rebalance`

Type `/rebalance` (or `/rebalance 2026-12` for a specific month). Claude runs these steps; your
part is in **bold**.

| # | Step | Command Claude runs | What you check |
|---|---|---|---|
| 1 | Health check, fresh prices | `doctor`, `data` | prices are 0-5 days old |
| 1b | *Live mode only:* balances | `sync --set ... --deposit ...` | **read your balances from the 401k website when Claude asks** |
| 2 | Where we are | `status` | value, gain, P(goal) |
| 3 | Systematic proposal | `propose` | signals, tactical notes, orders |
| 4 | Research + challenge in parallel | `macro-analyst` and `risk-officer` sub-agents | sources are dated; verdict PASS |
| 5 | Optional bounded override | `override ...` (usually none) | the reason is specific and sourced |
| 6 | Policy check | `validate` | must print PASS |
| 7 | Memo | writes `journal/YYYY-MM.md` | **read it (2 minutes)** |
| 8 | Decision | asks "Do you approve?" | **type `approve`, or ask questions / defer** |
| 9 | Execute & record | `approve --yes --by <you>` (permission prompt) then `report` | **press Yes on the prompt** |
| 10 | *Live mode only:* place trades | gives you a click-list | **update contribution %, then exchanges (sells before buys)**; next month's `sync` captures the result |

**What "good" looks like:** most months the orders are "within band: invest new money only" and the
memo says "no override". That is the strategy working, not doing nothing. Activity is not value.

**Reading the proposal (portfolio/proposals/YYYY-MM.md):**
- *Signals*: `trend DOWN` means a sleeve is below its 10-month average. Under the trend rule part of
  that sleeve's weight moves to cash until it recovers.
- *Weights*: strategic (long-run plan) → tactical (after rules) → override (if any) → **final**.
- *Orders*: dollars per fund, estimated units, and the contribution-election percentages.
- *Where this is heading*: Monte Carlo median and 10th percentile at your horizon; probability of goal.

## 4. Annual: `/annual-review`

1. Year in numbers: value, contributions, gain, months approved, overrides and whether they helped.
2. Capital-market assumptions: the macro-analyst collects current 10-year forecasts (Vanguard, J.P.
   Morgan, BlackRock, Research Affiliates); Claude proposes changes of at most ±1 point per sleeve, each
   cited. **You approve the edit to `config/cma.yaml`.**
3. Life check: **new salary or contribution? employer match? horizon or goal change?** Check the IRS
   401k contribution limit for the new year (irs.gov, "401(k) contribution limit"), including catch-up
   contributions if you are 50 or older.
4. Re-plan (`plan`): new strategic weights. They change because of the glide path, because you are
   ahead or behind the goal, or because the assumptions changed. Claude explains which.
5. Back-test refresh and dashboard.
6. Risk-officer review of the guardrails. **Only you edit `config/guardrails.yaml`**, outside a
   rebalancing session, with a dated note in `journal/`.
7. Update and sign off `journal/IPS.md`.

## 5. Events: what to do when…

| Situation | Action |
|---|---|
| **Markets fall 20%+** | Do nothing special. The trend filter and the bands already react at month-end. If you can't sleep, run `/status` and `/explain drawdown`. Never override in panic: losses alone don't meet the evidence bar (CLAUDE.md rule 3). |
| You missed a month | Just run `/rebalance` for the current month. Don't back-fill old months. |
| You want an extra mid-month rebalance | `/rebalance` works any time, once per month label. Use it rarely; plan frequent-trading rules apply. |
| Raise / new contribution amount | `/annual-review` (or `./ai401k.sh init --force` with the new numbers, then `plan`). Holdings and ledger are kept. |
| Job change / rollover to an IRA | Update `config/universe.yaml` tickers to the new account's funds, `sync` the new balances, re-run `plan`. |
| Your plan changes its fund menu | Map sleeves to the new funds in `config/universe.yaml` (permission prompt), `data`, `sync`. |
| Goal reached early | `/annual-review`: the target solver will de-risk automatically; consider a new goal. |
| Engine prints `OVERRIDE REJECTED` or `validate` FAIL | That is the guardrail doing its job. Claude must not work around it; the month proceeds without the override, or is deferred. |
| `DOWNLOAD FAILED` | Yahoo is down or throttling. Retry later; Claude stops rather than trade on stale prices. `./ai401k.sh data --offline` is only for practice. |
| Claude seems to invent a number | Ask "which command produced that number?" Every figure must come from engine output or a cited source (CLAUDE.md rule 1). |

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `./ai401k.sh: Not installed yet` | run `./install.sh` (Windows: `install.bat`) |
| `No portfolio/profile.yaml yet` | run `/onboard` (or `./ai401k.sh init`) |
| `price data ... days old` | `./ai401k.sh data` |
| `... is already approved` | that month is done; the next proposal is for next month |
| `guardrails are infeasible` | someone edited `config/guardrails.yaml` into a contradiction (e.g. min cash above max) |
| Claude asks permission for everything, or says it "wasn't allowed to run the engine" | start `claude` from inside this folder, and answer **Yes** to "Do you trust the files in this folder?" Until the folder is trusted, Claude Code ignores the allow-list in `.claude/settings.json`. If you answered No, quit (`/exit`) and start `claude` again here |
| Plan says a trade was blocked for "excessive trading" | §2a step 4: switch goal or widen the drift band; skip that fund's trade this month and note it in the memo |
| `claude: command not found` | INSTALL.md step 3; open a new terminal after installing |
| Windows: `./ai401k.sh` not recognised | Claude uses Git Bash; in Command Prompt use `ai401k <command>`, in PowerShell `.\ai401k <command>` |
| Tests fail after you edited code | `git diff` / restore the file; re-run `.venv/bin/python -m pytest -q` |

## 7. Without Claude (manual fallback)

The engine works on its own, which is handy for an interview demo or when you're offline from Claude:

```bash
./ai401k.sh data
./ai401k.sh status
./ai401k.sh propose
./ai401k.sh validate
./ai401k.sh approve          # asks you to type APPROVE
./ai401k.sh report           # open reports/dashboard.html
```

## 8. Turning this into a portfolio piece

After 6-12 months you have a real, timestamped track record:
- `reports/dashboard.html` (one-page visual),
- `journal/` (monthly memos with sources, risk reviews and lessons learned),
- `journal/IPS.md` and `STRATEGY.md` (your methodology),
- `reports/backtest.md` (the evidence, with honest caveats),
- the override log in `portfolio/proposals/*.json` (did the AI layer add value?).

If you put it on GitHub, use paper mode or remove `portfolio/` and real balances first.

*Educational project, not investment advice.*
