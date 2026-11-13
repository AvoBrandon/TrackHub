# Runs the backend as a Windows service on your tower, so it survives reboots and logouts.
# Prereqs: Python 3.12+ on PATH, and NSSM (https://nssm.cc) in PATH or next to this script.
# Run from an elevated PowerShell:  .\install-windows-service.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Push-Location $backend
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --quiet -e .
if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Write-Host "Created backend\.env - edit it, then re-run." }
Pop-Location
$py = Join-Path $backend ".venv\Scripts\python.exe"
nssm install Clawback $py "-m app"
nssm set Clawback AppDirectory $backend
nssm set Clawback AppStdout (Join-Path $backend "data\service.log")
nssm set Clawback AppStderr (Join-Path $backend "data\service.log")
nssm set Clawback Start SERVICE_AUTO_START
nssm start Clawback
Write-Host "Service 'Clawback' running on http://localhost:8787 - open http://localhost:8787/health to check."
