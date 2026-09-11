# Run the collector and widget directly on Windows without WSL.
[CmdletBinding()]
param(
    [switch]$CollectorOnly
)

$ErrorActionPreference = 'Stop'
trap {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        $_.Exception.Message, 'Claude Usage Bot', 'OK', 'Error'
    ) | Out-Null
    exit 1
}

$python = Get-Command 'pythonw.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) {
    $python = Get-Command 'python.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $python) {
    throw 'Python 3 was not found. Install it from python.org and enable "Add Python to PATH".'
}

if ($CollectorOnly) {
    $entryPath = Join-Path $PSScriptRoot 'collector.py'
    $arguments = '"{0}" --loop' -f $entryPath
} else {
    # Use the same host as the executable: it resolves configuration paths,
    # owns the writer lock, and keeps the collector alive with its widget.
    $entryPath = Join-Path $PSScriptRoot 'native_app.py'
    $arguments = '"{0}"' -f $entryPath
}

$hostProcess = Start-Process -FilePath $python.Source -ArgumentList $arguments `
    -WindowStyle Hidden -PassThru
try {
    $hostProcess.WaitForExit()
    exit $hostProcess.ExitCode
} finally {
    if (-not $hostProcess.HasExited) {
        Stop-Process -Id $hostProcess.Id -Force
    }
}
