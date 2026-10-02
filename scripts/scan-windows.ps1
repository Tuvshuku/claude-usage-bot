# Fail the release when Microsoft Defender detects a threat or cannot scan it.
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Path)

$ErrorActionPreference = 'Stop'
$scanner = Join-Path $env:ProgramFiles 'Windows Defender\MpCmdRun.exe'
if (-not (Test-Path -LiteralPath $scanner)) {
    throw 'Microsoft Defender scanner is unavailable; this package has not been cleared for release.'
}
$target = (Resolve-Path -LiteralPath $Path).ProviderPath
# DisableRemediation applies only to this scan: a detection must fail the build,
# rather than remove a dependency and report a successful remediation. It does
# not change real-time protection or add an exclusion.
& $scanner -Scan -ScanType 3 -File $target -DisableRemediation
if ($LASTEXITCODE -ne 0) {
    throw "Microsoft Defender did not clear the package (exit $LASTEXITCODE)."
}
Write-Output 'Microsoft Defender scan passed.'
