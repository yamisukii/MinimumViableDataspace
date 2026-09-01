# Starts the multi-tenant Dataspace Portal (host process, http://127.0.0.1:5180).
# Requires: .\start-dataspace.ps1 (EDC + Keycloak) and .\start-discovery.ps1 (search).
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

$port = 5180
Write-Host "Starting Dataspace Portal on http://127.0.0.1:$port"
Write-Host "Login: <firmenname> / password  (Keycloak realm 'mvd')"

python .\ui\portal\server.py $port
