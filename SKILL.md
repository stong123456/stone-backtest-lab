---
name: hermes-backtest-lab
description: Build and run an open-source local crypto backtest lab for OKX public market data and GeckoTerminal on-chain DEX candles. Use when the user wants to backtest arbitrary OKX spot/perpetual symbols, replay chain token or pool prices, analyze 90/180 day performance, compare factors, or generate a shareable non-secret report without using GetAgent or private exchange credentials.
---

# 石头量化回测实验室 v2.1

English name: Hermes Backtest Lab v2.1.

Use this skill to run a local, shareable crypto backtest that does not require API keys.

Current script version: `hermes-backtest-lab-v2.1.0`.

## Safety

- Uses OKX public market endpoints only.
- Does not read `.env`, account files, API keys, Telegram tokens, or live positions.
- Writes only local reports, trade CSVs, and metrics JSON under the chosen output directory.
- Designed for research. Do not treat historical backtest performance as a live trading guarantee.

## Quick Start

Run from the skill folder or pass the script path explicitly:

```powershell
python .\scripts\hermes_backtest_lab.py --preset demo
```

Useful examples:

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

# Backtest any OKX USDT perpetual symbols.
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI,LINK --inst-type SWAP --days 180 --bar 1H

# Backtest OKX spot symbols.
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SUI --inst-type SPOT --days 180 --bar 1H --allow-short false

# Use full OKX instIds directly.
python .\scripts\hermes_backtest_lab.py --symbols BTC-USDT-SWAP,ETH-USDT-SWAP --days 90 --bar 4H

# Test short-only or long-only variants.
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SOL --inst-type SWAP --days 180 --allow-long false
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SOL --inst-type SWAP --days 180 --allow-short false

# Make entries stricter and costs higher.
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH --days 180 --entry-score 90 --fee-bps 5 --slippage-bps 5

# Use one shared portfolio account instead of splitting capital by symbol.
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI,LINK --inst-type SWAP --days 180 --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000
```

## Workflow

1. Resolve symbols into OKX `instId` or GeckoTerminal chain token/pool identifiers.
2. Fetch candles from OKX public historical endpoints or GeckoTerminal public DEX OHLCV endpoints.
3. Build replay-safe indicators: EMA, RSI, ATR, Bollinger Bands, ADX, volume z-score, relative trend state.
4. Score long and short setups using Hermes-style trend and range logic.
5. Apply the optional oracle-180d profile layer: ATR/ADX bands, pullback-long and rebound-short style tags, late-extension rejection, leverage caps, margin scaling, fast adverse exits, large-margin ATR gates, volume-heat filters, and per-trade trend hold windows.
6. Simulate entries, dynamic margin, dynamic leverage, TP/SL, time exits, account-stop liquidation, fees, and slippage.
7. Write:
   - `report.md`
   - `trades.csv`
   - `metrics.json`
   - cached candle JSON under `cache/`

## Public Presets

- `demo`: 30-day BTC/ETH smoke test.
- `conservative`: blue-chip perpetuals, lower exposure, stricter ATR.
- `balanced`: default public 180-day portfolio replay.
- `aggressive`: higher-volatility altcoin/meme research preset.
- `spot`: spot-only long replay.
- `onchain-demo`: Base WETH token replay through GeckoTerminal.

## Reading Results

Focus on:

- Total return and max drawdown together.
- Win rate plus profit factor.
- Number of trades; too few trades can be sample noise.
- Consecutive losses and average loss.
- Factor attribution: whether winners really had stronger ADX, volume, trend slope, or range reversion.

## Suggested 180 Day Review

Use broad symbols first:

```powershell
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI,LINK,BNB,XRP,DOGE,ADA,AVAX,NEAR,APT,ARB,OP,LTC,TRX,DOT,UNI,AAVE --inst-type SWAP --days 180 --bar 1H
```

Then compare stricter gates:

```powershell
python .\scripts\hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI,LINK --inst-type SWAP --days 180 --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000 --entry-score 90 --bt-large-margin-min-atr-pct 1.8 --oracle-trend-hold-bars 48
```
