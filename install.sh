#!/usr/bin/env bash
# Copies the Windows-side pieces next to the data file and (optionally) wires up
# autostart for both halves.
#
#   ./install.sh                 copy widget + launcher to the Windows folder
#   ./install.sh --autostart     also launch the widget at Windows sign-in
#   ./install.sh --service       also run the collector as a systemd user service
set -euo pipefail

APP_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$APP_DIR"

AUTOSTART=0
SERVICE=0
for arg in "$@"; do
    case "$arg" in
        --autostart) AUTOSTART=1 ;;
        --service)   SERVICE=1 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

chmod +x run-collector.sh install.sh collector.py 2>/dev/null || true

# Ask the collector where it decided to write, so both halves agree on the path.
DATA_PATH="$(python3 - <<'PY'
import sys
sys.path.insert(0, ".")
from collector import load_config, resolve_output_path
print(resolve_output_path(load_config()))
PY
)"
TARGET_DIR="$(dirname "$DATA_PATH")"

echo "data file    : $DATA_PATH"
echo "windows dir  : $TARGET_DIR"

case "$TARGET_DIR" in
    /mnt/*) ;;
    *)
        echo
        echo "WARNING: that path is not under /mnt, so Windows cannot read it."
        echo "Set \"output_path\" in config.json to something like"
        echo "  /mnt/c/Users/<you>/.claude-widget/usage.json"
        exit 1
        ;;
esac

mkdir -p "$TARGET_DIR"
cp -f widget.ps1 "$TARGET_DIR/"

# Bake the distro name into the launcher so it can wake WSL at sign-in.
DISTRO="${WSL_DISTRO_NAME:-}"
case "$DISTRO" in
    ""|*[!A-Za-z0-9._-]*)
        if [[ -n "$DISTRO" ]]; then
            echo "launcher     : distro name has unsupported characters; using the WSL default"
        fi
        DISTRO=""
        ;;
esac
WIN_DIR="$(wslpath -w "$TARGET_DIR")"
WIN_DATA="$(wslpath -w "$DATA_PATH")"
# Absolute paths keep the same launcher usable beside the widget and in Startup.
python3 - "$DISTRO" "$WIN_DIR" "$WIN_DATA" "$TARGET_DIR/Start-Widget.vbs" <<'PY'
import sys
from pathlib import Path
from launcher_config import render_wsl_launcher

distro, widget_dir, data, destination = sys.argv[1:]
Path(destination).write_text(render_wsl_launcher(
    Path("Start-Widget.vbs").read_text(), distro, widget_dir + "\\widget.ps1", data
), encoding="utf-16")
PY
echo "copied       : widget.ps1, Start-Widget.vbs (distro: ${DISTRO:-<default>})"

if [[ $AUTOSTART -eq 1 ]]; then
    STARTUP_WIN="$(/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile \
        -Command '[Environment]::GetFolderPath("Startup")' | tr -d '\r')"
    STARTUP="$(wslpath -u "$STARTUP_WIN")"
    if [[ -d "$STARTUP" ]]; then
        AUTOSTART_PATH="$STARTUP/ClaudeUsageBot.vbs"
        LEGACY_AUTOSTART="$STARTUP/CuteClaudeWidget.vbs"
        if [[ -f "$LEGACY_AUTOSTART" && ! -e "$AUTOSTART_PATH" ]]; then
            mv "$LEGACY_AUTOSTART" "$AUTOSTART_PATH"
        fi
        cp -f "$TARGET_DIR/Start-Widget.vbs" "$AUTOSTART_PATH"
        echo "autostart    : installed to the Windows Startup folder"
    else
        echo "autostart    : SKIPPED (Startup folder not found at $STARTUP)"
    fi
fi

if [[ $SERVICE -eq 1 ]]; then
    UNIT_DIR="$HOME/.config/systemd/user"
    mkdir -p "$UNIT_DIR"
    cat > "$UNIT_DIR/claude-usage-collector.service" <<UNIT
[Unit]
Description=Claude Usage Bot collector

[Service]
Type=simple
WorkingDirectory="$APP_DIR"
ExecStart=/usr/bin/env python3 "$APP_DIR/collector.py" --loop
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT
    systemctl --user daemon-reload
    systemctl --user enable --now claude-usage-collector.service
    echo "service      : claude-usage-collector.service enabled and started"
    echo "               (logs: journalctl --user -u claude-usage-collector -f)"
    if [[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]]; then
        if loginctl enable-linger "$USER"; then
            echo "linger       : enabled (collector can start before a WSL shell opens)"
        else
            echo "linger       : WARNING: could not enable it; run: loginctl enable-linger $USER"
        fi
    fi
fi

cat <<EOF

Done. To run it:

  1. collector (WSL)      ./run-collector.sh
$( [[ $SERVICE -eq 1 ]] && echo "                          ...already running as a systemd user service" )
  2. widget (Windows)     open  $WIN_DIR\\Start-Widget.vbs

Drag the card to move it, click to toggle the dashboard,
right-click for refresh / quit.
EOF
