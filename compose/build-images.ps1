# Builds the two locally-customised EDC images that the company stacks use:
#   mvd-controlplane-local  (incl. IdentityClaimMapperExtension -> ctx.agent.claims.identity)
#   mvd-dataplane-local     (incl. KeySeedExtension -> writes the dataplane keypair into Vault)
#
# IdentityHub and IssuerService are pulled from ghcr.io and need no local build.
#
# Only required once, and again whenever the Java sources under launchers/ or
# extensions/ change. Run before the first .\start-dataspace.ps1.
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

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

Write-Host ""
Write-Host "Building EDC launcher fat jars..."
.\gradlew.bat :launchers:controlplane:shadowJar :launchers:dataplane:shadowJar

Write-Host ""
Write-Host "Building controlplane image..."
podman build `
    -t mvd-controlplane-local:latest `
    -f .\launchers\controlplane\src\main\docker\Dockerfile `
    --build-arg JAR=launchers/controlplane/build/libs/controlplane.jar `
    .

Write-Host ""
Write-Host "Building dataplane image..."
podman build `
    -t mvd-dataplane-local:latest `
    -f .\launchers\dataplane\src\main\docker\Dockerfile `
    --build-arg JAR=launchers/dataplane/build/libs/dataplane.jar `
    .

Write-Host ""
Write-Host "Building UI image (documentation + discovery in one container)..."
podman build -t am2scale-ui:latest -f .\ui\Dockerfile .

Write-Host ""
Write-Host "Images built:"
podman images --filter "reference=localhost/mvd-*-local" --format "table {{.Repository}}\t{{.Tag}}\t{{.Created}}"
podman images --filter "reference=localhost/am2scale-ui" --format "table {{.Repository}}\t{{.Tag}}\t{{.Created}}"

Write-Host ""
Write-Host "Next: .\start-dataspace.ps1  (running stacks need a recreate to pick up new images:"
Write-Host "      podman compose -p mvd-<name> --env-file companies\<name>\.env -f company\docker-compose.yml up -d --force-recreate cp-<name> dp-<name>)"
