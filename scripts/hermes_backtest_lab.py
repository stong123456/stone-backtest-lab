from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time, timezone
from pathlib import Path
from typing import Any, Iterable

import requests


OKX_PUBLIC = "https://www.okx.com"
GECKOTERMINAL_PUBLIC = "https://api.geckoterminal.com/api/v2"
VERSION = "hermes-backtest-lab-v2.1.0"
TOOL_NAME_CN = "石头量化回测实验室 v2.1"
TOOL_NAME_EN = "Hermes Backtest Lab v2.1"

DEFAULT_SWAP_SYMBOLS = "BTC,ETH,SOL,XRP,DOGE,SUI,BNB,TON,TRX,LINK,AVAX,NEAR,AAVE,UNI,LTC,APT,ARB,OP,DOT,ICP"
MEME_SWAP_SYMBOLS = "PEPE,DOGE,TRUMP,MERL,SUI,TON,ARB,OP,NEAR"
BLUECHIP_SWAP_SYMBOLS = "BTC,ETH,SOL,BNB,LINK,AAVE,LTC,XRP"

EXAMPLE_TEXT = f"""
{TOOL_NAME_CN} / {TOOL_NAME_EN} examples

1) 30-day quick smoke test
   python scripts/hermes_backtest_lab.py --preset demo

2) Balanced 180-day portfolio replay
   python scripts/hermes_backtest_lab.py --preset balanced

3) Conservative blue-chip perpetuals
   python scripts/hermes_backtest_lab.py --preset conservative --days 180

4) Aggressive altcoin/meme replay
   python scripts/hermes_backtest_lab.py --preset aggressive --days 90

5) Spot-only long replay
   python scripts/hermes_backtest_lab.py --preset spot --symbols BTC,ETH,SOL,SUI --days 180

6) Custom OKX instrument IDs
   python scripts/hermes_backtest_lab.py --symbols BTC-USDT-SWAP,ETH-USDT-SWAP --inst-type SWAP --days 90 --bar 4H

7) Override a preset safely
   python scripts/hermes_backtest_lab.py --preset balanced --symbols BTC,ETH,SOL --days 90 --max-leverage 8

8) Refresh public candle cache
   python scripts/hermes_backtest_lab.py --preset balanced --refresh

9) On-chain token replay through GeckoTerminal
   python scripts/hermes_backtest_lab.py --preset onchain-demo

10) On-chain custom token or pool
   python scripts/hermes_backtest_lab.py --data-source geckoterminal --symbols base:token:0x4200000000000000000000000000000000000006,base:pool:0xPOOL_ADDRESS --days 30 --bar 1H

Outputs:
   report.md     human-readable report
   metrics.json  machine-readable metrics and config
   trades.csv    every simulated trade
"""


PRESET_DESCRIPTIONS: dict[str, str] = {
    "demo": "30 天 BTC/ETH 快速试跑，最适合第一次确认环境。",
    "balanced": "180 天多币种合约组合，默认正式研究版本。",
    "conservative": "180 天主流币保守版，频率更低，回撤优先。",
    "aggressive": "90 天高波动币种进攻版，适合压力测试。",
    "spot": "现货只做多版本，不开合约空单。",
    "onchain-demo": "链上 DEX 数据示例，通过 GeckoTerminal 拉池子 K 线。",
}


PRESET_ARGS: dict[str, list[str]] = {
    "demo": [
        "--symbols", "BTC,ETH",
        "--inst-type", "SWAP",
        "--days", "30",
        "--bar", "1H",
        "--portfolio-mode", "1",
        "--starting-balance", "10000",
        "--min-margin", "100",
        "--max-margin", "300",
        "--max-open-positions", "2",
        "--portfolio-new-entries-per-bar", "1",
        "--max-total-margin-pct", "30",
        "--max-leverage", "5",
    ],
    "conservative": [
        "--symbols", BLUECHIP_SWAP_SYMBOLS,
        "--inst-type", "SWAP",
        "--days", "180",
        "--bar", "1H",
        "--portfolio-mode", "1",
        "--starting-balance", "100000",
        "--min-margin", "1000",
        "--max-margin", "3000",
        "--max-open-positions", "6",
        "--portfolio-new-entries-per-bar", "1",
        "--max-total-margin-pct", "30",
        "--entry-score", "90",
        "--bt-large-margin-min-atr-pct", "2.0",
        "--bt-max-vol-z", "1.5",
        "--max-leverage", "10",
        "--oracle-trend-hold-bars", "48",
    ],
    "balanced": [
        "--symbols", DEFAULT_SWAP_SYMBOLS,
        "--inst-type", "SWAP",
        "--days", "180",
        "--bar", "1H",
        "--portfolio-mode", "1",
        "--starting-balance", "100000",
        "--min-margin", "2000",
        "--max-margin", "5000",
        "--max-open-positions", "16",
        "--portfolio-new-entries-per-bar", "2",
        "--max-total-margin-pct", "80",
        "--entry-score", "90",
        "--bt-large-margin-min-atr-pct", "1.8",
        "--bt-max-vol-z", "2.0",
        "--oracle-trend-hold-bars", "48",
    ],
    "aggressive": [
        "--symbols", f"{DEFAULT_SWAP_SYMBOLS},{MEME_SWAP_SYMBOLS}",
        "--inst-type", "SWAP",
        "--days", "90",
        "--bar", "1H",
        "--portfolio-mode", "1",
        "--starting-balance", "100000",
        "--min-margin", "2000",
        "--max-margin", "8000",
        "--max-open-positions", "16",
        "--portfolio-new-entries-per-bar", "3",
        "--max-total-margin-pct", "90",
        "--entry-score", "80",
        "--bt-large-margin-min-atr-pct", "1.6",
        "--bt-max-vol-z", "2.0",
        "--oracle-trend-hold-bars", "60",
    ],
    "spot": [
        "--symbols", "BTC,ETH,SOL,SUI,LINK",
        "--inst-type", "SPOT",
        "--days", "180",
        "--bar", "1H",
        "--allow-short", "0",
        "--starting-balance", "10000",
        "--min-margin", "100",
        "--max-margin", "500",
        "--max-leverage", "1",
        "--base-leverage", "1",
    ],
    "onchain-demo": [
        "--data-source", "geckoterminal",
        "--symbols", "base:token:0x4200000000000000000000000000000000000006",
        "--days", "30",
        "--bar", "1H",
        "--allow-short", "0",
        "--starting-balance", "10000",
        "--min-margin", "100",
        "--max-margin", "500",
        "--max-leverage", "1",
        "--base-leverage", "1",
        "--entry-score", "70",
        "--portfolio-mode", "0",
    ],
}

HTTP = requests.Session()
HTTP.trust_env = False


@dataclass
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    side: str
    score: float
    mode: str
    confirmations: int
    stop_pct: float
    leverage: float
    max_hold_bars: int
    reason: str
    features: dict[str, float]


