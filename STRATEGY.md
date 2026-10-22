# Investment strategy: Goal-based core, rules-based tilts, AI-assisted judgement, human decision

This document is the methodology behind the kit and doubles as your **Investment Policy Statement (IPS)
template**. Every rule below is implemented in `ai401k/` and configured in `config/`, so you can point
an interviewer to the exact line that does what you claim.

---

## 1. Philosophy in one paragraph

Most of a long-horizon portfolio's outcome comes from its **strategic asset allocation** (Brinson, Hood
& Beebower 1986) and from **staying invested and contributing**, not from clever trades. So the core
of the strategy is a goal-driven strategic mix that changes slowly and predictably. Around it sit
**published, testable rules** (trend and momentum) that are allowed to tilt the mix within tight
bands. On top, **Claude acts as an investment committee assistant**: it runs the engine, researches
the macro backdrop, challenges the proposal through an independent risk officer, may add a small
documented override, and writes the memo. **The human approves every trade.** Code enforces the
limits, so neither the rules nor the AI can push the portfolio outside the policy.

```
           ┌──────────────────────── once a year ────────────────────────┐
 inputs →  │ 1. STRATEGIC   goal + horizon + wealth + capital-market        │ → strategic weights (SAA)
 (you)     │    ALLOCATION  assumptions → efficient frontier → Monte Carlo │
           └──────────────────────────────────────────────────────────────┘
           ┌──────────────────────── every month ────────────────────────┐
           │ 2. TACTICAL    10-month trend filter  or  dual momentum       │ → tilted weights (±15 pts max)
           │ 3. AI OVERLAY  macro-analyst + risk-officer sub-agents;       │ → final weights (±5 pts max)
           │                optional override with sourced reason          │
           │ 4. GUARDRAILS  bounds, equity glide cap, tilt band (code)     │ → validated weights
           │ 5. EXECUTION   new money first, 3-pt drift band, 40% turnover │ → orders + contribution %
           │ 6. HUMAN       reads memo, types "approve"                    │ → ledger, dashboard
           └──────────────────────────────────────────────────────────────┘
```

## 2. Universe: five sleeves, five low-cost index funds

| Sleeve | Trade ETF (fee) | History proxy for back-tests | Role |
|---|---|---|---|
| `US_EQ` US stocks | VTI (0.03%) | SPY | main growth engine |
| `INTL_EQ` international stocks | VXUS (0.05%) | EFA | diversification, cheaper valuations, non-USD exposure |
| `BONDS` US aggregate bonds | BND (0.03%) | AGG | income, deflation/recession hedge |
| `GOLD` gold | GLDM (0.10%) | GLD | crisis and inflation hedge, low correlation to both stocks and bonds (Erb & Harvey 2013) |
| `CASH` T-bills | SGOV (0.09%) | BIL, then the 13-week T-bill yield | dry powder, where the trend filter parks risk |

**401k reality check.** Many plans do not offer ETFs. Map each sleeve to the closest index fund on your
plan's menu in `config/universe.yaml` (any Yahoo Finance symbol works, e.g. FXAIX, FTIHX, FXNAX).
Gold is often unavailable in a 401k; set the gold bounds in `config/guardrails.yaml` to `[0, 0]` (and,
for the `momentum` goal, its own gold override in `config/profiles.yaml`) and the optimiser simply works
without it. Step-by-step: RUNBOOK.md §2a. Trades inside a 401k have no tax and usually no commission, which is
why monthly rebalancing is practical here and not in a taxable account.

## 3. Strategic allocation (SAA): from goal to weights

### 3.1 Inputs you give

| Input | Example | Where |
|---|---|---|
| Current balance | $100,000 | `portfolio/profile.yaml: initial_balance` |
| Annual contribution incl. employer match | $20,000, growing 3%/yr with raises | `annual_contribution`, `contribution_growth` |
| Horizon | 25 years | `horizon_years` |
| Goal | `$1,000,000` (target) or `max_wealth`, `conservative`, `balanced`, `aggressive`, `momentum` | `goal`, `target_amount` |
| Confidence (target goal) | 70% | `confidence` |

