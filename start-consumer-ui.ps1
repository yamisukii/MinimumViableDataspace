$ErrorActionPreference = "Stop"

Set-Location "C:\Users\SEM\Documents\AM2Scale\MinimumViableDataspace"

$port = 5173
Write-Host "Starting Consumer UI on http://127.0.0.1:$port"
Write-Host "Requires Traefik port-forward on port 80:"
Write-Host "kubectl port-forward svc/traefik 80:80 -n traefik"

python .\ui\consumer-ui\server.py $port
