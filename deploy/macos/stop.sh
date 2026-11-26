#!/usr/bin/env bash
ROOT="${1:-$HOME/Legion}"; touch "$ROOT/state/STOP_REQUEST"; echo "graceful stop requested"
