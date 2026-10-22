---
description: Monthly investment committee - refresh data, propose, research, challenge, memo, approval
argument-hint: "[YYYY-MM] (default: current month)"
---
Monthly rebalancing session for month `$ARGUMENTS` (if empty, use the current month). Follow
CLAUDE.md strictly. Target: under 15 minutes of the owner's time.

**Step 1 — Data and position**
- `./ai401k.sh doctor` then `./ai401k.sh data`. If the download fails, stop and tell the owner
  (do not trade on stale prices unless the owner explicitly accepts it).
- Live mode only: ask the owner for current balances from the 401k website and contributions
  received since the last session; run `./ai401k.sh sync --set ... --deposit ...`.
- `./ai401k.sh status`.
- If this month is already approved, say so and stop.

**Step 2 — Systematic proposal**
- `./ai401k.sh propose $ARGUMENTS` and read `portfolio/proposals/<M>.md`.

**Step 3 — Research and challenge (in parallel)** — launch both sub-agents in one message:
- `macro-analyst`: "Monthly brief for <M>. Current proposal: <final weights + tactical notes>."
- `risk-officer`: "Review portfolio/proposals/<M>.json for <M>."

**Step 4 — Discretionary decision**
- Default: no override. Consider one only if the macro brief rates evidence "meets bar" for a sleeve
  AND the risk officer did not flag it. Use
  `./ai401k.sh override --month <M> --set <SLEEVE>=<+/-x>,<SLEEVE>=<-/+x> --reason "<sourced reason>"`.
  If the engine rejects it, accept the rejection and record it in the memo.
- `./ai401k.sh validate --month <M>` must print PASS. If it fails, stop and report.

**Step 5 — Memo**
- Write `journal/<M>.md` using the template in CLAUDE.md. Numbers only from engine output or
  cited sources. Keep it to one page.

**Step 6 — Present and ask**
- Show the owner: 3-line summary, the orders table, the contribution election, and the question
  "Do you approve the <M> rebalance?" Do NOT approve on your own.

**Step 7 — After approval** (only if the owner says approve)
- `./ai401k.sh approve --month <M> --yes --by "<owner name>"`
- Live mode: give the owner a numbered click-list for the 401k website (contribution election %
  first, then any exchanges, sells before buys) and remind them to `sync` after settlement.
- `./ai401k.sh report`; update section 7 of the memo with the decision and timestamp.
- If the owner defers or rejects, record that in section 7 and stop.
