#!/usr/bin/env python
"""Render a self-contained HTML report for Hermes Backtest Lab runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fmt_money(value: float) -> str:
    return f"{value:,.2f} U"


def fmt_pct(value: float) -> str:
    return f"{value:,.2f}%"


def fmt_time(ms: int) -> str:
    if not ms:
        return "-"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_trades(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["_entry_ts"] = as_int(row.get("entry_ts"))
        row["_exit_ts"] = as_int(row.get("exit_ts"))
        row["_pnl"] = as_float(row.get("pnl_usdt"))
        row["_score"] = as_float(row.get("score"))
        row["_margin"] = as_float(row.get("margin"))
        row["_notional"] = as_float(row.get("notional"))
        row["_entry"] = as_float(row.get("entry"))
        row["_exit"] = as_float(row.get("exit"))
        row["_lev"] = as_float(row.get("leverage"))
        try:
            row["_features"] = json.loads(row.get("features") or "{}")
        except json.JSONDecodeError:
            row["_features"] = {}
    return rows


def load_candles(cache_dir: Path, inst_id: str) -> list[dict[str, float]]:
    name = inst_id.replace("-", "_") + "_1H_180d.json"
    path = cache_dir / name
    if not path.exists():
        return []
    payload = load_json(path)
    if isinstance(payload, dict):
        payload = payload.get("data") or payload.get("candles") or []
    candles: list[dict[str, float]] = []
    for item in payload:
        if isinstance(item, dict):
            ts = as_int(item.get("ts"))
            candles.append(
                {
                    "ts": ts,
                    "open": as_float(item.get("open")),
                    "high": as_float(item.get("high")),
                    "low": as_float(item.get("low")),
                    "close": as_float(item.get("close")),
                    "volume": as_float(item.get("volume")),
                }
            )
        elif isinstance(item, (list, tuple)) and len(item) >= 6:
            candles.append(
                {
                    "ts": as_int(item[0]),
                    "open": as_float(item[1]),
                    "high": as_float(item[2]),
                    "low": as_float(item[3]),
                    "close": as_float(item[4]),
                    "volume": as_float(item[5]),
                }
            )
    return sorted([c for c in candles if c["ts"]], key=lambda x: x["ts"])


def polyline(points: list[tuple[float, float]], width: int, height: int, pad: int = 28) -> str:
    if not points:
        return ""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if math.isclose(min_x, max_x):
        max_x += 1
    if math.isclose(min_y, max_y):
        max_y += 1
    scaled = []
    for x, y in points:
        sx = pad + (x - min_x) / (max_x - min_x) * (width - pad * 2)
        sy = height - pad - (y - min_y) / (max_y - min_y) * (height - pad * 2)
        scaled.append(f"{sx:.1f},{sy:.1f}")
    return " ".join(scaled)


def render_line_chart(
    points: list[tuple[float, float]],
    width: int,
    height: int,
    title: str,
    accent: str,
    fill: bool = False,
) -> str:
    if not points:
        return '<div class="empty">暂无数据</div>'
    line = polyline(points, width, height)
    area = ""
    if fill:
        first_x = line.split()[0].split(",")[0]
        last_x = line.split()[-1].split(",")[0]
        area = (
            f'<polygon points="{first_x},{height - 28} {line} {last_x},{height - 28}" '
            f'fill="{accent}" opacity="0.12"/>'
        )
    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{html.escape(title)}">
      <defs>
        <filter id="glow-{html.escape(title).replace(' ', '-')}">
          <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
          <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#081915"/>
      <g opacity="0.18" stroke="#c9f7df">
        <line x1="28" x2="{width - 28}" y1="{height * 0.25:.1f}" y2="{height * 0.25:.1f}"/>
        <line x1="28" x2="{width - 28}" y1="{height * 0.50:.1f}" y2="{height * 0.50:.1f}"/>
        <line x1="28" x2="{width - 28}" y1="{height * 0.75:.1f}" y2="{height * 0.75:.1f}"/>
      </g>
      {area}
      <polyline points="{line}" fill="none" stroke="{accent}" stroke-width="3.5" filter="url(#glow-{html.escape(title).replace(' ', '-')})"/>
    </svg>
    """