@dataclass
class Trade:
    inst_id: str
    side: str
    mode: str
    entry_ts: int
    exit_ts: int
    entry: float
    exit: float
    margin: float
    leverage: float
    notional: float
    pnl_usdt: float
    pnl_pct_on_margin: float
    exit_reason: str
    score: float
    confirmations: int
    max_hold_bars: int
    features: dict[str, float]


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def utc_text(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def parse_date_ms(value: str, *, end_of_day: bool = False) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        if len(normalized) == 10 and normalized[4] == "-" and normalized[7] == "-":
            day = datetime.strptime(normalized, "%Y-%m-%d").date()
            dt = datetime.combine(day, dt_time.max if end_of_day else dt_time.min, tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(f"bad date '{value}'. Use YYYY-MM-DD or ISO time like 2026-01-31T08:00:00Z.") from exc
    return int(dt.timestamp() * 1000)


def resolve_time_window(args: argparse.Namespace) -> tuple[int, int, str]:
    now_ms = int(time.time() * 1000)
    start_ms = parse_date_ms(getattr(args, "start_date", ""), end_of_day=False)
    end_ms = parse_date_ms(getattr(args, "end_date", ""), end_of_day=True)
    if start_ms is None and end_ms is None:
        end_ms = now_ms
        start_ms = end_ms - int(args.days * 86_400_000)
        label = f"{args.days}d"
    elif start_ms is None:
        assert end_ms is not None
        start_ms = end_ms - int(args.days * 86_400_000)
        label = f"{utc_text(start_ms)}_to_{utc_text(end_ms)}"
    elif end_ms is None:
        end_ms = min(now_ms, start_ms + int(args.days * 86_400_000))
        label = f"{utc_text(start_ms)}_to_{utc_text(end_ms)}"
    else:
        label = f"{utc_text(start_ms)}_to_{utc_text(end_ms)}"
    if end_ms <= start_ms:
        raise ValueError("--end-date must be later than --start-date")
    return start_ms, end_ms, safe_cache_key(label)


def okx_get(path: str, params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    url = f"{OKX_PUBLIC}{path}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = HTTP.get(url, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            if str(payload.get("code", "0")) != "0":
                raise RuntimeError(f"OKX error {payload.get('code')}: {payload.get('msg')}")
            return payload
        except Exception as exc:
            last_error = exc
            time.sleep(0.4 + attempt * 0.6)
    raise RuntimeError(f"request failed {path} {params}: {last_error}")


def public_get_json(base_url: str, path: str, params: dict[str, Any] | None = None, retries: int = 3) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = HTTP.get(url, params=params or {}, timeout=25)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 + attempt * 0.8)
    raise RuntimeError(f"request failed {url} {params or {}}: {last_error}")


def normalize_inst_id(symbol: str, inst_type: str, quote: str) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        raise ValueError("empty symbol")
    if "-" in raw:
        return raw
    if inst_type.upper() == "SPOT":
        return f"{raw}-{quote.upper()}"
    return f"{raw}-{quote.upper()}-SWAP"


def safe_cache_key(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value))


def gecko_bar_parts(bar: str) -> tuple[str, int]:
    raw = str(bar or "").strip()
    table = {
        "1m": ("minute", 1),
        "5m": ("minute", 5),
        "15m": ("minute", 15),
        "30m": ("minute", 30),
        "1H": ("hour", 1),
        "2H": ("hour", 2),
        "4H": ("hour", 4),
        "6H": ("hour", 6),
        "12H": ("hour", 12),
        "1D": ("day", 1),
        "1Dutc": ("day", 1),
    }
    if raw not in table:
        raise ValueError(f"unsupported GeckoTerminal bar: {bar}. Try 1m, 5m, 15m, 1H, 4H, or 1D.")
    return table[raw]


def parse_onchain_symbol(raw_symbol: str, default_network: str, default_id_type: str) -> dict[str, str]:
    raw = str(raw_symbol or "").strip()
    if not raw:
        raise ValueError("empty on-chain symbol")
    parts = raw.split(":")
    if len(parts) == 1:
        return {"network": default_network, "id_type": default_id_type, "address": parts[0].strip()}
    if len(parts) == 2:
        return {"network": parts[0].strip(), "id_type": default_id_type, "address": parts[1].strip()}
    network, id_type, address = parts[0].strip(), parts[1].strip().lower(), ":".join(parts[2:]).strip()
    if id_type not in {"token", "pool"}:
        raise ValueError(f"unsupported on-chain id type: {id_type}. Use token or pool.")
    return {"network": network, "id_type": id_type, "address": address}


def gecko_pool_liquidity_usd(pool: dict[str, Any]) -> float:
    attrs = pool.get("attributes") or {}
    candidates = [
        attrs.get("reserve_in_usd"),
        attrs.get("liquidity_usd"),
        attrs.get("fdv_usd"),
    ]
    for value in candidates:
        parsed = safe_float(value, -1.0)
        if parsed >= 0:
            return parsed
    return 0.0


def gecko_resolve_pool(network: str, id_type: str, address: str) -> tuple[str, str]:
    network = network.strip()
    address = address.strip()
    if not network or not address:
        raise ValueError("on-chain network and address are required")
    if id_type == "pool":
        return address, f"{network}:pool:{address}"
    payload = public_get_json(GECKOTERMINAL_PUBLIC, f"/networks/{network}/tokens/{address}/pools", {"page": "1"})
    pools = payload.get("data") or []
    if not pools:
        raise RuntimeError(f"No GeckoTerminal pools found for {network}:{address}")
    pools.sort(key=gecko_pool_liquidity_usd, reverse=True)
    pool = pools[0]
    pool_address = str((pool.get("attributes") or {}).get("address") or pool.get("id") or "").split("_")[-1]
    if not pool_address:
        raise RuntimeError(f"Cannot resolve pool address for {network}:{address}")
    return pool_address, f"{network}:token:{address}->{pool_address}"


def symbol_from_inst_id(inst_id: str) -> str:
    return str(inst_id or "").upper().split("-")[0]


def priority_symbols(args: argparse.Namespace) -> set[str]:
    return {item.strip().upper() for item in str(args.priority_symbols or "").split(",") if item.strip()}


def is_priority_inst(inst_id: str, args: argparse.Namespace) -> bool:
    return symbol_from_inst_id(inst_id) in priority_symbols(args)


def high_score_heat_level(signal: Signal, args: argparse.Namespace) -> str:
    if not args.enable_backtest_180d_guards:
        return ""
    score = float(signal.score)
    if score < args.bt_high_score_heat_floor or signal.mode == "range":
        return ""
    f = signal.features
    extreme = score >= args.bt_extreme_score_heat_floor
    if signal.side == "long":
        hot = extreme or f.get("rsi", 50.0) >= 60.0 or f.get("chg_24h", 0.0) >= 2.0 or f.get("distance_ema20_pct", 0.0) >= 0.8
    else:
        hot = extreme or f.get("rsi", 50.0) <= 42.0 or f.get("chg_24h", 0.0) <= -2.0 or f.get("distance_ema20_pct", 0.0) <= -0.8
    if not hot:
        return ""
    return "extreme" if extreme else "high"


def oracle_180d_profile(side: str, features: dict[str, float], args: argparse.Namespace) -> dict[str, Any]:
    side = "short" if str(side or "").lower() == "short" else "long"
    atr = safe_float(features.get("atr_pct"))
    adx_value = safe_float(features.get("adx"))
    rsi_value = safe_float(features.get("rsi"), 50.0)
    chg = safe_float(features.get("chg_24h"))
    ema_distance = safe_float(features.get("distance_ema20_pct"))

    atr_band = "unknown"
    if atr > 0:
        if atr < args.oracle_atr_floor_pct:
            atr_band = "too_low"
        elif atr < args.oracle_atr_preferred_pct:
            atr_band = "low_ok"
        elif atr < args.oracle_atr_strong_pct:
            atr_band = "preferred"
        elif atr < args.oracle_atr_hot_pct:
            atr_band = "strong"
        else:
            atr_band = "hot"

    adx_band = "unknown"
    if adx_value > 0:
        if adx_value < args.oracle_adx_floor:
            adx_band = "weak"
        elif adx_value < args.oracle_adx_strong:
            adx_band = "tradable"
        elif adx_value < args.oracle_adx_elite:
            adx_band = "strong"
        else:
            adx_band = "elite"

    if side == "long":
        position_style = "pullback_long" if chg <= 0 and ema_distance <= 0.5 and rsi_value <= 55 else "momentum_long"
        rsi_ok = 28.0 <= rsi_value <= 58.0
        chg_ok = chg <= args.oracle_preferred_abs_chg_24h_pct
        ema_ok = ema_distance <= args.oracle_preferred_ema20_distance_pct
        overextended = chg > args.oracle_max_abs_chg_24h_pct or ema_distance > args.oracle_max_ema20_distance_pct
    else:
        position_style = "rebound_short" if chg >= 0 and ema_distance >= -0.5 and rsi_value >= 45 else "momentum_short"
        rsi_ok = 42.0 <= rsi_value <= 74.0
        chg_ok = chg >= -args.oracle_preferred_abs_chg_24h_pct
        ema_ok = ema_distance >= -args.oracle_preferred_ema20_distance_pct
        overextended = chg < -args.oracle_max_abs_chg_24h_pct or ema_distance < -args.oracle_max_ema20_distance_pct

    trend_quality = 0.0
    if atr_band == "low_ok":
        trend_quality += 1.0
    elif atr_band == "preferred":
        trend_quality += 2.0
    elif atr_band == "strong":
        trend_quality += 3.0
    elif atr_band == "hot":
        trend_quality += 2.0
    if adx_band == "tradable":
        trend_quality += 1.0
    elif adx_band == "strong":
        trend_quality += 2.0
    elif adx_band == "elite":
        trend_quality += 3.0
    if rsi_ok:
        trend_quality += 1.0
    if chg_ok:
        trend_quality += 1.0
    if ema_ok:
        trend_quality += 1.0

    return {
        "atr": atr,
        "adx": adx_value,
        "rsi": rsi_value,
        "chg": chg,
        "ema_distance": ema_distance,
        "atr_band": atr_band,
        "adx_band": adx_band,
        "position_style": position_style,
        "atr_ok": atr <= 0 or atr >= args.oracle_atr_floor_pct,
        "adx_ok": adx_value <= 0 or adx_value >= args.oracle_adx_floor,
        "rsi_ok": rsi_ok,
        "chg_ok": chg_ok,
        "ema_ok": ema_ok,
        "overextended": overextended,
        "trend_quality": trend_quality,
    }


def oracle_180d_rejects(side: str, mode: str, features: dict[str, float], hard: int, soft: int, args: argparse.Namespace) -> list[str]:
    if not args.enable_oracle_180d_profile:
        return []
    if mode == "range":
        return []
    profile = oracle_180d_profile(side, features, args)
    rejects: list[str] = []
    if not profile["atr_ok"]:
        rejects.append("oracle180_atr_too_low")
    if not profile["adx_ok"] and hard < 2:
        rejects.append("oracle180_adx_weak")
    if profile["overextended"]:
        public_flow_proxy = safe_float(features.get("vol_z")) >= 0.6
        if not (public_flow_proxy and hard >= 2 and soft >= 1):
            rejects.append("oracle180_late_extended")
    return rejects


def oracle_180d_score_delta(side: str, mode: str, features: dict[str, float], args: argparse.Namespace) -> tuple[float, list[str]]:
    if not args.enable_oracle_180d_profile or mode == "range":
        return 0.0, []
    profile = oracle_180d_profile(side, features, args)
    delta = 0.0
    reasons: list[str] = []
    if profile["atr_band"] == "preferred":
        delta += 5.0
        reasons.append("oracle180_atr_preferred")
    elif profile["atr_band"] == "strong":
        delta += 7.0
        reasons.append("oracle180_atr_strong")
    elif profile["atr_band"] == "hot":
        delta -= 1.0
        reasons.append("oracle180_atr_hot")
    elif profile["atr_band"] == "too_low":
        delta -= 15.0
        reasons.append("oracle180_atr_too_low")
    if profile["adx_band"] == "tradable":
        delta += 3.0
    elif profile["adx_band"] == "strong":
        delta += 5.0
        reasons.append("oracle180_adx_strong")
    elif profile["adx_band"] == "elite":
        delta += 7.0
        reasons.append("oracle180_adx_elite")
    elif profile["adx_band"] == "weak":
        delta -= 13.0
        reasons.append("oracle180_adx_weak")
    if side == "long" and profile["position_style"] == "pullback_long":
        delta += 6.0
        reasons.append("oracle180_pullback_long")
    elif side == "short" and profile["position_style"] == "rebound_short":
        delta += 6.0
        reasons.append("oracle180_rebound_short")
    if safe_float(profile["trend_quality"]) >= 6.0:
        delta += 4.0
        reasons.append("oracle180_trend_quality")
    if profile["overextended"]:
        delta -= 12.0
        reasons.append("oracle180_overextended")
    if not profile["rsi_ok"]:
        delta -= 4.0
    if not profile["ema_ok"]:
        delta -= 5.0
    return delta, reasons


def oracle_180d_hold_bars(signal: Signal, args: argparse.Namespace) -> int:
    base = max(int(args.max_hold_bars), 1)
    if not args.enable_oracle_180d_profile or signal.mode == "range":
        return base
    profile = oracle_180d_profile(signal.side, signal.features, args)
    trend_like = safe_float(profile["trend_quality"]) >= 5.0 or (
        safe_float(profile["atr"]) >= args.oracle_atr_preferred_pct
        and safe_float(profile["adx"]) >= args.oracle_adx_floor
    )
    if trend_like and not bool(profile["overextended"]):
        return max(base, int(args.oracle_trend_hold_bars))
    return base


def bar_to_ms(bar: str) -> int:
    value = bar.strip()
    table = {
        "1m": 60_000,
        "3m": 180_000,
        "5m": 300_000,
        "15m": 900_000,
        "30m": 1_800_000,
        "1H": 3_600_000,
        "2H": 7_200_000,
        "4H": 14_400_000,
        "6H": 21_600_000,
        "12H": 43_200_000,
        "1D": 86_400_000,
        "1Dutc": 86_400_000,
    }
    if value not in table:
        raise ValueError(f"unsupported bar: {bar}")
    return table[value]


def parse_okx_candle(row: list[Any]) -> Bar:
    return Bar(
        ts=int(row[0]),
        open=safe_float(row[1]),
        high=safe_float(row[2]),
        low=safe_float(row[3]),
        close=safe_float(row[4]),
        volume=safe_float(row[5] if len(row) > 5 else 0.0),
    )


def fetch_candles(
    inst_id: str,
    bar: str,
    days: int,
    cache_dir: Path,
    refresh: bool = False,
    *,
    start_ms: int | None = None,
    end_ms: int | None = None,
    window_label: str | None = None,
) -> list[Bar]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)
    resolved_end = int(end_ms or now_ms)
    resolved_start = int(start_ms if start_ms is not None else resolved_end - int(days * 86_400_000))
    label = safe_cache_key(window_label or f"{days}d")
    cache_path = cache_dir / f"{inst_id.replace('-', '_')}_{bar}_{label}.json"
    if cache_path.exists() and not refresh:
        rows = json.loads(cache_path.read_text(encoding="utf-8"))
        return [Bar(**row) for row in rows]

    cursor: int | None = resolved_end + 1
    seen: set[int] = set()
    bars: list[Bar] = []
    limit = 100

    while True:
        params: dict[str, Any] = {"instId": inst_id, "bar": bar, "limit": str(limit)}
        if cursor is not None:
            params["after"] = str(cursor)
        payload = okx_get("/api/v5/market/history-candles", params)
        data = payload.get("data") or []
        if not data:
            if cursor is None:
                payload = okx_get("/api/v5/market/candles", params)
                data = payload.get("data") or []
            if not data:
                break
        parsed = [parse_okx_candle(row) for row in data if len(row) >= 5]
        new_count = 0
        for candle in parsed:
            if candle.ts in seen:
                continue
            if resolved_start <= candle.ts <= resolved_end:
                bars.append(candle)
                seen.add(candle.ts)
                new_count += 1
        oldest = min((candle.ts for candle in parsed), default=None)
        if oldest is None or oldest <= resolved_start or new_count == 0:
            break
        cursor = oldest - 1
        if len(bars) > int((resolved_end - resolved_start) / bar_to_ms(bar)) + 500:
            break
        time.sleep(0.12)

    bars = sorted(bars, key=lambda row: row.ts)
    cache_path.write_text(json.dumps([asdict(row) for row in bars], ensure_ascii=False), encoding="utf-8")
    return bars


