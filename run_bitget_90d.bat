@echo off
cd /d "%~dp0"
python scripts\hermes_backtest_lab.py --data-source bitget --symbols-file examples\symbols_bitget_bluechip.txt --inst-type SWAP --days 90 --bar 1H --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000
