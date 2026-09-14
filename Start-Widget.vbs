' Launches the widget with no console window.
' Double-click this file, or drop a shortcut to it in shell:startup.
'
' install.sh rewrites DISTRO below to the WSL distro that runs the collector.

Const DISTRO = "__WSL_DISTRO__"
Const WIDGET_PATH = "__WIDGET_PATH__"
Const DATA_PATH = "__DATA_PATH__"
Const CALIBRATION_COMMAND = "__CALIBRATION_COMMAND__"

Dim fso, shell, here, ps1, data, target, windowsDir, wsl, powershell
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = WIDGET_PATH
data = DATA_PATH
If Left(ps1, 2) = "__" Then ps1 = fso.BuildPath(here, "widget.ps1")
If Left(data, 2) = "__" Then data = fso.BuildPath(here, "usage.json")
windowsDir = shell.ExpandEnvironmentStrings("%SystemRoot%")
wsl = fso.BuildPath(windowsDir, "System32\wsl.exe")
powershell = fso.BuildPath(windowsDir, "System32\WindowsPowerShell\v1.0\powershell.exe")

If Not fso.FileExists(ps1) Then
    MsgBox "widget.ps1 not found next to this launcher:" & vbCrLf & ps1, 16, "Claude Usage Bot"
    WScript.Quit 1
End If

' Nudge WSL awake so the collector's systemd service starts. Fire-and-forget:
' the widget shows an "offline" badge for the few seconds WSL takes to boot.
On Error Resume Next
If Len(DISTRO) = 0 Or Left(DISTRO, 2) = "__" Then
    target = """" & wsl & """ -e true"                     ' default distro
Else
    target = """" & wsl & """ -d """ & DISTRO & """ -e true"
End If
shell.Run target, 0, False
On Error GoTo 0

target = """" & powershell & """ -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """ -DataPath """ & data & """"
If Len(CALIBRATION_COMMAND) > 0 And Left(CALIBRATION_COMMAND, 2) <> "__" Then
    target = target & " -WslCalibrationCommand " & CALIBRATION_COMMAND
End If
shell.Run target, 0, False
