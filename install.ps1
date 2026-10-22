# Windows installer for the AI 401k kit.
#   Double-click install.bat, or from PowerShell:  .\install.ps1 [-Offline] [-WithClaude]
# Installs Python 3.12 (and Git, which Claude Code needs on Windows) with winget when missing,
# creates .venv, installs the engine, loads prices and runs the tests.
param([switch]$Offline, [switch]$WithClaude)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Say($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}
function Find-Python {
    $check = "import sys, venv; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
    foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
        $exe = $cand[0]; $pre = @($cand | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        if ((Get-Command $exe).Source -like "*WindowsApps*") { continue }   # Microsoft Store alias
        try { & $exe @pre -c $check 2>&1 | Out-Null } catch { continue }
        if ($LASTEXITCODE -eq 0) { return (@($exe) + $pre) }
    }
}

$haveWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
$py = @(Find-Python)
if ($py.Count -eq 0) {
    if (-not $haveWinget) { Write-Error "Python >= 3.10 not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and rerun." }
    Say "Installing Python 3.12 with winget"
    winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
    Refresh-Path
    $py = @(Find-Python)
    if ($py.Count -eq 0) { Write-Error "Python was installed but is not on PATH yet. Close this window, open a new one and rerun install.bat." }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue) -and $haveWinget) {
    Say "Installing Git for Windows (Claude Code uses its Git Bash shell)"
    winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
    Refresh-Path
}
$exe = $py[0]; $pre = @($py | Select-Object -Skip 1)
Say ("Using " + (& $exe @pre --version))

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Say "Creating a private Python environment in .venv"
    & $exe @pre -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Error "could not create the virtual environment" }
}
Say "Installing numpy, pandas, scipy, matplotlib, yfinance and the ai401k engine"
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -e ".[dev]" --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed" }

Say "Loading prices"
if ($Offline) { & $venvPy -m ai401k data --offline } else { & $venvPy -m ai401k data }

Say "Running the tests"
& $venvPy -m pytest -q

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    if ($WithClaude) {
        Say "Installing Claude Code"
        Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
        Refresh-Path
    } else {
        Say "Claude Code not found. Install it in PowerShell with:  irm https://claude.ai/install.ps1 | iex   (see INSTALL.md)"
    }
}
& $venvPy -m ai401k doctor

Write-Host @"

Done. Next steps (from this folder):
  claude              start Claude Code here, then type  /onboard
  ai401k --help       the engine's commands, if you want to run them yourself
  RUNBOOK.md          what to do every month
"@
