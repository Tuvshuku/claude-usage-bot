"""Launch the real app with isolated usage data and verify its WPF dashboard."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def main():
    if os.name != "nt":
        raise SystemExit("This check requires Windows and an interactive desktop session.")
    repo = Path(__file__).resolve().parents[1]
    # Spaces and non-ASCII characters catch quoting and locale-dependent bugs.
    with tempfile.TemporaryDirectory(prefix="usage bot \ud14c\uc2a4\ud2b8 ") as tmp:
        root = Path(tmp)
        data = root / "app data"
        profile = root / "profile"
        roaming = root / "roaming"
        claude = root / "custom Claude"
        project = claude / "projects" / "sample"
        for directory in (data, profile, roaming, project):
            directory.mkdir(parents=True)
        (data / "config.json").write_text(json.dumps({
            "live_sync": False, "interval_seconds": 1,
        }), encoding="utf-8")
        fixture = {
            "type": "assistant", "requestId": "smoke-request", "sessionId": "smoke-session",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": {"model": "claude-sonnet-4-6", "usage": {
                "input_tokens": 11, "output_tokens": 7,
            }},
        }
        (project / "session.jsonl").write_text(json.dumps(fixture) + "\n", encoding="utf-8")
        result = root / "dashboard.json"
        if len(sys.argv) > 1:
            source = Path(sys.argv[1]).resolve()
            downloads = root / "Downloads"
            if source.suffix.lower() == '.zip':
                with zipfile.ZipFile(source) as bundle:
                    bundle.extractall(downloads)
                exe = downloads / "ClaudeUsageBot" / "ClaudeUsageBot.exe"
            elif (source.parent / '_internal').is_dir():
                shutil.copytree(source.parent, downloads / 'ClaudeUsageBot')
                exe = downloads / 'ClaudeUsageBot' / source.name
            else:
                downloads.mkdir()
                exe = downloads / source.name
                shutil.copyfile(source, exe)
            command = [str(exe)]
        else:
            command = [sys.executable, str(repo / "native_app.py")]
        command.extend(["--smoke-test", str(result)])
        env = dict(os.environ, CLAUDE_USAGE_BOT_DATA_DIR=str(data),
                   CLAUDE_CONFIG_DIR=str(claude), USERPROFILE=str(profile),
                   APPDATA=str(roaming), LOCALAPPDATA=str(root / "local"))
        # An executable must work without Python, Git, or WSL on PATH.
        if len(sys.argv) > 1:
            env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        process = subprocess.Popen(command, cwd=root, env=env)
        try:
            code = process.wait(timeout=45)
            if code != 0 or not result.is_file():
                raise AssertionError(f"App exited with {code}; dashboard result exists: {result.exists()}")
            actual = json.loads(result.read_text(encoding="utf-8-sig"))
            if actual["tokens"] != 18 or actual["gauges"] != 3 or "18" not in actual["footer"]:
                raise AssertionError(f"Incorrect dashboard: {actual}")
            snapshot = json.loads((profile / ".claude-widget" / "usage.json").read_text())
            if snapshot["today"]["tokens"] != 18:
                raise AssertionError("Collector did not read the isolated Claude directory")
            print("Windows smoke OK: standalone startup, custom Unicode paths, usage, dashboard, clean exit")
        except BaseException:
            if process.poll() is None:
                subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32" / "taskkill.exe"),
                                "/PID", str(process.pid), "/T", "/F"], check=False)
                process.wait(timeout=10)
            for name in ("startup.log", "widget.log"):
                path = data / name
                if path.exists():
                    print(f"{name}:\n{path.read_bytes().decode('utf-8', errors='replace')}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
