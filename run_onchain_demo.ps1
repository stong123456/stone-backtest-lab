$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
python scripts/hermes_backtest_lab.py --preset onchain-demo