def parse_gecko_ohlcv(row: list[Any]) -> Bar:
    return Bar(
        ts=int(safe_float(row[0]) * 1000),
        open=safe_float(row[1]),
        high=safe_float(row[2]),
        low=safe_float(row[3]),
        close=safe_float(row[4]),
        volume=safe_float(row[5] if len(row) > 5 else 0.0),
    )


def fetch_geckoterminal_candles(
    symbol: str,
    bar: str,
    days: int,
    cache_dir: Path,
    *,
    network_default: str,
    id_type_default: str,
    currency: str,
    token_side: str,
    limit: int,
    refresh: bool = False,
    start_ms: int | None = None,
    end_ms: int | None = None,
    window_label: str | None = None,
) -> tuple[str, list[Bar]]:
    spec = parse_onchain_symbol(symbol, network_default, id_type_default)
    timeframe, aggregate = gecko_bar_parts(bar)
    pool_address, label = gecko_resolve_pool(spec["network"], spec["id_type"], spec["address"])
    inst_id = f"GT:{label}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)
    resolved_end = int(end_ms or now_ms)
    resolved_start = int(start_ms if start_ms is not None else resolved_end - int(days * 86_400_000))
    cache_label = safe_cache_key(window_label or f"{days}d")
    cache_path = cache_dir / f"{safe_cache_key(inst_id)}_{safe_cache_key(bar)}_{cache_label}.json"
    if cache_path.exists() and not refresh:
        rows = json.loads(cache_path.read_text(encoding="utf-8"))
        return inst_id, [Bar(**row) for row in rows]

    before_timestamp: int | None = int(resolved_end / 1000) + 1
    seen: set[int] = set()
    bars: list[Bar] = []
    page_limit = max(1, min(int(limit or 1000), 1000))

    while True:
        params: dict[str, Any] = {
            "aggregate": str(aggregate),
            "limit": str(page_limit),
            "currency": currency,
            "token": token_side,
        }
        if before_timestamp is not None:
            params["before_timestamp"] = str(before_timestamp)
        payload = public_get_json(
            GECKOTERMINAL_PUBLIC,
            f"/networks/{spec['network']}/pools/{pool_address}/ohlcv/{timeframe}",
            params,
        )
        rows = ((payload.get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
        if not rows:
            break
        parsed = [parse_gecko_ohlcv(row) for row in rows if len(row) >= 5]
        new_count = 0
        for candle in parsed:
            if candle.ts in seen:
                continue
            if resolved_start <= candle.ts <= resolved_end:
                bars.append(candle)
                seen.add(candle.ts)
                new_count += 1
        oldest = min((candle.ts for candle in parsed), default=None)
        if oldest is None or oldest <= resolved_start or new_count == 0:
            break
        before_timestamp = int(oldest / 1000) - 1
        if len(bars) > int((resolved_end - resolved_start) / bar_to_ms(bar)) + 500:
            break
        time.sleep(0.35)

    bars = sorted(bars, key=lambda row: row.ts)
    cache_path.write_text(json.dumps([asdict(row) for row in bars], ensure_ascii=False), encoding="utf-8")
    return inst_id, bars


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    alpha = 2.0 / (period + 1.0)
    current = sum(values[:period]) / period
    out[period - 1] = current
    for idx in range(period, len(values)):
        current = values[idx] * alpha + current * (1.0 - alpha)
        out[idx] = current
    return out


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    rolling = sum(values[:period])
    out[period - 1] = rolling / period
    for idx in range(period, len(values)):
        rolling += values[idx] - values[idx - period]
        out[idx] = rolling / period
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for idx in range(1, period + 1):
        delta = values[idx] - values[idx - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for idx in range(period + 1, len(values)):
        delta = values[idx] - values[idx - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period
        out[idx] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def atr(bars: list[Bar], period: int = 14) -> list[float | None]:
    tr: list[float] = []
    for idx, bar in enumerate(bars):
        if idx == 0:
            tr.append(bar.high - bar.low)
            continue
        prev_close = bars[idx - 1].close
        tr.append(max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close)))
    return ema(tr, period)


def bollinger(values: list[float], period: int = 20, mult: float = 2.0) -> tuple[list[float | None], list[float | None], list[float | None]]:
    mid = sma(values, period)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)
    for idx in range(period - 1, len(values)):
        window = values[idx - period + 1 : idx + 1]
        sd = statistics.pstdev(window)
        center = mid[idx]
        if center is None:
            continue
        upper[idx] = center + sd * mult
        lower[idx] = center - sd * mult
    return lower, mid, upper


def adx(bars: list[Bar], period: int = 14) -> list[float | None]:
    if len(bars) <= period * 2:
        return [None] * len(bars)
    trs = [0.0]
    plus_dm = [0.0]
    minus_dm = [0.0]
    for idx in range(1, len(bars)):
        up = bars[idx].high - bars[idx - 1].high
        down = bars[idx - 1].low - bars[idx].low
        trs.append(max(bars[idx].high - bars[idx].low, abs(bars[idx].high - bars[idx - 1].close), abs(bars[idx].low - bars[idx - 1].close)))
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
    tr_ema = ema(trs, period)
    plus_ema = ema(plus_dm, period)
    minus_ema = ema(minus_dm, period)
    dx: list[float] = [0.0] * len(bars)
    for idx in range(len(bars)):
        if tr_ema[idx] in (None, 0) or plus_ema[idx] is None or minus_ema[idx] is None:
            continue
        plus_di = 100.0 * plus_ema[idx] / max(tr_ema[idx] or 1e-9, 1e-9)
        minus_di = 100.0 * minus_ema[idx] / max(tr_ema[idx] or 1e-9, 1e-9)
        dx[idx] = 100.0 * abs(plus_di - minus_di) / max(plus_di + minus_di, 1e-9)
    return ema(dx, period)


def rolling_z(values: list[float], period: int = 24) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for idx in range(period - 1, len(values)):
        window = values[idx - period + 1 : idx + 1]
        sd = statistics.pstdev(window)
        out[idx] = 0.0 if sd == 0 else (values[idx] - statistics.mean(window)) / sd
    return out


def build_context(bars: list[Bar]) -> dict[str, list[float | None]]:
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]
    lower, bb_mid, upper = bollinger(closes)
    return {
        "ema20": ema(closes, 20),
        "ema50": ema(closes, 50),
        "rsi14": rsi(closes, 14),
        "atr14": atr(bars, 14),
        "bb_lower": lower,
        "bb_mid": bb_mid,
        "bb_upper": upper,
        "adx14": adx(bars, 14),
        "vol_z": rolling_z(volumes, 24),
    }


