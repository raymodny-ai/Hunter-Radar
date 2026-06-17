"""§3.1.9 M4 接力 — BD-085 数据集构建演示 wrapper。

- 默认调 `python -m etl.backtest_dataset` 主入口(已带 argparse)
- 沙箱下设 HR_SANDBOX_SKIP=1 走空跑分支(不连 PG,退 0)
- 真实环境下需保证 daily_price / short_volume / form4_event 已有 ≥ 1 年数据
  (否则 res.inserted=0,只能等历史 EOD 拉满)

用法:
    HR_SANDBOX_SKIP=1 python scripts/m4_build_dataset.py            # 沙箱演示
    python scripts/m4_build_dataset.py --tickers AAPL,TSLA --years 1  # 真实跑
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# 让子进程能找到 backend/ 下的 etl/ 与 app/
BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hunter Radar V1.4 — M4 BD-085 wrapper")
    p.add_argument("--end", default=os.environ.get("HR_BT_END", "2024-12-31"), help="截止日 YYYY-MM-DD")
    p.add_argument("--years", type=int, default=int(os.environ.get("HR_BT_YEARS", "2")))
    p.add_argument(
        "--tickers",
        default=os.environ.get("HR_BT_TICKERS", ""),
        help="逗号分隔;留空走全 universe",
    )
    p.add_argument(
        "--sandbox-skip",
        action="store_true",
        default=os.environ.get("HR_SANDBOX_SKIP") == "1",
        help="沙箱下不连 PG,SKIP 退 0",
    )
    p.add_argument("--python", default=sys.executable, help="python 解释器(默认当前)")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    # 沙箱直接 SKIP 退 0(与 etl.backtest_dataset.main 内部逻辑一致)
    if args.sandbox_skip:
        print(
            f"[m4_build_dataset] SKIP sandbox (no PG). end={args.end} years={args.years} "
            f"tickers={args.tickers or '<universe>'}"
        )
        return 0

    # 真实环境:子进程跑 etl.backtest_dataset 主入口
    cmd = [
        args.python,
        "-m",
        "etl.backtest_dataset",
        "--end",
        args.end,
        "--years",
        str(args.years),
    ]
    if args.tickers.strip():
        cmd += ["--tickers", args.tickers]

    print(f"[m4_build_dataset] exec: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(BACKEND_ROOT), check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
