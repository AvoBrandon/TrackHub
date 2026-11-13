# Runs the backend as a Windows service on your tower, so it survives reboots and logouts.
# Prereqs: Python 3.12+ on PATH, and NSSM (https://nssm.cc) in PATH or next to this script.
# Run from an elevated PowerShell:  .\install-windows-service.ps1
#   or, if nssm.exe is not on PATH:  .\install-windows-service.ps1 -Nssm "F:\path\to\nssm.exe"
param([string]$Nssm = "nssm")
$ErrorActionPreference = "Stop"
if (-not (Get-Command $Nssm -ErrorAction SilentlyContinue) -and -not (Test-Path $Nssm)) {
  throw "nssm not found. Pass -Nssm 'C:\full\path\nssm.exe'"
}
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Push-Location $backend
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --quiet -e .
if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Write-Host "Created backend\.env - edit it, then re-run." }
Pop-Location
$py = Join-Path $backend ".venv\Scripts\python.exe"
& $Nssm install Clawback $py "-m app"
& $Nssm set Clawback AppDirectory $backend
& $Nssm set Clawback AppStdout (Join-Path $backend "data\service.log")
& $Nssm set Clawback AppStderr (Join-Path $backend "data\service.log")
& $Nssm set Clawback Start SERVICE_AUTO_START
& $Nssm start Clawback
Write-Host "Service 'Clawback' running on http://localhost:8787 - open http://localhost:8787/health to check."
