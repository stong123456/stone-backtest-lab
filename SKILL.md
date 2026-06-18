---
name: hermes-backtest-lab
description: Build and run an open-source local crypto backtest lab for OKX and Bitget public market data plus GeckoTerminal on-chain DEX candles. Use when the user wants to backtest arbitrary OKX/Bitget spot or perpetual symbols, replay chain token or pool prices, analyze 90/180 day performance, compare factors, or generate a shareable non-secret report without using GetAgent or private exchange credentials.
---

# 石头量化回测实验室 v2.2

English name: Hermes Backtest Lab v2.2.

Use this skill to run a local, shareable crypto backtest that does not require API keys.

Current script version: `hermes-backtest-lab-v2.2.0`.

## Safety

- Uses OKX, Bitget, and GeckoTerminal public market endpoints only.
- Does not read `.env`, account files, API keys, Telegram tokens, or live positions.
- Writes only local reports, trade CSVs, metrics JSON, and optional HTML reports under the chosen output directory.
- Designed for research. Do not treat historical backtest performance as a live trading guarantee.

## Quick Start

Run from the skill folder or pass the script path explicitly:

```powershell
python .\scripts\hermes_backtest_lab.py --preset demo
```

Useful commands:

```powershell
# Print the short Chinese beginner menu.
python .\scripts\hermes_backtest_lab.py

# Show preset names and Chinese descriptions.
python .\scripts\hermes_backtest_lab.py --list-presets

# Preview the resolved config without downloading candles.
python .\scripts\hermes_backtest_lab.py --dry-run --preset balanced

# Print command recipes.
python .\scripts\hermes_backtest_lab.py --examples

# Print the full advanced parameter reference.
python .\scripts\hermes_backtest_lab.py --advanced-help
```

## Common Backtests

```powershell
# Beginner smoke test.
python .\scripts\hermes_backtest_lab.py --preset demo

# Balanced shared-portfolio replay.
python .\scripts\hermes_backtest_lab.py --preset balanced

# Use a text file with one symbol per line.
python .\scripts\hermes_backtest_lab.py --preset balanced --symbols-file examples\symbols_okx_bluechip.txt

# On-chain DEX token replay.
python .\scripts\hermes_backtest_lab.py --preset onchain-demo

# Windows one-click wrappers.
.\run_demo.ps1
.\run_balanced.ps1
.\run_onchain_demo.ps1
.\run_bitget_90d.ps1
```

## OKX Examples

```powershell
# Backtest OKX USDT perpetual symbols.
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI,LINK --inst-type SWAP --days 180 --bar 1H

# Backtest OKX spot symbols.
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SUI --inst-type SPOT --days 180 --bar 1H --allow-short false

# Use full OKX instIds directly.
python .\scripts\hermes_backtest_lab.py --symbols BTC-USDT-SWAP,ETH-USDT-SWAP --days 90 --bar 4H
```

## Bitget Examples

```powershell
# Backtest Bitget USDT perpetual symbols.
python .\scripts\hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H

# Backtest Bitget spot symbols.
python .\scripts\hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL --inst-type SPOT --allow-short false --base-leverage 1 --max-leverage 1 --days 90 --bar 1H

# Bitget hackathon-style shared portfolio replay.
python .\scripts\hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000
```

## On-chain Examples

```powershell
# Token mode: chain:token:contract. The script selects a high-liquidity pool from GeckoTerminal.
python .\scripts\hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H

# Pool mode: chain:pool:pool_address.
python .\scripts\hermes_backtest_lab.py --data-source geckoterminal --symbols base:pool:0xPOOL_ADDRESS --days 30 --bar 1H
```

## Workflow

1. Resolve symbols into OKX `instId`, Bitget symbols, or GeckoTerminal chain token/pool identifiers.
2. Fetch candles from OKX/Bitget public historical endpoints or GeckoTerminal public DEX OHLCV endpoints.
3. Build replay-safe indicators: EMA, RSI, ATR, Bollinger Bands, ADX, volume z-score, relative trend state.
4. Score long and short setups using Hermes-style trend and range logic.
5. Apply the optional oracle-180d profile layer: ATR/ADX bands, pullback-long and rebound-short style tags, late-extension rejection, leverage caps, margin scaling, fast adverse exits, large-margin ATR gates, volume-heat filters, and per-trade trend hold windows.
6. Simulate entries, dynamic margin, dynamic leverage, TP/SL, time exits, account-stop liquidation, fees, and slippage.
7. Write `report.md`, `trades.csv`, `metrics.json`, cached candle JSON, and optional `visual_report.html`.

## v2 Research Entry

Use `scripts/hermes_backtest_lab_v2.py` for:

- grid search
- genetic-style parameter search
- Walk-forward validation
- Monte Carlo robustness testing
- HTML optimizer reports

Examples are in:

```text
examples/commands.md
examples/v2_commands.md
```

## Reading Results

Focus on:

- Total return and max drawdown together.
- Win rate plus profit factor.
- Number of trades; too few trades can be sample noise.
- Consecutive losses and average loss.
- Factor attribution: whether winners really had stronger ADX, volume, trend slope, or range reversion.
