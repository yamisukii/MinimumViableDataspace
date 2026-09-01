# Starts the Discovery service (host process, http://127.0.0.1:5185):
# knowledge-graph store + semantic vector search over the shared master data.
# The portal calls this service; start it before .\start-portal.ps1.
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

# offline-friendly HuggingFace cache (no symlink privilege needed on Windows)
$env:HF_HUB_DISABLE_SYMLINKS = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

$port = 5185
Write-Host "Starting Discovery service (vector search) on http://127.0.0.1:$port"
Write-Host "First start downloads the embedding model (~30 MB) once; afterwards fully offline."

python .\ui\discovery\server.py $port
