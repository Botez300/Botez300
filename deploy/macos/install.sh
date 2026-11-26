#!/usr/bin/env bash
# Legion Quant Capital - macOS install (PAPER). Usage: deploy/macos/install.sh ~/Legion
set -euo pipefail
ROOT="${1:-$HOME/Legion}"; REPO="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$ROOT/state/logs" "$ROOT/logs"
[ -d "$ROOT/.venv" ] || python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -U pip && "$ROOT/.venv/bin/pip" install -r "$REPO/requirements.txt" -r "$REPO/requirements-drive.txt" keyring
[ -f "$ROOT/config.json" ] || cp "$REPO/deploy/config.example.json" "$ROOT/config.json"
"$ROOT/.venv/bin/python" -m pytest -q "$REPO/tests"
sed -e "s#/Users/YOU/Legion/Botez300#$REPO#g" -e "s#/Users/YOU/Legion#$ROOT#g" "$REPO/deploy/com.legion.paper-service.plist" > "$HOME/Library/LaunchAgents/com.legion.paper-service.plist"
echo "Next: $ROOT/.venv/bin/python -m legion.rh_auth login ; then deploy/macos/start.sh $ROOT"
