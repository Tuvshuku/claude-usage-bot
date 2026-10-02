#!/usr/bin/env python3
"""Native Windows host for the collector and WPF desktop pet."""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
from contextlib import redirect_stderr, redirect_stdout
# The child is a fixed system PowerShell path and shell mode is never used.
import subprocess  # nosec B404
import sys
import time
import traceback
from pathlib import Path

import collector


APP_TITLE = "Claude Usage Bot"


def bundled_asset(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / name


def show_error(message: str) -> None:
    if "--smoke-test" in sys.argv:
        collector.log(message)
        return
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, 0x10)
    elif sys.stderr is not None:
        print(message, file=sys.stderr)


def install_example_config() -> None:
    """Put an editable example next to native state on the first run."""
    source = bundled_asset("config.example.json")
    destination = collector.APP_DIR / "config.example.json"
    if source.is_file() and not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def launch_widget(data_path: Path, smoke_result: Path | None = None) -> subprocess.Popen:
    widget = bundled_asset("widget.ps1")
    if not widget.is_file():
        raise FileNotFoundError(f"Widget asset not found: {widget}")

    powershell = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )
    if not powershell.is_file():
        raise FileNotFoundError(f"Windows PowerShell not found: {powershell}")

    command = [
        str(powershell),
        "-NoProfile",
        "-STA",
        "-ExecutionPolicy", "Bypass",
        "-WindowStyle", "Hidden",
        "-File", str(widget),
        "-DataPath", str(data_path),
        "-NativeMode",
        "-CollectorDataDir", str(collector.APP_DIR),
    ]
    if smoke_result is not None:
        command.extend(["-SmokeTestResult", str(smoke_result)])
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # PyInstaller changes the DLL search path. System PowerShell must use its
    # own libraries, not the copies extracted by the Python bootloader.
    frozen_windows = os.name == "nt" and getattr(sys, "frozen", False)
    if frozen_windows:
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:
        with (collector.APP_DIR / "widget.log").open("wb") as log:
            return subprocess.Popen(  # nosec B603
                command, creationflags=flags, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
            )
    finally:
        if frozen_windows:
            ctypes.windll.kernel32.SetDllDirectoryW(str(sys._MEIPASS))


def main(smoke_result: Path | None = None) -> int:
    if os.name != "nt":
        show_error("The desktop executable currently supports Windows 10 and 11.")
        return 2

    try:
        if not collector.acquire_loop_lock():
            show_error(
                "Claude Usage Bot is already running, or its data folder "
                "is not writable."
            )
            return 1
        with (collector.APP_DIR / "startup.log").open(
            "w", encoding="utf-8", errors="backslashreplace", buffering=1,
        ) as log, redirect_stderr(log), redirect_stdout(log):
            return run_app(smoke_result)
    except Exception as exc:
        show_error(f"Claude Usage Bot could not start.\n\n{exc}")
        return 1


def run_app(smoke_result: Path | None = None) -> int:
    widget_process = None
    try:
        install_example_config()
        cfg = collector.load_config()
        output_path = collector.resolve_output_path(cfg)
        # Show the pet before a potentially slow history rebuild or network
        # request, so first launch does not appear to do nothing.
        widget_process = (launch_widget(output_path, smoke_result) if smoke_result
                          else launch_widget(output_path))
        state = collector.load_state()
        interval = max(float(cfg["interval_seconds"]), 1.0)
        next_pass = time.monotonic()
        while (exit_code := widget_process.poll()) is None:
            remaining = next_pass - time.monotonic()
            if remaining > 0:
                time.sleep(min(remaining, 0.25))
                continue
            try:
                collector.run_once(state, cfg, output_path)
            except Exception as exc:
                collector.log(f"pass failed: {exc!r}")
            next_pass = time.monotonic() + interval
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        traceback.print_exc()
        show_error(
            f"Claude Usage Bot could not start.\n\n{exc}\n\n"
            f"Details: {collector.APP_DIR / 'startup.log'}"
        )
        return 1
    finally:
        if widget_process is not None and widget_process.poll() is None:
            widget_process.terminate()
            widget_process.wait(timeout=10)
    if exit_code != 0:
        show_error(
            f"The desktop widget stopped unexpectedly (exit code {exit_code}).\n\n"
            f"Error details are saved in:\n{collector.APP_DIR / 'widget.log'}\n\n"
            "Share that log when reporting the problem."
        )
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--smoke-test", type=Path, help=argparse.SUPPRESS)
    raise SystemExit(main(parser.parse_args().smoke_test))
