#!/usr/bin/env bash
# Run the ai401k command from this folder's private Python environment (macOS, Linux, Git Bash on Windows).
#   ./ai401k.sh status      ./ai401k.sh propose      ./ai401k.sh --help
cd "$(dirname "$0")"
if [[ -x .venv/bin/python ]]; then PY=.venv/bin/python
elif [[ -x .venv/Scripts/python.exe ]]; then PY=.venv/Scripts/python.exe
else echo "Not installed yet: run ./install.sh (Windows: install.bat)" >&2; exit 1; fi
exec "$PY" -m ai401k "$@"
