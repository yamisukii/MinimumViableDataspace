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

# Discovery and Docs run as one container (stack mvd-ui), brought up by
# start-dataspace.ps1. Only the portal is still a host process.
Write-Host ""
Write-Host "Waiting for Discovery on :5185 (container loads the embedding model) ..."
if (-not (Wait-Port 5185 150)) {
    Write-Warning "Discovery did not bind :5185 - check:  podman logs am2scale-ui"
}
if (-not (Wait-Port 5190 30)) {
    Write-Warning "Docs did not bind :5190 - check:  podman logs am2scale-ui"
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
Write-Host "  Discovery  :5185  $(if (Test-Port 5185) {'up'} else {'DOWN'})   (container am2scale-ui)"
Write-Host "  Docs       :5190  $(if (Test-Port 5190) {'up'} else {'DOWN'})   (container am2scale-ui)"
Write-Host "  Portal     :5180  $(if (Test-Port 5180) {'up'} else {'DOWN'})   (host process)"
if ($WithOnboarding) { Write-Host "  Onboarding :5175  $(if (Test-Port 5175) {'up'} else {'DOWN'})" }

Write-Host ""
Write-Host "Open the portal:  http://127.0.0.1:5180"
Write-Host "  Login: <firmenname> / password   (e.g. fha-wien)"
Write-Host "Documentation:    http://docs.localhost  (or http://127.0.0.1:5190)"
Write-Host ""
Write-Host "Docs and Discovery live in the container am2scale-ui and keep running on"
Write-Host "their own. The portal is still a window - closing it stops the portal. If"
Write-Host "it did not open (e.g. from a non-interactive shell): compose\start-portal.ps1"
Write-Host "For local work without containers there are still compose\start-docs.ps1 and"
Write-Host "compose\start-discovery.ps1 - stop the container first, the ports collide."
Write-Host ""
Write-Host "The knowledge graph persists in the volume mvd-ui_ui-data, so search works"
Write-Host "right after a restart. Rebuild it only after changing the dataset:"
Write-Host "  python ui\discovery\import_dataset.py --all"
Write-Host "(Discovery's /health 'entries' counts portal-uploaded assets only - 0 is normal.)"
