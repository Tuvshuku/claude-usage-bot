import copy
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import collector
from launcher_config import render_wsl_launcher


NOW = 1_800_001_800.0  # Half past an epoch hour.


def config():
    cfg = copy.deepcopy(collector.DEFAULT_CONFIG)
    cfg["live_sync"] = False
    return cfg


def record(request_id, timestamp, output, **usage):
    return {
        "type": "assistant", "requestId": request_id, "timestamp": timestamp,
        "sessionId": "one", "message": {
            "model": "claude-opus-4-6",
            "usage": {"output_tokens": output, **usage},
        },
    }


class TranscriptRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patcher = patch.object(collector, "PROJECTS_DIR", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.cfg = config()
        self.state = collector.new_state()

    def write(self, name, *records):
        path = self.root / name
        path.write_text("".join(json.dumps(r) + "\n" for r in records))
        os.utime(path, (NOW, NOW))
        return path

    def scan(self):
        added = collector.scan(self.state, self.cfg, NOW)
        collector.prune(self.state, self.cfg, NOW)
        return added

    def test_streaming_updates_count_once_and_update_all_rollups(self):
        self.write("a.jsonl", record("a", NOW - 60, 7), record("a", NOW - 50, 315))
        self.assertEqual(self.scan(), 1)
        self.assertEqual(collector.totals_of(self.state["session_models"]), [0, 315, 0, 0, 0, 1])
        snap = collector.build_snapshot(self.state, self.cfg, NOW)
        self.assertEqual(snap["today"]["tokens"], 315)
        self.assertEqual(snap["burn"]["tokens_per_min"], 10.5)
        self.assertEqual(sum(snap["sparkline"]), 315)
        self.assertEqual(snap["today"]["cost_usd"], round(315 * 25 / 1e6, 4))

    def test_update_after_restart_and_replayed_partial_do_not_duplicate(self):
        first = record("a", NOW - 60, 7)
        self.write("a.jsonl", first)
        self.scan()
        # A serialization round trip models a daemon restart between updates.
        self.state = json.loads(json.dumps(self.state))
        self.write("a.jsonl", first, record("a", NOW - 50, 315))
        self.assertEqual(self.scan(), 1)
        self.write("copy.jsonl", first)
        self.assertEqual(self.scan(), 0)
        self.assertEqual(collector.totals_of(self.state["session_models"])[1::4], [315, 1])

    def test_old_import_does_not_join_current_session_or_duplicate_on_copy(self):
        self.write("current.jsonl", record("current", NOW - 60, 10))
        self.scan()
        historical = record("old", NOW - 3 * collector.DAY, 1000)
        self.write("history.jsonl", historical)
        self.scan()
        self.assertEqual(collector.totals_of(self.state["session_models"])[1], 10)
        self.state = json.loads(json.dumps(self.state))
        self.write("copy.jsonl", historical)
        self.assertEqual(self.scan(), 0)
        self.assertEqual(sum(collector.totals_of(m)[1] for m in self.state["hours"].values()), 1010)

    def test_late_update_to_previous_session_cannot_roll_current_session_back(self):
        old = record("old", NOW - 6 * collector.HOUR, 7)
        self.write("a.jsonl", old, record("new", NOW - 60, 10))
        self.scan()
        anchor = self.state["session_start"]
        self.write("update.jsonl", record("old", NOW - 6 * collector.HOUR + 10, 315))
        self.scan()
        self.assertEqual(self.state["session_start"], anchor)
        self.assertEqual(collector.totals_of(self.state["session_models"])[1], 10)

    def test_earlier_copy_of_session_starting_request_keeps_its_usage(self):
        self.write("a.jsonl", record("one", NOW - 30, 100))
        self.scan()
        self.write("copy.jsonl", record("one", NOW - 60, 7))
        self.scan()
        self.assertEqual(self.state["session_start"], NOW - 60)
        self.assertEqual(collector.totals_of(self.state["session_models"])[1], 100)

    def test_retention_prunes_ledger_and_totals_together(self):
        self.cfg["retention_days"] = 1
        self.write("a.jsonl", record("old", NOW - collector.DAY + 10, 100), record("new", NOW - 60, 10))
        self.scan()
        collector.prune(self.state, self.cfg, NOW + 20)
        self.assertEqual(set(self.state["requests"]), {"new"})
        self.assertEqual(sum(collector.totals_of(m)[1] for m in self.state["hours"].values()), 10)

    def test_non_hour_week_anchor_includes_only_requests_inside_window(self):
        self.cfg["week_anchor"] = NOW - 900
        self.write("a.jsonl", record("before", NOW - 1000, 200), record("inside", NOW - 600, 100))
        self.scan()
        windows = collector.compute_windows(self.state, self.cfg, NOW)
        self.assertEqual(collector.totals_of(windows["week"]["models"])[1], 100)

    def test_window_boundaries_are_exact_even_within_one_hour(self):
        self.write("a.jsonl", *(record(str(i), NOW + delta, count) for i, (delta, count) in enumerate([
            (-1000, 200), (-600, 100), (-300, 50), (0, 25),
        ])))
        self.scan()
        total = collector.window_totals(self.state["hours"], NOW - 900, NOW - 300,
                                        self.cfg, requests=self.state["requests"])
        self.assertEqual(collector.totals_of(total)[1], 100)

    def test_partial_transcript_line_is_consumed_after_completion(self):
        raw = json.dumps(record("one", NOW - 60, 100))
        path = self.root / "a.jsonl"
        path.write_text(raw[:30])
        os.utime(path, (NOW, NOW))
        self.assertEqual(self.scan(), 0)
        path.write_text(raw + "\n")
        os.utime(path, (NOW + 1, NOW + 1))
        self.assertEqual(self.scan(), 1)
        self.assertEqual(self.scan(), 0)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self):
        return json.dumps(self.payload).encode()


class LiveRegressionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.cfg["live_sync"] = True
        self.state = collector.new_state()
        self.state["last_live"] = {
            "at": NOW - 120, "gauges": {
                "session": {"pct": .73, "resets_at": NOW + 3600},
                "week": {"pct": .45, "resets_at": NOW + 7200},
            },
        }

    def fetch_patch(self, payload):
        return patch.object(collector._LIVE_OPENER, "open", return_value=Response(payload))

    def test_empty_or_unusable_response_keeps_saved_readings(self):
        for payload in ({}, {"limits": []}, {"limits": [{"kind": "session", "percent": "bad"}]}):
            with self.subTest(payload=payload), patch.object(
                Path, "read_text", return_value=json.dumps({"claudeAiOauth": {"accessToken": "test"}})
            ), patch.dict(collector._live_cache, attempt_at=0, success_at=0, data=None, error=None), self.fetch_patch(payload):
                snap = collector.build_snapshot(self.state, self.cfg, NOW)
            self.assertFalse(snap["live"]["ok"])
            self.assertEqual(snap["live"]["error"], "invalid response")
            self.assertEqual(snap["gauges"][0]["source"], "last_live")
            self.assertEqual(snap["gauges"][0]["pct"], .73)

    def test_successful_payload_expires_between_polls(self):
        payload = {"limits": [{"kind": "session", "percent": 99, "resets_at": NOW + 5}]}
        with patch.dict(collector._live_cache, attempt_at=NOW, success_at=NOW, data=payload, error=None), patch.object(
            collector._LIVE_OPENER, "open"
        ) as request:
            first = collector.build_snapshot(self.state, self.cfg, NOW)
            expired = collector.build_snapshot(self.state, self.cfg, NOW + 10)
            request.assert_not_called()
        self.assertEqual(first["gauges"][0]["source"], "live")
        self.assertNotIn(expired["gauges"][0]["source"], {"live", "last_live"})
        self.assertEqual(expired["gauges"][0]["pct"], 0)

    def test_partial_response_preserves_missing_gauge_and_its_sync_age(self):
        payload = {"limits": [{"kind": "weekly_all", "percent": 50, "resets_at": NOW + 7200}]}
        with patch.dict(collector._live_cache, attempt_at=NOW, success_at=NOW, data=payload, error=None):
            snap = collector.build_snapshot(self.state, self.cfg, NOW)
        session, week = snap["gauges"][:2]
        self.assertEqual((session["source"], session["pct"], session["age_seconds"]), ("last_live", .73, 120))
        self.assertEqual((week["source"], week["pct"]), ("live", .5))
        self.assertEqual(self.state["last_live"]["gauges"]["session"]["at"], NOW - 120)

    def test_legacy_gauge_also_expires(self):
        self.assertIsNone(collector.live_window({
            "five_hour": {"utilization": 99, "resets_at": NOW},
        }, "session", NOW))

    def test_disabled_sync_never_uses_saved_account_data(self):
        self.cfg["live_sync"] = False
        snap = collector.build_snapshot(self.state, self.cfg, NOW)
        self.assertFalse(snap["live"]["cached"])
        self.assertNotIn(snap["gauges"][0]["source"], {"live", "last_live"})


