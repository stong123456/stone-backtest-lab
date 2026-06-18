#!/usr/bin/env python
"""Render a self-contained HTML report for Hermes Backtest Lab runs."""

from __future__ import annotations

import argparse
import base64
import bisect
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


ROOT = Path(__file__).resolve().parents[1]
CREATOR_NAME = "@Stone141319"
CREATOR_URL = "https://x.com/Stone141319"
AVATAR_PATH = ROOT / "assets" / "stone141319-avatar.png"


def avatar_data_uri() -> str:
    if not AVATAR_PATH.exists():
        return ""
    data = base64.b64encode(AVATAR_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def creator_card() -> str:
    avatar = avatar_data_uri()
    image = f'<img src="{avatar}" alt="{CREATOR_NAME} avatar">' if avatar else '<div class="avatar-fallback">S</div>'
    return f"""
      <a class="creator-card" href="{CREATOR_URL}" target="_blank" rel="noopener noreferrer" aria-label="关注 {CREATOR_NAME}">
        {image}
        <span>
          <b>{CREATOR_NAME}</b>
          <em>关注我，持续更新量化回测工具和自动交易实验</em>
        </span>
      </a>
    """


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
    prefix = inst_id.replace("-", "_").replace(":", "_") + "_1H_"
    bitget_prefix = ""
    if inst_id.startswith("BITGET:"):
        bitget_symbol = inst_id.split(":", 1)[1]
        bitget_prefix = f"BITGET_{bitget_symbol}_"
    preferred = cache_dir / f"{prefix}180d.json"
    candidates = [preferred] if preferred.exists() else []
    candidates.extend(sorted(cache_dir.glob(f"{prefix}*.json"), key=lambda item: item.stat().st_mtime, reverse=True))
    if bitget_prefix:
        candidates.extend(sorted(cache_dir.glob(f"{bitget_prefix}*.json"), key=lambda item: item.stat().st_mtime, reverse=True))
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
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


def symbol_from_cache_path(path: Path) -> str:
    stem = path.stem
    if "_1H_" not in stem:
        return ""
    base = stem.split("_1H_", 1)[0]
    if base.startswith("BITGET_"):
        parts = base.split("_")
        if len(parts) >= 2:
            return f"BITGET:{parts[1]}"
        return ""
    parts = base.split("_")
    if len(parts) >= 3 and parts[-1] in {"SWAP", "FUTURES", "MARGIN"}:
        return "-".join(parts[-3:])
    if len(parts) >= 2:
        return "-".join(parts[-2:])
    return ""


def available_kline_symbols(trades: list[dict[str, Any]], cache_dir: Path) -> list[str]:
    counts = Counter(t.get("inst_id", "") for t in trades)
    ordered: list[str] = []
    seen: set[str] = set()
    for inst, _ in counts.most_common():
        if inst and inst not in seen and load_candles(cache_dir, inst):
            ordered.append(inst)
            seen.add(inst)
    cached = sorted(
        {symbol_from_cache_path(path) for path in cache_dir.glob("*_1H_*.json")}
        - {""}
        - seen
    )
    for inst in cached:
        if load_candles(cache_dir, inst):
            ordered.append(inst)
            seen.add(inst)
    return ordered


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
        if inst and load_candles(cache_dir, inst):
            return inst
    for fallback in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SUI-USDT-SWAP", "BITGET:BTCUSDT", "BITGET:ETHUSDT"):
        if load_candles(cache_dir, fallback):
            return fallback
    return ""


def render_kline(candles: list[dict[str, float]], trades: list[dict[str, Any]], inst_id: str) -> str:
    width, height, pad = 1160, 520, 48
    if not candles:
        return '<div class="empty">暂无K线缓存</div>'
    inst_trades = [t for t in trades if t.get("inst_id") == inst_id]
    # Use the full cached backtest period. A local trade window is easier to read,
    # but it hides most of the tested regime and makes 90d/180d reports misleading.
    window = candles
    lows = [c["low"] for c in window]
    highs = [c["high"] for c in window]
    min_p, max_p = min(lows), max(highs)
    if math.isclose(min_p, max_p):
        max_p += 1
    step = (width - pad * 2) / max(len(window), 1)
    body_w = max(0.6, min(5.0, step * 0.72))
    wick_w = 1.2 if len(window) <= 500 else 0.65

    def y(price: float) -> float:
        return height - pad - (price - min_p) / (max_p - min_p) * (height - pad * 2)

    times = [int(c["ts"]) for c in window]

    def x_for_index(index: int) -> float:
        return pad + index * step + step / 2

    def x_at(ts: int) -> float:
        if not window:
            return pad
        if ts <= times[0]:
            return x_for_index(0)
        if ts >= times[-1]:
            return x_for_index(len(times) - 1)
        pos = bisect.bisect_left(times, ts)
        if pos < len(times) and times[pos] == ts:
            return x_for_index(pos)
        left = max(0, pos - 1)
        right = min(len(times) - 1, pos)
        if left == right or times[right] == times[left]:
            return x_for_index(left)
        ratio = (ts - times[left]) / (times[right] - times[left])
        return x_for_index(left) + ratio * (x_for_index(right) - x_for_index(left))

    candle_svg = []
    for idx, c in enumerate(window):
        x = x_for_index(idx)
        color = "#4ef09a" if c["close"] >= c["open"] else "#ff6868"
        top = min(y(c["open"]), y(c["close"]))
        bottom = max(y(c["open"]), y(c["close"]))
        candle_svg.append(
            f'<line class="k-candle-wick" data-x="{x:.4f}" data-y1="{y(c["high"]):.4f}" data-y2="{y(c["low"]):.4f}" x1="{x:.1f}" x2="{x:.1f}" y1="{y(c["high"]):.1f}" y2="{y(c["low"]):.1f}" stroke="{color}" stroke-width="{wick_w:.2f}" opacity="0.95"/>'
            f'<rect class="k-candle-body" data-x="{x:.4f}" data-base-width="{body_w:.4f}" data-y="{top:.4f}" data-height="{max(1.5, bottom - top):.4f}" x="{x - body_w / 2:.1f}" y="{top:.1f}" width="{body_w:.1f}" height="{max(1.5, bottom - top):.1f}" rx="2" fill="{color}" opacity="0.78"/>'
        )

    markers = []
    first_ts, last_ts = window[0]["ts"], window[-1]["ts"]
    for trade in inst_trades:
        side = trade.get("side", "")
        entry_color = "#47f7ff" if side == "long" else "#ffd166"
        if first_ts <= trade["_entry_ts"] <= last_ts:
            x = x_at(trade["_entry_ts"])
            price_y = y(trade["_entry"])
            markers.append(
                f'<g class="trade-marker" data-x="{x:.4f}" data-y="{price_y:.4f}">'
                f'<line class="marker-guide" x1="0" x2="0" y1="{pad - price_y:.1f}" y2="{height - pad - price_y:.1f}" stroke="{entry_color}" opacity="0.20"/>'
                f'<circle cx="0" cy="0" r="6" fill="{entry_color}" stroke="#06110f" stroke-width="2"/>'
                f'<text x="8" y="-8" fill="{entry_color}" font-size="12">{html.escape(side.upper())} IN</text>'
                f'</g>'
            )
        if first_ts <= trade["_exit_ts"] <= last_ts:
            x = x_at(trade["_exit_ts"])
            price_y = y(trade["_exit"])
            exit_color = "#4ef09a" if trade["_pnl"] >= 0 else "#ff6868"
            markers.append(
                f'<g class="trade-marker" data-x="{x:.4f}" data-y="{price_y:.4f}">'
                f'<line class="marker-guide" x1="0" x2="0" y1="{pad - price_y:.1f}" y2="{height - pad - price_y:.1f}" stroke="{exit_color}" opacity="0.18" stroke-dasharray="4 5"/>'
                f'<rect x="-5" y="-5" width="10" height="10" rx="2" fill="{exit_color}" stroke="#06110f" stroke-width="2"/>'
                f'<text x="8" y="16" fill="{exit_color}" font-size="12">OUT {trade["_pnl"]:+.1f}U</text>'
                f'</g>'
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
      <g class="zoom-layer" data-start="0" data-end="{width}">
        {''.join(candle_svg)}
      </g>
      <g class="marker-layer">{''.join(markers)}</g>
      <text x="{pad}" y="30" fill="#f7fff8" font-size="18" font-weight="800">{html.escape(inst_id)} 1H 全周期K线与入场/出场标记</text>
      <text x="{pad}" y="{height - 16}" fill="#9eb3a6" font-size="12">{fmt_time(int(window[0]["ts"]))} 至 {fmt_time(int(window[-1]["ts"]))}，共 {len(window)} 根K线</text>
    </svg>
    """


def render_kline_selector(symbols: list[str], selected: str) -> str:
    if not symbols:
        return ""
    options = []
    for symbol in symbols:
        selected_attr = " selected" if symbol == selected else ""
        options.append(f'<option value="{html.escape(symbol)}"{selected_attr}>{html.escape(symbol)}</option>')
    return f"""
    <div class="kline-toolbar">
      <label for="kline-symbol">选择K线标的</label>
      <select id="kline-symbol" aria-label="选择K线标的">
        {''.join(options)}
      </select>
      <button type="button" id="kline-reset">重置缩放</button>
    </div>
    """


def render_kline_panels(symbols: list[str], cache_dir: Path, trades: list[dict[str, Any]], selected: str) -> str:
    if not symbols:
        return '<div class="empty">暂无可选择的K线缓存</div>'
    panels = []
    for symbol in symbols:
        candles = load_candles(cache_dir, symbol)
        active = " active" if symbol == selected else ""
        panels.append(
            f'<div class="kline-panel{active}" data-symbol="{html.escape(symbol)}">'
            f'{render_kline(candles, trades, symbol)}'
            '</div>'
        )
    return "".join(panels)


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
    kline_symbols = available_kline_symbols(trades, cache_dir)
    symbol = pick_kline_symbol(trades, cache_dir)
    if symbol not in kline_symbols:
        symbol = kline_symbols[0] if kline_symbols else ""
    config = metrics.get("config") or {}
    data_source = str(config.get("data_source") or "okx").upper()

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
  <title>石头量化回测实验室 v2.2 页面报告</title>
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
    .kline-toolbar {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 0 0 14px; }}
    .kline-toolbar label {{ color: #c9ffdd; font-weight: 800; font-size: 13px; letter-spacing: 0.04em; }}
    .kline-toolbar select {{
      min-width: 240px;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 14px;
      color: var(--text);
      background: rgba(6, 20, 16, 0.95);
      outline: none;
    }}
    .kline-toolbar button {{
      border: 1px solid rgba(255, 209, 102, 0.42);
      border-radius: 14px;
      padding: 10px 14px;
      color: #ffe7a7;
      background: rgba(255, 209, 102, 0.10);
      cursor: pointer;
      font-weight: 800;
    }}
    .kline-toolbar button:hover {{ background: rgba(255, 209, 102, 0.18); }}
    .kline-panel {{ display: none; }}
    .kline-panel.active {{ display: block; }}
    .kline {{ cursor: grab; user-select: none; touch-action: none; }}
    .kline.dragging {{ cursor: grabbing; }}
    .zoom-layer {{ transform-box: fill-box; transform-origin: 0 0; }}
    .marker-layer {{ pointer-events: none; }}
    .trade-marker text {{ paint-order: stroke; stroke: #06110f; stroke-width: 3px; stroke-linejoin: round; }}
    .mini {{ color: var(--muted); font-size: 13px; line-height: 1.7; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; overflow: hidden; }}
    th, td {{ padding: 12px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }}
    th {{ color: #c9ffdd; font-size: 12px; letter-spacing: 0.05em; text-transform: uppercase; }}
    tr:hover td {{ background: rgba(255,255,255,0.035); }}
    .empty {{ color: var(--muted); padding: 36px; border: 1px dashed var(--line); border-radius: 18px; }}
    .pillrow {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }}
    .pill {{ border: 1px solid var(--line); color: #cdf9dd; border-radius: 999px; padding: 8px 12px; background: rgba(255,255,255,0.04); font-size: 13px; }}
    .pill.major {{ border-color: rgba(255, 209, 102, 0.62); color: #ffe7a7; background: rgba(255, 209, 102, 0.13); font-weight: 900; }}
    .warn {{ border-left: 4px solid var(--gold); padding-left: 14px; color: #ffe7a7; }}
    .hero-top {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 22px; }}
    .creator-card {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 270px;
      max-width: 360px;
      padding: 12px 14px;
      border: 1px solid rgba(255, 209, 102, 0.38);
      border-radius: 999px;
      background: rgba(255, 209, 102, 0.10);
      color: var(--text);
      text-decoration: none;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.20);
    }}
    .creator-card img, .avatar-fallback {{
      width: 58px;
      height: 58px;
      border-radius: 50%;
      border: 2px solid rgba(255, 209, 102, 0.82);
      flex: 0 0 auto;
      object-fit: cover;
    }}
    .avatar-fallback {{ display: grid; place-items: center; background: var(--gold); color: #081915; font-weight: 900; }}
    .creator-card b {{ display: block; color: var(--gold); font-size: 17px; letter-spacing: -0.02em; }}
    .creator-card em {{ display: block; margin-top: 2px; color: #dbeedf; font-style: normal; font-size: 12px; line-height: 1.35; }}
    .creator-card:hover {{ transform: translateY(-1px); border-color: var(--gold); }}
    @media (max-width: 980px) {{
      .cards {{ grid-template-columns: repeat(2, 1fr); }}
      .grid {{ grid-template-columns: 1fr; }}
      .hero-top {{ flex-direction: column; }}
      .creator-card {{ min-width: 0; width: 100%; border-radius: 24px; }}
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
      <div class="hero-top">
        <div>
          <div class="stamp">石头量化回测实验室 v2.2 / Hermes Backtest Lab v2.2</div>
          <h1>自动交易回测页面报告</h1>
        </div>
        {creator_card()}
      </div>
      <div class="subtitle">
        数据来源：{html.escape(str(run_dir.name))}。本页为离线自包含报告，可直接用浏览器打开。
        资金曲线按逐笔平仓盈亏重建，K线来自本地 {html.escape(data_source)} 1H 缓存，并叠加代表性交易的入场与出场标记。
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
        <span class="pill major">Bitget 行情源已接入</span>
        <span class="pill major">支持现货与 USDT 永续回测</span>
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
        {render_kline_selector(kline_symbols, symbol)}
        {render_kline_panels(kline_symbols, cache_dir, trades, symbol)}
        <p class="mini">圆点代表入场，方块代表出场；蓝色为多单入场，黄色为空单入场，绿色为盈利出场，红色为亏损出场。这里按回测缓存完整周期展示，90天回测显示90天K线，180天回测显示180天K线；下拉框可切换本次报告中有本地K线缓存的任意标的。</p>
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
  <script>
    (() => {{
      const selector = document.getElementById("kline-symbol");
      if (!selector) return;
      const panels = Array.from(document.querySelectorAll(".kline-panel"));
      const reset = document.getElementById("kline-reset");
      const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
      const width = 1160;
      const maxScale = 18;
      const minSpan = width / maxScale;

      const xMap = (rawX, start, end) => ((rawX - start) / (end - start)) * width;

      const applyWindow = (svg, start, end) => {{
        const layer = svg.querySelector(".zoom-layer");
        if (!layer) return;
        let nextStart = start;
        let nextEnd = end;
        const span = Math.max(minSpan, nextEnd - nextStart);
        if (nextStart < 0) {{
          nextEnd -= nextStart;
          nextStart = 0;
        }}
        if (nextEnd > width) {{
          nextStart -= nextEnd - width;
          nextEnd = width;
        }}
        nextStart = clamp(nextStart, 0, width - span);
        nextEnd = nextStart + span;
        layer.dataset.start = String(nextStart);
        layer.dataset.end = String(nextEnd);
        const zoomRatio = width / (nextEnd - nextStart);

        svg.querySelectorAll(".k-candle-wick").forEach((wick) => {{
          const rawX = Number(wick.dataset.x || "0");
          const sx = xMap(rawX, nextStart, nextEnd);
          const visible = sx >= -20 && sx <= width + 20;
          wick.style.display = visible ? "" : "none";
          if (!visible) return;
          wick.setAttribute("x1", sx);
          wick.setAttribute("x2", sx);
        }});

        svg.querySelectorAll(".k-candle-body").forEach((body) => {{
          const rawX = Number(body.dataset.x || "0");
          const sx = xMap(rawX, nextStart, nextEnd);
          const visible = sx >= -20 && sx <= width + 20;
          body.style.display = visible ? "" : "none";
          if (!visible) return;
          const baseWidth = Number(body.dataset.baseWidth || "1");
          const nextWidth = clamp(baseWidth * zoomRatio, 0.8, 14);
          body.setAttribute("x", sx - nextWidth / 2);
          body.setAttribute("width", nextWidth);
        }});

        svg.querySelectorAll(".trade-marker").forEach((marker) => {{
          const rawX = Number(marker.dataset.x || "0");
          const rawY = Number(marker.dataset.y || "0");
          const sx = xMap(rawX, nextStart, nextEnd);
          const visible = sx >= -30 && sx <= width + 30;
          marker.style.display = visible ? "" : "none";
          if (visible) marker.setAttribute("transform", `translate(${{sx}} ${{rawY}})`);
        }});
      }};

      const resetZoom = (panel) => {{
        const svg = panel?.querySelector(".kline");
        if (svg) applyWindow(svg, 0, width);
      }};

      const activate = (symbol) => {{
        panels.forEach((panel) => {{
          panel.classList.toggle("active", panel.dataset.symbol === symbol);
        }});
      }};

      panels.forEach((panel) => {{
        const svg = panel.querySelector(".kline");
        const layer = svg?.querySelector(".zoom-layer");
        if (!svg || !layer) return;
        applyWindow(svg, 0, width);

        svg.addEventListener("wheel", (event) => {{
          event.preventDefault();
          const rect = svg.getBoundingClientRect();
          const mouseX = ((event.clientX - rect.left) / rect.width) * width;
          const oldStart = Number(layer.dataset.start || "0");
          const oldEnd = Number(layer.dataset.end || String(width));
          const oldSpan = oldEnd - oldStart;
          const factor = event.deltaY < 0 ? 1.22 : 1 / 1.22;
          const nextSpan = clamp(oldSpan / factor, minSpan, width);
          const anchor = oldStart + (mouseX / width) * oldSpan;
          const nextStart = anchor - (mouseX / width) * nextSpan;
          applyWindow(svg, nextStart, nextStart + nextSpan);
        }}, {{ passive: false }});

        let dragging = false;
        let lastX = 0;
        svg.addEventListener("pointerdown", (event) => {{
          dragging = true;
          lastX = event.clientX;
          svg.classList.add("dragging");
          svg.setPointerCapture(event.pointerId);
        }});
        svg.addEventListener("pointermove", (event) => {{
          if (!dragging) return;
          const rect = svg.getBoundingClientRect();
          const dx = ((event.clientX - lastX) / rect.width);
          lastX = event.clientX;
          const start = Number(layer.dataset.start || "0");
          const end = Number(layer.dataset.end || String(width));
          const span = end - start;
          const dataDx = dx * span;
          applyWindow(svg, start - dataDx, end - dataDx);
        }});
        const stopDrag = (event) => {{
          dragging = false;
          svg.classList.remove("dragging");
          try {{ svg.releasePointerCapture(event.pointerId); }} catch (_) {{}}
        }};
        svg.addEventListener("pointerup", stopDrag);
        svg.addEventListener("pointercancel", stopDrag);
        svg.addEventListener("pointerleave", () => {{
          dragging = false;
          svg.classList.remove("dragging");
        }});
      }});

      selector.addEventListener("change", (event) => activate(event.target.value));
      reset?.addEventListener("click", () => {{
        const active = document.querySelector(".kline-panel.active");
        resetZoom(active);
      }});
      activate(selector.value);
    }})();
  </script>
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
