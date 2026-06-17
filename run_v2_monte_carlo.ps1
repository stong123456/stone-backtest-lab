$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python scripts/hermes_backtest_lab_v2.py --mode monte-carlo --sims 300 -- --preset demo
