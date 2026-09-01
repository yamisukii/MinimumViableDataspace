# Brings up the whole AM2Scale dataspace POC in one go:
#   1. the Podman compose stacks (infra + one stack per company)
#   2. the Discovery service   (host process, own window, :5185)
#   3. the Dataspace Portal    (host process, own window, :5180)
#
# Idempotent - run it again after a reboot, all state lives in named volumes.
#
# Options:
#   -StacksOnly     only the containers, no host UIs
#   -WithOnboarding additionally open the onboarding UI (:5175)
param(
    [switch]$StacksOnly,
    [switch]$WithOnboarding
)

$ErrorActionPreference = "Stop"
$compose = Join-Path $PSScriptRoot "compose"

& (Join-Path $compose "start-dataspace.ps1")

if ($StacksOnly) {
    Write-Host ""
    Write-Host "Stacks only - skipping host services."
    return
}

function Test-Port($port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect("127.0.0.1", $port); $c.Close(); return $true
    } catch { return $false }
}

function Wait-Port($port, $seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $port) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Start-HostService($script, $title) {
    Write-Host "Starting $title in a new window..."
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $compose $script)
    ) | Out-Null
}

Write-Host ""
Start-HostService "start-discovery.ps1" "Discovery (:5185)"

# the portal calls discovery, and discovery loads its embedding model first,
# so wait for it to bind before starting the portal
Write-Host "Waiting for Discovery on :5185 (loads the embedding model) ..."
if (-not (Wait-Port 5185 120)) {
    Write-Warning "Discovery did not bind :5185 within 120s - check its window for errors."
}

Start-HostService "start-portal.ps1" "Portal (:5180)"
if (-not (Wait-Port 5180 60)) {
    Write-Warning "Portal did not bind :5180 within 60s - check its window for errors."
}
if ($WithOnboarding) {
    Start-HostService "start-onboarding.ps1" "Onboarding (:5175)"
    if (-not (Wait-Port 5175 60)) {
        Write-Warning "Onboarding did not bind :5175 within 60s - check its window for errors."
    }
}

Write-Host ""
Write-Host "Status:"
Write-Host "  Discovery  :5185  $(if (Test-Port 5185) {'up'} else {'DOWN'})"
Write-Host "  Portal     :5180  $(if (Test-Port 5180) {'up'} else {'DOWN'})"
if ($WithOnboarding) { Write-Host "  Onboarding :5175  $(if (Test-Port 5175) {'up'} else {'DOWN'})" }

Write-Host ""
Write-Host "Open the portal:  http://127.0.0.1:5180"
Write-Host "  Login: <firmenname> / password   (e.g. huber-ag)"
Write-Host ""
Write-Host "The host services run in their own windows - closing a window stops that"
Write-Host "service. If a window did not open (e.g. when run from a non-interactive"
Write-Host "shell), start them by hand:  compose\start-discovery.ps1, compose\start-portal.ps1"
Write-Host ""
Write-Host "The knowledge graph and its vectors persist in ui\discovery\kg.json, so search"
Write-Host "works right after a restart. Rebuild it only after changing the dataset:"
Write-Host "  python ui\discovery\import_dataset.py --all"
Write-Host "(Discovery's /health 'entries' counts portal-uploaded assets only - 0 is normal.)"
