# Installation guide (no programming experience needed)

Total time: about 15 minutes. You need a Mac, Windows or Linux computer, an internet connection and
about 700 MB of free disk space.

You'll install three things:

| What | Why | How |
|---|---|---|
| Python 3.10+ and the kit's libraries | the calculation engine | the kit's installer does it for you |
| Claude Code | the AI assistant that runs the process | one command (step 3) |
| A Claude account | Claude Code needs it to sign in | Claude Pro or Max subscription, or an Anthropic Console account with API credits |

---

## Step 1: Get the folder

Copy the `student2` folder anywhere you like, e.g. `Documents/student2`. If you received a zip,
unzip it first. (If you use git: `git clone <repo>` and `cd <repo>/student2`.)

## Step 2: Run the installer

**macOS**
1. Open *Terminal* (press ⌘-Space, type "Terminal", press Enter).
2. Type `cd ` (with a space), drag the `student2` folder into the Terminal window, press Enter.
3. Type `./install.sh` and press Enter.
   - If Python is missing it uses Homebrew. Without Homebrew, install Python from
     https://www.python.org/downloads/ first and run `./install.sh` again.

**Windows**
1. Open the `student2` folder in File Explorer.
2. Double-click **`install.bat`**. If Windows SmartScreen warns you, click *More info → Run anyway*.
   - It installs Python 3.12 and Git for Windows with `winget` if they're missing (Claude Code needs
     Git's "Git Bash" shell on Windows). If it says Python isn't on PATH yet, close the window and
     double-click `install.bat` again.

**Linux**: `cd student2 && ./install.sh` (uses apt, dnf, pacman or zypper if Python is missing).

The installer:
1. finds or installs Python ≥ 3.10;
2. creates a private environment in `student2/.venv` (nothing is installed system-wide);
3. installs numpy, pandas, scipy, matplotlib, yfinance and the `ai401k` engine;
4. downloads 25 years of prices for the ETFs (or uses the bundled snapshot with `--offline`);
5. runs the 13 automated tests: you should see `13 passed`;
6. runs `ai401k doctor`, a health check.

Options: `./install.sh --offline` (no download, uses `data/prices_snapshot.csv`),
`./install.sh --with-claude` (also installs Claude Code). On Windows: `install.bat --offline --with-claude`.

## Step 3: Install Claude Code

Skip this if `claude --version` already prints a version.

| System | Command (paste into the terminal) |
|---|---|
| macOS / Linux | `curl -fsSL https://claude.ai/install.sh \| bash` |
| Windows (PowerShell) | `irm https://claude.ai/install.ps1 \| iex` |
| Alternative (any system with Node.js 18+) | `npm install -g @anthropic-ai/claude-code` |

Then **open a new terminal window** and check: `claude --version`.
Official documentation: https://docs.claude.com/en/docs/claude-code/setup

## Step 4: Sign in and start

```bash
cd path/to/student2
claude
```

The first time, Claude Code opens a browser to sign in with your Claude account (or asks for an
Anthropic Console login). Then:

1. Claude Code asks whether you trust this folder. Answer **Yes**: that loads `CLAUDE.md` (the
   committee rules), `.claude/commands/` (the slash commands) and `.claude/settings.json`
   (what Claude may and may not do). **This matters:** until the folder is trusted, Claude Code
   ignores the settings' allow-list, so every engine command needs a manual permission click (and
   in non-interactive runs, e.g. `claude -p`, they are refused). Always start `claude` from inside
   `student2`, or the folder's settings and commands aren't found at all.
2. Type **`/onboard`** and answer the questions.

## Step 5: Verify (optional)

```bash
./ai401k.sh doctor        # every line [ok] except "investor profile" before onboarding
./ai401k.sh --help        # list of engine commands
```

Inside Claude Code, type `/` to see `/onboard`, `/rebalance`, `/status`, `/annual-review`, `/explain`,
and `/agents` to see `macro-analyst` and `risk-officer`.

## What's in the folder

```
student2/
├── README.md  INSTALL.md  RUNBOOK.md  STRATEGY.md     documentation
├── CLAUDE.md                     the committee rules Claude Code follows
├── .claude/
│   ├── settings.json             permissions: allowed / ask-first / forbidden actions
│   ├── commands/                 /onboard /rebalance /status /annual-review /explain
│   └── agents/                   macro-analyst (web research), risk-officer (independent check)
├── config/
│   ├── universe.yaml             which fund represents each sleeve (edit for your plan's menu)
│   ├── profiles.yaml             goals → strategic weights and tactical rules
│   ├── cma.yaml                  expected returns / volatilities (reviewed yearly)
│   └── guardrails.yaml           hard limits (only you edit this)
├── ai401k/                       the Python engine (data, plan, tactical, guardrails, rebalance, backtest, report)
├── tests/                        automated tests
├── data/prices_snapshot.csv      bundled prices (offline use)
├── portfolio/                    YOUR records: profile, strategic weights, holdings, ledger, proposals
├── journal/                      monthly memos, IPS, annual reviews (written by Claude, approved by you)
├── reports/                      plan.md, backtest.md, dashboard.html
├── examples/                     a complete worked example ($100k, $20k/yr, 25 years, $1M goal)
├── install.sh / install.bat / install.ps1
└── ai401k.sh / ai401k.bat        run an engine command
```

## Updating and uninstalling

- **Update prices**: `./ai401k.sh data` (Claude does this every month).
- **Update the kit**: replace the files but **keep** `portfolio/`, `journal/` and your edited `config/`
  files, then run the installer again.
- **Uninstall**: delete the `student2` folder. Nothing was installed outside it apart from Python,
  Git (Windows) and Claude Code.

## Privacy

Your balances stay on your computer in `portfolio/`. During a session Claude Code sends the content it
reads (proposals, memos) to Anthropic to generate replies, and the `macro-analyst` agent performs web
searches. Don't type account numbers or passwords into Claude; the kit never needs them.
