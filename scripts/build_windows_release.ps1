param(
    [string]$OutputDirectory = 'artifacts\windows-release',
    [string]$PythonVersion = '3.11.9',
    [string]$NpmRegistry = $(if ($env:TWIN_NPM_REGISTRY) { $env:TWIN_NPM_REGISTRY } else { 'https://registry.npmjs.org' }),
    [string]$PipIndex = $env:TWIN_PIP_INDEX
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if ($env:OS -ne 'Windows_NT') {
    throw 'Windows release packages must be built on Windows so native dependencies target win_amd64.'
}
if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'A 64-bit Windows build host is required.'
}

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Copy-Tree([string]$Source, [string]$Destination, [string[]]$ExcludedDirectories = @()) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $RoboCopyArgs = @($Source, $Destination, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:2', '/W:1')
    if ($ExcludedDirectories.Count -gt 0) {
        $RoboCopyArgs += '/XD'
        $RoboCopyArgs += $ExcludedDirectories
    }
    & robocopy.exe @RoboCopyArgs
    if ($LASTEXITCODE -gt 7) {
        throw "Copying $Source failed with robocopy exit code $LASTEXITCODE."
    }
}

function New-Zip([string]$SourceDirectory, [string]$Destination) {
    if (Test-Path $Destination) {
        Remove-Item $Destination -Force
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $SourceDirectory,
        $Destination,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )
    $Size = (Get-Item $Destination).Length
    if ($Size -ge 2GB) {
        throw "$Destination is $Size bytes; every release asset must be smaller than 2 GB."
    }
}

Set-Location $Root
$Output = [System.IO.Path]::GetFullPath((Join-Path $Root $OutputDirectory))
$Work = Join-Path $Output 'work'
$Base = Join-Path $Work 'base'
$Portable = Join-Path $Work 'portable'
$Lite = Join-Path $Work 'lite'
$Runtime = Join-Path $Portable 'runtime'
$SitePackages = Join-Path $Runtime 'Lib\site-packages'
$PreviousDataDirectory = $env:TWIN_DATA_DIR

