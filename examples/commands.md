# 石头量化回测实验室 v2.2 命令手册

这些命令都不需要 API Key，只使用公开市场数据。支持 OKX、Bitget 和 GeckoTerminal 链上 K 线。

## 1. 环境检查

```powershell
python scripts/hermes_backtest_lab.py --version
python scripts/hermes_backtest_lab.py
python scripts/hermes_backtest_lab.py --list-presets
python scripts/hermes_backtest_lab.py --dry-run --preset balanced
python scripts/hermes_backtest_lab.py --help
python scripts/hermes_backtest_lab.py --advanced-help
python scripts/hermes_backtest_lab.py --examples
```

## 2. 新手一键运行

```powershell
python scripts/hermes_backtest_lab.py --preset demo
```

Windows：

```powershell
.\run_demo.ps1
.\run_demo.bat
```

## 3. Bitget 黑客松示例

Bitget USDT 永续，90 天，多币种组合账户：

```powershell
python scripts/hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000
```

Bitget 现货，只做多：

```powershell
python scripts/hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL --inst-type SPOT --allow-short 0 --base-leverage 1 --max-leverage 1 --days 90 --bar 1H
```

Bitget 指定日期窗口：

```powershell
python scripts/hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL --inst-type SWAP --start-date 2026-04-01 --end-date 2026-06-01 --bar 1H
```

Windows 一键跑：

```powershell
.\run_bitget_90d.ps1
.\run_bitget_90d.bat
```

## 4. OKX 组合账户回测

```powershell
python scripts/hermes_backtest_lab.py --preset balanced
```

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL,BNB,LINK,AAVE --inst-type SWAP --portfolio-mode 1 --starting-balance 100000 --min-margin 1000 --max-margin 3000 --days 180
```

Windows：

```powershell
.\run_balanced.ps1
```

## 5. 用 TXT 管理币种

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --symbols-file examples/symbols_okx_bluechip.txt
python scripts/hermes_backtest_lab.py --data-source bitget --symbols-file examples/symbols_bitget_bluechip.txt --inst-type SWAP --days 90
```

文件格式很简单，每行一个币种：

```text
BTC
ETH
SOL
BNB
```

## 6. 保守版

```powershell
python scripts/hermes_backtest_lab.py --preset conservative
```

适合先看主流币、低杠杆、低持仓暴露。

## 7. 激进版

```powershell
python scripts/hermes_backtest_lab.py --preset aggressive
```

适合研究高波动标的。不要直接拿这套参数上实盘。

## 8. 现货只做多

OKX：

```powershell
python scripts/hermes_backtest_lab.py --preset spot
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI --inst-type SPOT --allow-short 0 --days 180
```

Bitget：

```powershell
python scripts/hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL --inst-type SPOT --allow-short 0 --base-leverage 1 --max-leverage 1 --days 90
```

## 9. 链上 token 回测

```powershell
python scripts/hermes_backtest_lab.py --preset onchain-demo
```

```powershell
.\run_onchain_demo.ps1
```

Base 链 WETH：

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H --allow-short 0
```

多个链上 token：

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols-file examples/symbols_onchain_base.txt --days 30 --bar 1H --allow-short 0
```

直接指定 DEX 池：

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:pool:0xPOOL_ADDRESS --days 30 --bar 1H
```

链上高滑点研究：

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H --slippage-bps 30 --fee-bps 10
```

## 10. 多空方向控制

只做空：

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL --inst-type SWAP --allow-long 0 --allow-short 1 --days 180
```

只做多：

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL --inst-type SWAP --allow-long 1 --allow-short 0 --days 180
```

## 11. 成本压力测试

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --fee-bps 8 --slippage-bps 8
```

如果加完成本策略直接失效，说明它可能只赚纸面波动。

## 12. 杠杆和仓位

降低杠杆：

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --max-leverage 8 --base-leverage 3
```

放大本金和单笔保证金：

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI --inst-type SWAP --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000 --days 180
```

## 13. 入场门槛

收紧入场：

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --entry-score 95 --bt-large-margin-min-atr-pct 2.0
```

放宽入场：

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --entry-score 80 --bt-large-margin-min-atr-pct 1.4
```

放宽入场通常会提高交易次数，也会提高回撤和手续费消耗。

## 14. 重新拉取数据

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --refresh
```

## 15. 生成或重建可视化报告

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id>
```

不自动打开浏览器：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id> --no-open
```

## 16. 输出文件

每次运行会生成一个时间戳目录：

```text
outputs/hermes_backtest_lab/YYYYMMDD-HHMMSS/
```

里面包含：

```text
report.md
metrics.json
trades.csv
visual_report.html
```

最适合分享的是 `visual_report.html`。  
适合二次分析的是 `trades.csv`。  
适合程序读取的是 `metrics.json`。
