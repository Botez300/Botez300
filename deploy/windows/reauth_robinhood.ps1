# Interactive Robinhood OAuth (browser). Tokens go to Windows Credential Manager only.
param([string]$Root = "C:\Legion")
& "$Root\.venv\Scripts\python.exe" -m legion.rh_auth login
