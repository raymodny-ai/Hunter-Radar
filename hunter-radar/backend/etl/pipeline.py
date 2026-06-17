"""ETL 集中编排器(M2 启动层)。

把分散的 6 个 ETL 落库模块与 2 个计算模块串成一个 `run_daily_pipeline()` 入口,
供:
1. Airflow DAG 内部各 task 调
2. CLI:`uv run python -m etl.pipeline 2024-02-01`
3. 集成测试(集成跑通后即可验证 4 模组 ETL 全链路)

执行顺序(M2 视角,带数据依赖):
    1. pull + load_daily_price (BD-008)   ← 量价背离需要
    2. pull + load_short_volume (BD-004)
    3. pull + load_ats_short (BD-005)
    4. pull + load_options_chain (BD-009)
    5. compute_option_anomaly (BD-020/021/022)  ← 依赖 options_chain
    6. pull + load_form4 (BD-006) + load_buyback (BD-051)
    7. compute_etf_proxy (BD-032/088)   ← 依赖 daily_price
    8. compute_threat_score (BD-061)    ← M2 末实现
    9. refresh_data_status (BD-011)     ← 每个 task 尾部
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from etl.load_etf_proxy import compute_etf_proxy
from etl.load_form4 import load_buyback, load_form4
from etl.load_options_chain import compute_option_anomaly, load_options_chain
from etl.load_short_volume import load_short_volume
from etl.refresh_data_status import mark_failed, mark_ready

log = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineReport:
    """单日 ETL 流水线执行报告。"""

    trade_date: date
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def ok(self) -> bool:
        return len(self.errors) == 0

    def stage(self, name: str, **metrics: Any) -> None:
        self.stages[name] = metrics

    def add_error(self, stage: str, error: str) -> None:
        self.errors.append(f"{stage}: {error}")

    def summary(self) -> str:
        ok_str = "✅" if self.ok() else "❌"
        lines = [f"{ok_str} Pipeline {self.trade_date}"]
        for name, m in self.stages.items():
            metric_str = ", ".join(f"{k}={v}" for k, v in m.items() if not k.startswith("_"))
            lines.append(f"  · {name:30s} {metric_str}")
        if self.errors:
            lines.append("  errors:")
            for e in self.errors:
                lines.append(f"    - {e}")
        return "\n".join(lines)


async def run_daily_pipeline(
    trade_date: date,
    *,
    skip_yahoo: bool = False,
    skip_sec: bool = False,
) -> PipelineReport:
    """M1 末 → M2 流水线主入口。

    Args:
        trade_date: 计算当日
        skip_yahoo: True 时跳过 yfinance 拉取(便于回测 / 离线场景)
        skip_sec: True 时跳过 SEC 拉取(stub 阶段)
    """
    from etl.finra_short import run as finra_run
    from etl.yfinance_pull import fetch_daily_bars, fetch_options_chain
    from etl.symbol_seed import DEFAULT_SEEDS

    report = PipelineReport(trade_date=trade_date)

    # ---- 1) 拉取 + 落库 daily_price ----
    if not skip_yahoo:
        try:
            from etl.load_daily_price import load_daily_price as _load_dp

            from datetime import timedelta

            total = {"attempted": 0, "inserted": 0, "skipped": 0, "failures": 0}
            for seed in DEFAULT_SEEDS:
                if not seed["is_universe"]:
                    continue
                try:
                    bars = await fetch_daily_bars(
                        seed["ticker"],
                        trade_date - timedelta(days=10),
                        trade_date,
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning("yahoo.eod.fail", sym=seed["ticker"], error=str(e))
                    continue
                res = await _load_dp(bars)
                total["attempted"] += res.attempted
                total["inserted"] += res.inserted
                total["skipped"] += res.skipped
                total["failures"] += res.failures
            await mark_ready(
                trade_date,
                "yfinance_eod",
                detail={"attempted": total["attempted"], "inserted": total["inserted"]},
            )
            report.stage("load_daily_price", **total)
        except Exception as e:  # noqa: BLE001
            report.add_error("load_daily_price", str(e))
            await mark_failed(trade_date, "yfinance_eod", error=str(e))

    # ---- 2) FINRA 做空落库 ----
    try:
        rows = await finra_run(trade_date)
        res = await load_short_volume(rows)
        await mark_ready(
            trade_date,
            "finra",
            detail={"attempted": res.attempted, "inserted": res.inserted},
        )
        report.stage("load_short_volume", attempted=res.attempted, inserted=res.inserted, skipped=res.skipped, failures=res.failures)
    except Exception as e:  # noqa: BLE001
        report.add_error("load_short_volume", str(e))
        await mark_failed(trade_date, "finra", error=str(e))

    # ---- 3) ATS 周报(M2 接真实 CSV)----
    # M1 阶段只写 pending
    try:
        from etl.refresh_data_status import mark_pending
        await mark_pending(trade_date, "finra_ats", reason="M2 接入真实 ATS 周报")
        report.stage("load_ats_short", status="pending")
    except Exception as e:  # noqa: BLE001
        report.add_error("load_ats_short", str(e))

    # ---- 4) Yahoo 期权链 + 末日 Put 异常合约 ----
    if not skip_yahoo:
        try:
            total = {"attempted": 0, "inserted": 0, "skipped": 0, "failures": 0}
            for seed in DEFAULT_SEEDS:
                if not (seed["is_universe"] and seed["type"] in ("stock", "etf")):
                    continue
                try:
                    rows = await fetch_options_chain(seed["ticker"])
                except Exception as e:  # noqa: BLE001
                    log.warning("yahoo.opt.fail", sym=seed["ticker"], error=str(e))
                    continue
                res = await load_options_chain(rows, trade_date=trade_date)
                total["attempted"] += res.attempted
                total["inserted"] += res.inserted
                total["skipped"] += res.skipped
                total["failures"] += res.failures
            await mark_ready(
                trade_date,
                "yfinance_options",
                detail={"attempted": total["attempted"], "inserted": total["inserted"]},
            )
            report.stage("load_options_chain", **total)

            # 末日 Put 异常合约
            ar = await compute_option_anomaly(trade_date)
            report.stage(
                "compute_option_anomaly",
                attempted=ar.attempted,
                candidates=ar.candidates,
                hits=ar.hits,
                inserted=ar.inserted,
            )
        except Exception as e:  # noqa: BLE001
            report.add_error("options_chain_or_anomaly", str(e))
            await mark_failed(trade_date, "yfinance_options", error=str(e))

    # ---- 5) SEC Form 4 + Buyback ----
    if not skip_sec:
        try:
            from etl.sec_form4 import run as sec_run
            from app.services.insider import BuybackEvent

            # M1 阶段 sec_run 仍为 stub,M2 接入真实 CIK 解析
            form_rows = await sec_run("placeholder", trade_date)
            res_f4 = await load_form4(form_rows)
            res_bb = await load_buyback([])  # M2 接 8-K 解析后才有 BuybackEvent
            await mark_ready(
                trade_date,
                "sec_form4",
                detail={"attempted": res_f4.attempted, "inserted": res_f4.inserted},
            )
            report.stage("load_form4", attempted=res_f4.attempted, inserted=res_f4.inserted, skipped_etf=res_f4.skipped_etf)
            report.stage("load_buyback", attempted=res_bb.attempted, inserted=res_bb.inserted)
        except Exception as e:  # noqa: BLE001
            report.add_error("sec_form4_or_buyback", str(e))
            await mark_failed(trade_date, "sec_form4", error=str(e))

    # ---- 6) ETF 折溢价率代理指标 ----
    try:
        etf = await compute_etf_proxy(trade_date)
        report.stage("compute_etf_proxy", attempted=etf.attempted, inserted=etf.inserted, signals=len(etf.signals or {}))
    except Exception as e:  # noqa: BLE001
        report.add_error("compute_etf_proxy", str(e))

    # ---- 7) 派生计算:short_ratio_daily / divergence_window / threat_score_daily(BD-030/031/032/040/041/042/060/061) ----
    # 顺序依赖:short_ratio_daily ← short_volume,divergence_window ← daily_price,threat_score_daily ← 前两者 + option_anomaly
    try:
        from etl.load_short_ratio import compute_short_ratio

        sr = await compute_short_ratio(trade_date)
        report.stage(
            "compute_short_ratio",
            attempted=sr.attempted,
            inserted=sr.inserted,
            z_scored=sr.z_scored,
            z_warmup=sr.z_warmup,
        )
    except Exception as e:  # noqa: BLE001
        report.add_error("compute_short_ratio", str(e))

    try:
        from etl.load_divergence import compute_divergence

        dv = await compute_divergence(trade_date)
        report.stage(
            "compute_divergence",
            attempted=dv.attempted,
            inserted=dv.inserted,
            rising=dv.rising,
            confirmed=dv.confirmed,
            warmup=dv.warmup,
        )
    except Exception as e:  # noqa: BLE001
        report.add_error("compute_divergence", str(e))

    # ---- 8) 市场门控 + Threat Score 汇总(BD-063 / BD-060/061/062/062b) ----
    try:
        from app.services.regime import compute_regime

        regime_snap = await compute_regime(trade_date)
        report.stage(
            "compute_regime",
            regime=regime_snap.regime,
            vix=regime_snap.vix,
            spx_close=regime_snap.spx_close,
            threshold_red=regime_snap.threshold_red,
        )
    except Exception as e:  # noqa: BLE001
        report.add_error("compute_regime", str(e))
        regime_snap = None  # noqa: F841

    try:
        from etl.load_threat_score import compute_threat_scores

        ts = await compute_threat_scores(trade_date)
        report.stage(
            "compute_threat_score",
            attempted=ts.attempted,
            inserted=ts.inserted,
            red=ts.red_count,
            yellow=ts.yellow_count,
            green=ts.green_count,
        )
        # M3 增量:根据 regime 把 threat_score_daily.regime 回填
        if regime_snap is not None and ts.inserted > 0:
            from sqlalchemy import update

            from app.core.database import AsyncSessionLocal
            from app.models import Symbol as _Sym

            tbl = _Sym.__table__.metadata.tables["threat_score_daily"]
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(tbl)
                    .where(tbl.c.trade_date == trade_date)
                    .values(regime=regime_snap.regime)
                )
                await session.commit()
    except Exception as e:  # noqa: BLE001
        report.add_error("compute_threat_score", str(e))

    return report


async def main() -> None:
    """CLI:`uv run python -m etl.pipeline [YYYY-MM-DD]`"""
    import asyncio
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    report = await run_daily_pipeline(target)
    print(report.summary())
    if not report.ok():
        import sys as _s

        _s.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