def build_equity_curve(trades: list[dict[str, Any]], start_balance: float) -> list[tuple[float, float]]:
    equity = start_balance
    curve = [(0.0, equity)]
    for index, trade in enumerate(sorted(trades, key=lambda x: (x["_exit_ts"], x["_entry_ts"]))):
        equity += trade["_pnl"]
        curve.append((float(index + 1), equity))
    return curve


def build_drawdown_curve(equity_curve: list[tuple[float, float]]) -> list[tuple[float, float]]:
    peak = -float("inf")
    out = []
    for x, equity in equity_curve:
        peak = max(peak, equity)
        dd = 0.0 if peak <= 0 else (equity / peak - 1.0) * 100
        out.append((x, dd))
    return out


def render_bar_chart(items: list[tuple[str, float]], width: int, height: int, accent: str) -> str:
    if not items:
        return '<div class="empty">暂无数据</div>'
    max_abs = max(abs(v) for _, v in items) or 1
    gap = 10
    left = 120
    bar_h = max(16, (height - 44 - gap * (len(items) - 1)) / max(len(items), 1))
    bars = []
    zero_x = left
    usable = width - left - 40
    for i, (label, value) in enumerate(items):
        y = 24 + i * (bar_h + gap)
        w = abs(value) / max_abs * usable
        color = accent if value >= 0 else "#ff6b6b"
        bars.append(
            f'<text x="18" y="{y + bar_h * 0.68:.1f}" fill="#c6d8cc" font-size="13">{html.escape(label[:16])}</text>'
            f'<rect x="{zero_x}" y="{y:.1f}" width="{w:.1f}" height="{bar_h:.1f}" rx="8" fill="{color}" opacity="0.88"/>'
            f'<text x="{zero_x + w + 8:.1f}" y="{y + bar_h * 0.68:.1f}" fill="#f4fff8" font-size="12">{value:.2f}</text>'
        )
    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart">
      <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#081915"/>
      {''.join(bars)}
    </svg>
    """


def render_pnl_bars(trades: list[dict[str, Any]], width: int, height: int) -> str:
    if not trades:
        return '<div class="empty">暂无数据</div>'
    values = [t["_pnl"] for t in trades[-80:]]
    max_abs = max(abs(v) for v in values) or 1
    pad = 26
    bar_w = max(2, (width - pad * 2) / len(values) * 0.72)
    zero_y = height / 2
    bars = []
    for i, value in enumerate(values):
        x = pad + i * ((width - pad * 2) / len(values))
        h = abs(value) / max_abs * (height / 2 - pad)
        y = zero_y - h if value >= 0 else zero_y
        color = "#53f29b" if value >= 0 else "#ff6b6b"
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="4" fill="{color}" opacity="0.82"/>')
    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart">
      <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#081915"/>
      <line x1="{pad}" x2="{width - pad}" y1="{zero_y:.1f}" y2="{zero_y:.1f}" stroke="#d6ffe5" opacity="0.22"/>
      {''.join(bars)}
    </svg>
    """


def pick_kline_symbol(trades: list[dict[str, Any]], cache_dir: Path) -> str:
    counts = Counter(t.get("inst_id", "") for t in trades)
    for inst, _ in counts.most_common():
        if (cache_dir / (inst.replace("-", "_") + "_1H_180d.json")).exists():
            return inst
    for fallback in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SUI-USDT-SWAP"):
        if (cache_dir / (fallback.replace("-", "_") + "_1H_180d.json")).exists():
            return fallback
    return ""


