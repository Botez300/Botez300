# Windows deployment (primary target): PAPER mode

**Not installed or tested on any real Windows machine.** Treat each step as unverified until you run it.

## 1. Prerequisites
- Windows 10/11, Python 3.12 (`py -3.12`), and Git.
- Google Drive for desktop (for local sync). Set `Legion Quant Capital/03_Verified_Signals` to **Mirror** or **Available offline**.
- Optional: Claude Code CLI, logged in (for advisory escalation).

## 2. Install
```powershell
git clone https://github.com/Botez300/Botez300 C:\Legion\Botez300
cd C:\Legion\Botez300
powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1 -Root C:\Legion
```
The script does the following:
- creates `C:\Legion\.venv`
- installs `requirements*.txt` + `keyring`
- copies `deploy\config.example.json` to `C:\Legion\config.json`
- runs the test suite and refuses to register the task if any test fails
- registers the `LegionPaperService` task (logon/boot triggers, restart on failure, 60 s polling inside the process)

## 3. Configure
Edit `C:\Legion\config.json`:
- `"source": "local"`
- `"local_dir": "G:/My Drive/Legion Quant Capital/03_Verified_Signals"`
- `"state_dir": "C:/Legion/state"`
- optional `"strategy_variants": {"PARABOLIC_MOMENTUM": "PARABOLIC_NATIVE"}`

Environment template: `deploy\env.example`. No secrets go in either file.

## 4. Robinhood authentication (interactive, once, and again whenever tokens expire)
```powershell
powershell -File deploy\windows\reauth_robinhood.ps1 -Root C:\Legion
```
- This opens Robinhood's OAuth login.
- Tokens are stored in **Windows Credential Manager** only (`keyring`). The code refuses to store them anywhere else.
- Refresh is automatic through the MCP SDK.
- If refresh fails, the service fails closed, raises `CONNECTION_LOST`, and you run the script again.

## 5. Operate
| Action | Command |
|---|---|
| Start | `deploy\windows\start.ps1` (refuses while `EMERGENCY_STOP` exists) |
| Graceful stop (exits within 60 s) | `deploy\windows\stop.ps1` |
| Restart | `deploy\windows\restart.ps1` |
| Emergency shutdown | `deploy\windows\emergency_stop.ps1`, then delete `state\EMERGENCY_STOP` manually to resume |
| Status, heartbeat, alerts, token presence | `deploy\windows\status.ps1` |

- Logs: `C:\Legion\state\logs\legion.log` (rotating, 10 x 5 MB).
- Alerts: `state\alerts.jsonl`.
- Decisions: `state\decisions.jsonl`.
- Reboot recovery: the task triggers at boot and logon; ledger and paper state reload from `state\`; duplicates are prevented by the content-hash ledger and the executed-signal list.

## 6. Acceptance (do on the machine)
1. `install.ps1` test step passes.
2. `reauth_robinhood.ps1` prints an SPY quote. This is the first genuinely authenticated read-only test.
3. `$env:LEGION_LIVE_RH="1"; .venv\Scripts\python -m pytest tests -k live` passes.
4. Heartbeat updates each minute.
5. A TEST_ONLY file in Drive is rejected, with no order.
6. Kill the process: the task restarts it.
7. `emergency_stop.ps1`: the service stays down.

## macOS
Use `deploy/macos/install.sh`, `start.sh`, `stop.sh`, `emergency_stop.sh` and `reauth_robinhood.sh`, with the launchd plist (`KeepAlive`). Tokens go to the macOS Keychain.
