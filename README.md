# 石头量化回测实验室 v2.1

英文名：Hermes Backtest Lab v2.1。

一个不需要 API Key 的本地加密货币回测工具。

它使用 OKX 公开 K 线数据和 GeckoTerminal 公开 DEX 数据，支持现货、USDT 永续合约、多链链上 token、多币种组合账户回测、手续费/滑点建模、动态杠杆、动态保证金、止盈止损、时间退出、因子归因和报告导出。

> 这不是投资建议。历史回测不代表未来收益。请先用小样本和模拟盘验证。

## 功能

- 任意 OKX 现货或 USDT 永续合约符号回测
- 任意 GeckoTerminal 支持的链上 token 或 DEX pool 回测
- 单币种回测或多币种组合账户回测
- 支持多空双向、只做多、只做空
- 内置趋势跟踪和震荡均值回归逻辑
- 内置 ATR、ADX、RSI、EMA、布林带、成交量 z-score 等指标
- 支持手续费、滑点、最大持仓、账户回撤熔断
- 输出 `report.md`、`metrics.json`、`trades.csv`
- 不读取 `.env`、交易所账户、私钥、API Key 或 Telegram Token

## 安装

需要 Python 3.10+。

```powershell
cd hermes-backtest-lab
python -m pip install -r requirements.txt
```

Windows 用户也可以直接运行：

```powershell
.\run_setup.ps1
```

## 最快开始

```powershell
python scripts/hermes_backtest_lab.py --preset demo
```

如果不知道该用什么命令，先看中文短菜单：

```powershell
python scripts/hermes_backtest_lab.py
```

运行后会在 `outputs/hermes_backtest_lab/<时间戳>/` 生成：

- `report.md`：适合人看的回测报告
- `metrics.json`：适合程序读取的指标
- `trades.csv`：每一笔模拟交易明细

## 常用预设

```powershell
# 查看所有预设和中文解释
python scripts/hermes_backtest_lab.py --list-presets

# 只看配置，不联网、不回测
python scripts/hermes_backtest_lab.py --dry-run --preset balanced

# 30 天快速检查，适合确认环境是否正常
python scripts/hermes_backtest_lab.py --preset demo

# 180 天均衡组合回测
python scripts/hermes_backtest_lab.py --preset balanced

# 更保守，只跑主流币，降低组合暴露
python scripts/hermes_backtest_lab.py --preset conservative

# 更激进，加入更多高波动标的
python scripts/hermes_backtest_lab.py --preset aggressive

# 现货只做多
python scripts/hermes_backtest_lab.py --preset spot
```

```powershell
# 链上 token 回测，自动选择流动性最高的池子
python scripts/hermes_backtest_lab.py --preset onchain-demo

# Base 链 WETH token
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H

# 直接指定某个 DEX pool
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:pool:0xPOOL_ADDRESS --days 30 --bar 1H
```

你可以覆盖预设里的任何参数：

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --symbols BTC,ETH,SOL --days 90 --max-leverage 8
```

也可以把币种放进 txt 文件，每行一个，方便普通用户维护：

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --symbols-file examples/symbols_okx_bluechip.txt
```

Windows 一键脚本：

```powershell
.\run_demo.ps1
.\run_balanced.ps1
.\run_onchain_demo.ps1
```

## 自定义回测

```powershell
# 任意 OKX USDT 永续
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SUI,LINK --inst-type SWAP --days 180 --bar 1H

# 指定真实日期窗口，适合严谨复盘和 Walk-forward 验证
python scripts/hermes_backtest_lab.py --symbols BTC,ETH --inst-type SWAP --start-date 2026-01-01 --end-date 2026-03-31 --bar 1H

# 直接传 OKX instId
python scripts/hermes_backtest_lab.py --symbols BTC-USDT-SWAP,ETH-USDT-SWAP --days 90 --bar 4H

# 现货回测
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL --inst-type SPOT --allow-short 0 --days 180

# 链上 token。格式为 chain:token:contract，脚本会自动选择流动性最高的池子。
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols eth:token:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H

# 链上池子。格式为 chain:pool:pool_address。
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols solana:pool:POOL_ADDRESS --days 30 --bar 1H

# 多币种共享一个账户，不按币种拆分本金
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL,SUI,LINK --inst-type SWAP --portfolio-mode 1 --starting-balance 100000 --min-margin 1000 --max-margin 3000
```

## 重要参数