def render_kline(candles: list[dict[str, float]], trades: list[dict[str, Any]], inst_id: str) -> str:
    width, height, pad = 1160, 520, 48
    if not candles:
        return '<div class="empty">暂无K线缓存</div>'
    inst_trades = [t for t in trades if t.get("inst_id") == inst_id]
    center_ts = inst_trades[0]["_entry_ts"] if inst_trades else candles[-1]["ts"]
    before = [c for c in candles if c["ts"] <= center_ts]
    start_index = max(0, len(before) - 70)
    window = candles[start_index : start_index + 140] or candles[-140:]
    lows = [c["low"] for c in window]
    highs = [c["high"] for c in window]
    min_p, max_p = min(lows), max(highs)
    if math.isclose(min_p, max_p):
        max_p += 1
    step = (width - pad * 2) / max(len(window), 1)
    body_w = max(3, step * 0.58)

    def y(price: float) -> float:
        return height - pad - (price - min_p) / (max_p - min_p) * (height - pad * 2)

    def x_at(ts: int) -> float:
        if not window:
            return pad
        first = window[0]["ts"]
        last = window[-1]["ts"]
        if first == last:
            return pad
        return pad + (ts - first) / (last - first) * (width - pad * 2)

    candle_svg = []
    for idx, c in enumerate(window):
        x = pad + idx * step + step / 2
        color = "#4ef09a" if c["close"] >= c["open"] else "#ff6868"
        top = min(y(c["open"]), y(c["close"]))
        bottom = max(y(c["open"]), y(c["close"]))
        candle_svg.append(
            f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y(c["high"]):.1f}" y2="{y(c["low"]):.1f}" stroke="{color}" stroke-width="1.4" opacity="0.95"/>'
            f'<rect x="{x - body_w / 2:.1f}" y="{top:.1f}" width="{body_w:.1f}" height="{max(1.5, bottom - top):.1f}" rx="2" fill="{color}" opacity="0.78"/>'
        )

    markers = []
    first_ts, last_ts = window[0]["ts"], window[-1]["ts"]
    for trade in inst_trades:
        if not (first_ts <= trade["_entry_ts"] <= last_ts):
            continue
        x = x_at(trade["_entry_ts"])
        price_y = y(trade["_entry"])
        side = trade.get("side", "")
        color = "#47f7ff" if side == "long" else "#ffd166"
        markers.append(
            f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pad}" y2="{height - pad}" stroke="{color}" opacity="0.22"/>'
            f'<circle cx="{x:.1f}" cy="{price_y:.1f}" r="6" fill="{color}" stroke="#06110f" stroke-width="2"/>'
            f'<text x="{x + 8:.1f}" y="{price_y - 8:.1f}" fill="{color}" font-size="12">{html.escape(side.upper())}</text>'
        )
    grid = []
    for i in range(5):
        gy = pad + i * (height - pad * 2) / 4
        price = max_p - i * (max_p - min_p) / 4
        grid.append(
            f'<line x1="{pad}" x2="{width - pad}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="#d6ffe5" opacity="0.13"/>'
            f'<text x="{width - pad + 8}" y="{gy + 4:.1f}" fill="#a4b8ab" font-size="12">{price:.4g}</text>'
        )
    return f"""
    <svg viewBox="0 0 {width} {height}" class="kline">
      <rect x="0" y="0" width="{width}" height="{height}" rx="24" fill="#071712"/>
      {''.join(grid)}
      {''.join(candle_svg)}
      {''.join(markers)}
      <text x="{pad}" y="30" fill="#f7fff8" font-size="18" font-weight="800">{html.escape(inst_id)} 1H K线与入场标记</text>
      <text x="{pad}" y="{height - 16}" fill="#9eb3a6" font-size="12">{fmt_time(int(window[0]["ts"]))} 至 {fmt_time(int(window[-1]["ts"]))}</text>
    </svg>
    """


