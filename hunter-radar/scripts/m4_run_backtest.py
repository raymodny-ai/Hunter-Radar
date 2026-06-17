"""§3.1.9 M4 接力 — BD-089 回测 CLI 演示 wrapper。

- 默认调 `python -m app.services.backtest run/compare` 主入口(已带 argparse)
- 沙箱下设 HR_SANDBOX_SKIP=1 走空跑分支(无 PG/无 backtest_dataset,退 0)
- 真实环境需保证:
  1. backtest_dataset 表已灌历史(走 m4_build_dataset.py)
  2. backtest_event_goldset 表已灌事件(走 etl.backtest_event_goldset.bulk_import_from_jsonl)
  3. settings.threat_red_threshold 已设为 70(校准前默认)

用法:
    HR_SANDBOX_SKIP=1 python scripts/m4_run_backtest.py run     # 沙箱演示
    python scripts/m4_run_backtest.py run --tickers AAPL,TSLA --start 2023-01-01 --end 2024-01-01
    python scripts/m4_run_backtest.py compare --tickers AAPL --weights-a stock --weights-b etf
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hunter Radar V1.4 — M4 BD-089 wrapper")
    p.add_argument(
        "--sandbox-skip",
        action="store_true",
        default=os.environ.get("HR_SANDBOX_SKIP") == "1",
        help="沙箱下不连 PG,SKIP 退 0",
    )
    p.add_argument("--python", default=sys.executable)
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="单组权重回测")
    pr.add_argument("--tickers", default="AAPL,TSLA,GME,AMC,META,COIN,LCID")
    pr.add_argument("--start", default="2023-01-01")
    pr.add_argument("--end", default="2024-12-31")
    pr.add_argument("--weights", default="default")
    pr.add_argument("--halflife", type=int, default=2)
    pr.add_argument("--output", default="backtest_output")

    pc = sub.add_parser("compare", help="A/B 权重对比")
    pc.add_argument("--tickers", default="AAPL,TSLA,GME,AMC,META,COIN,LCID")
    pc.add_argument("--start", default="2023-01-01")
    pc.add_argument("--end", default="2024-12-31")
    pc.add_argument("--weights-a", default="stock")
    pc.add_argument("--weights-b", default="etf")
    pc.add_argument("--halflife", type=int, default=2)
    pc.add_argument("--output", default="backtest_output")
    return p.parse_args()


def _build_summary(args: argparse.Namespace) -> str:
    """沙箱演示用的「假如真跑」summary(无实际数据)。"""
    if args.cmd == "run":
        return (
            f"[m4_run_backtest] SKIP sandbox (no PG). "
            f"cmd=run tickers={args.tickers} range={args.start}..{args.end} "
            f"weights={args.weights} halflife={args.halflife} output={args.output}\n"
            f"  (生产: 期望 hit_rate≥0.55, fa_rate≤0.05, score_lift>0; 详见 BD-087 v2.0 校准基线)"
        )
    return (
        f"[m4_run_backtest] SKIP sandbox (no PG). "
        f"cmd=compare tickers={args.tickers} range={args.start}..{args.end} "
        f"weights_a={args.weights_a} vs weights_b={args.weights_b} halflife={args.halflife}\n"
        f"  (生产: 期望 B 比 A 在 ETF 标的 hit_rate 提升 ≥5%,fa_rate 下降 ≥10%)"
    )


def main() -> int:
    args = _parse_args()

    if args.sandbox_skip:
        print(_build_summary(args))
        return 0

    if args.cmd == "run":
        cmd = [
            args.python,
            "-m",
            "app.services.backtest",
            "run",
            "--tickers",
            args.tickers,
            "--start",
            args.start,
            "--end",
            args.end,
            "--weights",
            args.weights,
            "--halflife",
            str(args.halflife),
            "--output",
            args.output,
        ]
    else:  # compare
        cmd = [
            args.python,
            "-m",
            "app.services.backtest",
            "compare",
            "--tickers",
            args.tickers,
            "--start",
            args.start,
            "--end",
            args.end,
            "--weights-a",
            args.weights_a,
            "--weights-b",
            args.weights_b,
            "--halflife",
            str(args.halflife),
            "--output",
            args.output,
        ]

    print(f"[m4_run_backtest] exec: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(BACKEND_ROOT), check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
