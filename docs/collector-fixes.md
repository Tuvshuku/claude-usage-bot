# Collector and launcher fixes

## Updating an existing installation

Restart the collector after updating the source. State schema 5 rebuilds local
totals from transcripts on its first run, preserving the saved account readings.
The request ledger retains timestamps and token counts for `retention_days`, so
the state file is larger than schema 4. It contains no transcript message text
or OAuth credentials.

For WSL installations, stop the old collector before restarting it: the older
Python process does not participate in the new writer lock. Re-run
`./install.sh --service --autostart` to refresh the installed widget and Startup
launcher, then reopen the widget. Native Windows source users can close and
reopen `Start-Windows.vbs`; executable users need a build containing these fixes.

## Corrected behavior

- Repeated streaming records update the stored token counts for their request.
  Replayed partial records cannot reduce counts or add another request.
- Deduplication lasts for the full retained history, including copied transcripts.
  Newly discovered older requests do not join an already established session.
- Weekly and daily totals use individual timestamps at partial-hour boundaries.
  Hourly buckets still drive the sparkline and historical limit estimates.
- Successful account responses expire at each gauge's reset boundary, including
  responses reused between polls. Empty or unusable responses fall back to saved
  readings. Partial responses preserve other gauges and their original sync ages.
- Local percentages retain `~` even after calibration. `*` denotes a saved
  account reading. The widget's **Reload snapshot** action rereads the shared file;
  it does not trigger an account request.
- Malformed budget metrics and automatic floors fall back to defaults.
- All collector state writers use the same lock on Windows and POSIX. Calibration
  scans in memory and updates only configuration, so it can run while the daemon
  is active. Restart the collector to apply the calibration.
- The installed WSL launcher embeds absolute widget and snapshot paths and works
  when copied into Startup. The installer finds the actual Windows Startup folder
  independently of the configured output directory.
- Windows source mode uses the same host as the executable. The collector and
  widget receive the same configured snapshot path. Relative output paths resolve
  against the collector's data directory.

## Verification

Run `python3 -m unittest discover -s tests -v` and
`ruff check collector.py native_app.py launcher_config.py tests`.
The suite includes real competing-process lock checks on both platforms and a
Windows-only VBScript compilation check that exits before launching anything.
CI also parses the PowerShell scripts and checks Bash syntax.
