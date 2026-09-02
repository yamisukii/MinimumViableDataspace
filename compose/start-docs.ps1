# Starts the documentation service (host process, http://127.0.0.1:5190).
# Serves the user handbook plus every technical note in the repository, and
# exposes them over its own API (/api/docs, /api/search, /api/health).
# Independent of the dataspace - the docs stay readable even when nothing runs.
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

$port = 5190
Write-Host "Starting documentation service on http://127.0.0.1:$port"
Write-Host "Markdown is the source: edit ui\docs\content\*.md or docs\*.md and reload."

python .\ui\docs\server.py $port
