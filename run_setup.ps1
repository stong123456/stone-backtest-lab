$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
python -m pip install -r requirements.txt
python scripts/hermes_backtest_lab.py --version
