# Build locally without installing packages into the user's Python environment.
[CmdletBinding()]
param([string]$BuildDirectory = '')

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).ProviderPath
$buildRoot = $BuildDirectory
if (-not $buildRoot) {
    $buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('claude-usage-bot-build-' + [guid]::NewGuid().ToString('N'))
}
$venv = Join-Path $buildRoot 'venv'
$dist = Join-Path $repo 'dist'
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    & python.exe -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated build environment.' }
}
& $python -m pip install --disable-pip-version-check pyinstaller==6.22.2
if ($LASTEXITCODE -ne 0) { throw 'Could not install the pinned packager.' }

Push-Location $repo
try {
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; no executable was built.' }
    & $python -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name ClaudeUsageBot --distpath $dist `
        --workpath (Join-Path $buildRoot 'work') --specpath $buildRoot `
        --add-data "${repo}\widget.ps1:." `
        --add-data "${repo}\config.example.json:." `
        (Join-Path $repo 'native_app.py')
    if ($LASTEXITCODE -ne 0) { throw 'Executable packaging failed.' }
    $exe = Join-Path $dist 'ClaudeUsageBot.exe'
    & $python (Join-Path $PSScriptRoot 'check-bundle.py') $exe
    if ($LASTEXITCODE -ne 0) { throw 'Bundled asset verification failed.' }
    $hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  ClaudeUsageBot.exe" | Set-Content -LiteralPath (Join-Path $dist 'SHA256SUMS.txt') -Encoding ASCII
    Write-Output "Built: $exe"
    Write-Output "SHA256: $hash"
    Write-Output "Temporary build environment: $buildRoot"
} finally {
    Pop-Location
}
