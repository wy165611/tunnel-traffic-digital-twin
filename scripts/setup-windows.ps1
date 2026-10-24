$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$env:TWIN_DATA_DIR = Join-Path $Root 'data'
$NpmRegistry = if ($env:TWIN_NPM_REGISTRY) { $env:TWIN_NPM_REGISTRY } else { 'https://registry.npmjs.org' }
$PipArgs = @()
if ($env:TWIN_PIP_INDEX) {
    $PipArgs = @('--index-url', $env:TWIN_PIP_INDEX)
}

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Get-Command py.exe -ErrorAction SilentlyContinue)) {
    throw 'Python Launcher was not found. Install 64-bit Python 3.11 or newer from python.org, then reopen PowerShell.'
}
$pyInfo = (& py -3 -c "import sys,struct; print('%d.%d;%d' % (sys.version_info.major,sys.version_info.minor,struct.calcsize('P')*8))").Trim()
Assert-LastExitCode 'Checking Python'
$pyParts = $pyInfo.Split(';')
if ($pyParts.Count -ne 2 -or [Version]$pyParts[0] -lt [Version]'3.11' -or $pyParts[1] -ne '64') {
    throw "Python 3.11+ 64-bit is required; detected $pyInfo. Install a 64-bit Python and reopen PowerShell."
}

if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    throw 'Node.js was not found. Install Node.js 22.12+ or 24 LTS, then reopen PowerShell.'
}
$nodeText = (& node --version | Select-Object -First 1).Trim()
Assert-LastExitCode 'Checking Node.js'
$nodeVersion = [Version]$nodeText.TrimStart('v')
if (-not (($nodeVersion.Major -eq 20 -and $nodeVersion.Minor -ge 19) -or ($nodeVersion.Major -eq 22 -and $nodeVersion.Minor -ge 12) -or $nodeVersion.Major -gt 22)) {
    throw "Node.js 20.19+ or 22.12+ is required; detected $nodeText. Install a supported LTS version and reopen PowerShell."
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'npm.cmd was not found. Reinstall Node.js with npm, then reopen PowerShell.'
}
$python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host 'Creating the project Python environment...'
    & py -3 -m venv .venv
    Assert-LastExitCode 'Creating the Python environment'
}

& $python -m pip install --upgrade pip
Assert-LastExitCode 'Upgrading pip'

Write-Host 'Installing official CPU-only PyTorch packages...'
& $python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
Assert-LastExitCode 'Installing CPU-only PyTorch'

Write-Host 'Installing Python dependencies...'
& $python -m pip install -r requirements.txt @PipArgs
Assert-LastExitCode 'Installing Python dependencies'
& $python scripts\lock_dependencies.py --check
Assert-LastExitCode 'Checking installed dependencies'

Write-Host 'Downloading and verifying pretrained model weights...'
& $python scripts\download_models.py
Assert-LastExitCode 'Downloading model weights'
& $python scripts\prepare_demo.py --video (Join-Path $Root 'examples\tunnel-demo.mp4')
Assert-LastExitCode 'Preparing demo data'

Write-Host 'Installing frontend dependencies and building the web interface...'
Push-Location (Join-Path $Root 'frontend')
try {
    & npm.cmd ci --registry=$NpmRegistry
    Assert-LastExitCode 'Installing frontend dependencies'
    & npm.cmd run build
    Assert-LastExitCode 'Building the frontend'
} finally {
    Pop-Location
}

Write-Host ''
Write-Host 'Setup complete. Start the application with start-windows.bat.'
