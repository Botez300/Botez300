# Legion Quant Capital - Windows install (PAPER mode). Run in PowerShell (no administrator rights needed) from the repo root.
# One-time, per-user, Microsoft-documented policy for locally created scripts (does NOT bypass signing for downloaded scripts):
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#   .\deploy\windows\install.ps1 -Root C:\Legion
param([string]$Root = "C:\Legion")
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path "$PSScriptRoot\..\..").Path
New-Item -ItemType Directory -Force -Path $Root, "$Root\state", "$Root\state\logs" | Out-Null
if (-not (Test-Path "$Root\.venv")) { py -3.12 -m venv "$Root\.venv" }
& "$Root\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Root\.venv\Scripts\python.exe" -m pip install -r "$Repo\requirements.txt" -r "$Repo\requirements-drive.txt"
if (-not (Test-Path "$Root\config.json")) {
  Copy-Item "$Repo\deploy\config.example.json" "$Root\config.json"
  Write-Host "Edit $Root\config.json (local_dir / drive_folder_id, state_dir=$Root\state)."
}
& "$Root\.venv\Scripts\python.exe" -m pytest -q "$Repo\tests"
if ($LASTEXITCODE -ne 0) { throw "tests failed on this host; not registering the task" }
Write-Host "Installed. NO scheduled task was registered."
Write-Host "Next: edit $Root\config.json, run .\deploy\windows\reauth_robinhood.ps1, then the acceptance tests (docs/DEPLOYMENT_WINDOWS.md)."
Write-Host "Register the task only after review: .\deploy\windows\register_task.ps1 -Root $Root  (it registers the task DISABLED)."