### 3.2 Capital market assumptions (CMA)

Forward-looking 10-year expected returns and volatilities per sleeve live in `config/cma.yaml` (US
equity 6.0%, international 7.0%, bonds 4.5%, gold 4.0%, cash 3.3%, inflation 2.5% as of Oct 2026). They
follow the building-block logic used by Vanguard, J.P. Morgan and Research Affiliates: equities =
dividend yield + real growth + inflation ± valuation change; bonds ≈ current yield. Correlations are
estimated from the last 15 years of monthly returns. **Why not historical average returns?** Because
starting valuations matter (high CAPE predicts lower 10-year US returns), and because 2006-2026 US
equity returns (≈11%/yr) are a poor forecast of the next 20 years (Ilmanen 2011).

### 3.3 Preset goals (`config/profiles.yaml`)

| Goal | US | Intl | Bonds | Gold | Cash | Tactical rule |
|---|---|---|---|---|---|---|
| conservative | 22% | 10% | 50% | 8% | 10% | trend filter, cut 50% |
| balanced | 38% | 20% | 32% | 6% | 4% | trend filter, cut 50% |
| aggressive | 55% | 28% | 10% | 5% | 2% | trend filter, cut 30% |
| max_wealth | 58% | 32% | 3% | 5% | 2% | none: stay invested, rebalance only |
| momentum | anchor = balanced | | | | | dual momentum (rotates fully) |
| target | **solved** (§3.4) | | | | | trend filter, cut 50% |

**Glide path.** In the last 10 years before the goal date the preset weights slide linearly toward
`conservative` (the target-date fund idea). Independently, `guardrails.yaml` caps total equity at
70% with < 7 years left and 45% with < 3 years left, for every goal.

### 3.4 The `target` goal: goal-based investing

1. **Real target.** "$1M" is interpreted in today's dollars by default and grown at the CMA inflation
   rate: $1M today = **$1.85M** nominal in 25 years. (Use `--nominal` to opt out.) Without this, a
   $1M nominal goal is so easy that the safest-looking answer is 60% cash, which quietly loses to
   inflation; we found exactly that in testing and fixed the specification.
2. **Efficient frontier.** 25 long-only minimum-variance portfolios under the policy bounds
   (Markowitz 1952), including a home-bias band: international = 20-45% of equity.
3. **Monte Carlo.** For each frontier portfolio, 5,000 paths of monthly returns with **fat tails**
   (Student-t, 5 degrees of freedom), monthly contributions growing with raises, fund fees deducted.
4. **Choice rule.** Among portfolios whose P(wealth ≥ target) ≥ confidence, choose the one with the
   **best 10th-percentile outcome** ("still reaches the goal, and hurts least if markets disappoint").
   This is a safety-first criterion in the spirit of Roy (1952) and Telser (1955) and of mental-account
   goal-based portfolios (Das, Markowitz, Scheid & Statman 2010). Alternatives (`min_vol`, `max_median`)
   are one setting away (`selection:` in the profile).
5. **Stretch goals.** If no portfolio reaches the confidence level, take the one with the highest
   probability and **solve for the contribution that would be needed**. This turns an unrealistic goal
   into an actionable conversation: save more, work longer, lower the target or accept lower confidence.
6. **Annual re-solve = automatic de-risking.** Each year the solver restarts from the actual balance. If
   markets were kind and you are ahead, it needs less risk and moves down the frontier; if you are
   behind, it tells you how far.

