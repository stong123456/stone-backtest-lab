$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python scripts/hermes_backtest_lab_v2.py --mode walk-forward --walk-windows 2 --walk-candidates 4 --grid entry-score=80,90 --grid max-leverage=5,10 -- --preset demo
