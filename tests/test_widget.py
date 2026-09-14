"""Exercise pure widget functions without opening a desktop window."""

import base64
import json
import os
import subprocess
import unittest
from pathlib import Path

from launcher_config import render_wsl_launcher


@unittest.skipUnless(os.name == "nt", "requires Windows PowerShell")
class WidgetLogicTests(unittest.TestCase):
    def powershell(self, script):
        executable = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        result = subprocess.run(
            [str(executable), "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.decode("utf-8-sig").strip()

    def test_stale_timeout_matches_refresh_and_supports_old_snapshots(self):
        path = str(Path(__file__).resolve().parents[1] / "widget.ps1").replace("'", "''")
        result = self.powershell("""
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '""" + path + """', [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$fn = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Get-SnapshotStaleAfter'
}, $true)
. ([scriptblock]::Create($fn.Extent.Text))
@(
    Get-SnapshotStaleAfter ([pscustomobject]@{})
    foreach ($value in @(5, 60, 120, -1, 'bad', 'NaN', 'Infinity')) {
        Get-SnapshotStaleAfter ([pscustomobject]@{refresh_interval_seconds=$value})
    }
) | ConvertTo-Json -Compress
""")
        self.assertEqual(json.loads(result), [45, 45, 135, 255, 45, 45, 45, 45])

    def test_calibration_script_passes_arguments_without_shell_interpolation(self):
        directory = '/home/test/project\'s "quoted" $folder'
        encoded = render_wsl_launcher("__CALIBRATION_COMMAND__", "Ubuntu", "", "", directory)
        script = base64.b64decode(encoded).decode("utf-16le")
        result = self.powershell("""
function Start-Process {
    param($FilePath, $ArgumentList, [switch]$NoNewWindow, [switch]$Wait, [switch]$PassThru)
    $script:Captured = $ArgumentList
    [pscustomobject]@{ExitCode=0}
}
function Read-Host { param($Prompt) }
""" + script + "\n$script:Captured | ConvertTo-Json -Compress")
        self.assertEqual(json.loads(result), subprocess.list2cmdline([
            "--distribution", "Ubuntu", "--cd", directory,
            "--exec", "python3", "collector.py", "--calibrate",
        ]))
