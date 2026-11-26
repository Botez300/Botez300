# Host acceptance tests (you must be at the PC). Each step records a file in state\acceptance only if it REALLY passes.
param([string]$Root = "C:\Legion")
$py = "$Root\.venv\Scripts\python.exe"; $Repo = (Resolve-Path "$PSScriptRoot\..\..").Path
Write-Host "1/3 Robinhood authenticated read-only test"; & $py "$Repo\scripts\acceptance.py" robinhood --state "$Root\state"
Write-Host "2/3 Google Drive integration test";         & $py "$Repo\scripts\acceptance.py" drive --state "$Root\state" --config "$Root\config.json"
Write-Host "3/3 Emergency-stop drill";                  & $py "$Repo\scripts\acceptance.py" estop --state "$Root\state"
& $py -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1])), indent=1))" "$Root\state\activation_status.json" 2>$null
