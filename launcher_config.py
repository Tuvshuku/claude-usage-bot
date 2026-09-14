"""Render the WSL launcher with paths independent of its install location."""

import base64
import re
import subprocess  # nosec B404 -- list2cmdline only; no process is started here.


def render_wsl_launcher(template: str, distro: str, widget: str, data: str,
                        collector_dir: str = "") -> str:
    calibration = ""
    if collector_dir:
        # Use WSL's argument interface, not a shell command containing paths.
        args = (["--distribution", distro] if distro else []) + [
            "--cd", collector_dir, "--exec", "python3", "collector.py", "--calibrate",
        ]
        arguments = subprocess.list2cmdline(args).replace("'", "''")
        script = (
            "$ErrorActionPreference = 'Stop'; try { "
            "$wsl = Join-Path $env:SystemRoot 'System32\\wsl.exe'; "
            f"$p = Start-Process -FilePath $wsl -ArgumentList '{arguments}' "
            "-NoNewWindow -Wait -PassThru; "
            "if ($p.ExitCode -ne 0) { Write-Host ('Calibration failed: ' + $p.ExitCode) } "
            "} catch { Write-Host $_ }; Read-Host 'Press Enter to close'"
        )
        calibration = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    values = {"__WSL_DISTRO__": distro, "__WIDGET_PATH__": widget,
              "__DATA_PATH__": data, "__CALIBRATION_COMMAND__": calibration}
    # VBScript escapes embedded quotes by doubling them. A single substitution
    # avoids interpreting placeholder-like text inside a user-supplied path.
    return re.sub(
        r"__WSL_DISTRO__|__WIDGET_PATH__|__DATA_PATH__|__CALIBRATION_COMMAND__",
        lambda match: values[match.group()].replace('"', '""'),
        template,
    )
