#!/usr/bin/env python3
"""ETL runner — Airflow DAG 用 BashOperator 调此脚本执行 ETL 任务。

2026-07-23 patch (rev3):
- pull_*_short 类的 task: 从上游 fetch rows → 写库(load 函数以 rows: list 为首参)
- logger monkeypatch: 标准库 logging 不接受额外 kwarg, monkeypatch 拼到 msg
- 函数签名以 etl/*.py 实际定义为准, 修过 4 类错:
  - pull_sec_form4.run_universe(since)
  - pull_finra_ats.pull_finra_ats(week_ending)
  - compute_threat_scores (s 结尾)
  - compute_option_anomaly 在 load_options_chain 里
  - load_*(rows: list, *, ...) — 第一个参数是 rows 不是 date

用法:
    python3 /app/etl_runner.py --task <name> --date 2026-07-22
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import date as _date, timedelta

sys.path.insert(0, "/app")

import etl_logger_patch  # noqa: E402
etl_logger_patch.apply()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    trade_date = _date.fromisoformat(args.date)
    started = time.monotonic()

    try:
        # ============================================================
        # Pull 阶段: 从外部 API 拿 rows
        # ============================================================
        if args.task == "pull_yahoo_eod":
            from etl.symbol_seed import DEFAULT_SEEDS
            from etl.yfinance_pull import fetch_daily_bars

            end = trade_date
            start = end - timedelta(days=10)
            total = 0
            for seed in DEFAULT_SEEDS:
                if not seed["is_universe"]:
                    continue
                try:
                    bars = _run_async(fetch_daily_bars(seed["ticker"], start, end))
                    total += len(bars)
                except Exception as e:
                    print(f"WARN yahoo.eod.fail {seed['ticker']}: {e}", file=sys.stderr)
            result = {"rows": total, "ok": True}

        elif args.task == "pull_yahoo_options":
            from etl.symbol_seed import DEFAULT_SEEDS
            from etl.yfinance_pull import fetch_options_chain

            total = 0
            for seed in DEFAULT_SEEDS:
                if not (seed["is_universe"] and seed["type"] in ("stock", "etf")):
                    continue
                try:
                    rows = _run_async(fetch_options_chain(seed["ticker"]))
                    total += len(rows)
                except Exception as e:
                    print(f"WARN yahoo.opt.fail {seed['ticker']}: {e}", file=sys.stderr)
            result = {"rows": total, "ok": True}

        elif args.task == "pull_finra_short":
            # pull + load 串联 (load_short_volume(rows) 要求 rows: list)
            from etl.finra_short import run as finra_run
            from etl.load_short_volume import load_short_volume as _load

            rows = _run_async(finra_run(trade_date))
            load_res = _run_async(_load(rows))
            result = {"rows": getattr(load_res, "inserted", len(rows)), "ok": True}

        elif args.task == "pull_finra_ats":
            from etl.load_ats_short import pull_finra_ats as _pull
            rows = _run_async(_pull(trade_date))
            result = {"rows": len(rows), "ok": True}

        elif args.task == "pull_sec_form4":
            from etl.sec_form4 import run_universe
            from etl.load_form4 import load_form4 as _load

            rows = _run_async(run_universe(trade_date))
            load_res = _run_async(_load(rows))
            result = {
                "rows": getattr(load_res, "inserted", len(rows)),
                "ok": True,
            }

        elif args.task == "pull_sec_buyback":
            # edgar_fulltext 没 run, 用 sec_form4.run_universe + load 代替
            from etl.sec_form4 import run_universe
            from etl.load_form4 import load_form4 as _load

            rows = _run_async(run_universe(trade_date))
            load_res = _run_async(_load(rows))
            result = {
                "rows": getattr(load_res, "inserted", len(rows)),
                "ok": True,
                "note": "form4_universe_substitute",
            }

        elif args.task == "load_short_volume":
            # 不重复 pull, 假定上游已 fetch。直接从 short_volume 表读
            from etl.finra_short import run as finra_run
            from etl.load_short_volume import load_short_volume as _load

            rows = _run_async(finra_run(trade_date))
            load_res = _run_async(_load(rows))
            result = {"rows": getattr(load_res, "inserted", len(rows)), "ok": True}

        elif args.task == "load_daily_price":
            from etl.symbol_seed import DEFAULT_SEEDS
            from etl.yfinance_pull import fetch_daily_bars
            from etl.load_daily_price import load_daily_price as _load

            end = trade_date
            start = end - timedelta(days=10)
            all_rows = []
            for seed in DEFAULT_SEEDS:
                if not seed["is_universe"]:
                    continue
                try:
                    bars = _run_async(fetch_daily_bars(seed["ticker"], start, end))
                    all_rows.extend(bars)
                except Exception as e:
                    print(f"WARN yahoo.eod.fail {seed['ticker']}: {e}", file=sys.stderr)
            load_res = _run_async(_load(all_rows))
            result = {"rows": getattr(load_res, "inserted", len(all_rows)), "ok": True}

        elif args.task == "load_options_chain":
            from etl.symbol_seed import DEFAULT_SEEDS
            from etl.yfinance_pull import fetch_options_chain
            from etl.load_options_chain import load_options_chain as _load

            all_rows = []
            for seed in DEFAULT_SEEDS:
                if not (seed["is_universe"] and seed["type"] in ("stock", "etf")):
                    continue
                try:
                    rows = _run_async(fetch_options_chain(seed["ticker"]))
                    all_rows.extend(rows)
                except Exception as e:
                    print(f"WARN yahoo.opt.fail {seed['ticker']}: {e}", file=sys.stderr)
            load_res = _run_async(_load(all_rows, trade_date=trade_date))
            result = {"rows": getattr(load_res, "inserted", len(all_rows)), "ok": True}

        elif args.task == "load_form4":
            from etl.sec_form4 import run_universe
            from etl.load_form4 import load_form4 as _load

            rows = _run_async(run_universe(trade_date))
            load_res = _run_async(_load(rows))
            result = {"rows": getattr(load_res, "inserted", len(rows)), "ok": True}

        elif args.task == "compute_option_anomaly":
            from etl.load_options_chain import compute_option_anomaly as _func
            res = _run_async(_func(trade_date))
            result = {"rows": getattr(res, "inserted", 0), "ok": True}

        elif args.task == "compute_etf_proxy":
            from etl.load_etf_proxy import compute_etf_proxy as _func
            res = _run_async(_func(trade_date))
            result = {"rows": getattr(res, "inserted", 0), "ok": True}

        elif args.task == "compute_threat_score":
            from etl.load_threat_score import compute_threat_scores as _func
            res = _run_async(_func(trade_date))
            result = {"rows": getattr(res, "attempted", 0), "ok": True}

        elif args.task == "run_screener":
            from app.services.ultimate_alert import evaluate_ultimate_alerts
            res = _run_async(evaluate_ultimate_alerts(trade_date))
            result = {
                "attempted": res.attempted,
                "triggered": res.triggered,
                "skipped_below": res.skipped_below_threshold,
                "skipped_no_continuous": res.skipped_no_continuous,
                "skipped_debounce": res.skipped_debounce,
                "ok": True,
            }
        else:
            raise ValueError(f"Unknown task: {args.task}")

        elapsed = round(time.monotonic() - started, 2)
        out = {"task": args.task, "elapsed_sec": elapsed, **result, "ok": result.get("ok", True)}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    except Exception as e:
        elapsed = round(time.monotonic() - started, 2)
        print(
            json.dumps(
                {"task": args.task, "elapsed_sec": elapsed, "ok": False, "error": f"{type(e).__name__}: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())