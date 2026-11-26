# Emergency shutdown: write EMERGENCY_STOP (service exits code 3 and refuses to restart), then end the task immediately.
param([string]$Root = "C:\Legion")
New-Item -ItemType File -Force "$Root\state\EMERGENCY_STOP" | Out-Null
schtasks /End /TN LegionPaperService
Write-Host "EMERGENCY_STOP set. Delete $Root\state\EMERGENCY_STOP manually to allow restart."