| 参数 | 说明 |
|---|---|
| `--symbols` | 币种列表，支持 `BTC,ETH` 或 `BTC-USDT-SWAP` |
| `--data-source` | 数据源，`okx` 或 `geckoterminal` |
| `--inst-type` | `SWAP` 或 `SPOT` |
| `--onchain-network` | 默认链上网络，例如 `eth`、`bsc`、`base`、`solana` |
| `--onchain-id-type` | 默认链上地址类型，`token` 或 `pool` |
| `--gecko-currency` | GeckoTerminal 计价货币，默认 `usd` |
| `--gecko-token-side` | 池子里使用 `base` 还是 `quote` token 的 OHLCV |
| `--days` | 回测天数 |
| `--bar` | K 线周期，例如 `1H`、`4H`、`1D` |
| `--portfolio-mode` | 是否使用共享组合账户 |
| `--starting-balance` | 初始本金 |
| `--min-margin` | 单笔最低保证金或名义资金单位 |
| `--max-margin` | 单笔最高保证金或名义资金单位 |
| `--max-leverage` | 最高杠杆 |
| `--entry-score` | 入场最低分 |
| `--fee-bps` | 单边手续费，bps |
| `--slippage-bps` | 单边滑点，bps |
| `--reward-r` | 止盈 R 倍数 |
| `--account-stop-pct` | 账户回撤熔断比例 |
| `--refresh` | 重新拉取公开 K 线，忽略缓存 |

## 查看更多命令

```powershell
python scripts/hermes_backtest_lab.py
python scripts/hermes_backtest_lab.py --list-presets
python scripts/hermes_backtest_lab.py --examples
python scripts/hermes_backtest_lab.py --advanced-help
```

## 结果怎么看

不要只看胜率。优先看：

- 总收益和最大回撤是否匹配
- Profit Factor 是否大于 1
- 平均盈利是否明显大于平均亏损
- 交易次数是否足够，不要被小样本骗
- 盈利是否集中在少数几天或少数币
- 加入手续费和滑点后是否仍然有效

## 链上数据注意事项

- token 模式会自动选择 GeckoTerminal 返回的最高流动性池子，不一定等于你主观想交易的那个池子。
- pool 模式更精确，适合你已经知道目标池子地址的情况。
- 新币、小池子、低流动性池子的 K 线可能不完整，报告里会显示数据警告。
- 链上回测默认只是价格序列研究，没有模拟 MEV、gas、池子冲击成本、买卖税、黑名单、暂停交易、路由失败等真实链上执行风险。
- Meme 和小盘 token 的滑点建议手动调高，例如 `--slippage-bps 30` 或更高。

## 开源分享建议

如果你要发到 GitHub，建议只提交这些内容：

- `README.md`
- `SKILL.md`
- `requirements.txt`
- `scripts/hermes_backtest_lab.py`
- `scripts/hermes_backtest_lab_v2.py`
- `scripts/render_visual_report.py`
- `examples/commands.md`
- `examples/v2_commands.md`
- `run_v2_grid.ps1`
- `run_v2_monte_carlo.ps1`
- `run_v2_walk_forward.ps1`
- `.gitignore`

不要提交：

- `outputs/`
- `runtime-logs/`
- `cache/`
- `.env`
- API Key、Telegram Token、交易所账户文件

## Hermes Backtest Lab v2.1

这是当前唯一维护的最新版。工具内部有两个入口：`scripts/hermes_backtest_lab.py` 是核心回测引擎，`scripts/hermes_backtest_lab_v2.py` 是研究优化入口，用来调度核心引擎做参数优化和鲁棒性分析。

核心能力：

- Walk-forward 优化：训练窗口挑参数，验证窗口复测。
- 真实日期窗口：核心引擎支持 `--start-date` / `--end-date`，Walk-forward 使用真实滚动训练和验证区间。
- 参数网格搜索：支持多因子组合扫描。
- 遗传算法风格优化：参数很多时先做探索式搜索。
- Monte Carlo 模拟：随机抽样交易盈亏，观察尾部风险和破产概率。
- 多策略/多参数组合对比：把不同参数组当成候选策略自动排名。
- HTML 报告：生成 `optimizer_report.html`、`walk_forward_report.html`、`monte_carlo_report.html`，可用浏览器打印成 PDF。
- 交易级页面报告：每一次实际回测都会生成 `visual_report.html`，包含收益卡片、资金曲线、回撤曲线、盈亏分布、K 线入场标记、因子差异和全部交易明细。
- 自动弹出报告：研究优化入口默认会打开主 HTML 汇总页；单独渲染 `visual_report.html` 也会默认打开浏览器。

快速示例：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --limit 6 --grid entry-score=80,90 --grid max-leverage=5,10 -- --preset demo
```

如果你在服务器或不想弹出浏览器，加上：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --no-open-report --limit 6 --grid entry-score=80,90 --grid max-leverage=5,10 -- --preset demo
```

Monte Carlo：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode monte-carlo --sims 500 -- --preset balanced
```

Walk-forward：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode walk-forward --walk-windows 3 --walk-candidates 8 -- --preset balanced
```

指定真实滚动窗口起点：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode walk-forward --walk-start-date 2026-01-01 --train-days 90 --test-days 30 --step-days 30 --walk-windows 3 -- --preset balanced
```

更多命令见：

```text
examples/v2_commands.md
```

如果只想把某次核心回测结果转成漂亮页面报告：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id>
```

如果只生成文件、不自动打开：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id> --no-open
```