def value_at(series: list[float | None], idx: int, default: float = 0.0) -> float:
    if idx < 0 or idx >= len(series):
        return default
    return safe_float(series[idx], default)


def score_signal(inst_id: str, bars: list[Bar], ctx: dict[str, list[float | None]], idx: int, side: str, args: argparse.Namespace) -> Signal | None:
    close = bars[idx].close
    ema20 = value_at(ctx["ema20"], idx)
    ema50 = value_at(ctx["ema50"], idx)
    rsi14 = value_at(ctx["rsi14"], idx, 50.0)
    atr14 = value_at(ctx["atr14"], idx)
    adx14 = value_at(ctx["adx14"], idx)
    bb_lower = value_at(ctx["bb_lower"], idx)
    bb_mid = value_at(ctx["bb_mid"], idx)
    bb_upper = value_at(ctx["bb_upper"], idx)
    vol_z = value_at(ctx["vol_z"], idx)
    if min(close, ema20, ema50, atr14, bb_lower, bb_mid, bb_upper) <= 0:
        return None

    atr_pct = atr14 / close * 100.0
    ema_gap = (ema20 - ema50) / close * 100.0
    distance_ema20_pct = (close - ema20) / close * 100.0
    chg_24h = (close / bars[idx - 24].close - 1.0) * 100.0 if idx >= 24 and bars[idx - 24].close > 0 else 0.0
    trend_up = close > ema20 > ema50
    trend_down = close < ema20 < ema50
    range_mode = adx14 < args.range_adx
    score = 38.0
    hard = 0
    soft = 0
    reasons: list[str] = []

    if side == "long":
        if trend_up:
            score += 20.0
            hard += 1
            reasons.append("trend_up")
        if adx14 >= args.trend_adx:
            score += 12.0
            hard += 1
            reasons.append("adx_trend")
        if close >= ema20 and abs((close - ema20) / close * 100.0) <= 1.2:
            score += 8.0
            soft += 1
            reasons.append("ema20_hold")
        if 42.0 <= rsi14 <= 68.0:
            score += 7.0
            soft += 1
            reasons.append("rsi_ok")
        elif rsi14 > 78.0:
            score -= 12.0
            reasons.append("late_chase")
        if range_mode and close <= bb_lower * 1.01 and rsi14 <= 38.0:
            score += 18.0
            hard += 1
            reasons.append("range_rebound")
        mode = "range" if range_mode and "range_rebound" in reasons else "trend"
    else:
        if trend_down:
            score += 20.0
            hard += 1
            reasons.append("trend_down")
        if adx14 >= args.trend_adx:
            score += 12.0
            hard += 1
            reasons.append("adx_trend")
        if close <= ema20 and abs((close - ema20) / close * 100.0) <= 1.2:
            score += 8.0
            soft += 1
            reasons.append("ema20_reject")
        if 32.0 <= rsi14 <= 58.0:
            score += 7.0
            soft += 1
            reasons.append("rsi_ok")
        elif rsi14 < 22.0:
            score -= 10.0
            reasons.append("late_short")
        if range_mode and close >= bb_upper * 0.99 and rsi14 >= 62.0:
            score += 18.0
            hard += 1
            reasons.append("range_fade")
        mode = "range" if range_mode and "range_fade" in reasons else "trend"

    if vol_z >= 0.6:
        score += 7.0
        soft += 1
        reasons.append("volume_expand")
    elif vol_z <= -0.8:
        score -= 5.0
        reasons.append("thin_volume")
    if atr_pct > args.max_atr_pct:
        score -= 14.0
        reasons.append("volatility_too_hot")
    if atr_pct < args.min_atr_pct:
        score -= 6.0
        reasons.append("volatility_too_cold")

    confirmations = hard + soft
    features = {
        "adx": adx14,
        "rsi": rsi14,
        "atr_pct": atr_pct,
        "ema_gap": ema_gap,
        "vol_z": vol_z,
        "distance_ema20_pct": distance_ema20_pct,
        "chg_24h": chg_24h,
        "hard_confirmations": hard,
        "soft_confirmations": soft,
    }
    oracle_delta, oracle_reasons = oracle_180d_score_delta(side, mode, features, args)
    if oracle_delta:
        score += oracle_delta
    reasons.extend(oracle_reasons)

    if (
        args.enable_backtest_180d_guards
        and side == "long"
        and not is_priority_inst(inst_id, args)
    ):
        structure_ok = bool(trend_up or "ema20_hold" in reasons or "range_rebound" in reasons)
        strong_volume = vol_z >= args.bt_alt_long_min_vol_z
        if hard < args.bt_alt_long_min_hard:
            reasons.append("bt180_hard_low")
            return None
        if soft < args.bt_alt_long_min_soft:
            reasons.append("bt180_soft_low")
            return None
        if not structure_ok:
            reasons.append("bt180_no_structure")
            return None
        if adx14 < args.bt_alt_long_min_adx and "range_rebound" not in reasons:
            reasons.append("bt180_weak_adx")
            return None
        if not strong_volume and "range_rebound" not in reasons:
            reasons.append("bt180_weak_volume")
            return None
        if chg_24h >= args.bt_alt_long_max_chg_24h and not (strong_volume and hard >= 3):
            reasons.append("bt180_late_chase")
            return None
        if rsi14 >= args.bt_alt_long_max_rsi and "range_rebound" not in reasons:
            reasons.append("bt180_rsi_hot")
            return None
        if distance_ema20_pct >= args.bt_alt_long_max_distance_ema20_pct and "ema20_hold" not in reasons:
            reasons.append("bt180_ema_extended")
            return None
        if ema20 <= ema50 and "range_rebound" not in reasons:
            reasons.append("bt180_ma_not_aligned")
            return None

    if args.enable_futures_long_replay_throttle and side == "long" and "range_rebound" not in reasons:
        structure_ok = bool("ema20_hold" in reasons or trend_up)
        external_flow = bool(vol_z >= args.bt_alt_long_min_vol_z and "volume_expand" in reasons)
        if score < args.futures_long_replay_min_score and not (external_flow and structure_ok):
            return None
        if score >= args.futures_long_replay_hot_score and not (external_flow and structure_ok and hard >= 2 and soft >= 1):
            return None

    if oracle_180d_rejects(side, mode, features, hard, soft, args):
        return None

    if args.enable_backtest_180d_guards:
        large_margin_mode = float(args.min_margin) >= float(args.bt_large_margin_threshold)
        if large_margin_mode and atr_pct < float(args.bt_large_margin_min_atr_pct):
            return None
        if vol_z >= float(args.bt_max_vol_z) and atr_pct < float(args.oracle_atr_hot_pct):
            return None
        if (
            float(args.bt_adx_dead_zone_low) <= adx14 < float(args.bt_adx_dead_zone_high)
            and vol_z >= 0.6
            and float(args.bt_hot_score_low) <= score < float(args.bt_hot_score_high)
        ):
            return None
        if (
            adx14 >= float(args.bt_extreme_adx)
            and abs(chg_24h) >= float(args.bt_extreme_adx_min_abs_chg_24h)
            and score < float(args.bt_hot_score_high)
        ):
            return None

    stop_pct = clamp(atr_pct * args.atr_stop_mult, args.min_stop_pct, args.max_stop_pct)
    leverage = dynamic_leverage(inst_id, side, score, confirmations, atr_pct, features, args)
    if score < args.entry_score or confirmations < args.min_confirmations:
        return None
    provisional = Signal(
        side=side,
        score=round(score, 2),
        mode=mode,
        confirmations=confirmations,
        stop_pct=stop_pct,
        leverage=leverage,
        max_hold_bars=max(int(args.max_hold_bars), 1),
        reason=",".join(reasons),
        features=features,
    )
    provisional.max_hold_bars = oracle_180d_hold_bars(provisional, args)
    return provisional