try {
    New-Item -ItemType Directory -Path $Output -Force | Out-Null
    if (Test-Path $Work) {
        Remove-Item $Work -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Base -Force | Out-Null

    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw 'Node.js and npm are required to build the frontend.'
    }
    Write-Host 'Installing frontend dependencies and building frontend/dist...'
    Push-Location (Join-Path $Root 'frontend')
    try {
        & npm.cmd ci --registry=$NpmRegistry
        Assert-LastExitCode 'Installing frontend dependencies'
        & npm.cmd run build
        Assert-LastExitCode 'Building the frontend'
    } finally {
        Pop-Location
    }

    Write-Host 'Assembling application sources...'
    Copy-Tree (Join-Path $Root 'backend') (Join-Path $Base 'backend') @('data', '__pycache__', '.pytest_cache')
    Copy-Tree (Join-Path $Root 'frontend') (Join-Path $Base 'frontend') @('node_modules', 'dist', '.vite')
    Copy-Tree (Join-Path $Root 'scripts') (Join-Path $Base 'scripts') @('__pycache__')
    Copy-Tree (Join-Path $Root 'examples') (Join-Path $Base 'examples')
    Copy-Tree (Join-Path $Root 'docs') (Join-Path $Base 'docs')
    Copy-Item (Join-Path $Root 'frontend\dist') (Join-Path $Base 'frontend\dist') -Recurse -Force
    foreach ($File in @(
        'config.yaml', 'models.json', 'requirements.txt', 'README.md', 'CHANGELOG.md',
        '一键启动.bat', 'start-windows.bat', '停止.bat'
    )) {
        Copy-Item (Join-Path $Root $File) (Join-Path $Base $File)
    }
    foreach ($Directory in @('videos', 'models', 'runs', 'calibrations')) {
        New-Item -ItemType Directory -Path (Join-Path $Base "data\$Directory") -Force | Out-Null
    }

    Copy-Tree $Base $Portable
    Copy-Tree $Base $Lite

    Write-Host "Downloading Python $PythonVersion embeddable runtime (x64)..."
    $Downloads = Join-Path $Work 'downloads'
    New-Item -ItemType Directory -Path $Downloads -Force | Out-Null
    $RuntimeZip = Join-Path $Downloads "python-$PythonVersion-embed-amd64.zip"
    $RuntimeUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
    Invoke-WebRequest -UseBasicParsing -Uri $RuntimeUrl -OutFile $RuntimeZip
    Expand-Archive -Path $RuntimeZip -DestinationPath $Runtime -Force

    $PathConfig = Get-ChildItem -Path $Runtime -Filter 'python*._pth' | Select-Object -First 1
    if (-not $PathConfig) {
        throw 'The embedded Python ._pth file was not found.'
    }
    $PathLines = [System.IO.File]::ReadAllLines($PathConfig.FullName)
    $PathLines = $PathLines | ForEach-Object { if ($_ -eq '#import site') { 'import site' } else { $_ } }
    foreach ($RequiredPath in @('Lib\site-packages', '..', 'import site')) {
        if ($PathLines -notcontains $RequiredPath) {
            $PathLines += $RequiredPath
        }
    }
    [System.IO.File]::WriteAllLines($PathConfig.FullName, $PathLines, [System.Text.UTF8Encoding]::new($false))
    New-Item -ItemType Directory -Path $SitePackages -Force | Out-Null

    Write-Host 'Bootstrapping pip in the embedded runtime...'
    $GetPip = Join-Path $Downloads 'get-pip.py'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/pip/get-pip.py' -OutFile $GetPip
    $PythonExe = Join-Path $Runtime 'python.exe'
    & $PythonExe $GetPip --no-warn-script-location
    Assert-LastExitCode 'Bootstrapping pip'

    Write-Host 'Installing CPU-only PyTorch and application dependencies into the embedded runtime...'
    $DependencyArgs = @('-m', 'pip', 'install', '--no-cache-dir', 'torch', 'torchvision', '-r', (Join-Path $Portable 'requirements.txt'), '--index-url', 'https://download.pytorch.org/whl/cpu', '--extra-index-url', 'https://pypi.org/simple')
    if ($PipIndex) {
        $DependencyArgs += @('--extra-index-url', $PipIndex)
    }
    & $PythonExe @DependencyArgs
    Assert-LastExitCode 'Installing application dependencies'

    $env:TWIN_DATA_DIR = Join-Path $Portable 'data'
    Push-Location $Portable
    try {
        Write-Host 'Downloading model weights and verifying models.json SHA-256 entries...'
        & $PythonExe scripts\download_models.py
        Assert-LastExitCode 'Downloading and verifying model weights'
        & $PythonExe scripts\prepare_demo.py --video (Join-Path $Portable 'examples\tunnel-demo.mp4')
        Assert-LastExitCode 'Preparing demo data'
        & $PythonExe scripts\lock_dependencies.py --check
        Assert-LastExitCode 'Checking installed dependency versions'
        & $PythonExe -c "import fastapi, uvicorn, cv2, torch, ultralytics; assert torch.__version__.endswith('+cpu'), torch.__version__"
        Assert-LastExitCode 'Validating the embedded runtime'
    } finally {
        Pop-Location
    }
    Copy-Tree (Join-Path $Portable 'data') (Join-Path $Lite 'data') @('models')
    $LiteModelFiles = @(Get-ChildItem -Path (Join-Path $Lite 'data\models') -Recurse -File -ErrorAction SilentlyContinue)
    if ($LiteModelFiles.Count -ne 0) {
        throw 'The lite package must not contain model weights.'
    }

    $PortableZip = Join-Path $Output 'TunnelTwin-Windows-x64-portable.zip'
    $LiteZip = Join-Path $Output 'TunnelTwin-Windows-x64-lite.zip'
    Write-Host 'Creating portable and lite release archives...'
    New-Zip $Portable $PortableZip
    New-Zip $Lite $LiteZip

    $ChecksumLines = @($PortableZip, $LiteZip) | ForEach-Object {
        $Item = Get-Item $_
        $Hash = (Get-FileHash -Algorithm SHA256 $Item.FullName).Hash.ToLowerInvariant()
        "$Hash  $($Item.Name)"
    }
    $ChecksumPath = Join-Path $Output 'SHA256SUMS.txt'
    [System.IO.File]::WriteAllLines($ChecksumPath, $ChecksumLines, [System.Text.UTF8Encoding]::new($false))

    Remove-Item $Work -Recurse -Force
    Write-Host ''
    Write-Host "Release assets created in $Output"
    Get-Item $PortableZip, $LiteZip, $ChecksumPath | Select-Object Name, Length
} finally {
    $env:TWIN_DATA_DIR = $PreviousDataDirectory
    Set-Location $Root
}
