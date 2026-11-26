param([string]$Root = "C:\Legion")
if (Test-Path "$Root\state\EMERGENCY_STOP") { Write-Error "EMERGENCY_STOP present - remove it deliberately to resume"; exit 3 }
schtasks /Run /TN LegionPaperService