def dynamic_leverage(inst_id: str, side: str, score: float, confirmations: int, atr_pct: float, features: dict[str, float], args: argparse.Namespace) -> float:
    leverage = float(args.base_leverage)
    if score >= 68:
        leverage = max(leverage, 8.0)
    if score >= 76:
        leverage = max(leverage, 12.0)
    if score >= 84 and confirmations >= 3:
        leverage = max(leverage, 16.0)
    if score >= 92 and confirmations >= 4:
        leverage = max(leverage, 20.0)
    if atr_pct > args.max_atr_pct * 0.8:
        leverage *= 0.7
    if args.enable_backtest_180d_guards:
        if side == "long" and not is_priority_inst(inst_id, args):
            leverage = min(leverage, args.bt_nonpriority_long_leverage_cap)
        if side == "short" and atr_pct >= args.max_atr_pct * 0.7:
            leverage = min(leverage, args.bt_short_hot_atr_leverage_cap)
        if score >= args.bt_high_score_heat_floor:
            if side == "short":
                leverage = min(leverage, args.bt_short_high_score_leverage_cap)
            elif score >= args.bt_extreme_score_heat_floor:
                leverage = min(leverage, args.bt_extreme_score_leverage_cap)
            else:
                leverage = min(leverage, args.bt_high_score_leverage_cap)
    if args.enable_oracle_180d_profile:
        profile = oracle_180d_profile(side, features, args)
        if profile["atr_band"] == "too_low" or profile["adx_band"] == "weak":
            leverage = min(leverage, args.oracle_low_quality_leverage_cap)
        if profile["atr_band"] == "hot":
            leverage = min(leverage, args.oracle_hot_atr_leverage_cap)
        if (
            profile["atr_band"] in {"strong", "preferred"}
            and profile["adx_band"] in {"strong", "elite"}
            and not bool(profile["overextended"])
        ):
            leverage = min(args.max_leverage, leverage + max(args.oracle_strong_trend_leverage_bonus, 0.0))
    return round(clamp(leverage, 1.0, args.max_leverage), 2)


def margin_for(equity: float, args: argparse.Namespace, signal: Signal, inst_id: str) -> float:
    margin = clamp(equity * args.margin_pct / 100.0, args.min_margin, args.max_margin)
    if args.enable_backtest_180d_guards:
        if signal.side == "long" and not is_priority_inst(inst_id, args):
            margin *= args.bt_alt_long_margin_scale
        if signal.mode in {"range", "choppy", "volatile"}:
            margin *= args.bt_choppy_margin_scale
        if signal.side == "short" and signal.features.get("atr_pct", 0.0) >= args.max_atr_pct * 0.7:
            margin *= 0.75
        heat = high_score_heat_level(signal, args)
        if heat:
            if signal.side == "short":
                margin *= args.bt_short_high_score_margin_scale
            elif heat == "extreme":
                margin *= args.bt_extreme_score_margin_scale
            else:
                margin *= args.bt_high_score_margin_scale
    if args.enable_oracle_180d_profile:
        profile = oracle_180d_profile(signal.side, signal.features, args)
        if profile["atr_band"] == "too_low":
            margin *= args.oracle_low_atr_margin_scale
        elif profile["atr_band"] == "hot":
            margin *= args.oracle_hot_atr_margin_scale
        elif profile["atr_band"] == "strong" and profile["adx_band"] in {"strong", "elite"} and not bool(profile["overextended"]):
            margin *= args.oracle_strong_trend_margin_scale
    if 0 < margin < args.min_margin:
        margin = args.min_margin
    return round(clamp(margin, args.min_margin, args.max_margin), 4)


def choose_signal(long_signal: Signal | None, short_signal: Signal | None, allow_long: bool, allow_short: bool) -> Signal | None:
    options = [
        signal
        for signal in (long_signal if allow_long else None, short_signal if allow_short else None)
        if signal
    ]
    if not options:
        return None
    options.sort(key=lambda row: (row.score, row.confirmations), reverse=True)
    return options[0]


def close_trade(inst_id: str, trade: dict[str, Any], bar: Bar, exit_price: float, reason: str, args: argparse.Namespace) -> Trade:
    side = trade["side"]
    entry = trade["entry"]
    direction_return = (exit_price - entry) / entry if side == "long" else (entry - exit_price) / entry
    notional = trade["notional"]
    gross = direction_return * notional
    costs = notional * ((args.fee_bps + args.slippage_bps) / 10_000.0) * 2.0
    pnl = gross - costs
    margin = trade["margin"]
    return Trade(
        inst_id=inst_id,
        side=side,
        mode=trade["mode"],
        entry_ts=trade["entry_ts"],
        exit_ts=bar.ts,
        entry=entry,
        exit=exit_price,
        margin=margin,
        leverage=trade["leverage"],
        notional=notional,
        pnl_usdt=round(pnl, 6),
        pnl_pct_on_margin=round(pnl / max(margin, 1e-9) * 100.0, 4),
        exit_reason=reason,
        score=trade["score"],
        confirmations=trade["confirmations"],
        max_hold_bars=int(trade.get("max_hold_bars") or 0),
        features=trade["features"],
    )


def backtest_symbol(inst_id: str, bars: list[Bar], args: argparse.Namespace, starting_equity: float) -> dict[str, Any]:
    if len(bars) < 80:
        return {"inst_id": inst_id, "error": "not enough candles", "trades": [], "equity_curve": [], "start": starting_equity, "end": starting_equity, "max_dd": 0.0}
    ctx = build_context(bars)
    equity = starting_equity
    peak = equity
    max_dd = 0.0
    position: dict[str, Any] | None = None
    trades: list[Trade] = []
    equity_curve: list[tuple[int, float]] = [(bars[0].ts, equity)]

    for idx in range(60, len(bars) - 1):
        bar = bars[idx]
        next_bar = bars[idx + 1]
        if position:
            side = position["side"]
            entry = position["entry"]
            stop_pct = position["stop_pct"] / 100.0
            tp_pct = stop_pct * args.reward_r
            max_hold = int(position.get("max_hold_bars") or args.max_hold_bars)
            exit_price = 0.0
            reason = ""
            bars_held = idx - int(position["entry_idx"])
            direction_return = (bar.close - entry) / entry * 100.0 if side == "long" else (entry - bar.close) / entry * 100.0
            if side == "long":
                if bar.low <= entry * (1.0 - stop_pct):
                    exit_price = entry * (1.0 - stop_pct)
                    reason = "stop"
                elif bar.high >= entry * (1.0 + tp_pct):
                    exit_price = entry * (1.0 + tp_pct)
                    reason = "take_profit"
            else:
                if bar.high >= entry * (1.0 + stop_pct):
                    exit_price = entry * (1.0 + stop_pct)
                    reason = "stop"
                elif bar.low <= entry * (1.0 - tp_pct):
                    exit_price = entry * (1.0 - tp_pct)
                    reason = "take_profit"
            if (
                not reason
                and args.enable_oracle_180d_profile
                and bars_held >= int(args.oracle_fast_adverse_bars)
                and direction_return <= -abs(float(args.oracle_fast_adverse_cut_pct))
            ):
                exit_price = bar.close
                reason = "oracle_fast_adverse"
            if not reason and idx - position["entry_idx"] >= max_hold:
                exit_price = bar.close
                reason = "time_exit"
            if reason:
                closed = close_trade(inst_id, position, bar, exit_price, reason, args)
                trades.append(closed)
                equity += closed.pnl_usdt
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / max(peak, 1e-9))
                equity_curve.append((bar.ts, equity))
                position = None
                if equity <= starting_equity * (1.0 - args.account_stop_pct / 100.0):
                    break

        if position is not None:
            continue
        long_signal = score_signal(inst_id, bars, ctx, idx, "long", args)
        short_signal = score_signal(inst_id, bars, ctx, idx, "short", args)
        signal = choose_signal(long_signal, short_signal, args.allow_long, args.allow_short)
        if not signal:
            continue
        entry_price = next_bar.open * (1.0 + args.slippage_bps / 10_000.0 if signal.side == "long" else 1.0 - args.slippage_bps / 10_000.0)
        margin = margin_for(equity, args, signal, inst_id)
        if margin <= 0 or equity <= margin * 0.05:
            continue
        position = {
            "side": signal.side,
            "mode": signal.mode,
            "entry_idx": idx + 1,
            "entry_ts": next_bar.ts,
            "entry": entry_price,
            "margin": margin,
            "leverage": signal.leverage,
            "notional": margin * signal.leverage,
            "stop_pct": signal.stop_pct,
            "score": signal.score,
            "confirmations": signal.confirmations,
            "max_hold_bars": signal.max_hold_bars,
            "features": signal.features,
        }

    if position:
        closed = close_trade(inst_id, position, bars[-1], bars[-1].close, "final_close", args)
        trades.append(closed)
        equity += closed.pnl_usdt
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / max(peak, 1e-9))
        equity_curve.append((bars[-1].ts, equity))

    return {"inst_id": inst_id, "trades": trades, "equity_curve": equity_curve, "start": starting_equity, "end": equity, "max_dd": max_dd}


def position_exit_signal(inst_id: str, position: dict[str, Any], bar: Bar, idx: int, args: argparse.Namespace) -> tuple[float, str]:
    side = position["side"]
    entry = position["entry"]
    stop_pct = position["stop_pct"] / 100.0
    tp_pct = stop_pct * args.reward_r
    max_hold = int(position.get("max_hold_bars") or args.max_hold_bars)
    bars_held = idx - int(position["entry_idx"])
    direction_return = (bar.close - entry) / entry * 100.0 if side == "long" else (entry - bar.close) / entry * 100.0
    if side == "long":
        if bar.low <= entry * (1.0 - stop_pct):
            return entry * (1.0 - stop_pct), "stop"
        if bar.high >= entry * (1.0 + tp_pct):
            return entry * (1.0 + tp_pct), "take_profit"
    else:
        if bar.high >= entry * (1.0 + stop_pct):
            return entry * (1.0 + stop_pct), "stop"
        if bar.low <= entry * (1.0 - tp_pct):
            return entry * (1.0 - tp_pct), "take_profit"
    if (
        args.enable_oracle_180d_profile
        and bars_held >= int(args.oracle_fast_adverse_bars)
        and direction_return <= -abs(float(args.oracle_fast_adverse_cut_pct))
    ):
        return bar.close, "oracle_fast_adverse"
    if bars_held >= max_hold:
        return bar.close, "time_exit"
    return 0.0, ""


