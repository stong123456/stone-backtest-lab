# Hermes Backtest Lab v2.0 命令手册

v2.0 是研究层，不替代 v1 主回测器。它会多次调用 `scripts/hermes_backtest_lab.py`，用于参数优化、Walk-forward、Monte Carlo 和 HTML 报告。

默认行为：运行结束后会自动打开主 HTML 报告。  
如果不想弹出浏览器，在 `--mode` 后加 `--no-open-report`。

## 网格搜索

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --limit 12 --grid entry-score=80,85,90 --grid max-leverage=5,10 -- --preset demo
```

不自动打开浏览器：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --no-open-report --limit 12 --grid entry-score=80,85,90 --grid max-leverage=5,10 -- --preset demo
```

## 遗传算法风格优化

```powershell
python scripts/hermes_backtest_lab_v2.py --mode genetic --population 10 --generations 3 --limit 24 -- --preset balanced
```

## Walk-forward 近似验证

训练窗口挑参数，验证窗口复测。

```powershell
python scripts/hermes_backtest_lab_v2.py --mode walk-forward --walk-windows 3 --walk-candidates 8 -- --preset balanced
```

## Monte Carlo 鲁棒性测试

随机抽样交易盈亏，观察收益分布、尾部回撤和破产概率。

```powershell
python scripts/hermes_backtest_lab_v2.py --mode monte-carlo --sims 500 -- --preset balanced
```

## 输出

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

如果你已经有一份 v1 回测结果，也可以单独生成页面报告：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id>
```

只生成文件、不自动打开：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id> --no-open
```
