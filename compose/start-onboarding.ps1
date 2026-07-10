# Starts the onboarding / registry service (web UI on http://127.0.0.1:5175).
# Requires the infra stack to be running (start-dataspace.ps1).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$port = 5175
Write-Host "Starting onboarding service on http://127.0.0.1:$port"
python .\onboarding\server.py $port