def backtest_portfolio(bars_by_inst: dict[str, list[Bar]], args: argparse.Namespace, starting_equity: float) -> dict[str, Any]:
    usable = {inst: bars for inst, bars in bars_by_inst.items() if len(bars) >= 80}
    if not usable:
        return {"inst_id": "PORTFOLIO", "error": "not enough candles", "trades": [], "equity_curve": [], "start": starting_equity, "end": starting_equity, "max_dd": 0.0}
    contexts = {inst: build_context(bars) for inst, bars in usable.items()}
    ts_to_idx = {inst: {bar.ts: idx for idx, bar in enumerate(bars)} for inst, bars in usable.items()}
    timestamps = sorted(
        {
            bar.ts
            for bars in usable.values()
            for idx, bar in enumerate(bars)
            if 60 <= idx < len(bars) - 1
        }
    )
    equity = starting_equity
    peak = equity
    max_dd = 0.0
    positions: list[dict[str, Any]] = []
    trades: list[Trade] = []
    equity_curve: list[tuple[int, float]] = [(timestamps[0], equity)] if timestamps else []
    max_positions = max(int(getattr(args, "max_open_positions", 16) or 16), 1)
    new_entries_per_bar = max(int(getattr(args, "portfolio_new_entries_per_bar", 2) or 2), 1)
    max_total_margin_pct = max(float(getattr(args, "max_total_margin_pct", 80.0) or 80.0), 1.0) / 100.0

    def force_close_open_positions(reason: str, ts: int) -> None:
        nonlocal equity, peak, max_dd, positions
        remaining: list[dict[str, Any]] = []
        for position in positions:
            inst_id = position["inst_id"]
            idx_map = ts_to_idx.get(inst_id, {})
            idx = idx_map.get(ts)
            if idx is None:
                # Use the latest candle already visible to the portfolio clock.
                prior = [bar_idx for bar_ts, bar_idx in idx_map.items() if bar_ts <= ts]
                if not prior:
                    remaining.append(position)
                    continue
                idx = max(prior)
            bar = usable[inst_id][idx]
            closed = close_trade(inst_id, position, bar, bar.close, reason, args)
            trades.append(closed)
            equity += closed.pnl_usdt
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / max(peak, 1e-9))
            equity_curve.append((bar.ts, equity))
        positions = remaining

    for ts in timestamps:
        kept: list[dict[str, Any]] = []
        for position in positions:
            inst_id = position["inst_id"]
            idx = ts_to_idx.get(inst_id, {}).get(ts)
            if idx is None:
                kept.append(position)
                continue
            bar = usable[inst_id][idx]
            exit_price, reason = position_exit_signal(inst_id, position, bar, idx, args)
            if not reason:
                kept.append(position)
                continue
            closed = close_trade(inst_id, position, bar, exit_price, reason, args)
            trades.append(closed)
            equity += closed.pnl_usdt
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / max(peak, 1e-9))
            equity_curve.append((bar.ts, equity))
        positions = kept
        if equity <= starting_equity * (1.0 - args.account_stop_pct / 100.0):
            force_close_open_positions("account_stop_liquidation", ts)
            break

        if len(positions) >= max_positions:
            continue
        open_symbols = {position["inst_id"] for position in positions}
        used_margin = sum(safe_float(position.get("margin")) for position in positions)
        margin_cap = equity * max_total_margin_pct
        candidates: list[tuple[Signal, str, int]] = []
        for inst_id, bars in usable.items():
            if inst_id in open_symbols:
                continue
            idx = ts_to_idx[inst_id].get(ts)
            if idx is None or idx >= len(bars) - 1:
                continue
            long_signal = score_signal(inst_id, bars, contexts[inst_id], idx, "long", args)
            short_signal = score_signal(inst_id, bars, contexts[inst_id], idx, "short", args)
            signal = choose_signal(long_signal, short_signal, args.allow_long, args.allow_short)
            if signal:
                candidates.append((signal, inst_id, idx))
        candidates.sort(key=lambda row: (row[0].score, row[0].confirmations), reverse=True)

        opened = 0
        for signal, inst_id, idx in candidates:
            if len(positions) >= max_positions or opened >= new_entries_per_bar:
                break
            if inst_id in {position["inst_id"] for position in positions}:
                continue
            bars = usable[inst_id]
            next_bar = bars[idx + 1]
            entry_price = next_bar.open * (1.0 + args.slippage_bps / 10_000.0 if signal.side == "long" else 1.0 - args.slippage_bps / 10_000.0)
            margin = margin_for(equity, args, signal, inst_id)
            if margin <= 0 or used_margin + margin > margin_cap or equity <= margin * 0.05:
                continue
            positions.append(
                {
                    "inst_id": inst_id,
                    "side": signal.side,
                    "mode": signal.mode,
                    "entry_idx": idx + 1,
                    "entry_ts": next_bar.ts,
                    "entry": entry_price,
                    "margin": margin,
                    "leverage": signal.leverage,
                    "notional": margin * signal.leverage,
                    "stop_pct": signal.stop_pct,
                    "score": signal.score,
                    "confirmations": signal.confirmations,
                    "max_hold_bars": signal.max_hold_bars,
                    "features": signal.features,
                }
            )
            used_margin += margin
            opened += 1

    for position in positions:
        inst_id = position["inst_id"]
        bars = usable[inst_id]
        closed = close_trade(inst_id, position, bars[-1], bars[-1].close, "final_close", args)
        trades.append(closed)
        equity += closed.pnl_usdt
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / max(peak, 1e-9))
        equity_curve.append((bars[-1].ts, equity))

    return {"inst_id": "PORTFOLIO", "trades": trades, "equity_curve": equity_curve, "start": starting_equity, "end": equity, "max_dd": max_dd}


def metrics_for(results: list[dict[str, Any]], starting_balance: float) -> dict[str, Any]:
    all_trades: list[Trade] = []
    final_equity = 0.0
    max_dd = 0.0
    errors: list[str] = []
    for result in results:
        if result.get("error"):
            errors.append(f"{result.get('inst_id')}: {result.get('error')}")
        all_trades.extend(result.get("trades", []))
        final_equity += safe_float(result.get("end"), safe_float(result.get("start")))
        max_dd = max(max_dd, safe_float(result.get("max_dd")))
    wins = [trade for trade in all_trades if trade.pnl_usdt > 0]
    losses = [trade for trade in all_trades if trade.pnl_usdt <= 0]
    gross_win = sum(trade.pnl_usdt for trade in wins)
    gross_loss = abs(sum(trade.pnl_usdt for trade in losses))
    return {
        "version": VERSION,
        "tool_name_cn": TOOL_NAME_CN,
        "tool_name_en": TOOL_NAME_EN,
        "starting_balance": starting_balance,
        "ending_balance": round(final_equity, 4),
        "total_return_pct": round((final_equity / max(starting_balance, 1e-9) - 1.0) * 100.0, 4),
        "total_trades": len(all_trades),
        "win_rate_pct": round(len(wins) / max(len(all_trades), 1) * 100.0, 4),
        "profit_factor": round(gross_win / max(gross_loss, 1e-9), 4),
        "max_drawdown_pct": round(max_dd * 100.0, 4),
        "avg_win": round(gross_win / max(len(wins), 1), 4),
        "avg_loss": round(-gross_loss / max(len(losses), 1), 4),
        "errors": errors,
    }


def factor_attribution(trades: list[Trade]) -> list[dict[str, Any]]:
    keys = [
        "adx",
        "rsi",
        "atr_pct",
        "ema_gap",
        "vol_z",
        "distance_ema20_pct",
        "chg_24h",
        "hard_confirmations",
        "soft_confirmations",
    ]
    rows: list[dict[str, Any]] = []
    winners = [trade for trade in trades if trade.pnl_usdt > 0]
    losers = [trade for trade in trades if trade.pnl_usdt <= 0]
    for key in keys:
        win_values = [safe_float(trade.features.get(key)) for trade in winners]
        lose_values = [safe_float(trade.features.get(key)) for trade in losers]
        if not win_values and not lose_values:
            continue
        rows.append(
            {
                "factor": key,
                "winner_avg": round(statistics.mean(win_values), 4) if win_values else None,
                "loser_avg": round(statistics.mean(lose_values), 4) if lose_values else None,
                "note": factor_note(key, statistics.mean(win_values) if win_values else 0.0, statistics.mean(lose_values) if lose_values else 0.0),
            }
        )
    return rows


def factor_note(key: str, winner_avg: float, loser_avg: float) -> str:
    if winner_avg > loser_avg:
        return f"{key} was higher in winners"
    if winner_avg < loser_avg:
        return f"{key} was lower in winners"
    return f"{key} showed no clear split"


