#!/usr/bin/env bash
ROOT="${1:-$HOME/Legion}"; "$ROOT/.venv/bin/python" -m legion.rh_auth login     # tokens -> macOS Keychain only
