---
description: First session - interview the owner, create the investor profile, build the strategic plan and the first allocation
---
You are starting a new 401k engagement. Follow CLAUDE.md. Work through these steps in order and keep
the owner informed with one short line per step.

1. **Health check.** Run `./ai401k.sh doctor`. If data is missing or stale run `./ai401k.sh data`
   (fall back to `./ai401k.sh data --offline` if the download fails, and say so).

2. **Interview** (use the AskUserQuestion tool where it helps; accept the owner's numbers as given):
   - name; current 401k balance (default $100,000); annual contribution INCLUDING employer match
     (default $20,000) and expected yearly raise (default 3%); years until the money is needed
     (default 25)
   - goal, one of: a dollar target (e.g. $1,000,000 — ask whether in today's dollars, the default,
     or future dollars), `max_wealth`, `conservative`, `balanced`, `aggressive`, `momentum`.
     Explain each in one line using config/profiles.yaml descriptions.
   - for a dollar target: confidence level (default 70%)
   - mode: `paper` (simulate with ETFs, default) or `live` (real 401k; then ask for the plan's fund
     menu and map each sleeve to the closest index fund in config/universe.yaml — editing that file
     requires the owner's permission)
   - two risk-tolerance checks: "If your 401k fell 30% in a year, would you sell, hold or buy?" and
     "Which matters more: hitting the goal or avoiding a big loss?" If the answers clash with the
     chosen goal (e.g. "sell" + aggressive), point it out and let the owner decide.

3. **Create the profile:**
   `./ai401k.sh init --name "<name>" --initial <x> --contribution <x> --growth <g> --years <n> --goal <goal> [--target <x>] [--nominal] [--confidence <c>] --mode <paper|live>`
   (Claude Code will ask permission.) For live mode, next run
   `./ai401k.sh sync --set US_EQ=..,INTL_EQ=..,BONDS=..,GOLD=..,CASH=..` with today's balances.

4. **Strategic plan:** `./ai401k.sh plan`. Explain in plain English: the strategic weights, expected
   return and volatility, the median / bad-luck (10th pct) outcome in today's dollars, and the
   probability of the goal. If the status is "stretch", show the contribution needed and the options
   (save more, work longer, lower the target, accept lower confidence).

5. **Evidence:** `./ai401k.sh backtest --all` (takes a few minutes). Summarise in 4-5 bullets how the
   chosen strategy compares with the other goals and with 60/40 and 100% US stocks on IRR, max
   drawdown and worst 12 months. State the back-test caveats from STRATEGY.md §7.

6. **First allocation:** run the full `/rebalance` procedure for the current month (the deposit is the
   initial balance in paper mode). Write `journal/<YYYY-MM>.md` and the IPS summary
   `journal/IPS.md` (one page: objective, constraints, strategic weights, rebalancing rules,
   guardrails, review schedule — derived from the files, not invented).

7. Ask for approval. Only after the owner types "approve": `./ai401k.sh approve --yes --by "<name>"`,
   then `./ai401k.sh report` and tell the owner to open `reports/dashboard.html`.

Finish with the date of the next monthly session (first business day of next month) and remind the
owner that `/rebalance` is the command to type.