def write_outputs(out_dir: Path, results: list[dict[str, Any]], metrics: dict[str, Any], args: argparse.Namespace) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_trades: list[Trade] = []
    for result in results:
        all_trades.extend(result.get("trades", []))
    all_trades.sort(key=lambda trade: trade.entry_ts)

    with (out_dir / "trades.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "inst_id",
                "side",
                "mode",
                "entry_ts",
                "exit_ts",
                "entry_time_utc",
                "exit_time_utc",
                "entry",
                "exit",
                "margin",
                "leverage",
                "notional",
                "pnl_usdt",
                "pnl_pct_on_margin",
                "exit_reason",
                "score",
                "confirmations",
                "max_hold_bars",
                "features",
            ],
        )
        writer.writeheader()
        for trade in all_trades:
            row = asdict(trade)
            row["entry_time_utc"] = utc_text(trade.entry_ts)
            row["exit_time_utc"] = utc_text(trade.exit_ts)
            row["features"] = json.dumps(trade.features, ensure_ascii=False)
            writer.writerow(row)

    metrics["factor_attribution"] = factor_attribution(all_trades)
    metrics["config"] = vars(args)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {TOOL_NAME_CN} Report",
        "",
        f"- Version: `{VERSION}`",
        f"- Generated: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`",
        f"- Symbols: `{args.symbols}`",
        f"- Inst type: `{args.inst_type}`",
        f"- Days: `{args.days}`",
        f"- Start date: `{args.start_date or '-'}`",
        f"- End date: `{args.end_date or '-'}`",
        f"- Resolved UTC window: `{getattr(args, 'resolved_start_utc', '-')}` to `{getattr(args, 'resolved_end_utc', '-')}`",
        f"- Bar: `{args.bar}`",
        "",
        "## Summary",
        "",
        f"- Starting balance: `{metrics['starting_balance']:.2f}`",
        f"- Ending balance: `{metrics['ending_balance']:.2f}`",
        f"- Total return: `{metrics['total_return_pct']:.2f}%`",
        f"- Max drawdown: `{metrics['max_drawdown_pct']:.2f}%`",
        f"- Win rate: `{metrics['win_rate_pct']:.2f}%`",
        f"- Profit factor: `{metrics['profit_factor']:.2f}`",
        f"- Trades: `{metrics['total_trades']}`",
        f"- Avg win: `{metrics['avg_win']:.2f}`",
        f"- Avg loss: `{metrics['avg_loss']:.2f}`",
        "",
        "## Per Symbol",
        "",
        "| Symbol | Start | End | Return | Trades | Max DD |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        start = safe_float(result.get("start"))
        end = safe_float(result.get("end"), start)
        lines.append(
            f"| {result.get('inst_id')} | {start:.2f} | {end:.2f} | {(end / max(start, 1e-9) - 1.0) * 100.0:.2f}% | {len(result.get('trades', []))} | {safe_float(result.get('max_dd')) * 100.0:.2f}% |"
        )
    lines.extend(["", "## Factor Attribution", "", "| Factor | Winner Avg | Loser Avg | Read |", "|---|---:|---:|---|"])
    for row in metrics["factor_attribution"]:
        lines.append(f"| {row['factor']} | {row['winner_avg']} | {row['loser_avg']} | {row['note']} |")
    if metrics.get("errors"):
        lines.extend(["", "## Data Warnings", ""])
        lines.extend(f"- {item}" for item in metrics["errors"])
    lines.extend(
        [
            "",
            "## Research Notes",
            "",
            "- This backtest uses only public candles and replay-safe indicators.",
            "- Fees and slippage are modeled through `fee_bps` and `slippage_bps`.",
            "- It does not use private account fills, private order history, Telegram tokens, or API secrets.",
            "- Treat results as a research layer before changing a live bot.",
        ]
    )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_bool(raw: str) -> bool:
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def preset_table_text() -> str:
    lines = ["可用预设：", ""]
    for name in sorted(PRESET_ARGS):
        lines.append(f"  {name:<14} {PRESET_DESCRIPTIONS.get(name, '')}")
    lines.extend(
        [
            "",
            "示例：",
            "  python scripts/hermes_backtest_lab.py --preset demo",
            "  python scripts/hermes_backtest_lab.py --preset balanced",
            "  python scripts/hermes_backtest_lab.py --preset onchain-demo",
        ]
    )
    return "\n".join(lines)


def quick_help_text() -> str:
    return f"""
{TOOL_NAME_CN} / {TOOL_NAME_EN} {VERSION}

这个工具用来做加密货币策略回测：拉公开 K 线，模拟开仓/平仓，输出 report.md、metrics.json、trades.csv。
第一次使用不用研究几十个参数，直接从预设开始。

最快开始：
  python scripts/hermes_backtest_lab.py --preset demo

常用命令：
  python scripts/hermes_backtest_lab.py --preset balanced
  python scripts/hermes_backtest_lab.py --preset conservative
  python scripts/hermes_backtest_lab.py --preset aggressive
  python scripts/hermes_backtest_lab.py --preset spot
  python scripts/hermes_backtest_lab.py --preset onchain-demo

降低门槛的小工具：
  python scripts/hermes_backtest_lab.py --list-presets
  python scripts/hermes_backtest_lab.py --dry-run --preset balanced
  python scripts/hermes_backtest_lab.py --examples
  python scripts/hermes_backtest_lab.py --advanced-help

常见改法：
  python scripts/hermes_backtest_lab.py --preset balanced --symbols BTC,ETH,SOL --days 90
  python scripts/hermes_backtest_lab.py --preset balanced --symbols-file examples/symbols_okx_bluechip.txt

一键脚本：
  .\\run_demo.ps1
  .\\run_balanced.ps1
  .\\run_onchain_demo.ps1

输出目录默认在：
  outputs\\hermes_backtest_lab\\时间戳
""".strip()


def read_symbols_file(path_text: str) -> list[str]:
    path = Path(path_text).expanduser()
    if not path.exists() and not path.is_absolute():
        skill_relative = Path(__file__).resolve().parent.parent / path
        if skill_relative.exists():
            path = skill_relative
    rows = path.read_text(encoding="utf-8").splitlines()
    symbols: list[str] = []
    for row in rows:
        value = row.strip()
        if not value or value.startswith("#"):
            continue
        symbols.append(value)
    return symbols


def merge_symbols(symbols_text: str, symbols_file: str = "") -> list[str]:
    raw_symbols = [item.strip() for item in str(symbols_text or "").split(",") if item.strip()]
    if symbols_file:
        raw_symbols.extend(read_symbols_file(symbols_file))
    seen: set[str] = set()
    merged: list[str] = []
    for symbol in raw_symbols:
        key = symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        merged.append(symbol)
    return merged


def expand_preset_args(argv: Iterable[str]) -> list[str]:
    raw = list(argv)
    preset = ""
    for idx, item in enumerate(raw):
        if item == "--preset" and idx + 1 < len(raw):
            preset = raw[idx + 1].strip().lower()
            break
        if item.startswith("--preset="):
            preset = item.split("=", 1)[1].strip().lower()
            break
    if not preset:
        return raw
    if preset not in PRESET_ARGS:
        available = ", ".join(sorted(PRESET_ARGS))
        raise SystemExit(f"unknown preset: {preset}. Available presets: {available}")
    # Preset args are inserted before user args so explicit CLI flags override the preset.
    return [*PRESET_ARGS[preset], *raw]


