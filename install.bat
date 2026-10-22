@echo off
rem Double-click to install. Options: --offline (use bundled prices), --with-claude (also install Claude Code)
set ARGS=
:loop
if "%~1"=="" goto run
if /I "%~1"=="--offline" set ARGS=%ARGS% -Offline
if /I "%~1"=="--with-claude" set ARGS=%ARGS% -WithClaude
shift
goto loop
:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %ARGS%
pause
