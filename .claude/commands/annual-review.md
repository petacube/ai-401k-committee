---
description: Yearly review - capital market assumptions, strategic re-plan, contribution raise, back-test, IPS
---
Annual review. Follow CLAUDE.md. Produce `journal/<YYYY>-annual-review.md`.

1. `./ai401k.sh data` and `./ai401k.sh status`. Summarise the year: start/end value, contributions,
   money-weighted gain (from `reports/backtest_metrics.json` is NOT the live record — use the ledger
   and status), months approved, overrides used and whether they helped.
2. **Capital market assumptions.** Launch `macro-analyst` with: "Annual CMA check: collect the latest
   published 10-year expected returns for US equity, international equity, US aggregate bonds, gold
   and cash from at least two of Vanguard, J.P. Morgan LTCMA, BlackRock, Research Affiliates. Return a
   table with source, date and number." Compare with `config/cma.yaml`. Propose changes of at most
   ±1.0 point per sleeve, each cited. Edit `config/cma.yaml` only after the owner approves
   (permission prompt), and update `as_of`.
3. **Life check** with the owner: new salary/contribution? employer match change? horizon or goal
   change? If yes, `./ai401k.sh init --force ...` with the new values (ledger and holdings are kept).
4. `./ai401k.sh plan` — compare the new strategic weights with last year's (`git diff` is not
   available; read the previous annual review memo). Explain any change: glide path, funded status,
   new assumptions.
5. `./ai401k.sh backtest --all` and `./ai401k.sh report`.
6. Ask the `risk-officer` sub-agent to review the guardrails and the year's overrides for drift from
   policy. Any guardrail change is the owner's job (Claude cannot edit that file); list suggestions.
7. Update `journal/IPS.md` if anything changed; get the owner's sign-off.
