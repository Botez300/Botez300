# Registers LegionPaperService DISABLED. Even when you later enable it, the service runs OBSERVE_ONLY (no simulated
# orders) until every activation gate in legion/activation.py passes. No administrator rights needed.
param([string]$Root = "C:\Legion")
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$xml = (Get-Content "$Repo\deploy\windows_task.xml" -Raw).Replace("__PYTHON__", "$Root\.venv\Scripts\python.exe").Replace("__CONFIG__", "$Root\config.json").Replace("__REPO__", $Repo)
$tmp = "$env:TEMP\legion_task.xml"; $xml | Out-File -Encoding Unicode $tmp
schtasks /Create /XML $tmp /TN LegionPaperService /F
schtasks /Change /TN LegionPaperService /DISABLE
Write-Host "Registered DISABLED. Enable deliberately with: schtasks /Change /TN LegionPaperService /ENABLE"
