"""Airflow DAG:Hunter Radar 每日 EOD 流水线(M1 末,任务依赖完整版)。

任务顺序(BD-003 / BD-004 / BD-005 / BD-006 / BD-008 / BD-009 / BD-011):
    pull_finra_short   ─┐
    pull_finra_ats     ─┼─→ load_short_volume   ─→  refresh_data_status
    pull_yahoo_eod     ─┼─→ load_daily_price    ─┐
    pull_yahoo_options ─┼─→ load_options_chain   ─┼─→ compute_option_anomaly ─→ refresh_data_status
    pull_sec_form4     ─┼─→ load_form4          ─┤
    pull_sec_buyback   ─┘                        ─→ compute_etf_proxy     ─→ refresh_data_status
                                                                ↓
                                                    compute_threat_score(M2 末) → screener(M3)

所有 task 内部调 ETL 函数;每个 ETL task 尾部串接 `refresh_data_status`。
Airflow 进程内不能直接 await asyncio.run()(会污染事件循环),这里用 sync wrapper + subprocess 调用
(更稳);或继续用 asyncio.run()(scheduler 会启动新 loop,本仓库测试过 OK)。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task

log = logging.getLogger(__name__)

# ---- 默认参数 ----
default_args = {
    "owner": "hunter-radar",
    "depends_on_past": False,
    "email": ["ops@hunter-radar.example"],
    "email_on_failure": True,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


def _run_async(coro):
    """Airflow task 内部跑协程的统一入口。"""
    import asyncio

    return asyncio.run(coro)


def _mark_status(trade_date, source: str, status: str, **detail) -> bool:
    """便捷:在 Airflow task 内写状态灯,任何错误吞咽(不阻塞主 ETL)。"""
    from etl.refresh_data_status import mark_ready, mark_failed, mark_pending, mark_skipped

    detail_str = detail.pop("detail", None) or ""
    try:
        if status == "ready":
            return _run_async(mark_ready(trade_date, source, detail={"detail": detail_str} if detail_str else None))
        if status == "failed":
            return _run_async(mark_failed(trade_date, source, error=detail_str))
        if status == "pending":
            return _run_async(mark_pending(trade_date, source, reason=detail_str))
        if status == "skipped":
            return _run_async(mark_skipped(trade_date, source, reason=detail_str))
    except Exception as e:  # noqa: BLE001
        log.warning("status_write.fail", source=source, error=str(e))
    return False


@dag(
    dag_id="hunter_radar_eod_daily",
    default_args=default_args,
    description="每日 EOD:FINRA / SEC / Yahoo → DB → 异常合约/ETF 代理 → 状态灯",
    schedule="0 22 * * 1-5",  # 美东 18:00 + 处理耗时 = UTC 22:00 触发
    start_date=datetime(2026, 6, 16),
    catchup=False,
    max_active_runs=1,
    tags=["hunter-radar", "etl", "eod"],
)
def hunter_radar_eod() -> None:
    """EOD 流水线(任务依赖完整版)。"""

    # ---- 1) 拉取任务 ----

    @task
    def pull_finra_short(trade_date: str) -> dict:
        """BD-004:FINRA 全监管做空(原始 CSV)。"""
        from datetime import date as _date
        from etl.finra_short import run as finra_run

        d = _date.fromisoformat(trade_date)
        try:
            rows = _run_async(finra_run(d))
            return {"rows": len(rows), "ok": True}
        except Exception as e:  # noqa: BLE001
            log.error("pull_finra_short.fail", error=str(e))
            return {"rows": 0, "ok": False, "error": str(e)}

    @task
    def pull_finra_ats(trade_date: str) -> dict:
        """BD-005:FINRA ATS 周报(拉取 + 落库,M3 接力实装)。"""
        from datetime import date as _date
        from etl.load_ats_short import load_ats_short, pull_finra_ats as _pull

        d = _date.fromisoformat(trade_date)
        try:
            rows = _run_async(_pull(week_ending=d))
            res = _run_async(load_ats_short(rows, source="finra_ats"))
            _mark_status(
                d,
                "finra_ats",
                "ready" if res.failures == 0 else "failed",
                detail=f"attempted={res.attempted} inserted={res.inserted} unknown={res.unknown_symbols}",
            )
            return {
                "rows": len(rows),
                "inserted": res.inserted,
                "ok": res.failures == 0,
            }
        except Exception as e:  # noqa: BLE001
            log.error("pull_finra_ats.fail", error=str(e))
            _mark_status(d, "finra_ats", "failed", detail=str(e))
            return {"rows": 0, "ok": False, "error": str(e)}

    @task
    def pull_yahoo_eod(trade_date: str) -> dict:
        """BD-008:Yahoo 日 K(Universe 标的)。"""
        from datetime import date as _date, timedelta
        from etl.symbol_seed import DEFAULT_SEEDS
        from etl.yfinance_pull import fetch_daily_bars

        end = _date.fromisoformat(trade_date)
        start = end - timedelta(days=10)
        n = 0
        for seed in DEFAULT_SEEDS:
            if not seed["is_universe"]:
                continue
            try:
                bars = _run_async(fetch_daily_bars(seed["ticker"], start, end))
                n += len(bars)
            except Exception as e:  # noqa: BLE001
                log.warning("yahoo.eod.fail", sym=seed["ticker"], error=str(e))
        return {"rows": n, "ok": True}

    @task
    def pull_yahoo_options(trade_date: str) -> dict:
        """BD-009:Yahoo 期权链(Universe 前 5 个)。"""
        from etl.symbol_seed import DEFAULT_SEEDS
        from etl.yfinance_pull import fetch_options_chain

        n = 0
        for seed in DEFAULT_SEEDS:
            if not (seed["is_universe"] and seed["type"] in ("stock", "etf")):
                continue
            try:
                rows = _run_async(fetch_options_chain(seed["ticker"]))
                n += len(rows)
            except Exception as e:  # noqa: BLE001
                log.warning("yahoo.opt.fail", sym=seed["ticker"], error=str(e))
        return {"rows": n, "ok": True}

    @task
    def pull_sec_form4(trade_date: str) -> dict:
        """BD-006:SEC Form 4 拉取 + 落库(M3 接力实装;接 EDGAR submissions API)。"""
        from datetime import date as _date, timedelta
        from etl.load_form4 import load_form4
        from etl.sec_form4 import run_universe

        d = _date.fromisoformat(trade_date)
        try:
            # 看近 30 日提交,覆盖典型 insider 提前披露窗口
            rows = _run_async(run_universe(since=d - timedelta(days=30)))
            res = _run_async(load_form4(rows))
            _mark_status(
                d,
                "sec_form4",
                "ready" if res.failures == 0 else "failed",
                detail=f"attempted={res.attempted} inserted={res.inserted} skipped_etf={res.skipped_etf}",
            )
            return {
                "rows": len(rows),
                "inserted": res.inserted,
                "skipped_etf": res.skipped_etf,
                "ok": res.failures == 0,
            }
        except Exception as e:  # noqa: BLE001
            log.error("pull_sec_form4.fail", error=str(e))
            _mark_status(d, "sec_form4", "failed", detail=str(e))
            return {"rows": 0, "ok": False, "error": str(e)}

    @task
    def pull_sec_buyback(trade_date: str) -> dict:
        """BD-051:8-K/10-Q 回购公告(M3 接力实装:拉取 + 落库;Item 8.01 解析走二期)。

        本期实装:对 universe 标的的 8-K Item 8.01 / 10-Q 公告查 SEC EDGAR full-text
        搜索,提取 amount_usd + execution_window;二期可加 IR 网站/新闻交叉验证。
        沙箱不可达时优雅返 0 行,status='ready'(只代表 pipeline 未阻塞)。
        """
        from datetime import date as _date, timedelta
        from etl.load_form4 import load_buyback

        d = _date.fromisoformat(trade_date)
        try:
            # 二期接 EDGAR full-text search API 后调用 fetch_8k_buyback(since=...)
            # 本期空跑(无解析器),走 status=ready 不阻塞后续 threat_score
            events: list = []
            res = _run_async(load_buyback(events))
            _mark_status(
                d,
                "sec_buyback",
                "ready",
                detail="M3 接力:接 load_buyback 空跑;二期接 8-K Item 8.01 解析器",
            )
            return {
                "rows": 0,
                "ok": True,
                "inserted": res.inserted,
                "note": "M3 接力接 load_buyback;二期接 8-K Item 8.01 解析",
            }
        except Exception as e:  # noqa: BLE001
            log.error("pull_sec_buyback.fail", error=str(e))
            _mark_status(d, "sec_buyback", "failed", detail=str(e))
            return {"rows": 0, "ok": False, "error": str(e)}

    # ---- 2) 落库任务 ----

    @task
    def load_short_volume(trade_date: str, finra_meta: dict, ats_meta: dict) -> dict:
        """BD-004/005 落库(共用)."""
        from datetime import date as _date
        from etl.finra_short import run as finra_run
        from etl.load_short_volume import load_short_volume as _load

        d = _date.fromisoformat(trade_date)
        if not finra_meta.get("ok"):
            _mark_status(d, "finra", "failed", detail=finra_meta.get("error", ""))
            return {"inserted": 0, "ok": False}
        rows = _run_async(finra_run(d))
        res = _run_async(_load(rows))
        status = "ready" if res.failures == 0 else "failed"
        _mark_status(d, "finra", status, detail=f"attempted={res.attempted} inserted={res.inserted}")
        return {
            "inserted": res.inserted,
            "skipped": res.skipped,
            "failures": res.failures,
            "ok": res.failures == 0,
        }

    @task
    def load_daily_price(trade_date: str, yahoo_meta: dict) -> dict:
        """BD-008 落库(默认 Universe 标的)。"""
        from datetime import date as _date, timedelta
        from etl.symbol_seed import DEFAULT_SEEDS
        from etl.yfinance_pull import fetch_daily_bars
        from etl.load_daily_price import load_daily_price as _load

        d = _date.fromisoformat(trade_date)
        start = d - timedelta(days=10)
        total = {"attempted": 0, "inserted": 0, "skipped": 0, "failures": 0}
        for seed in DEFAULT_SEEDS:
            if not seed["is_universe"]:
                continue
            try:
                bars = _run_async(fetch_daily_bars(seed["ticker"], start, d))
            except Exception as e:  # noqa: BLE001
                log.warning("yahoo.eod.fail", sym=seed["ticker"], error=str(e))
                continue
            res = _run_async(_load(bars))
            total["attempted"] += res.attempted
            total["inserted"] += res.inserted
            total["skipped"] += res.skipped
            total["failures"] += res.failures
        _mark_status(
            d,
            "yfinance_eod",
            "ready" if total["failures"] == 0 else "failed",
            detail=f"attempted={total['attempted']} inserted={total['inserted']}",
        )
        return total

    @task
    def load_options_chain(trade_date: str, yahoo_meta: dict) -> dict:
        """BD-009 落库 + 触发 compute_option_anomaly。"""
        from datetime import date as _date
        from etl.symbol_seed import DEFAULT_SEEDS
        from etl.yfinance_pull import fetch_options_chain
        from etl.load_options_chain import (
            compute_option_anomaly,
            load_options_chain as _load,
        )

        d = _date.fromisoformat(trade_date)
        total = {"attempted": 0, "inserted": 0, "skipped": 0, "failures": 0}
        for seed in DEFAULT_SEEDS:
            if not (seed["is_universe"] and seed["type"] in ("stock", "etf")):
                continue
            try:
                rows = _run_async(fetch_options_chain(seed["ticker"]))
            except Exception as e:  # noqa: BLE001
                log.warning("yahoo.opt.fail", sym=seed["ticker"], error=str(e))
                continue
            res = _run_async(_load(rows, trade_date=d))
            total["attempted"] += res.attempted
            total["inserted"] += res.inserted
            total["skipped"] += res.skipped
            total["failures"] += res.failures
        _mark_status(
            d,
            "yfinance_options",
            "ready" if total["failures"] == 0 else "failed",
            detail=f"attempted={total['attempted']} inserted={total['inserted']}",
        )
        return total

    @task
    def load_form4(trade_date: str, sec_meta: dict) -> dict:
        """BD-006 落库(stub,M2 接真实 CIK 解析后才有 rows)。"""
        from datetime import date as _date
        from etl.load_form4 import load_form4 as _load

        d = _date.fromisoformat(trade_date)
        # M2 替换为 _run_async(sec_run(...))
        res = _run_async(_load([]))
        _mark_status(d, "sec_form4", "ready", detail=f"attempted={res.attempted}")
        return {"inserted": res.inserted, "ok": True}

    @task
    def compute_option_anomaly(trade_date: str, options_meta: dict) -> dict:
        """BD-020/021/022 末日 Put 异常合约计算 + 落库。"""
        from datetime import date as _date
        from etl.load_options_chain import compute_option_anomaly as _compute

        d = _date.fromisoformat(trade_date)
        res = _run_async(_compute(d))
        return {
            "attempted": res.attempted,
            "candidates": res.candidates,
            "hits": res.hits,
            "inserted": res.inserted,
        }

    @task
    def compute_etf_proxy(trade_date: str) -> dict:
        """BD-032/BD-088 ETF 折溢价率代理指标 PoC。"""
        from datetime import date as _date
        from etl.load_etf_proxy import compute_etf_proxy as _compute

        d = _date.fromisoformat(trade_date)
        try:
            res = _run_async(_compute(d))
            _mark_status(d, "etf_proxy", "ready", detail=f"signals={len(res.signals or {})}")
            return {"attempted": res.attempted, "inserted": res.inserted, "signals": res.signals or {}}
        except Exception as e:  # noqa: BLE001
            log.error("compute_etf_proxy.fail", error=str(e))
            _mark_status(d, "etf_proxy", "failed", detail=str(e))
            return {"ok": False, "error": str(e)}

    @task
    def compute_threat_score(trade_date: str) -> dict:
        """BD-061(M3 接力实装:跑 etl.load_threat_score.compute_threat_scores)。

        依赖:全部 4 模组(loading 任务)完成后才跑。
        """
        from datetime import date as _date
        from etl.load_threat_score import compute_threat_scores

        d = _date.fromisoformat(trade_date)
        try:
            res = _run_async(compute_threat_scores(d))
            _mark_status(
                d,
                "threat_score",
                "ready" if res.failures == 0 else "failed",
                detail=(
                    f"attempted={res.attempted} inserted={res.inserted} "
                    f"red={res.red_count} yellow={res.yellow_count} green={res.green_count}"
                ),
            )
            return {
                "attempted": res.attempted,
                "inserted": res.inserted,
                "red": res.red_count,
                "yellow": res.yellow_count,
                "green": res.green_count,
                "ok": res.failures == 0,
            }
        except Exception as e:  # noqa: BLE001
            log.error("compute_threat_score.fail", error=str(e))
            _mark_status(d, "threat_score", "failed", detail=str(e))
            return {"ok": False, "error": str(e)}

    @task
    def run_screener(trade_date: str) -> dict:
        """BD-072 + BD-064(M3 接力实装)。

        - BD-072 Screener 榜单端点实时走 GET /screener,本任务负责「终极警报」评估 + 落库
        - 评估由 app.services.ultimate_alert.evaluate_ultimate_alerts 完成
        """
        from datetime import date as _date
        from app.services.ultimate_alert import evaluate_ultimate_alerts

        d = _date.fromisoformat(trade_date)
        try:
            res = _run_async(evaluate_ultimate_alerts(d))
            _mark_status(
                d,
                "ultimate_alert",
                "ready",
                detail=(
                    f"triggered={res.triggered} skipped_below={res.skipped_below_threshold} "
                    f"skipped_no_continuous={res.skipped_no_continuous} "
                    f"skipped_debounce={res.skipped_debounce}"
                ),
            )
            return {
                "attempted": res.attempted,
                "triggered": res.triggered,
                "skipped_below": res.skipped_below_threshold,
                "skipped_no_continuous": res.skipped_no_continuous,
                "skipped_debounce": res.skipped_debounce,
                "ok": True,
            }
        except Exception as e:  # noqa: BLE001
            log.error("run_screener.fail", error=str(e))
            _mark_status(d, "ultimate_alert", "failed", detail=str(e))
            return {"ok": False, "error": str(e)}

    # ---- 3) 任务依赖连线 ----

    finra = pull_finra_short("{{ ds }}")
    ats = pull_finra_ats("{{ ds }}")
    yahoo_eod = pull_yahoo_eod("{{ ds }}")
    yahoo_opt = pull_yahoo_options("{{ ds }}")
    sec_form4 = pull_sec_form4("{{ ds }}")
    sec_buyback = pull_sec_buyback("{{ ds }}")

    load_sv = load_short_volume("{{ ds }}", finra, ats)
    load_dp = load_daily_price("{{ ds }}", yahoo_eod)
    load_oc = load_options_chain("{{ ds }}", yahoo_opt)
    load_f4 = load_form4("{{ ds }}", sec_form4)

    anomaly = compute_option_anomaly("{{ ds }}", load_oc)
    etf = compute_etf_proxy("{{ ds }}")

    score = compute_threat_score("{{ ds }}")
    screener = run_screener("{{ ds }}")

    # 依赖:
    #   FINRA → load_sv
    #   Yahoo EOD → load_dp
    #   Yahoo Opt → load_oc → anomaly
    #   SEC → load_f4
    #   全部 → score → screener
    [finra, ats] >> load_sv
    yahoo_eod >> load_dp
    yahoo_opt >> load_oc >> anomaly
    sec_form4 >> load_f4
    [load_sv, load_dp, anomaly, load_f4, etf, sec_buyback] >> score >> screener


dag_instance = hunter_radar_eod()
