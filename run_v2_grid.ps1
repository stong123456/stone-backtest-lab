$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python scripts/hermes_backtest_lab_v2.py --mode grid --limit 6 --grid entry-score=80,90 --grid max-leverage=5,10 -- --preset demo
