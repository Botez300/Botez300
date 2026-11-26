# Deployment (PAPER mode only)

**Status: NOT installed or tested on any real host.** Nothing below is claimed to work until you complete the
acceptance checklist at the bottom on your own machine.

## Requirements
- Python 3.11+, a venv: `pip install -r requirements.txt -r requirements-drive.txt`
- Credentials live **outside the repo** (e.g. `~/.legion/`). The repo contains none; `state/` is git-ignored.

## Ingestion method A: Google Drive for desktop (no API credentials)
1. Install Google Drive for desktop, sign in as the Drive owner.
2. Set `Legion Quant Capital/03_Verified_Signals` to **Mirror** (or "Available offline") so real files exist locally, not
   cloud-only placeholders.
3. `config.json`: `"source": "local"`, `"local_dir"` = the synced path
   (Windows `G:/My Drive/Legion Quant Capital/03_Verified_Signals`; macOS `~/Library/CloudStorage/GoogleDrive-<account>/My Drive/Legion Quant Capital/03_Verified_Signals`).
4. Files modified < 5 s ago, `*.tmp`, `~$*`, `.crdownload` are skipped; truncated JSON younger than 120 s is *deferred* and retried, never ledgered.

## Ingestion method B: Drive API (read-only scope)
1. Google Cloud project -> enable Drive API.
2. Either (i) service account: create a key (JSON) outside the repo, share `03_Verified_Signals` with the service-account email as *Viewer*;
   or (ii) OAuth Desktop client: `python -m legion.drive_auth --client-secret <file> --token <file>`.
3. `config.json`: `"source": "api"`, `"drive_folder_id": "1j-_ZWjfYalftnVVldnEiV-E4WTdhffo7"`, and `service_account_file` or `oauth_token_file`.
4. Downloads are verified against Drive's `md5Checksum` and size. **`DriveApiSource` has never been run against Google.**

## Robinhood market data (required for any entry)
`legion.rh.McpHttpTransport` needs `LEGION_RH_MCP_URL` and `LEGION_RH_MCP_TOKEN`. The endpoint/auth scheme were not available when this was
written; the transport is untested. Without a working transport every entry fails closed (`MARKET_DATA_UNAVAILABLE`). Only the allowlisted read-only
tools are callable; order/cancel/exercise/watchlist/alert tools raise `ToolBlocked`.

## Scheduler
- Windows: edit paths in `deploy/windows_task.xml`, then `schtasks /Create /XML deploy\windows_task.xml /TN LegionPaperService`.
- macOS: edit `YOU` paths in `deploy/com.legion.paper-service.plist`, copy to `~/Library/LaunchAgents/`, `launchctl bootstrap gui/$(id -u) <plist>`.
- The process polls every 60 s (backoff 60->120->240->...->900 s on failure), follows the NYSE calendar in America/New_York, monitors paper
  positions only while the regular session is open, writes `state/heartbeat.json` and `state/alerts.jsonl`.
- **Emergency shutdown:** create `state/EMERGENCY_STOP` (or send SIGTERM). The service exits (code 3) and refuses to restart until the file is removed by hand.

## Acceptance checklist (must all be observed on the host)
1. `python -m pytest` passes there.
2. Service starts, `heartbeat.json` updates every ~60 s.
3. Drop a harmless TEST_ONLY json into the folder -> appears in `decisions.jsonl` as `REJECTED`, no paper order.
4. Kill the process -> task scheduler/launchd restarts it; ledger and paper state intact.
5. Disconnect network -> `CONNECTION_LOST` alert after 3 failures, recovery alert afterwards.
6. Create `EMERGENCY_STOP` -> service exits and stays down.
