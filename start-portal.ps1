$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$port = 5180
Write-Host "Starting Dataspace Portal on http://127.0.0.1:$port"
Write-Host "Requires the compose dataspace to be running (compose\start-dataspace.ps1)."
Write-Host "Login: <firmenname> / password"

python .\ui\portal\server.py $port
