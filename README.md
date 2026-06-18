# 石头量化回测实验室 v2.2

英文名：Hermes Backtest Lab v2.2

一个不需要 API Key 的本地加密货币回测工具。它不是交易所机器人，也不会读取你的账户信息，只做一件事：把交易想法放进真实历史 K 线里，加入手续费、滑点、杠杆、仓位和风控约束后，看看数据是否还能站得住。

## v2.2 黑客松重点更新：Bitget 数据源正式接入

这版专门补强了交易 Agent / 黑客松展示能力：

- 支持 Bitget 公开行情数据回测，无需 API Key。
- 支持 Bitget USDT 永续合约，适合多空双向策略验证。
- 支持 Bitget 现货，只做多策略也可以单独跑。
- 支持多币种组合账户回测，可以一次跑 BTC、ETH、SOL、SUI 等组合。
- 可视化报告支持 Bitget 标的下拉切换、全周期 K 线、入场/出场标记、K 线缩放拖动。
- 交易标记按真实 K 线时间定位，缩放时标记保持固定大小，更适合截图、路演和评审展示。

一句话：现在它不只是 OKX / 链上回测工具，也可以作为 Bitget Agent Hub / GetAgent 策略验证前的本地回测实验室。

## 项目定位

很多策略听起来很聪明，但真正上线前要先回答几个冷冰冰的问题：

- 加上手续费和滑点后还赚钱吗？
- 收益是不是只靠一两笔大单撑起来？
- 最大回撤能不能接受？
- 换一批币、换一个周期还能不能活？
- 胜率、盈亏比、交易次数是否足够可信？

石头量化回测实验室就是这个“质检员”。它使用 OKX、Bitget 公开 K 线数据和 GeckoTerminal 公开 DEX 数据，支持现货、USDT 永续合约、多链链上 token、多币种组合账户回测、手续费/滑点建模、动态杠杆、动态保证金、止盈止损、时间退出、因子归因和报告导出。

> 免责声明：历史回测不代表未来收益。本项目只用于研究和教学，不构成投资建议。

## 核心功能

- OKX 现货和 USDT 永续合约回测。
- Bitget 现货和 USDT 永续合约回测。
- GeckoTerminal 链上 token / DEX pool 回测。
- 单币种回测或多币种共享账户组合回测。
- 支持多空双向、只做多、只做空。
- 内置趋势跟踪和震荡均值回归逻辑。
- 内置 EMA、RSI、ATR、ADX、布林带、成交量 z-score 等常用因子。
- 支持手续费、滑点、最大持仓、账户回撤熔断、动态杠杆、动态保证金。
- 输出 `report.md`、`metrics.json`、`trades.csv`。
- 输出漂亮的 `visual_report.html`，包含收益曲线、回撤、K 线、交易标记、全部交易明细。
- v2 研究入口支持参数网格搜索、遗传算法风格优化、Walk-forward、Monte Carlo 鲁棒性测试。
- 不读取 `.env`、交易所账户、私钥、API Key 或 Telegram Token。

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

- `report.md`：适合人看的回测报告。
- `metrics.json`：适合程序读取的指标。
- `trades.csv`：逐笔模拟交易明细。
- `visual_report.html`：可视化网页报告。

## 黑客松 / Bitget 快速命令

Bitget USDT 永续合约，90 天多币种组合回测：

```powershell
python scripts/hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL,SUI --inst-type SWAP --days 90 --bar 1H --portfolio-mode 1 --starting-balance 100000 --min-margin 2000 --max-margin 5000
```

Bitget 现货，只做多：

```powershell
python scripts/hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL --inst-type SPOT --allow-short 0 --base-leverage 1 --max-leverage 1 --days 90 --bar 1H
```

Bitget 指定真实日期窗口：

```powershell
python scripts/hermes_backtest_lab.py --data-source bitget --symbols BTC,ETH,SOL --inst-type SWAP --start-date 2026-04-01 --end-date 2026-06-01 --bar 1H
```

Windows 一键跑 Bitget 示例：

```powershell
.\run_bitget_90d.ps1
```

## 常用预设

```powershell
# 查看所有预设和中文解释
python scripts/hermes_backtest_lab.py --list-presets

# 只看配置，不联网、不回测
python scripts/hermes_backtest_lab.py --dry-run --preset balanced

# 30 天快速检查
python scripts/hermes_backtest_lab.py --preset demo

# 180 天均衡组合回测
python scripts/hermes_backtest_lab.py --preset balanced

# 更保守，只跑主流币
python scripts/hermes_backtest_lab.py --preset conservative

# 更激进，加入更多高波动标的
python scripts/hermes_backtest_lab.py --preset aggressive

# 现货只做多
python scripts/hermes_backtest_lab.py --preset spot

# 链上 token 示例
python scripts/hermes_backtest_lab.py --preset onchain-demo
```

## OKX 示例

