#!/usr/bin/env bash
ROOT="${1:-$HOME/Legion}"; touch "$ROOT/state/EMERGENCY_STOP"; launchctl bootout "gui/$(id -u)/com.legion.paper-service" 2>/dev/null; echo "EMERGENCY_STOP set"
