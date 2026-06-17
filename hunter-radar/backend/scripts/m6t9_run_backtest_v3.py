"""M6-t9 BD-087 v3.0 真实回测 runner(沙箱 stub)。

CLI:
    uv run python scripts/m6t9_run_backtest_v3.py run --tickers AAPL,TSLA --start 2025-01-01 --end 2025-12-31
    uv run python scripts/m6t9_run_backtest_v3.py compare --weights-a v1.0 --weights-b candidate_a
    uv run python scripts/m6t9_run_backtest_v3.py report --input docs/BD-087-calibration-run-m6t9.json

沙箱降级:
- 无 PG → 不实跑 SQL;改返 fixture(n=0 events)
- 无 EOD → 命中/误报全 0
- runner 输出 JSON 而非写入 PG

生产应替换为:
    await session.execute(select(BacktestEvent)) + compute_threat_score(...)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

CANDIDATE_A_WEIGHTS = {
    "stock": {"options": 0.25, "short": 0.40, "divergence": 0.20, "insider": 0.15},
    "etf": {"options": 0.30, "short": 0.50, "divergence": 0.20},
}

V10_DEFAULT_WEIGHTS = {
    "stock": {"options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15},
    "etf": {"options": 0.35, "short": 0.45, "divergence": 0.20},
}


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def cmd_run(args: argparse.Namespace) -> dict:
    """沙箱 stub:不实跑历史 EOD,返 fixture 空命中。"""
    return {
        "mode": "run",
        "tickers": args.tickers.split(",") if args.tickers else [],
        "start": args.start,
        "end": args.end,
        "weights": args.weights,
        "sandbox": True,
        "n_event_days": 0,
        "n_hit_event_days": 0,
        "hit_rate": 0.0,
        "false_positive_rate": 0.0,
        "warning": "sandbox fallback: no PG / no EOD data; metrics are zero",
        "fetched_at": _now_iso(),
    }


def cmd_compare(args: argparse.Namespace) -> dict:
    """对比 v1.0 vs 候选 A 权重(沙箱无真实数据 → 返 fixture)。"""
    a_weights = V10_DEFAULT_WEIGHTS if args.weights_a == "v1.0" else CANDIDATE_A_WEIGHTS
    b_weights = CANDIDATE_A_WEIGHTS if args.weights_b == "candidate_a" else V10_DEFAULT_WEIGHTS
    return {
        "mode": "compare",
        "weights_a": {"name": args.weights_a, "values": a_weights},
        "weights_b": {"name": args.weights_b, "values": b_weights},
        "sandbox": True,
        "n_event_days": 0,
        "delta_hit_rate": 0.0,
        "delta_false_positive_rate": 0.0,
        "warning": "sandbox fallback: candidate A vs v1.0 needs real EOD (BD-085) to compare",
        "fetched_at": _now_iso(),
    }


def cmd_report(args: argparse.Namespace) -> dict:
    """读已有 runner JSON 输出,生成简报。"""
    src = Path(args.input)
    if not src.exists():
        return {"mode": "report", "error": f"missing input file: {src}"}
    data = json.loads(src.read_text(encoding="utf-8"))
    return {
        "mode": "report",
        "source": str(src),
        "sandbox": data.get("sandbox", True),
        "summary": {
            "n_event_days": data.get("n_event_days", 0),
            "hit_rate": data.get("hit_rate", 0.0),
        },
        "fetched_at": _now_iso(),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="BD-087 v3.0 backtest runner (sandbox stub)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="跑单组权重")
    p_run.add_argument("--tickers", type=str, default="", help="逗号分隔 ticker 列表")
    p_run.add_argument("--start", type=str, default="2025-01-01")
    p_run.add_argument("--end", type=str, default="2025-12-31")
    p_run.add_argument("--weights", type=str, default="v1.0", help="v1.0 | candidate_a | custom")

    p_cmp = sub.add_parser("compare", help="A/B 权重对比")
    p_cmp.add_argument("--weights-a", type=str, default="v1.0")
    p_cmp.add_argument("--weights-b", type=str, default="candidate_a")

    p_rpt = sub.add_parser("report", help="读 runner JSON 生成简报")
    p_rpt.add_argument("--input", type=str, required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "run":
        result = cmd_run(args)
    elif args.cmd == "compare":
        result = cmd_compare(args)
    elif args.cmd == "report":
        result = cmd_report(args)
    else:
        print(f"unknown cmd: {args.cmd}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())