# macOS deployment guide (MacBook): PAPER mode

**Not tested on your Mac.**

1. Install Python 3.12 (python.org or Homebrew) and Git (Xcode CLT). Claude Code is optional.
2. `git clone https://github.com/Botez300/Botez300 ~/Legion/Botez300 && cd ~/Legion/Botez300 && git checkout claude/cool-fermi-5sk4s9`
3. `deploy/macos/install.sh ~/Legion` creates the venv, installs requirements, runs the tests and writes `~/Library/LaunchAgents/com.legion.paper-service.plist`.
4. Google Drive for desktop: the folder is usually under `~/Library/CloudStorage/GoogleDrive-<account>/My Drive/Legion Quant Capital/03_Verified_Signals`. **Check the real path.**
5. Edit `~/Legion/config.json`: `local_dir`, `state_dir`, `paper_start_equity` (explicit).
6. `deploy/macos/reauth_robinhood.sh ~/Legion` stores tokens in the macOS Keychain only.
7. `LEGION_LIVE_RH=1 ~/Legion/.venv/bin/python -m pytest tests -k live -v`
8. Start: `deploy/macos/start.sh ~/Legion`. Stop: `deploy/macos/stop.sh ~/Legion`. Emergency: `deploy/macos/emergency_stop.sh ~/Legion`.
   launchd `KeepAlive` restarts the service after a crash or reboot, except after an emergency stop.
9. Logs: `~/Legion/state/logs/legion.log`, `~/Legion/logs/err.log`.
