#!/usr/bin/env bash
# macOS / Linux installer for the AI 401k kit.
#   ./install.sh                 install Python if needed, create .venv, install the kit, load prices, run tests
#   ./install.sh --offline       same, but use the bundled price snapshot instead of downloading
#   ./install.sh --with-claude   also install Claude Code (Anthropic's native installer) if it is missing
set -euo pipefail
cd "$(dirname "$0")"
OFFLINE=""; WITH_CLAUDE=""
for a in "$@"; do
  case "$a" in --offline) OFFLINE="--offline" ;; --with-claude) WITH_CLAUDE=1 ;; *) echo "unknown option $a" >&2; exit 2 ;; esac
done

say() { printf '\n==> %s\n' "$*"; }
SUDO=""; [[ $EUID -ne 0 ]] && command -v sudo >/dev/null && SUDO="sudo"

python_ok() { "$1" -c 'import sys, venv; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; }
find_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$c" >/dev/null && python_ok "$c"; then echo "$c"; return 0; fi
  done
  return 1
}
install_python() {
  say "Installing Python 3 with the system package manager (may ask for your password)"
  if command -v brew >/dev/null; then brew install python
  elif command -v apt-get >/dev/null; then $SUDO apt-get update -y && $SUDO apt-get install -y python3 python3-venv python3-pip
  elif command -v dnf >/dev/null; then $SUDO dnf install -y python3 python3-pip
  elif command -v pacman >/dev/null; then $SUDO pacman -Sy --noconfirm python python-pip
  elif command -v zypper >/dev/null; then $SUDO zypper install -y python3 python3-pip
  elif [[ "$(uname)" == "Darwin" ]]; then
    echo "Install Homebrew (https://brew.sh) or Python from https://www.python.org/downloads/ and rerun." >&2; exit 1
  else echo "No supported package manager. Install Python >= 3.10 from https://www.python.org and rerun." >&2; exit 1
  fi
}

PY="$(find_python || true)"
if [[ -z "$PY" ]]; then install_python; PY="$(find_python || true)"; fi
[[ -z "$PY" ]] && { echo "Python >= 3.10 is still not available." >&2; exit 1; }
say "Using $($PY --version) at $(command -v "$PY")"

if [[ ! -x .venv/bin/python ]]; then
  say "Creating a private Python environment in .venv"
  "$PY" -m venv .venv || { install_python; "$PY" -m venv --clear .venv; }   # Debian/Ubuntu ship venv separately
fi
say "Installing numpy, pandas, scipy, matplotlib, yfinance and the ai401k engine"
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -e ".[dev]" --quiet
chmod +x ai401k.sh

say "Loading prices"
./ai401k.sh data $OFFLINE

say "Running the tests"
.venv/bin/python -m pytest -q

if ! command -v claude >/dev/null; then
  if [[ -n "$WITH_CLAUDE" ]]; then
    say "Installing Claude Code"
    curl -fsSL https://claude.ai/install.sh | bash
  else
    say "Claude Code not found. Install it with:  curl -fsSL https://claude.ai/install.sh | bash   (see INSTALL.md)"
  fi
fi

./ai401k.sh doctor || true
cat <<'MSG'

Done. Next steps:
  claude                 start Claude Code in this folder, then type  /onboard
  ./ai401k.sh --help     the engine's commands, if you want to run them yourself
  RUNBOOK.md             what to do every month
MSG
