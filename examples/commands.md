# 石头量化回测实验室命令手册

这些命令都不需要 API Key，只使用 OKX 公开市场数据。

## 环境检查

```powershell
python scripts/hermes_backtest_lab.py --version
python scripts/hermes_backtest_lab.py
python scripts/hermes_backtest_lab.py --list-presets
python scripts/hermes_backtest_lab.py --dry-run --preset balanced
python scripts/hermes_backtest_lab.py --help
python scripts/hermes_backtest_lab.py --advanced-help
python scripts/hermes_backtest_lab.py --examples
```

## 新手一键运行

```powershell
python scripts/hermes_backtest_lab.py --preset demo
```

Windows 用户也可以直接运行：

```powershell
.\run_demo.ps1
.\run_demo.bat
```

## 组合账户回测

```powershell
python scripts/hermes_backtest_lab.py --preset balanced
```

```powershell
.\run_balanced.ps1
```

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL,BNB,LINK,AAVE --inst-type SWAP --portfolio-mode 1 --starting-balance 100000 --min-margin 1000 --max-margin 3000 --days 180
```

## 用 TXT 管理币种

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --symbols-file examples/symbols_okx_bluechip.txt
```

格式很简单，每行一个币种：

```text
BTC
ETH
SOL
BNB
```

## 保守版

```powershell
python scripts/hermes_backtest_lab.py --preset conservative
```

适合想先看主流币、低杠杆、低持仓暴露的人。

## 激进版

```powershell
python scripts/hermes_backtest_lab.py --preset aggressive
```

适合研究高波动标的。不要直接拿这套参数上实盘。

## 现货只做多

```powershell
python scripts/hermes_backtest_lab.py --preset spot
```

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI --inst-type SPOT --allow-short 0 --days 180
```

## 链上 token 回测

```powershell
python scripts/hermes_backtest_lab.py --preset onchain-demo
```

```powershell
.\run_onchain_demo.ps1
```

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H --allow-short 0
```

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols-file examples/symbols_onchain_base.txt --days 30 --bar 1H --allow-short 0
```

## 链上多 token 组合

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols eth:token:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,base:token:0x4200000000000000000000000000000000000006 --portfolio-mode 1 --starting-balance 10000 --min-margin 100 --max-margin 500 --days 30 --bar 1H
```

## 直接指定 DEX 池子

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:pool:0xPOOL_ADDRESS --days 30 --bar 1H
```

## 链上高滑点研究

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H --slippage-bps 30 --fee-bps 10
```

## 只做空

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL --inst-type SWAP --allow-long 0 --allow-short 1 --days 180
```

## 只做多

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL --inst-type SWAP --allow-long 1 --allow-short 0 --days 180
```

## 调高手续费和滑点

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --fee-bps 8 --slippage-bps 8
```

如果加完成本策略直接失效，说明它可能只赚纸面波动。

## 降低杠杆

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --max-leverage 8 --base-leverage 3
```

## 收紧入场

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --entry-score 95 --bt-large-margin-min-atr-pct 2.0
```

## 放宽入场

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --entry-score 80 --bt-large-margin-min-atr-pct 1.4
```

放宽入场通常会提高交易次数，也会提高回撤和手续费消耗。

## 重新拉取数据

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --refresh
```

## 输出文件

每次运行会生成一个时间戳目录：

```text
outputs/hermes_backtest_lab/YYYYMMDD-HHMMSS/
```

里面包含：

```text
report.md
metrics.json
trades.csv
```

## 分享报告

最适合分享的是 `report.md`。

如果要做二次分析，用 `trades.csv`。

如果要接入其他程序，用 `metrics.json`。
