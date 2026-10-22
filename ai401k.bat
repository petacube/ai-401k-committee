@echo off
rem Run the ai401k command from this folder's private Python environment (Windows Command Prompt / PowerShell).
rem   ai401k status      ai401k propose      ai401k --help
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Not installed yet: double-click install.bat first.
  exit /b 1
)
".venv\Scripts\python.exe" -m ai401k %*
