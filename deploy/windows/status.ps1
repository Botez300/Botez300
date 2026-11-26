param([string]$Root = "C:\Legion")
schtasks /Query /TN LegionPaperService /V /FO LIST | Select-String "Status|Last Run|Last Result"
Get-Content "$Root\state\heartbeat.json" -ErrorAction SilentlyContinue
Get-Content "$Root\state\alerts.jsonl" -Tail 10 -ErrorAction SilentlyContinue
& "$Root\.venv\Scripts\python.exe" -m legion.rh_auth status
