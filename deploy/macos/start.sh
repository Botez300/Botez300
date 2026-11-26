#!/usr/bin/env bash
ROOT="${1:-$HOME/Legion}"; [ -f "$ROOT/state/EMERGENCY_STOP" ] && { echo "EMERGENCY_STOP present"; exit 3; }
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.legion.paper-service.plist" 2>/dev/null || launchctl kickstart -k "gui/$(id -u)/com.legion.paper-service"
