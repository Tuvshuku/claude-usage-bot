import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import native_app


class NativeLauncherTests(unittest.TestCase):
    def test_widget_failure_is_reported_but_normal_exit_is_not(self):
        for child_code in (0, 1, 42):
            with self.subTest(child_code=child_code), patch.object(
                native_app, "os", types.SimpleNamespace(name="nt")
            ), patch.object(native_app.collector, "acquire_loop_lock", return_value=True), patch.object(
                native_app, "install_example_config"
            ), patch.object(native_app.collector, "load_config", return_value={"interval_seconds": 5}), patch.object(
                native_app.collector, "resolve_output_path"
            ), patch.object(native_app.collector, "load_state", return_value={}), patch.object(
                native_app.collector, "run_once"
            ), patch.object(native_app, "launch_widget") as launch, patch.object(
                native_app, "show_error"
            ) as error:
                launch.return_value.poll.return_value = child_code
                self.assertEqual(native_app.main(), int(child_code != 0))
                if child_code:
                    self.assertIn(f"exit code {child_code}", error.call_args.args[0])
                else:
                    error.assert_not_called()

    def test_host_passes_configured_output_to_collector_and_widget(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            native_app, "os", types.SimpleNamespace(name="nt")
        ), patch.object(native_app.collector, "APP_DIR", Path(tmp)), patch.object(
            native_app.collector, "acquire_loop_lock", return_value=True
        ), patch.object(native_app, "install_example_config"), patch.object(
            native_app.collector, "load_config", return_value={
                "output_path": "custom folder/snapshot.json", "interval_seconds": 5,
            }
        ), patch.object(native_app.collector, "load_state", return_value={}), patch.object(
            native_app.collector, "run_once"
        ) as collect, patch.object(native_app, "launch_widget") as launch:
            launch.return_value.poll.return_value = 0
            self.assertEqual(native_app.main(), 0)
            expected = Path(tmp) / "custom folder" / "snapshot.json"
            self.assertEqual(collect.call_args.args[2], expected)
            launch.assert_called_once_with(expected)

    def test_widget_uses_system_powershell_and_passes_paths_as_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            powershell = (
                root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            )
            powershell.parent.mkdir(parents=True)
            powershell.write_bytes(b"")
            widget = root / "widget.ps1"
            widget.write_text("# test")
            data_path = root / "profile with spaces" / "usage.json"

            with patch.dict(os.environ, {"SystemRoot": str(root)}), patch.object(
                native_app, "bundled_asset", return_value=widget
            ), patch.object(native_app.subprocess, "Popen") as popen:
                native_app.launch_widget(data_path)

            command = popen.call_args.args[0]
            self.assertEqual(command[0], str(powershell))
            self.assertEqual(command[command.index("-DataPath") + 1], str(data_path))
            self.assertEqual(command[command.index("-File") + 1], str(widget))
            self.assertIn("-NativeMode", command)


if __name__ == "__main__":
    unittest.main()
