# Hermes Backtest Lab v2.2 研究优化命令手册

v2.2 是当前唯一维护的最新版。它包含核心回测引擎和研究优化入口，可以用于参数优化、Walk-forward、Monte Carlo、HTML/PDF 报告和交易级可视化复盘。

默认行为：运行结束后会自动打开 HTML 报告。  
如果不想弹出浏览器，在 `--mode` 后加 `--no-open-report`。

## 1. 网格搜索

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --limit 12 --grid entry-score=80,85,90 --grid max-leverage=5,10 -- --preset demo
```

不自动打开浏览器：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --no-open-report --limit 12 --grid entry-score=80,85,90 --grid max-leverage=5,10 -- --preset demo
```

## 2. Bitget 参数网格搜索

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --limit 12 --grid entry-score=80,85,90 --grid max-leverage=5,10 -- --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000
```

## 3. 遗传算法风格优化

```powershell
python scripts/hermes_backtest_lab_v2.py --mode genetic --population 10 --generations 3 --limit 24 -- --preset balanced
```

Bitget 版本：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode genetic --population 10 --generations 3 --limit 24 -- --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H
```

## 4. Walk-forward 真实滚动验证

训练窗口挑参数，验证窗口复测。v2.2 会把 `--start-date` / `--end-date` 传给核心回测引擎，所以这里是真正的滚动训练和验证窗口。

```powershell
python scripts/hermes_backtest_lab_v2.py --mode walk-forward --walk-windows 3 --walk-candidates 8 -- --preset balanced
```

指定第一段训练窗口起点：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode walk-forward --walk-start-date 2026-01-01 --train-days 90 --test-days 30 --step-days 30 --walk-windows 3 -- --preset balanced
```

Bitget Walk-forward：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode walk-forward --walk-start-date 2026-03-01 --train-days 45 --test-days 15 --step-days 15 --walk-windows 3 --walk-candidates 8 -- --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --bar 1H
```

窗口含义示例：

```text
第 1 窗：2026-01-01 到 2026-04-01 训练，2026-04-01 到 2026-05-01 验证
第 2 窗：向前滚动 30 天
第 3 窗：继续向前滚动 30 天
```

## 5. Monte Carlo 鲁棒性测试

随机重排 / 抽样交易盈亏，观察收益分布、尾部回撤和破产概率。

```powershell
python scripts/hermes_backtest_lab_v2.py --mode monte-carlo --sims 500 -- --preset balanced
```

Bitget Monte Carlo：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode monte-carlo --sims 500 -- --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H
```

## 6. 输出目录

```text
outputs/hermes_backtest_lab_v2/
```

常见文件：

```text
optimizer_report.html
walk_forward_report.html
monte_carlo_report.html
optimizer_summary.json
walk_forward_summary.json
monte_carlo_summary.json
optimizer_runs.csv
walk_forward_windows.csv
```

HTML 报告可以直接用浏览器打开，也可以打印成 PDF。

每个实际回测子目录还会自动生成：

```text
visual_report.html
```

这个页面包含收益卡片、资金曲线、回撤曲线、盈亏分布、K 线入场标记、因子差异和全部交易明细。v2 汇总页的表格里会显示“打开页面报告”链接，可以直接跳到对应参数组合的完整复盘页。

## 7. 单独重建页面报告

如果你已经有一份核心回测结果，可以单独生成页面报告：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id>
```

只生成文件、不自动打开：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id> --no-open
```

## 8. 适合评审看的组合命令

先跑 Bitget 90 天回测：

```powershell
python scripts/hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000
```

再跑参数搜索：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --limit 12 --grid entry-score=80,85,90 --grid max-leverage=5,10 -- --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H
```

最后跑 Monte Carlo：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode monte-carlo --sims 500 -- --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H
```
