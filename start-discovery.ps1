$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# offline-friendly HuggingFace cache (no symlink privilege needed on Windows)
$env:HF_HUB_DISABLE_SYMLINKS = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

$port = 5185
Write-Host "Starting Discovery service (vector search) on http://127.0.0.1:$port"
Write-Host "First start downloads the embedding model (~30 MB) once; afterwards fully offline."

python .\ui\discovery\server.py $port
