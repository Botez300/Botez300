# Graceful stop: the service exits 0 at its next tick (<= 60 s) after seeing STOP_REQUEST.
param([string]$Root = "C:\Legion")
New-Item -ItemType File -Force "$Root\state\STOP_REQUEST" | Out-Null
Write-Host "STOP_REQUEST written; the service will exit within one polling interval."