def render_trade_table(trades: list[dict[str, Any]], limit: int | None = None) -> str:
    rows = []
    sorted_trades = sorted(trades, key=lambda x: x["_exit_ts"], reverse=True)
    if limit is not None:
        sorted_trades = sorted_trades[:limit]
    for trade in sorted_trades:
        pnl = trade["_pnl"]
        klass = "good" if pnl >= 0 else "bad"
        rows.append(
            "<tr>"
            f"<td>{html.escape(trade.get('inst_id', ''))}</td>"
            f"<td>{html.escape(trade.get('side', ''))}</td>"
            f"<td>{fmt_time(trade['_entry_ts'])}</td>"
            f"<td>{fmt_time(trade['_exit_ts'])}</td>"
            f"<td>{trade['_score']:.1f}</td>"
            f"<td>{trade['_lev']:.0f}x</td>"
            f"<td>{fmt_money(trade['_margin'])}</td>"
            f'<td class="{klass}">{fmt_money(pnl)}</td>'
            f"<td>{html.escape(trade.get('exit_reason', ''))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def summarize_by_symbol(trades: list[dict[str, Any]]) -> list[tuple[str, float]]:
    pnl_by_symbol: dict[str, float] = defaultdict(float)
    for trade in trades:
        pnl_by_symbol[trade.get("inst_id", "")] += trade["_pnl"]
    return sorted(pnl_by_symbol.items(), key=lambda x: x[1], reverse=True)[:10]


def render_report(run_dir: Path, cache_dir: Path, output: Path | None = None) -> Path:
    metrics = load_json(run_dir / "metrics.json")
    trades = load_trades(run_dir / "trades.csv")
    output = output or (run_dir / "visual_report.html")
    start_balance = as_float(metrics.get("starting_balance"), 100000.0)
    equity_curve = build_equity_curve(trades, start_balance)
    drawdown_curve = build_drawdown_curve(equity_curve)
    symbol = pick_kline_symbol(trades, cache_dir)
    candles = load_candles(cache_dir, symbol) if symbol else []

    errors = metrics.get("errors") or []
    factors = metrics.get("factor_attribution") or []
    factor_items = [
        (str(f.get("factor", "")), as_float(f.get("winner_avg")) - as_float(f.get("loser_avg")))
        for f in factors
    ]

    best = max((t["_pnl"] for t in trades), default=0)
    worst = min((t["_pnl"] for t in trades), default=0)
    avg_score = mean([t["_score"] for t in trades]) if trades else 0
    winners = [t for t in trades if t["_pnl"] > 0]
    losers = [t for t in trades if t["_pnl"] <= 0]

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hermes Backtest Lab 页面报告</title>
  <style>
    :root {{
      --bg: #04100d;
      --panel: rgba(10, 30, 24, 0.78);
      --panel-2: rgba(15, 44, 35, 0.86);
      --text: #f4fff7;
      --muted: #98ad9f;
      --line: rgba(198, 255, 224, 0.14);
      --green: #4df39b;
      --cyan: #49e9ff;
      --gold: #ffd166;
      --red: #ff6b6b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 16% 8%, rgba(72, 255, 170, 0.22), transparent 30rem),
        radial-gradient(circle at 86% 12%, rgba(73, 233, 255, 0.16), transparent 28rem),
        linear-gradient(145deg, #04100d 0%, #071d17 46%, #020807 100%);
      min-height: 100vh;
    }}
    .wrap {{ max-width: 1320px; margin: 0 auto; padding: 34px 28px 52px; }}
    .hero {{
      border: 1px solid var(--line);
      border-radius: 30px;
      padding: 34px;
      background: linear-gradient(135deg, rgba(11, 45, 34, 0.92), rgba(6, 18, 15, 0.84));
      box-shadow: 0 30px 90px rgba(0, 0, 0, 0.34);
      position: relative;
      overflow: hidden;
    }}
    .hero:after {{
      content: "";
      position: absolute;
      inset: auto -15% -55% 45%;
      height: 280px;
      background: radial-gradient(circle, rgba(77, 243, 155, 0.32), transparent 65%);
      pointer-events: none;
    }}
    h1 {{ margin: 0; font-size: clamp(34px, 5vw, 66px); letter-spacing: -0.05em; }}
    .subtitle {{ margin-top: 12px; color: var(--muted); font-size: 16px; line-height: 1.75; max-width: 880px; }}
    .stamp {{ color: var(--green); font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 22px; }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
      background: var(--panel);
      backdrop-filter: blur(10px);
    }}
    .label {{ color: var(--muted); font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; }}
    .value {{ margin-top: 10px; font-size: 29px; font-weight: 900; letter-spacing: -0.04em; }}
    .good {{ color: var(--green); }}
    .bad {{ color: var(--red); }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 18px; }}
    .section {{
      border: 1px solid var(--line);
      border-radius: 26px;
      padding: 20px;
      background: var(--panel);
      box-shadow: 0 18px 60px rgba(0, 0, 0, 0.24);
    }}
    .section.full {{ grid-column: 1 / -1; }}
    h2 {{ margin: 0 0 14px; font-size: 20px; letter-spacing: -0.02em; }}
    .chart, .kline {{ width: 100%; display: block; }}
    .mini {{ color: var(--muted); font-size: 13px; line-height: 1.7; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; overflow: hidden; }}
    th, td {{ padding: 12px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }}
    th {{ color: #c9ffdd; font-size: 12px; letter-spacing: 0.05em; text-transform: uppercase; }}
    tr:hover td {{ background: rgba(255,255,255,0.035); }}
    .empty {{ color: var(--muted); padding: 36px; border: 1px dashed var(--line); border-radius: 18px; }}
    .pillrow {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }}
    .pill {{ border: 1px solid var(--line); color: #cdf9dd; border-radius: 999px; padding: 8px 12px; background: rgba(255,255,255,0.04); font-size: 13px; }}
    .warn {{ border-left: 4px solid var(--gold); padding-left: 14px; color: #ffe7a7; }}
    @media (max-width: 980px) {{
      .cards {{ grid-template-columns: repeat(2, 1fr); }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 620px) {{
      .wrap {{ padding: 18px; }}
      .hero {{ padding: 22px; }}
      .cards {{ grid-template-columns: 1fr; }}
      table {{ font-size: 12px; }}
      th, td {{ padding: 10px 8px; }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="stamp">Hermes Backtest Lab Visual Report</div>
      <h1>自动交易回测页面报告</h1>
      <div class="subtitle">
        数据来源：{html.escape(str(run_dir.name))}。本页为离线自包含报告，可直接用浏览器打开。
        资金曲线按逐笔平仓盈亏重建，K线来自本地 OKX 1H 缓存，并叠加代表性交易入场标记。
      </div>
      <div class="cards">
        <div class="card"><div class="label">总收益</div><div class="value {'good' if as_float(metrics.get('total_return_pct')) >= 0 else 'bad'}">{fmt_pct(as_float(metrics.get('total_return_pct')))}</div></div>
        <div class="card"><div class="label">期末权益</div><div class="value">{fmt_money(as_float(metrics.get('ending_balance')))}</div></div>
        <div class="card"><div class="label">胜率</div><div class="value">{fmt_pct(as_float(metrics.get('win_rate_pct')))}</div></div>
        <div class="card"><div class="label">最大回撤</div><div class="value bad">{fmt_pct(as_float(metrics.get('max_drawdown_pct')))}</div></div>
        <div class="card"><div class="label">交易笔数</div><div class="value">{int(as_float(metrics.get('total_trades')))}</div></div>
        <div class="card"><div class="label">Profit Factor</div><div class="value">{as_float(metrics.get('profit_factor')):.3f}</div></div>
        <div class="card"><div class="label">最大盈利单</div><div class="value good">{fmt_money(best)}</div></div>
        <div class="card"><div class="label">最大亏损单</div><div class="value bad">{fmt_money(worst)}</div></div>
      </div>
      <div class="pillrow">
        <span class="pill">平均分 {avg_score:.1f}</span>
        <span class="pill">盈利单 {len(winners)}</span>
        <span class="pill">亏损单 {len(losers)}</span>
        <span class="pill">K线标的 {html.escape(symbol or '-')}</span>
      </div>
    </section>

    <section class="grid">
      <div class="section">
        <h2>资金曲线</h2>
        {render_line_chart(equity_curve, 620, 330, "equity curve", "#4df39b", True)}
      </div>
      <div class="section">
        <h2>回撤曲线</h2>
        {render_line_chart(drawdown_curve, 620, 330, "drawdown curve", "#ff6b6b", True)}
      </div>
      <div class="section">
        <h2>最近 80 笔盈亏分布</h2>
        {render_pnl_bars(trades, 620, 330)}
      </div>
      <div class="section">
        <h2>盈利贡献 Top 10</h2>
        {render_bar_chart(summarize_by_symbol(trades), 620, 330, "#49e9ff")}
      </div>
      <div class="section full">
        <h2>K线与交易标记</h2>
        {render_kline(candles, trades, symbol)}
        <p class="mini">圆点代表该标的在窗口内的入场位置。蓝色为多单，黄色为空单。为了保持页面轻量，这里展示代表性标的与局部窗口。</p>
      </div>
      <div class="section">
        <h2>因子差异</h2>
        {render_bar_chart(factor_items, 620, 430, "#ffd166")}
        <p class="mini">数值为盈利单均值减亏损单均值。正值说明盈利单该因子更高，负值说明盈利单该因子更低。</p>
      </div>
      <div class="section">
        <h2>策略诊断</h2>
        <p class="mini">
          这次回测收益为 <b>{fmt_pct(as_float(metrics.get('total_return_pct')))}</b>，
          胜率 <b>{fmt_pct(as_float(metrics.get('win_rate_pct')))}</b>，
          盈亏比结构主要靠单笔盈利大于单笔亏损支撑。
          最大回撤 <b class="bad">{fmt_pct(as_float(metrics.get('max_drawdown_pct')))}</b> 偏高，
          后续优化优先看止损后是否重复进场、极端波动下是否减仓、低质量震荡信号是否过多。
        </p>
        <div class="warn">
          <b>注意：</b>页面报告按交易记录重建，不等同于逐根K线级别权益曲线。如果后续要做机构级报告，建议在回测器里保存每根K线的账户净值快照。
        </div>
        {('<p class="mini"><b>数据错误：</b>' + '<br>'.join(html.escape(str(e)) for e in errors[:4]) + '</p>') if errors else ''}
      </div>
      <div class="section full">
        <h2>全部交易明细</h2>
        <p class="mini">共 {len(trades)} 笔，按平仓时间倒序展示。这里保留全部交易，方便逐笔复盘和截图分享。</p>
        <table>
          <thead>
            <tr><th>标的</th><th>方向</th><th>开仓</th><th>平仓</th><th>分数</th><th>杠杆</th><th>保证金</th><th>盈亏</th><th>退出原因</th></tr>
          </thead>
          <tbody>
            {render_trade_table(trades)}
          </tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>
"""
    output.write_text(html_doc, encoding="utf-8")
    return output


def open_report(path: Path) -> bool:
    try:
        return bool(webbrowser.open(path.resolve().as_uri()))
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Render visual HTML report for Hermes Backtest Lab.")
    parser.add_argument("--run-dir", required=True, help="Backtest output directory with metrics.json and trades.csv.")
    parser.add_argument("--cache-dir", default=None, help="Cache directory with *_1H_180d.json candle files.")
    parser.add_argument("--output", default=None, help="Output HTML path.")
    parser.add_argument("--open", dest="open_browser", action="store_true", default=True, help="Open the HTML report in your default browser. Enabled by default.")
    parser.add_argument("--no-open", dest="open_browser", action="store_false", help="Do not open the browser after rendering.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else (run_dir.parent / "cache").resolve()
    output = Path(args.output).resolve() if args.output else None
    result = render_report(run_dir, cache_dir, output)
    opened = open_report(result) if args.open_browser else False
    print(json.dumps({"ok": True, "output": str(result), "opened": opened}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
