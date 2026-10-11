param(
    [int]$SidecarPort = 8722,
    [int]$LlamaServerPort = 8721
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "SAGE environment not found. Run .\setup_windows.ps1 first."
    exit 1
}

$base = "http://127.0.0.1:$LlamaServerPort"
try {
    $null = Invoke-RestMethod -Uri "$base/v1/models" -TimeoutSec 3
} catch {
    Write-Error @"
Could not reach llama-server at $base/v1/models.
Start llama-server with a compatible SAGE GGUF model first.
The Python sidecar does not download or load GGUF models by itself.
"@
    exit 1
}

Write-Host "Starting SAGE sidecar on http://127.0.0.1:$SidecarPort" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop."
& $python (Join-Path $PSScriptRoot "sage_router_server.py") $SidecarPort $LlamaServerPort
exit $LASTEXITCODE
