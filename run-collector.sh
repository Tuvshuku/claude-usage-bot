#!/usr/bin/env bash
# Runs the collector in a loop. Python owns the cross-platform writer lock.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$APP_DIR"

exec python3 collector.py --loop
