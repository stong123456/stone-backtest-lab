from __future__ import annotations

import argparse
import base64
import csv
import itertools
import json
import math
import random
import statistics
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from render_visual_report import render_report


VERSION = "hermes-backtest-lab-v2.2.0"
ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "scripts" / "hermes_backtest_lab.py"
DEFAULT_OUTPUT = ROOT / "outputs" / "hermes_backtest_lab_v2"
DEFAULT_CORE_CACHE = ROOT / "outputs" / "hermes_backtest_lab" / "cache"
CREATOR_NAME = "@Stone141319"
CREATOR_URL = "https://x.com/Stone141319"
AVATAR_PATH = ROOT / "assets" / "stone141319-avatar.png"


@dataclass
class RunResult:
    label: str
    params: dict[str, Any]
    output_dir: str
    metrics: dict[str, Any]
    visual_report: str = ""


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def parse_utc_datetime(value: str | None, default: datetime) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return default
    normalized = raw.replace("Z", "+00:00")
    if len(normalized) == 10 and normalized[4] == "-" and normalized[7] == "-":
        dt = datetime.strptime(normalized, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
    return dt


def date_arg(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
      <span><b>{CREATOR_NAME}</b><em>关注我，持续更新量化回测工具和自动交易实验</em></span>
    </a>
    """


def score_metrics(metrics: dict[str, Any]) -> float:
    ret = safe_float(metrics.get("total_return_pct"))
    dd = safe_float(metrics.get("max_drawdown_pct"))
    pf = safe_float(metrics.get("profit_factor"))
    trades = safe_float(metrics.get("total_trades"))
    win = safe_float(metrics.get("win_rate_pct"))
    trade_penalty = 0.0 if trades >= 20 else (20 - trades) * 0.8
    return ret * 1.0 + pf * 8.0 + win * 0.08 - dd * 1.4 - trade_penalty


def parse_json_from_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"no JSON result in core output: {text[-1000:]}")
    return json.loads(text[start : end + 1])


def run_core(label: str, base_args: list[str], params: dict[str, Any], out_root: Path) -> RunResult:
    run_out = out_root / "runs"
    run_out.mkdir(parents=True, exist_ok=True)
    param_args: list[str] = []
    for key, value in params.items():
        param_args.extend([f"--{key.replace('_', '-')}", str(value)])
    cmd = [sys.executable, str(CORE), *base_args, *param_args, "--output-dir", str(run_out)]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=60 * 60 * 2)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "core run failed")[-3000:])
    payload = parse_json_from_stdout(proc.stdout)
    output_dir = payload.get("output_dir", "")
    visual_report = ""
    if output_dir:
        try:
            run_dir = Path(output_dir)
            run_cache = run_dir.parent / "cache"
            visual_report = str(render_report(run_dir, run_cache if run_cache.exists() else DEFAULT_CORE_CACHE))
        except Exception as exc:
            write_json(run_out / f"{label}-visual-report-error.json", {"label": label, "output_dir": output_dir, "error": str(exc)})
    return RunResult(label=label, params=params, output_dir=output_dir, metrics=payload.get("metrics", {}), visual_report=visual_report)


def parse_grid(values: list[str]) -> dict[str, list[str]]:
    grid: dict[str, list[str]] = {}
    for item in values:
        if "=" not in item:
            raise SystemExit(f"bad --grid item: {item}. Use name=a,b,c")
        key, raw = item.split("=", 1)
        grid[key.strip().replace("-", "_")] = [part.strip() for part in raw.split(",") if part.strip()]
    return grid


def default_grid() -> dict[str, list[str]]:
    return {
        "entry_score": ["80", "85", "90"],
        "max_leverage": ["8", "12", "20"],
        "reward_r": ["1.2", "1.6", "2.0"],
        "bt_large_margin_min_atr_pct": ["1.4", "1.8", "2.2"],
    }


def grid_param_sets(grid: dict[str, list[str]], limit: int) -> list[dict[str, Any]]:
    keys = list(grid)
    combos = [dict(zip(keys, combo)) for combo in itertools.product(*(grid[key] for key in keys))]
    return combos[:limit]


def genetic_param_sets(grid: dict[str, list[str]], population: int, generations: int) -> list[dict[str, Any]]:
    rng = random.Random(141319)
    keys = list(grid)

    def sample() -> dict[str, Any]:
        return {key: rng.choice(grid[key]) for key in keys}

    population_rows = [sample() for _ in range(max(population, 4))]
    all_rows: list[dict[str, Any]] = []
    for _ in range(max(generations, 1)):
        all_rows.extend(population_rows)
        parents = population_rows[: max(2, len(population_rows) // 3)]
        children: list[dict[str, Any]] = []
        while len(children) < population:
            a, b = rng.sample(parents, 2)
            child = {key: (a[key] if rng.random() < 0.5 else b[key]) for key in keys}
            if rng.random() < 0.35:
                key = rng.choice(keys)
                child[key] = rng.choice(grid[key])
            children.append(child)
        population_rows = children
    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in all_rows:
        sig = json.dumps(row, sort_keys=True)
        if sig not in seen:
            seen.add(sig)
            unique.append(row)
    return unique


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def open_html_report(path: Path) -> bool:
    try:
        return bool(webbrowser.open(path.resolve().as_uri()))
    except Exception:
        return False


def result_row(result: RunResult) -> dict[str, Any]:
    m = result.metrics
    return {
        "label": result.label,
        "score": round(score_metrics(m), 4),
        "return_pct": m.get("total_return_pct"),
        "max_drawdown_pct": m.get("max_drawdown_pct"),
        "win_rate_pct": m.get("win_rate_pct"),
        "profit_factor": m.get("profit_factor"),
        "total_trades": m.get("total_trades"),
        "ending_balance": m.get("ending_balance"),
        "params": json.dumps(result.params, ensure_ascii=False, sort_keys=True),
        "output_dir": result.output_dir,
        "visual_report": result.visual_report,
    }


def row_value_keys(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    base = ["label", "score", "return_pct", "max_drawdown_pct", "win_rate_pct", "profit_factor", "total_trades"]
    window_keys = ["train_start", "train_end", "test_start", "test_end"]
    keys = [*base, *(key for key in window_keys if any(row.get(key) for row in rows)), "params"]
    return tuple(keys)


def load_trades(output_dir: str) -> list[dict[str, Any]]:
    path = Path(output_dir) / "trades.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def monte_carlo_from_trades(trades: list[dict[str, Any]], starting_balance: float, sims: int = 500) -> dict[str, Any]:
    pnls = [safe_float(row.get("pnl_usdt")) for row in trades]
    if not pnls:
        return {"sims": 0, "note": "no trades"}
    rng = random.Random(20260617)
    endings: list[float] = []
    max_dds: list[float] = []
    ruin_count = 0
    for _ in range(sims):
        equity = starting_balance
        peak = equity
        max_dd = 0.0
        sample = [rng.choice(pnls) for _ in pnls]
        for pnl in sample:
            equity += pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / max(peak, 1e-9) * 100.0)
            if equity <= starting_balance * 0.7:
                ruin_count += 1
                break
        endings.append(equity)
        max_dds.append(max_dd)
    endings_sorted = sorted(endings)
    dd_sorted = sorted(max_dds)
    return {
        "sims": sims,
        "ending_p05": round(percentile(endings_sorted, 5), 4),
        "ending_p50": round(percentile(endings_sorted, 50), 4),
        "ending_p95": round(percentile(endings_sorted, 95), 4),
        "max_dd_p50_pct": round(percentile(dd_sorted, 50), 4),
        "max_dd_p95_pct": round(percentile(dd_sorted, 95), 4),
        "ruin_probability_pct": round(ruin_count / sims * 100.0, 4),
    }


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    pos = (len(sorted_values) - 1) * pct / 100.0
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def html_report(path: Path, title: str, rows: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    top_rows = sorted(rows, key=lambda row: safe_float(row.get("score")), reverse=True)[:30]
    keys = row_value_keys(top_rows)
    bars = "".join(
        f"<div class='bar'><span>{escape(row['label'])}</span><b style='width:{max(2, min(100, safe_float(row.get('score')) + 30))}%'>{row.get('score')}</b></div>"
        for row in top_rows[:12]
    )
    table = "".join(
        "<tr>"
        + "".join(
            f"<td>{escape(str(row.get(key, '')))}</td>"
            for key in keys
        )
        + f"<td>{report_link(row)}</td>"
        + "</tr>"
        for row in top_rows
    )
    body = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
body{{margin:0;background:#0b1020;color:#edf3ff;font-family:Segoe UI,Microsoft YaHei,sans-serif;}}
.wrap{{max-width:1180px;margin:0 auto;padding:42px 28px;}}
.hero{{border:1px solid #2b416f;background:linear-gradient(135deg,#121a33,#08111f 55%,#172b46);border-radius:28px;padding:34px;box-shadow:0 30px 80px #0008;}}
h1{{margin:0 0 10px;font-size:36px;}}
.muted{{color:#9fb2d8;}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:24px;}}
.card{{border:1px solid #273b66;background:#111a2f;border-radius:22px;padding:22px;}}
.bar{{display:flex;align-items:center;gap:12px;margin:10px 0;}}
.bar span{{width:220px;color:#b9c9e8;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.bar b{{display:block;background:linear-gradient(90deg,#35d6ff,#ffd166);color:#06101f;border-radius:999px;padding:4px 8px;min-width:34px;font-size:12px;}}
table{{width:100%;border-collapse:collapse;margin-top:24px;background:#0e172a;border-radius:18px;overflow:hidden;}}
th,td{{border-bottom:1px solid #22365e;padding:10px;font-size:12px;text-align:left;vertical-align:top;}}
th{{background:#162342;color:#cfe0ff;}}
pre{{white-space:pre-wrap;background:#07101e;border:1px solid #24375d;border-radius:18px;padding:16px;max-height:420px;overflow:auto;}}
.hero-top{{display:flex;align-items:flex-start;justify-content:space-between;gap:22px;}}
.creator-card{{display:flex;align-items:center;gap:12px;min-width:270px;max-width:380px;padding:12px 14px;border:1px solid rgba(255,209,102,.42);border-radius:999px;background:rgba(255,209,102,.10);color:#edf3ff;text-decoration:none;}}
.creator-card img,.avatar-fallback{{width:58px;height:58px;border-radius:50%;border:2px solid rgba(255,209,102,.86);object-fit:cover;flex:0 0 auto;}}
.avatar-fallback{{display:grid;place-items:center;background:#ffd166;color:#08111f;font-weight:900;}}
.creator-card b{{display:block;color:#ffd166;font-size:17px;}}
.creator-card em{{display:block;margin-top:2px;color:#cfd9eb;font-style:normal;font-size:12px;line-height:1.35;}}
@media(max-width:860px){{.grid{{grid-template-columns:1fr;}}.hero-top{{flex-direction:column;}}.creator-card{{width:100%;min-width:0;border-radius:22px;}}}}
</style>
</head>
<body><div class="wrap">
<section class="hero"><div class="hero-top"><div><h1>{escape(title)}</h1><p class="muted">石头量化回测实验室 v2.2 / Hermes Backtest Lab v2.2. Bitget / OKX / on-chain data ready. Walk-forward / optimization / Monte Carlo / strategy portfolio ready.</p></div>{creator_card()}</div></section>
<div class="grid"><div class="card"><h2>Top Scores</h2>{bars}</div><div class="card"><h2>Payload</h2><pre>{escape(json.dumps(payload, ensure_ascii=False, indent=2)[:6000])}</pre></div></div>
<h2>Runs</h2>
<table><thead><tr>{''.join(f'<th>{escape(key)}</th>' for key in keys)}<th>visual report</th></tr></thead><tbody>{table}</tbody></table>
</div></body></html>"""
    path.write_text(body, encoding="utf-8")


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def report_link(row: dict[str, Any]) -> str:
    path = str(row.get("visual_report") or "")
    if not path:
        return "-"
    href = Path(path).as_uri()
    return f'<a href="{escape(href)}" style="color:#35d6ff;font-weight:700;">打开页面报告</a>'


def run_optimizer(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = args.output_dir / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out_dir.mkdir(parents=True, exist_ok=True)
    grid = parse_grid(args.grid) if args.grid else default_grid()
    param_sets = (
        genetic_param_sets(grid, args.population, args.generations)
        if args.mode == "genetic"
        else grid_param_sets(grid, args.limit)
    )
    results: list[RunResult] = []
    for idx, params in enumerate(param_sets[: args.limit], start=1):
        label = f"{args.mode}-{idx:03d}"
        try:
            results.append(run_core(label, args.core_args, params, out_dir))
        except Exception as exc:
            write_json(out_dir / f"{label}-error.json", {"label": label, "params": params, "error": str(exc)})
    rows = sorted([result_row(item) for item in results], key=lambda row: safe_float(row.get("score")), reverse=True)
    best = rows[0] if rows else {}
    payload = {"version": VERSION, "mode": args.mode, "grid": grid, "best": best, "run_count": len(rows)}
    write_json(out_dir / "optimizer_summary.json", payload)
    write_csv(out_dir / "optimizer_runs.csv", rows)
    report_path = out_dir / "optimizer_report.html"
    html_report(report_path, "Hermes Backtest Lab v2.2 参数优化报告", rows, payload)
    opened = open_html_report(report_path) if args.open_report else False
    return {"status": "ok", "output_dir": str(out_dir), "report": str(report_path), "opened": opened, **payload}


def run_monte_carlo(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = args.output_dir / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    base = run_core("base", args.core_args, {}, out_dir)
    trades = load_trades(base.output_dir)
    mc = monte_carlo_from_trades(trades, safe_float(base.metrics.get("starting_balance"), args.starting_balance), args.sims)
    rows = [result_row(base)]
    payload = {"version": VERSION, "mode": "monte-carlo", "base_output_dir": base.output_dir, "monte_carlo": mc}
    write_json(out_dir / "monte_carlo_summary.json", payload)
    report_path = out_dir / "monte_carlo_report.html"
    html_report(report_path, "Hermes Backtest Lab v2.2 Monte Carlo 鲁棒性报告", rows, payload)
    opened = open_html_report(report_path) if args.open_report else False
    return {"status": "ok", "output_dir": str(out_dir), "report": str(report_path), "opened": opened, **payload}


def run_walk_forward(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = args.output_dir / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    grid = parse_grid(args.grid) if args.grid else default_grid()
    windows: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    total_days = args.train_days + args.test_days + max(args.walk_windows - 1, 0) * args.step_days
    default_start = datetime.now(timezone.utc) - timedelta(days=total_days)
    walk_start = parse_utc_datetime(args.walk_start_date, default_start)
    for idx in range(args.walk_windows):
        train_start = walk_start + timedelta(days=idx * args.step_days)
        train_end = train_start + timedelta(days=args.train_days)
        test_start = train_end
        test_end = test_start + timedelta(days=args.test_days)
        train_args = [
            *args.core_args,
            "--days",
            str(args.train_days),
            "--start-date",
            date_arg(train_start),
            "--end-date",
            date_arg(train_end),
        ]
        test_args_base = [
            *args.core_args,
            "--days",
            str(args.test_days),
            "--start-date",
            date_arg(test_start),
            "--end-date",
            date_arg(test_end),
        ]
        train_sets = grid_param_sets(grid, args.walk_candidates)
        train_results: list[RunResult] = []
        for pidx, params in enumerate(train_sets, start=1):
            try:
                train_results.append(run_core(f"wf{idx+1}-train-{pidx:02d}", train_args, params, out_dir))
            except Exception:
                continue
        ranked = sorted(train_results, key=lambda res: score_metrics(res.metrics), reverse=True)
        best_params = ranked[0].params if ranked else {}
        test_result = run_core(f"wf{idx+1}-test", test_args_base, best_params, out_dir)
        row = result_row(test_result)
        row["train_start"] = date_arg(train_start)
        row["train_end"] = date_arg(train_end)
        row["test_start"] = date_arg(test_start)
        row["test_end"] = date_arg(test_end)
        row["train_days"] = args.train_days
        row["test_days"] = args.test_days
        rows.append(row)
        windows.append(
            {
                "window": idx + 1,
                "train_start": date_arg(train_start),
                "train_end": date_arg(train_end),
                "test_start": date_arg(test_start),
                "test_end": date_arg(test_end),
                "train_days": args.train_days,
                "test_days": args.test_days,
                "best_params": best_params,
                "test": row,
            }
        )
    payload = {"version": VERSION, "mode": "walk-forward", "walk_start_date": date_arg(walk_start), "windows": windows}
    write_json(out_dir / "walk_forward_summary.json", payload)
    write_csv(out_dir / "walk_forward_windows.csv", rows)
    report_path = out_dir / "walk_forward_report.html"
    html_report(report_path, "Hermes Backtest Lab v2.2 Walk-forward 报告", rows, payload)
    opened = open_html_report(report_path) if args.open_report else False
    return {"status": "ok", "output_dir": str(out_dir), "report": str(report_path), "opened": opened, **payload}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hermes Backtest Lab v2.2: optimizer, walk-forward, Monte Carlo and HTML reports.")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--mode", choices=["grid", "genetic", "walk-forward", "monte-carlo"], default="grid")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--grid", action="append", default=[], help="Parameter grid item, e.g. entry-score=80,85,90. Can repeat.")
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--population", type=int, default=10)
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--sims", type=int, default=500)
    parser.add_argument("--starting-balance", type=float, default=100000.0)
    parser.add_argument("--train-days", type=int, default=90)
    parser.add_argument("--test-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=30)
    parser.add_argument("--walk-windows", type=int, default=3)
    parser.add_argument("--walk-candidates", type=int, default=8)
    parser.add_argument("--walk-start-date", default="", help="UTC start of the first training window. Default uses enough recent history for all windows.")
    parser.add_argument("--open-report", dest="open_report", action="store_true", default=True, help="Open the main HTML report in your default browser. Enabled by default.")
    parser.add_argument("--no-open-report", dest="open_report", action="store_false", help="Do not open the browser after the run.")
    parser.add_argument("core_args", nargs=argparse.REMAINDER, help="Arguments passed to scripts/hermes_backtest_lab.py after --")
    args = parser.parse_args(argv)
    if args.core_args and args.core_args[0] == "--":
        args.core_args = args.core_args[1:]
    if not args.core_args:
        args.core_args = ["--preset", "demo"]
    if args.mode in ("grid", "genetic"):
        payload = run_optimizer(args)
    elif args.mode == "monte-carlo":
        payload = run_monte_carlo(args)
    else:
        payload = run_walk_forward(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
