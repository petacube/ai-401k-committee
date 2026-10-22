# AI-assisted 401k: goal-based allocation with monthly rebalancing run by Claude Code

*A portfolio-manager-in-training project: allocate a 401k across US stocks, international stocks,
bonds, gold and cash with low-cost ETFs, and run a monthly investment-committee process with an AI
harness. The rules are documented, the arithmetic is reproducible, the limits are enforced in code,
and a human approves every trade.*

## What you give it

| Input | Example |
|---|---|
| Current 401k balance | $100,000 |
| Annual contribution (incl. employer match) | $20,000, growing 3%/yr |
| Horizon | 25 years |
| Goal | `$1,000,000` (in today's dollars) · `max_wealth` · `conservative` · `balanced` · `aggressive` · `momentum` |

## What you get back

- **A strategic allocation** solved for your goal: efficient frontier + 5,000 fat-tailed Monte Carlo
  paths, a probability of success, and the contribution you'd need if the goal is a stretch.
- **A monthly proposal**: trend/momentum signals, tilts, guardrail-checked target weights, dollar
  orders, and the contribution-election percentages for your plan website.
- **A monthly memo** written by Claude: macro brief with dated sources (`macro-analyst` sub-agent),
  independent review (`risk-officer` sub-agent), optional bounded override, your approval.
- **Evidence**: a walk-forward back-test since 2006 against 60/40 and 100% US stocks, and an HTML dashboard.

## How it works

```
 you ──/onboard, /rebalance──▶ Claude Code (CLAUDE.md rules, slash commands, permissions)
                                   │  runs                     │ delegates
                                   ▼                           ▼
                         ai401k engine (Python)        macro-analyst  ─ web research, sourced
                         data → plan → signals →       risk-officer   ─ independent challenge
                         guardrails → orders
                                   │
                                   ▼
             proposal.md + memo ──▶ YOU type "approve" ──▶ ledger, holdings, dashboard
```

| Layer | Rule | Limit (enforced in code) |
|---|---|---|
| Strategic | goal → frontier → Monte Carlo; glide path to the goal date | per-sleeve bounds, equity 10-90%, ≤70% with <7y, ≤45% with <3y |
| Tactical | 10-month trend filter (Faber) or dual momentum (Antonacci) | ±15 pts vs strategic |
| AI overlay | sourced, dated catalyst only; default "no override" | ±5 pts per sleeve, 10 pts total, expires monthly |
| Execution | new money first, then rebalance if drift > 3 pts | 40% max turnover, $100 min trade |
| Human | reads memo, approves | `approve` always prompts for permission |

Full methodology, back-test results and references: **[STRATEGY.md](STRATEGY.md)**.

## Quick start

```bash
git clone https://github.com/petacube/ai-401k-committee.git && cd ai-401k-committee
./install.sh            # Windows: double-click install.bat     (details: INSTALL.md)
claude                  # start Claude Code in this folder
/onboard                # first session: interview → plan → back-test → first allocation
/rebalance              # every month (RUNBOOK.md)
```

## Worked example (the inputs above, $1M goal in today's dollars, 70% confidence)

From `examples/` (generated with real prices on 2026-10-21). **Live example dashboard:** https://petacube.github.io/ai-401k-committee/examples/dashboard.html

- $1M today ≈ **$1.85M** in 2051 dollars at 2.5% inflation.
- Best feasible plan: 50% US / 40% intl / 8% gold / 2% cash; median outcome $2.14M (≈ $1.16M in
  today's dollars), bad-luck 10th percentile $1.12M, **61% probability** of reaching the goal.
- To reach 70% confidence: raise contributions to about **$23,400/yr**.
- October 2026 signals: stocks in uptrends; bonds and gold below their 10-month averages, so the trend
  rule moved half the gold weight to cash for the first allocation.

| Back-test 2006-2026, same deposits | Final value | IRR | Max drawdown |
|---|---|---|---|
| target plan | $1.50M | 6.8% | -35% |
| balanced | $1.54M | 6.9% | -23% |
| momentum | $1.93M | 8.6% | -8% |
| 60/40 | $1.92M | 8.6% | -32% |
| 100% US stocks | $3.24M | 12.4% | -51% |

## Documents

| File | For |
|---|---|
| [INSTALL.md](INSTALL.md) | installing Python, the kit and Claude Code on Mac/Windows/Linux |
| [RUNBOOK.md](RUNBOOK.md) | what to do monthly, yearly and when things happen; troubleshooting |
| [STRATEGY.md](STRATEGY.md) | the investment methodology / IPS template, back-test, references, interview points |
| [CLAUDE.md](CLAUDE.md) | the rules Claude Code follows (the "committee charter") |
| `examples/` | a complete run: `plan.md`, `proposal_2026-10.md`, `memo_2026-10.md` (written by Claude), `backtest.md`, `dashboard.html` |

Licensed under the [Apache License 2.0](LICENSE): free to use, copy, modify and redistribute, including commercially.

*Educational project, not investment advice. Past and simulated performance do not guarantee future results.*
