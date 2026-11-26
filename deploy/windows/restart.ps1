param([string]$Root = "C:\Legion")
& "$PSScriptRoot\stop.ps1" -Root $Root; Start-Sleep -Seconds 75; schtasks /End /TN LegionPaperService 2>$null; & "$PSScriptRoot\start.ps1" -Root $Root
