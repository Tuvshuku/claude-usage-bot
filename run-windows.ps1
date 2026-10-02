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

$pythonPath = $null
foreach ($name in @('py.exe', 'python.exe')) {
    foreach ($candidate in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
        # Store aliases can open the Store instead of running Python. The
        # Python launcher also finds installs that were not added to PATH.
        if ($candidate.Source -like '*\Microsoft\WindowsApps\*') { continue }
        $probeArgs = @('-c', 'import sys; print(sys.executable) if sys.version_info >= (3, 10) else sys.exit(1)')
        if ($name -eq 'py.exe') { $probeArgs = @('-3') + $probeArgs }
        try {
            $resolved = & $candidate.Source @probeArgs 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved -and (Test-Path -LiteralPath "$resolved")) {
                $pythonPath = "$resolved"
                break
            }
        } catch { continue }
    }
    if ($pythonPath) { break }
}
if (-not $pythonPath) {
    throw 'Source mode needs Python 3.10 or newer. Install it from python.org, or download ClaudeUsageBot.exe from https://github.com/Tuvshuku/claude-usage-bot/releases/latest (no Python needed).'
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

$hostProcess = Start-Process -FilePath $pythonPath -ArgumentList $arguments `
    -WindowStyle Hidden -PassThru
try {
    $hostProcess.WaitForExit()
    exit $hostProcess.ExitCode
} finally {
    if (-not $hostProcess.HasExited) {
        Stop-Process -Id $hostProcess.Id -Force
    }
}