def main(argv: Iterable[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    raw_has_symbols = any(item == "--symbols" or item.startswith("--symbols=") for item in raw_argv)
    if not raw_argv or "--help" in raw_argv or "-h" in raw_argv:
        print(quick_help_text())
        return 0
    if "--list-presets" in raw_argv:
        print(preset_table_text())
        return 0
    if "--examples" in raw_argv or "-E" in raw_argv:
        print(EXAMPLE_TEXT.strip())
        return 0
    expanded_argv = expand_preset_args(raw_argv)

    parser = argparse.ArgumentParser(
        description="Open-source crypto backtest lab. 默认 --help 是中文短菜单，高级参数请用 --advanced-help。",
        epilog="Run with --examples for recipes, --list-presets for presets, or --dry-run to preview config.",
        add_help=False,
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--help", "-h", action="store_true", help="Print beginner Chinese help and exit.")
    parser.add_argument("--advanced-help", action="store_true", help="Print the full advanced parameter reference and exit.")
    parser.add_argument("--list-presets", action="store_true", help="Print preset names and Chinese descriptions, then exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved config and exit without downloading candles.")
    parser.add_argument("--examples", "-E", action="store_true", help="Print copy-paste command examples and exit.")
    parser.add_argument("--preset", choices=sorted(PRESET_ARGS), default="", help="Load a beginner-friendly parameter preset. Explicit CLI flags override preset values.")
    parser.add_argument("--data-source", default="okx", choices=["okx", "geckoterminal"], help="Market data source: okx for CEX candles, geckoterminal for on-chain DEX pool candles.")
    parser.add_argument("--symbols", default="", help="Comma-separated symbols. OKX: BTC,ETH or BTC-USDT-SWAP. On-chain: base:token:0xTOKEN or base:pool:0xPOOL.")
    parser.add_argument("--symbols-file", default="", help="Optional UTF-8 text file with one symbol per line. Lines starting with # are ignored.")
    parser.add_argument("--inst-type", default="SWAP", choices=["SWAP", "SPOT"], help="Instrument type for bare symbols.")
    parser.add_argument("--quote", default="USDT")
    parser.add_argument("--onchain-network", default="base", help="Default GeckoTerminal network id for bare on-chain addresses, e.g. eth, bsc, base, solana.")
    parser.add_argument("--onchain-id-type", default="token", choices=["token", "pool"], help="Default interpretation for bare on-chain addresses.")
    parser.add_argument("--gecko-currency", default="usd", help="GeckoTerminal OHLCV currency, usually usd.")
    parser.add_argument("--gecko-token-side", default="base", choices=["base", "quote"], help="Whether OHLCV should use the pool base token or quote token.")
    parser.add_argument("--gecko-limit", type=int, default=1000, help="GeckoTerminal candles per request, max 1000.")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--start-date", default="", help="UTC start date/time for the backtest window. Use YYYY-MM-DD or ISO time.")
    parser.add_argument("--end-date", default="", help="UTC end date/time for the backtest window. Use YYYY-MM-DD or ISO time.")
    parser.add_argument("--bar", default="1H")
    parser.add_argument("--output-dir", default=str(Path("outputs") / "hermes_backtest_lab"))
    parser.add_argument("--starting-balance", type=float, default=10_000.0)
    parser.add_argument("--portfolio-mode", type=parse_bool, default=False, help="Use one shared account across all symbols instead of one sub-account per symbol.")
    parser.add_argument("--max-open-positions", type=int, default=16)
    parser.add_argument("--portfolio-new-entries-per-bar", type=int, default=2)
    parser.add_argument("--max-total-margin-pct", type=float, default=80.0)
    parser.add_argument("--priority-symbols", default="BTC,ETH")
    parser.add_argument("--entry-score", type=float, default=90.0)
    parser.add_argument("--min-confirmations", type=int, default=2)
    parser.add_argument("--allow-long", type=parse_bool, default=True)
    parser.add_argument("--allow-short", type=parse_bool, default=True)
    parser.add_argument("--base-leverage", type=float, default=5.0)
    parser.add_argument("--max-leverage", type=float, default=20.0)
    parser.add_argument("--margin-pct", type=float, default=2.0)
    parser.add_argument("--min-margin", type=float, default=300.0)
    parser.add_argument("--max-margin", type=float, default=500.0)
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--reward-r", type=float, default=1.6)
    parser.add_argument("--atr-stop-mult", type=float, default=1.8)
    parser.add_argument("--min-stop-pct", type=float, default=0.7)
    parser.add_argument("--max-stop-pct", type=float, default=3.8)
    parser.add_argument("--min-atr-pct", type=float, default=0.6)
    parser.add_argument("--max-atr-pct", type=float, default=12.0)
    parser.add_argument("--trend-adx", type=float, default=25.0)
    parser.add_argument("--range-adx", type=float, default=18.0)
    parser.add_argument("--max-hold-bars", type=int, default=6)
    parser.add_argument("--account-stop-pct", type=float, default=35.0)
    parser.add_argument("--enable-backtest-180d-guards", type=parse_bool, default=True)
    parser.add_argument("--bt-alt-long-min-hard", type=int, default=2)
    parser.add_argument("--bt-alt-long-min-soft", type=int, default=2)
    parser.add_argument("--bt-alt-long-min-adx", type=float, default=24.0)
    parser.add_argument("--bt-alt-long-min-vol-z", type=float, default=0.0)
    parser.add_argument("--bt-alt-long-max-chg-24h", type=float, default=10.0)
    parser.add_argument("--bt-alt-long-max-rsi", type=float, default=72.0)
    parser.add_argument("--bt-alt-long-max-distance-ema20-pct", type=float, default=2.2)
    parser.add_argument("--bt-alt-long-margin-scale", type=float, default=0.55)
    parser.add_argument("--bt-choppy-margin-scale", type=float, default=0.60)
    parser.add_argument("--bt-nonpriority-long-leverage-cap", type=float, default=8.0)
    parser.add_argument("--bt-short-hot-atr-leverage-cap", type=float, default=6.0)
    parser.add_argument("--bt-high-score-heat-floor", type=float, default=80.0)
    parser.add_argument("--bt-extreme-score-heat-floor", type=float, default=88.0)
    parser.add_argument("--bt-high-score-margin-scale", type=float, default=0.55)
    parser.add_argument("--bt-extreme-score-margin-scale", type=float, default=0.42)
    parser.add_argument("--bt-short-high-score-margin-scale", type=float, default=0.50)
    parser.add_argument("--bt-high-score-leverage-cap", type=float, default=8.0)
    parser.add_argument("--bt-extreme-score-leverage-cap", type=float, default=6.0)
    parser.add_argument("--bt-short-high-score-leverage-cap", type=float, default=6.0)
    parser.add_argument("--bt-large-margin-threshold", type=float, default=1500.0)
    parser.add_argument("--bt-large-margin-min-atr-pct", type=float, default=1.8)
    parser.add_argument("--bt-max-vol-z", type=float, default=2.0)
    parser.add_argument("--bt-adx-dead-zone-low", type=float, default=35.0)
    parser.add_argument("--bt-adx-dead-zone-high", type=float, default=45.0)
    parser.add_argument("--bt-extreme-adx", type=float, default=60.0)
    parser.add_argument("--bt-extreme-adx-min-abs-chg-24h", type=float, default=5.0)
    parser.add_argument("--bt-hot-score-low", type=float, default=80.0)
    parser.add_argument("--bt-hot-score-high", type=float, default=100.0)
    parser.add_argument("--enable-futures-long-replay-throttle", type=parse_bool, default=True)
    parser.add_argument("--futures-long-replay-min-score", type=float, default=70.0)
    parser.add_argument("--futures-long-replay-hot-score", type=float, default=75.0)
    parser.add_argument("--enable-oracle-180d-profile", type=parse_bool, default=True)
    parser.add_argument("--oracle-atr-floor-pct", type=float, default=0.6)
    parser.add_argument("--oracle-atr-preferred-pct", type=float, default=1.0)
    parser.add_argument("--oracle-atr-strong-pct", type=float, default=1.6)
    parser.add_argument("--oracle-atr-hot-pct", type=float, default=2.5)
    parser.add_argument("--oracle-adx-floor", type=float, default=25.0)
    parser.add_argument("--oracle-adx-strong", type=float, default=35.0)
    parser.add_argument("--oracle-adx-elite", type=float, default=45.0)
    parser.add_argument("--oracle-preferred-abs-chg-24h-pct", type=float, default=8.0)
    parser.add_argument("--oracle-max-abs-chg-24h-pct", type=float, default=15.0)
    parser.add_argument("--oracle-preferred-ema20-distance-pct", type=float, default=2.0)
    parser.add_argument("--oracle-max-ema20-distance-pct", type=float, default=4.0)
    parser.add_argument("--oracle-fast-adverse-cut-pct", type=float, default=2.5)
    parser.add_argument("--oracle-fast-adverse-bars", type=int, default=3)
    parser.add_argument("--oracle-trend-hold-bars", type=int, default=48)
    parser.add_argument("--oracle-low-atr-margin-scale", type=float, default=0.60)
    parser.add_argument("--oracle-hot-atr-margin-scale", type=float, default=0.72)
    parser.add_argument("--oracle-strong-trend-margin-scale", type=float, default=1.08)
    parser.add_argument("--oracle-low-quality-leverage-cap", type=float, default=6.0)
    parser.add_argument("--oracle-hot-atr-leverage-cap", type=float, default=8.0)
    parser.add_argument("--oracle-strong-trend-leverage-bonus", type=float, default=2.0)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(expanded_argv)
    if args.advanced_help:
        print(parser.format_help())
        return 0

    out_root = Path(args.output_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = out_root / stamp
    cache_dir = out_root / "cache"
    symbols_source = args.symbols if raw_has_symbols or not args.symbols_file else ""
    symbols = merge_symbols(symbols_source, args.symbols_file)
    args.symbols = ",".join(symbols)
    start_ms, end_ms, window_label = resolve_time_window(args)
    args.resolved_start_ms = start_ms
    args.resolved_end_ms = end_ms
    args.resolved_start_utc = utc_text(start_ms)
    args.resolved_end_utc = utc_text(end_ms)
    if not symbols:
        raise SystemExit("--symbols is required unless you use a preset. Try: --preset demo, --list-presets, or --examples")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "dry-run",
                    "version": VERSION,
                    "message": "配置解析成功，未联网拉取 K 线，也未执行回测。",
                    "symbols": symbols,
                    "config": vars(args),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    results: list[dict[str, Any]] = []

    if args.portfolio_mode:
        bars_by_inst: dict[str, list[Bar]] = {}
        for symbol in symbols:
            try:
                if args.data_source == "geckoterminal":
                    inst_id, candles = fetch_geckoterminal_candles(
                        symbol,
                        args.bar,
                        args.days,
                        cache_dir,
                        network_default=args.onchain_network,
                        id_type_default=args.onchain_id_type,
                        currency=args.gecko_currency,
                        token_side=args.gecko_token_side,
                        limit=args.gecko_limit,
                        refresh=args.refresh,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        window_label=window_label,
                    )
                else:
                    inst_id = normalize_inst_id(symbol, args.inst_type, args.quote)
                    candles = fetch_candles(inst_id, args.bar, args.days, cache_dir, refresh=args.refresh, start_ms=start_ms, end_ms=end_ms, window_label=window_label)
                bars_by_inst[inst_id] = candles
            except Exception as exc:
                inst_id = symbol if args.data_source == "geckoterminal" else normalize_inst_id(symbol, args.inst_type, args.quote)
                results.append({"inst_id": inst_id, "error": str(exc), "trades": [], "start": 0.0, "end": 0.0, "max_dd": 0.0})
        if bars_by_inst:
            results.append(backtest_portfolio(bars_by_inst, args, args.starting_balance))
    else:
        per_symbol_balance = args.starting_balance / len(symbols)
        for symbol in symbols:
            try:
                if args.data_source == "geckoterminal":
                    inst_id, candles = fetch_geckoterminal_candles(
                        symbol,
                        args.bar,
                        args.days,
                        cache_dir,
                        network_default=args.onchain_network,
                        id_type_default=args.onchain_id_type,
                        currency=args.gecko_currency,
                        token_side=args.gecko_token_side,
                        limit=args.gecko_limit,
                        refresh=args.refresh,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        window_label=window_label,
                    )
                else:
                    inst_id = normalize_inst_id(symbol, args.inst_type, args.quote)
                    candles = fetch_candles(inst_id, args.bar, args.days, cache_dir, refresh=args.refresh, start_ms=start_ms, end_ms=end_ms, window_label=window_label)
                result = backtest_symbol(inst_id, candles, args, per_symbol_balance)
            except Exception as exc:
                inst_id = symbol if args.data_source == "geckoterminal" else normalize_inst_id(symbol, args.inst_type, args.quote)
                result = {"inst_id": inst_id, "error": str(exc), "trades": [], "start": per_symbol_balance, "end": per_symbol_balance, "max_dd": 0.0}
            results.append(result)

    metrics = metrics_for(results, args.starting_balance)
    write_outputs(out_dir, results, metrics, args)
    print(json.dumps({"status": "ok", "version": VERSION, "output_dir": str(out_dir), "metrics": metrics}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
