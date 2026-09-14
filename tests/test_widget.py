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
    def widget_functions(self, *names):
        path = str(Path(__file__).resolve().parents[1] / "widget.ps1").replace("'", "''")
        wanted = ",".join(f"'{name}'" for name in names)
        return """
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '""" + path + """', [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
foreach ($name in @(""" + wanted + """)) {
    $fn = $ast.Find({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq $name
    }, $true)
    . ([scriptblock]::Create($fn.Extent.Text))
}
"""

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

    def test_movement_delta_and_long_walk_targets(self):
        result = self.powershell(self.widget_functions("Get-MotionDelta", "Get-WalkTarget") + """
@{
    deltas = @(Get-MotionDelta -1; Get-MotionDelta 0.016; Get-MotionDelta 4)
    targets = @(
        Get-WalkTarget 500 4 1000 1 400
        Get-WalkTarget 980 4 1000 1 400
        Get-WalkTarget 20 4 1000 -1 400
        Get-WalkTarget -980 -1000 -4 -1 400
        Get-WalkTarget 50 4 100 1 400
        Get-WalkTarget 4 4 4 1 400
    )
} | ConvertTo-Json -Compress
""")
        values = json.loads(result)
        self.assertEqual(values["deltas"], [0, 0.016, 0.05])
        self.assertEqual(values["targets"], [900, 580, 420, -580, 100, 4])

    def test_walk_speed_is_frame_rate_independent_and_stops_at_target(self):
        result = self.powershell(self.widget_functions(
            "Step-Motion", "Reset-Pose", "Test-IsDormant", "Set-WalkPose"
        ) + """
function Get-CurrentWorkArea { [pscustomobject]@{Left=0; Right=2000} }
function Sync-EyesToMood {}
$ui = @{}
foreach ($name in @('BotTilt','BotHop','LegT0','LegT1','LegT2','LegT3',
                    'ArmLT','ArmRT','ShadeScale','Shade','BotFlip')) {
    $ui[$name] = [pscustomobject]@{X=0.0;Y=0.0;Angle=0.0;ScaleX=1.0;ScaleY=1.0;Opacity=1.0}
}
$window = [pscustomobject]@{Left=100.0;ActualWidth=136.0}
$script:Dragging=$false; $script:Open=$false; $script:Wander=$true
$script:Mood='happy'; $script:Dir=1; $script:LastHop=0
$distances = foreach ($fps in @(20,30,60)) {
    $window.Left=100.0; $script:State='walk'; $script:Tick=0.0
    $script:WalkDistance=0.0
    $script:NextAt=9999; $script:TargetX=1000.0
    for ($i=0; $i -lt $fps; $i++) { Step-Motion (1.0/$fps) }
    $window.Left - 100.0
}
$script:TargetX=$window.Left + 0.5
Step-Motion 0.05
$atTarget = ($window.Left -eq $script:TargetX -and $script:State -eq 'idle')
$script:State='walk'; $script:Mood='sleep'; $before=$window.Left
Step-Motion 0.016
$sleepStops = ($window.Left -eq $before -and $script:State -eq 'idle')
$script:Mood='happy'; $script:Open=$true; $script:State='walk'
Step-Motion 0.016
$dashboardStops = ($window.Left -eq $before -and $script:State -eq 'idle')
@{distances=@($distances);atTarget=$atTarget;sleepStops=$sleepStops;
  dashboardStops=$dashboardStops} | ConvertTo-Json -Compress
""")
        values = json.loads(result)
        for distance in values["distances"]:
            self.assertAlmostEqual(distance, 72)
        self.assertTrue(values["atTarget"])
        self.assertTrue(values["sleepStops"])
        self.assertTrue(values["dashboardStops"])

    def test_gait_alternates_feet_and_reset_clears_the_stride(self):
        result = self.powershell(self.widget_functions("Set-WalkPose", "Reset-Pose") + """
$ui = @{}
foreach ($name in @('BotTilt','BotHop','LegT0','LegT1','LegT2','LegT3',
                    'ArmLT','ArmRT','ShadeScale','Shade')) {
    $ui[$name] = [pscustomobject]@{X=0.0;Y=0.0;Angle=0.0;ScaleX=1.0;ScaleY=1.0;Opacity=1.0}
}
$poses = @(foreach ($distance in @(0,10,20,30,40)) {
    Set-WalkPose $distance
    [pscustomobject]@{x0=$ui.LegT0.X;x1=$ui.LegT1.X;y0=$ui.LegT0.Y;y1=$ui.LegT1.Y;
        y2=$ui.LegT2.Y;y3=$ui.LegT3.Y}
})
Set-WalkPose 10
Reset-Pose
@{poses=$poses;reset=@($ui.LegT0.X,$ui.LegT1.X,$ui.LegT2.X,$ui.LegT3.X,
    $ui.LegT0.Y,$ui.LegT1.Y,$ui.LegT2.Y,$ui.LegT3.Y)} | ConvertTo-Json -Depth 4 -Compress
""")
        values = json.loads(result)
        expected = [(0, 0, 0), (2.5, -6, 0), (0, 0, 0), (-2.5, 0, -6), (0, 0, 0)]
        for pose, (x, y0, y1) in zip(values["poses"], expected):
            self.assertAlmostEqual(pose["x0"], x)
            self.assertAlmostEqual(pose["x1"], -x)
            self.assertAlmostEqual(pose["y0"], y0)
            self.assertAlmostEqual(pose["y1"], y1)
            self.assertAlmostEqual(pose["y2"], y1)
            self.assertAlmostEqual(pose["y3"], y0)
        self.assertEqual(values["reset"], [0] * 8)