**Worked example ($100k, $20k/yr +3%, 25 years, $1M in today's dollars, 70% confidence, Oct 2026 CMA):**
the best achievable probability is 61% with 90% equities (50% US / 40% intl / 8% gold / 2% cash),
median outcome $2.14M nominal ≈ $1.16M real, bad-luck (10th pct) $1.12M nominal. Hitting 70% needs
about **$23,400/yr** of contributions. That single sentence is a better client conversation than any
allocation pie.

## 4. Tactical layer: published rules, bounded

| Rule | Used by | Logic | Evidence |
|---|---|---|---|
| **Trend filter** | conservative, balanced, aggressive, target | If a risky sleeve's month-end total-return index is below its 10-month average, move `trend_cut` (30-50%) of its strategic weight to cash until it recovers. | Faber (2007); Hurst, Ooi & Pedersen (2017): trend following cut drawdowns in most crises over a century |
| **Dual momentum** | momentum | Rank US, intl, bonds, gold by the average of 3/6/12-month returns. Weights 40/30/15/5% by rank + 10% cash; a sleeve whose momentum does not beat T-bills gives its slot to cash. | Antonacci (2014); Moskowitz, Ooi & Pedersen (2012) |
| **None** | max_wealth | strategic weights only | time in the market; trend filters cost return in V-shaped recoveries |

Signals use only **completed months** (no look-ahead). Except for the momentum goal, the final weight can
differ from strategic by at most ±15 points per sleeve.

## 5. AI layer: what Claude does and does not do

| Claude does | Claude does not |
|---|---|
| runs the engine and reads its output | compute weights or trades itself |
| sends the `macro-analyst` sub-agent to research rates, inflation, growth, valuations, catalysts, with dated sources | trade on headlines, recent performance or "feel" |
| sends the independent `risk-officer` sub-agent to challenge the proposal | edit guardrails, code, holdings or ledger (blocked in `.claude/settings.json`) |
| may propose an override: ±5 pts per sleeve, ≤10 pts total, nets to zero, ≥80-character sourced reason, expires after one month | approve: the `approve` command always triggers a permission prompt and the rules require the owner's explicit "approve" |
| writes the monthly memo and the lesson learned | give personalised investment advice |

The evidence bar for an override is deliberately high: *a specific, dated, verifiable catalyst that
price-based signals cannot see yet*. Most months the right answer is "no override", and the memo should
say why. Tracking override hit-rates in the annual review measures whether the AI layer adds value:
that track record is the most interesting thing you can show an employer.

## 6. Execution: how a 401k is actually rebalanced

1. **New money first.** Every month's contribution is directed to the most underweight sleeves
   (cash-flow rebalancing). Costless, and usually enough.
2. **Drift band.** Exchange existing balances only if some sleeve is more than **3 points** from target
   (Daryanani 2008; Jaconetti, Kinniry & Zilbering 2010 show bands beat calendar-only rebalancing).
3. **Turnover cap** of 40% of the account per month (momentum goal: none). Dust trades under $100 are skipped.
4. **Contribution election.** The engine prints the target as whole percentages that sum to 100 for
   the plan website's "future contributions" page.
5. **Frequent-trading policies.** Many plans block a round trip in the same fund within 30-90 days.
   Trend and momentum switches can trigger this; read your plan's rules and, if needed, use the
   `balanced`/`max_wealth` goals or widen `drift_band_abs`.

## 7. Back-test (walk-forward, Jan 2006 – Sep 2026, same deposits for all)

$100k initial, $20k/yr growing 3%, horizon 25 years (so the glide path engages near the end), fund fees
deducted, monthly decisions using only data available at the time.

| Strategy | Final value | Money-weighted IRR | Volatility | Max drawdown | Worst 12 months | Sharpe |
|---|---|---|---|---|---|---|
| target ($1M real) | $1.50M | 6.8% | 10.0% | -35.2% | -30.8% | 0.70 |
| max_wealth | $2.12M | 9.3% | 13.8% | -47.9% | -41.5% | 0.66 |
| conservative | $1.25M | 5.3% | 5.6% | -14.2% | -13.0% | 0.95 |
| balanced | $1.54M | 6.9% | 8.1% | -23.1% | -20.7% | 0.84 |
| aggressive | $1.94M | 8.7% | 11.2% | -36.2% | -30.7% | 0.75 |
| momentum | $1.93M | 8.6% | 7.9% | -7.9% | -6.4% | 1.07 |
| 60/40 US stocks/bonds | $1.92M | 8.6% | 9.9% | -32.2% | -27.5% | 0.83 |
| 100% US stocks | $3.24M | 12.4% | 15.5% | -50.9% | -43.4% | 0.75 |

Total contributed: $662k. Re-run with `./ai401k.sh backtest --all`; numbers change as data is added.

**How to read it honestly (interviewers will probe this):**
- 2006-2026 was an exceptional period for US large-cap stocks; anything diversified away from them
  (international, gold, bonds) lagged in *final wealth*. Do not extrapolate.
- The trend filter roughly halved the drawdown of the equivalent static mixes (balanced -23% vs 60/40 -32%)
  at the cost of return; in a lost decade for US stocks the ranking could flip.
- Dual momentum looks spectacular here (max drawdown -8%). It is in-sample on one path, has few
  independent decisions and is known to suffer whipsaws (e.g. 2011, 2015-16, 2022 bond losses).
- The `target` solver uses today's capital-market assumptions throughout, a mild look-ahead.
- Proxies (SPY, EFA, AGG, GLD, BIL) stand in for the trade ETFs before they existed.

## 8. Guardrails (hard limits, `config/guardrails.yaml`)

| Limit | Value |
|---|---|
| per-sleeve weight | US 0-70%, Intl 0-40%, Bonds 0-80%, Gold 0-15%, Cash 2-60% |
| total equity | 10-90%; ≤70% with < 7 years left; ≤45% with < 3 years left |
| international share of equity (optimiser) | 20-45% |
| tactical + AI tilt vs strategic | ±15 pts per sleeve |
| AI override | ±5 pts per sleeve, 10 pts total, nets to zero, written sourced reason |
| rebalancing | 3-pt drift band, $100 minimum trade, 40% max monthly turnover |

The momentum goal overrides some of these (gold up to 40%, cash up to 100%, no tilt band) because
rotation is the strategy. Only the human edits this file, outside a rebalancing session.

## 9. Interview talking points

1. *"I separated the deterministic engine from the AI. The LLM never does arithmetic; it does
   research, challenge and documentation, and code enforces the policy limits. That is how I would
   deploy AI on a real desk."*
2. *"I framed the goal in real terms and solved for the least-painful portfolio that reaches it; when
   the goal was out of reach, the model told me the contribution needed instead of just taking more risk."*
3. *"My back-test shows the cost of diversification in a US-dominated period, and I can explain why I
   still diversify."*
4. *"Every month has a memo, an independent risk review and an approval record; I can show you the
   override hit-rate of the AI layer."*

## 10. References

- Antonacci, G. (2014). *Dual Momentum Investing*. McGraw-Hill.
- Brinson, G., Hood, L. R. & Beebower, G. (1986). Determinants of portfolio performance. *Financial Analysts Journal* 42(4).
- Das, S., Markowitz, H., Scheid, J. & Statman, M. (2010). Portfolio optimization with mental accounts. *Journal of Financial and Quantitative Analysis* 45(2).
- Daryanani, G. (2008). Opportunistic rebalancing: a new paradigm for wealth managers. *Journal of Financial Planning* 21(1).
- Erb, C. & Harvey, C. (2013). The golden dilemma. *Financial Analysts Journal* 69(4).
- Faber, M. (2007). A quantitative approach to tactical asset allocation. *Journal of Wealth Management* 9(4).
- Hurst, B., Ooi, Y. H. & Pedersen, L. H. (2017). A century of evidence on trend-following investing. *Journal of Portfolio Management* 44(1).
- Ilmanen, A. (2011). *Expected Returns*. Wiley.
- Jaconetti, C., Kinniry, F. & Zilbering, Y. (2010). *Best practices for portfolio rebalancing*. Vanguard Research.
- Markowitz, H. (1952). Portfolio selection. *Journal of Finance* 7(1).
- Moskowitz, T., Ooi, Y. H. & Pedersen, L. H. (2012). Time series momentum. *Journal of Financial Economics* 104(2).
- Roy, A. D. (1952). Safety first and the holding of assets. *Econometrica* 20(3).
- Telser, L. (1955). Safety first and hedging. *Review of Economic Studies* 23(1).

*Educational project, not investment advice.*
