# Starts the whole dataspace (infra stack + all generated company stacks).
# Idempotent: running it again just brings everything up to date - all state
# (Postgres, Vault, Keycloak) is persisted in named volumes and survives restarts.
$ErrorActionPreference = "Stop"

$composeRoot = $PSScriptRoot

function Assert-PodmanMachine {
    $name = "podman-machine-default"
    $state = podman machine inspect $name --format "{{.State}}" 2>$null
    if ($state -eq "running") { return }

    Write-Host "Starting Podman machine '$name'..."
    podman machine start $name
    $code = $LASTEXITCODE

    $state = podman machine inspect $name --format "{{.State}}" 2>$null
    if ($state -eq "running") { return }

    Write-Host ""
    Write-Error @"
Podman machine '$name' could not be started (exit $code, state '$state').
Nothing else will work until it runs, so stopping here.

If the error above mentions WSL and code 0x80070569
("Anmeldung fehlgeschlagen / logon type not granted"), WSL itself cannot create
its VM - verify with:  wsl -d $name -- echo ok
That is a machine policy problem, not a problem with this repo: the account
'NT VIRTUAL MACHINE\Virtual Machines' needs the "Log on as a service" right.
Fixing it needs administrator rights (secpol.msc -> Local Policies ->
User Rights Assignment -> Log on as a service), so it is one for IT.
"@
}

Assert-PodmanMachine

Write-Host "Ensuring 'dataspace' network exists..."
podman network exists dataspace 2>$null
if ($LASTEXITCODE -ne 0) {
    podman network create dataspace | Out-Null
    Write-Host "  network created."
}

Write-Host ""
Write-Host "Starting infra stack (Traefik, Postgres, Keycloak, Vault, IssuerService)..."
podman compose -p mvd-infra -f (Join-Path $composeRoot "infra\docker-compose.yml") up -d

$companies = Get-ChildItem -Path (Join-Path $composeRoot "companies") -Directory -ErrorAction SilentlyContinue
if (-not $companies) {
    Write-Host ""
    Write-Host "No companies found. Create one with: .\new-company.ps1 -Name <name>"
} else {
    foreach ($c in $companies) {
        $envFile = Join-Path $c.FullName ".env"
        if (Test-Path $envFile) {
            Write-Host ""
            Write-Host "Starting company stack '$($c.Name)'..."
            podman compose -p "mvd-$($c.Name)" --env-file $envFile -f (Join-Path $composeRoot "company\docker-compose.yml") up -d
        }
    }
}

Write-Host ""
Write-Host "Container status:"
podman ps --format "table {{.Names}}\t{{.Status}}"

Write-Host ""
Write-Host "Dataspace is starting. Seed containers run in the background;"
Write-Host "check their progress with e.g.:  podman logs -f seed-identity-provider"
Write-Host ""
Write-Host "Endpoints (via Traefik on port 80, no port-forward needed):"
Write-Host "  Keycloak:  http://keycloak.localhost"
Write-Host "  Issuer:    http://issuer.localhost"
Write-Host "  Company:   http://cp.<name>.localhost/api/mgmt  (X-Api-Key: password)"
