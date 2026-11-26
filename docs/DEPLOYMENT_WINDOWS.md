# Windows deployment guide (primary host): PAPER mode

**Status: NOT installed or tested on your PC.** The cloud build environment is not your desktop. Every step below needs to be confirmed on the machine.
No administrator rights are needed.

| # | Step | Command / action |
|---|---|---|
| 1 | Python 3.12 (64-bit) | Install from python.org. Check: `py -3.12 --version` |
| 2 | Git | Install Git for Windows. Check: `git --version` |
| 3 | Claude Code (optional, for advisory escalation) | Follow Anthropic's official install instructions, then `claude --version` and log in |
| 4 | Checkout | `git clone https://github.com/Botez300/Botez300 C:\Legion\Botez300` |
| 5 | Draft PR branch | `cd C:\Legion\Botez300; git checkout claude/cool-fermi-5sk4s9` |
| 6 | Script policy (per user, once) | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` (Microsoft-documented; not a bypass) |
| 7 | venv + dependencies + tests | `.\deploy\windows\install.ps1 -Root C:\Legion`. Creates the venv, installs requirements and runs the full test suite. **It no longer registers any scheduled task (Phase 6)** |
| 8 | Google Drive for desktop | Install, sign in as the Drive owner |
| 9 | Sync | Set `Legion Quant Capital\03_Verified_Signals` to *Mirror* or *Available offline*. Find the real path in Explorer (often `G:\My Drive\...`; **check it, don't assume**) |
| 10 | Configure | Edit `C:\Legion\config.json`: `local_dir` (your real path from step 9), `state_dir` = `C:/Legion/state`, `paper_start_equity` (**your explicit choice; the service refuses to start while it is null**) |
| 11 | Secrets | None in config or env files. Robinhood tokens go to Windows Credential Manager (step 12). Drive needs no credentials with desktop sync |
| 12 | Robinhood login | `.\deploy\windows\reauth_robinhood.ps1 -Root C:\Legion` (browser OAuth). It prints an authenticated SPY quote on success |
| 13 | Acceptance tests | `.\deploy\windows\acceptance.ps1 -Root C:\Legion` runs (1) the authenticated Robinhood read-only test, (2) the Drive genuine-report test from your synced folder and (3) the emergency-stop drill. Each writes `state\acceptance\*.json` only if it really passes. Also run `$env:LEGION_LIVE_RH="1"; .venv\Scripts\python -m pytest tests -k live -v` |
| 14 | Task Scheduler (after you review config) | `.\deploy\windows\register_task.ps1 -Root C:\Legion` registers `LegionPaperService` **DISABLED**. Enable deliberately with `schtasks /Change /TN LegionPaperService /ENABLE`. Even when enabled, the service runs **OBSERVE_ONLY** (no simulated orders) until all activation gates pass (`state\activation_status.json`) |
| 15 | Start | `.\deploy\windows\start.ps1 -Root C:\Legion` |
| 16 | Status | `.\deploy\windows\status.ps1 -Root C:\Legion` (task state, heartbeat, last alerts, token presence), or `python -m legion.ops status --state C:\Legion\state` |
| 17 | Normal stop | `.\deploy\windows\stop.ps1 -Root C:\Legion` (STOP_REQUEST; exits within 60 s) |
| 18 | Emergency stop | `.\deploy\windows\emergency_stop.ps1 -Root C:\Legion`. The process is ended and stays down until you delete `state\EMERGENCY_STOP` |
| 19 | Reboot recovery | The boot/logon trigger restarts it. SQLite ledger, paper state and executed-signal list reload from `state\`. The single-instance lock prevents duplicates |
| 20 | Logs / troubleshooting | `state\logs\legion.log` (rotating), `state\alerts.jsonl`, `state\decisions.jsonl`, `state\outbox\` (daily journal and risk report), `schtasks /Query /TN LegionPaperService /V` |

## Known caveat
It is not yet confirmed that Robinhood's OAuth server accepts the app's own client registration. Robinhood documents connecting an *AI platform* (`claude mcp add ...`).
If step 12 fails at registration, stop. **Do not work around it.** Report the error; the fallback options are listed in `docs/ROBINHOOD_MCP.md`.

## What needs you physically at the PC
| Step | Why |
|---|---|
| 1-5, 7 | installs on your machine |
| 8-9 | Google sign-in; confirm the real synced path |
| 10 | your explicit starting-equity choice |
| 12 | Robinhood browser login (OAuth) |
| 13 | acceptance tests use your credentials and files |
| 14-15 | your decision to register and enable the task |
| 18 | emergency-stop drill (also automated in step 13) |

## Activation gates (`legion/activation.py`): all must be true before any simulated order
- starting_equity_set
- strategy_variant_configured
- entry_parameters_owner_approved
- exit_rules_owner_approved
- robinhood_live_readonly_test_passed
- google_drive_integration_test_passed
- emergency_stop_drill_passed
- owner_activation_signoff (you create `state\acceptance\OWNER_ACTIVATION_SIGNOFF.json` yourself)
- no_emergency_stop

## Drive outbox publication from the host
- `legion/drive_publish.py` uses the least-privilege `drive.file` scope.
- It reads every upload back and checks its md5 before marking it published, and keeps a ledger so restarts never re-publish.
- It needs a Drive API OAuth token created on the host. **UNTESTED against Google.**