任意 OKX USDT 永续：

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SUI,LINK --inst-type SWAP --days 180 --bar 1H
```

直接传 OKX instId：

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC-USDT-SWAP,ETH-USDT-SWAP --days 90 --bar 4H
```

OKX 现货回测：

```powershell
python scripts/hermes_backtest_lab.py --symbols BTC,ETH,SOL --inst-type SPOT --allow-short 0 --days 180
```

## 链上 token 示例

Base 链 WETH token：

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H
```

直接指定 DEX pool：

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:pool:0xPOOL_ADDRESS --days 30 --bar 1H
```

链上高滑点研究：

```powershell
python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006 --days 30 --bar 1H --slippage-bps 30 --fee-bps 10
```

## 使用 TXT 管理币种

每行一个币种，支持 `#` 注释：

```text
BTC
ETH
SOL
SUI
```

运行：

```powershell
python scripts/hermes_backtest_lab.py --preset balanced --symbols-file examples/symbols_okx_bluechip.txt
python scripts/hermes_backtest_lab.py --data-source bitget --symbols-file examples/symbols_bitget_bluechip.txt --inst-type SWAP --days 90
```

## 重要参数

| 参数 | 说明 |
|---|---|
| `--data-source` | 数据源：`okx`、`bitget`、`geckoterminal` |
| `--symbols` | 币种列表，例如 `BTC,ETH`、`BTC-USDT-SWAP`、`BTCUSDT` |
| `--symbols-file` | UTF-8 文本文件，每行一个标的 |
| `--inst-type` | `SWAP` 或 `SPOT` |
| `--bitget-product-type` | Bitget 合约产品线，默认 `USDT-FUTURES` |
| `--days` | 回测天数 |
| `--start-date` | 指定开始时间，适合严谨复盘和 Walk-forward |
| `--end-date` | 指定结束时间 |
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

查看更多：

```powershell
python scripts/hermes_backtest_lab.py --examples
python scripts/hermes_backtest_lab.py --advanced-help
```

## v2 研究优化入口

`scripts/hermes_backtest_lab_v2.py` 是研究优化入口，用来调度核心引擎做参数优化和鲁棒性分析。

网格搜索：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --limit 6 --grid entry-score=80,90 --grid max-leverage=5,10 -- --preset demo
```

遗传算法风格优化：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode genetic --population 10 --generations 3 --limit 24 -- --preset balanced
```

Monte Carlo：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode monte-carlo --sims 500 -- --preset balanced
```

Walk-forward：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode walk-forward --walk-start-date 2026-01-01 --train-days 90 --test-days 30 --step-days 30 --walk-windows 3 -- --preset balanced
```

如果不想自动打开浏览器：

```powershell
python scripts/hermes_backtest_lab_v2.py --mode grid --no-open-report --limit 6 --grid entry-score=80,90 -- --preset demo
```

更多命令见：

```text
examples/commands.md
examples/v2_commands.md
```

## 可视化报告

每次核心回测会自动生成 `visual_report.html`。你也可以对已有回测目录重新生成：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id>
```

只生成文件，不自动打开：

```powershell
python scripts/render_visual_report.py --run-dir outputs/hermes_backtest_lab/<run_id> --no-open
```

报告包含：

- 总收益、胜率、Profit Factor、最大回撤。
- 资金曲线和回撤曲线。
- K 线与交易标记，支持代币切换、缩放、拖动。
- 全部交易明细。
- 因子差异和策略复盘信息。
- 创作者入口：`@Stone141319` 头像和 X 主页链接。

## 如何看结果

不要只看胜率。建议优先看：

- 总收益和最大回撤是否匹配。
- Profit Factor 是否大于 1。
- 平均盈利是否明显大于平均亏损。
- 交易次数是否足够，不要被小样本骗。
- 盈利是否集中在少数几天或少数币。
- 加入手续费和滑点后是否仍然有效。

## 分享报告

已经上传的示例报告：

- GitHub 文件：`docs/reports/bitget_90d_hermes_auto_20260618.html`
- 在线预览：https://htmlpreview.github.io/?https://github.com/stong123456/stone-backtest-lab/blob/main/docs/reports/bitget_90d_hermes_auto_20260618.html

如果你开启 GitHub Pages，可以使用更短链接：

```text
https://stong123456.github.io/stone-backtest-lab/reports/bitget_90d_hermes_auto_20260618.html
```

## 开源安全说明

建议提交：

- `README.md`
- `SKILL.md`
- `requirements.txt`
- `scripts/`
- `examples/`
- `assets/`
- `docs/reports/`
- `run_*.ps1`、`run_*.bat`
- `.gitignore`

不要提交：

- `outputs/`
- `runtime-logs/`
- `cache/`
- `.env`
- API Key、Telegram Token、交易所账户文件

本项目默认 `.gitignore` 已忽略这些敏感或临时目录。