class ConfigurationAndLockTests(unittest.TestCase):
    def test_malformed_settings_and_fractional_limits_do_not_crash(self):
        for metric in ([], {}, None, True):
            cfg = config()
            cfg.update(budget_metric=metric, auto_floor={"session": "auto"}, limits={"week": .5})
            cfg = collector.validate_config(cfg)
            self.assertEqual(cfg["budget_metric"], "total")
            self.assertEqual(cfg["auto_floor"]["session"], collector.DEFAULT_CONFIG["auto_floor"]["session"])
            self.assertEqual(cfg["limits"]["week"], 1)
            collector.build_snapshot(collector.new_state(), cfg, NOW)

    def test_relative_output_is_relative_to_collector_data_directory(self):
        with patch.object(collector, "APP_DIR", Path("/example/app")):
            self.assertEqual(collector.resolve_output_path({"output_path": "custom/usage.json"}), Path("/example/app/custom/usage.json"))

    def test_schema_upgrade_preserves_account_cache_but_rebuilds_counts(self):
        old = {"version": 4, "hours": {"bad-old-rollup": {}}, "last_live": {"at": NOW, "gauges": {}}}
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "read_text", return_value=json.dumps(old)):
            state = collector.load_state()
        self.assertEqual(state["version"], collector.STATE_VERSION)
        self.assertEqual(state["hours"], {})
        self.assertEqual(state["requests"], {})
        self.assertEqual(state["last_live"], old["last_live"])

    def test_other_process_cannot_acquire_writer_lock_until_released(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(collector, "APP_DIR", Path(tmp)), patch.object(collector, "_loop_lock", None):
            self.assertTrue(collector.acquire_loop_lock())
            command = [sys.executable, "-c", "import collector; raise SystemExit(0 if collector.acquire_loop_lock() else 7)"]
            env = dict(os.environ, CLAUDE_USAGE_BOT_DATA_DIR=tmp)
            try:
                result = subprocess.run(command, env=env, cwd=collector.SOURCE_DIR, timeout=10)
                self.assertEqual(result.returncode, 7)
            finally:
                collector._loop_lock.close()
                collector._loop_lock = None
            result = subprocess.run(command, env=env, cwd=collector.SOURCE_DIR, timeout=10)
            self.assertEqual(result.returncode, 0)

    def test_all_cli_state_writers_require_lock(self):
        for args in (["--once"], ["--loop"], ["--rebuild"]):
            with self.subTest(args=args), patch.object(sys, "argv", ["collector.py", *args]), patch.object(
                collector, "load_config", return_value=config()
            ), patch.object(collector, "acquire_loop_lock", return_value=False), patch.object(collector, "load_state") as load:
                self.assertEqual(collector.main(), 1)
                load.assert_not_called()

    def test_calibration_never_writes_daemon_state(self):
        args = types.SimpleNamespace(session=20, week=None, fable=None)
        state = collector.new_state()
        state["session_start"] = NOW - 60
        state["session_models"] = {"claude-test|standard": [0, 100, 0, 0, 0, 1]}
        with patch.object(collector.time, "time", return_value=NOW), patch.object(
            collector, "scan"
        ), patch.object(collector, "save_state") as save_state, patch.object(
            collector, "save_config"
        ) as save_config, patch("builtins.print"):
            self.assertEqual(collector.do_calibrate(state, config(), args), 0)
        save_state.assert_not_called()
        self.assertEqual(save_config.call_args.args[0]["limits"]["session"], 500)


class LauncherTests(unittest.TestCase):
    def test_installed_launcher_uses_absolute_paths_when_copied_to_startup(self):
        template = (collector.SOURCE_DIR / "Start-Widget.vbs").read_text()
        widget = r"C:\Users\Test User\custom folder\widget.ps1"
        data = r"D:\usage data\custom.json"
        rendered = render_wsl_launcher(template, "Ubuntu", widget, data)
        self.assertIn(f'Const WIDGET_PATH = "{widget}"', rendered)
        self.assertIn(f'Const DATA_PATH = "{data}"', rendered)
        self.assertIn('Const DISTRO = "Ubuntu"', rendered)
        self.assertNotIn('"__WIDGET_PATH__"', rendered)

    def test_launcher_escapes_quotes_without_replacing_path_contents(self):
        self.assertEqual(render_wsl_launcher('"__WIDGET_PATH__" "__DATA_PATH__"', "", 'a"b', "__WIDGET_PATH__"), '"a""b" "__WIDGET_PATH__"')

    @unittest.skipUnless(os.name == "nt", "requires Windows Script Host")
    def test_rendered_launcher_compiles_in_windows_script_host(self):
        template = (collector.SOURCE_DIR / "Start-Widget.vbs").read_text()
        rendered = render_wsl_launcher(template, "Ubuntu", r"C:\사용자\widget.ps1", r"D:\custom data\usage.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "launcher.vbs"
            # WSH compiles the whole script before execution. Exit immediately
            # so this check never launches WSL or a desktop widget.
            path.write_text("WScript.Quit 0\n" + rendered, encoding="utf-16")
            cscript = Path(os.environ["SystemRoot"]) / "System32" / "cscript.exe"
            result = subprocess.run([str(cscript), "//nologo", str(path)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
