$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "SAGE Windows setup" -ForegroundColor Cyan
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & py -3 --version
    if ($LASTEXITCODE -ne 0) { throw "Python 3 was not found. Install Python 3.11 or newer and enable the Python Launcher." }
    & py -3 -m venv .venv
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw "Python was not found. Install Python 3.11 or newer from python.org and enable Add Python to PATH." }
    & python -m venv .venv
}
if ($LASTEXITCODE -ne 0) { throw "Could not create .venv." }

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements-windows.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

Write-Host "`nChecking Python syntax..." -ForegroundColor Cyan
& $venvPython -c "import ast,pathlib,sys; files=list(pathlib.Path('.').glob('*.py')); errors=[]; [(errors.append((str(p),str(e)))) for p in files for e in []]; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print(f'Syntax OK: {len(files)} top-level Python files')"
if ($LASTEXITCODE -ne 0) { throw "Python syntax check failed." }

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Important: SAGE's Windows inference uses llama-server, not MLX."
Write-Host "Start a compatible llama-server with your SAGE GGUF model on 127.0.0.1:8721 before running .\run_windows.ps1."
