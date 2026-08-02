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

# 触发 stdlib logger kwargs 兼容垫片(etl/*.py 用 structlog 风格 log.info("foo", k=v))
try:
    import app.main  # noqa: F401  (副作用: 注册 _patch_logger_log())
except Exception:
    pass

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from etl.load_ats_short import load_ats_short
from etl.load_etf_proxy import compute_etf_proxy
from etl.load_form4 import load_buyback, load_form4
from etl.load_options_chain import compute_option_anomaly, load_options_chain
from etl.load_short_volume import load_short_volume
from etl.refresh_data_status import mark_failed, mark_pending, mark_ready
from etl.retry_policy import etl_retry_async, run_stage_with_retry
from etl.validation import (
    ValidationResult,
    validate_options_chain,
    validate_short_volume,
)

log = logging.getLogger(__name__)


# ---- V1.6.1 通用验证门控 ----


class PipelineAbort(Exception):
    """critical 验证失败时中止批次。"""


async def _quarantine_batch(
    stage: str,
    trade_date: date,
    data_count: int,
    critical_errors: list,
) -> None:
    """将 critical 验证失败的批次写入 quarantine 记录(data_ingestion_status 表)。

    沙箱环境无 DB 时降级为仅日志。
    """
    try:
        from etl.refresh_data_status import mark_failed

        error_summary = f"quarantine: {len(critical_errors)} critical errors in {stage}"
        await mark_failed(trade_date, stage, error=error_summary)
    except Exception:  # noqa: BLE001
        pass
    log.error(
        "pipeline.quarantine",
        stage=stage,
        trade_date=str(trade_date),
        data_count=data_count,
        critical_count=len(critical_errors),
        errors=[str(e) for e in critical_errors[:5]],
    )


async def _load_with_gate(
    loader_fn,
    validator_fn,
    data: list,
    *,
    stage: str,
    trade_date: date,
    validator_kwargs: dict | None = None,
) -> Any:
    """V1.6.1 通用门控: 先验证再入库,critical 时 quarantine + 中止。

    Args:
        loader_fn: 异步落库函数 (data) -> LoadResult
        validator_fn: 校验函数 (data, **kwargs) -> ValidationResult
        data: 待入库数据
        stage: 阶段名(用于日志/报告)
        trade_date: 交易日
        validator_kwargs: 传给 validator_fn 的额外参数

    Returns:
        loader_fn 的返回值

    Raises:
        PipelineAbort: critical 验证失败时
    """
    vr: ValidationResult = validator_fn(data, **(validator_kwargs or {}))

    critical = [w for w in vr.warnings if w.severity == "critical"]
    if critical:
        await _quarantine_batch(stage, trade_date, len(data), critical)
        raise PipelineAbort(
            f"{stage}: {len(critical)} critical validation failures — batch quarantined"
        )

    # soft warnings: 记录但继续
    if vr.warnings:
        log.warning(
            "pipeline.validation.soft_warnings",
            stage=stage,
            trade_date=str(trade_date),
            warning_count=len(vr.warnings),
        )

    return await loader_fn(data)


@dataclass(slots=True)
class ReconcileResult:
    """行数对账结果(断裂点 2)。"""

    ok: bool
    attempted: int
    inserted: int
    failures: int
    loss_pct: float
    message: str


def _reconcile_loaded_rows(
    attempted: int,
    inserted: int,
    failures: int,
    *,
    stage: str,
    loss_tolerance_pct: float = 0.25,
    min_probe_rows: int = 5,
) -> ReconcileResult:
    """断裂点 2: 行数对账 — 检测「部分数据静默加载」。

    在 ETL 落库后核对 attempted(拉取行数) 与 inserted(实际入库)。
    当拉取行足够多但入库量明显偏低(failures 占比高 / inserted 丢失>容差)时,
    判定该 stage 存在静默数据丢失, 应标记 failed 而非无脑 ready。
    """
    if attempted <= 0:
        return ReconcileResult(
            ok=True, attempted=attempted, inserted=inserted, failures=failures,
            loss_pct=0.0, message=f"{stage}: no rows to reconcile",
        )
    loss_pct = (attempted - inserted) / attempted * 100.0
    # 静默丢失指 failures 占比高或 inserted 远低于 attempted
    silent_loss = (
        attempted >= min_probe_rows
        and (failures / attempted) >= loss_tolerance_pct
    ) or (
        attempted >= min_probe_rows
        and loss_pct >= loss_tolerance_pct * 100
    )
    if silent_loss:
        return ReconcileResult(
            ok=False, attempted=attempted, inserted=inserted, failures=failures,
            loss_pct=loss_pct,
            message=(
                f"{stage}: reconcile FAIL attempted={attempted} inserted={inserted} "
                f"failures={failures} loss={loss_pct:.1f}%"
            ),
        )
    return ReconcileResult(
        ok=True, attempted=attempted, inserted=inserted, failures=failures,
        loss_pct=loss_pct,
        message=f"{stage}: reconcile OK attempted={attempted} inserted={inserted} failures={failures}",
    )


async def _compute_historical_short_p99(
    trade_date: date,
    *,
    lookback_days: int = 120,
) -> dict[str, float]:
    """从 short_volume 表计算每 symbol 近 lookback_days 的做空量 P99。

    供 validate_short_volume 的 historical_p99 参数使用,使统计离群检测生效。
    出错时返回空 dict(不阻塞主流程)。
    """
    try:
        from datetime import timedelta

        from sqlalchemy import select, text

        from app.core.database import AsyncSessionLocal
        from app.models import Symbol

        sv = Symbol.__table__.metadata.tables["short_volume"]
        start = trade_date - timedelta(days=lookback_days)
        sql = (
            select(
                sv.c.symbol,
                sv.c.short_volume,
            )
            .where(sv.c.trade_date >= start)
            .where(sv.c.trade_date <= trade_date)
        )
        async with AsyncSessionLocal() as session:
            rs = await session.execute(sql)
            vols_by_sym: dict[str, list[int]] = {}
            for row in rs.all():
                vols_by_sym.setdefault(row.symbol, []).append(int(row.short_volume or 0))
        # 计算 P99(简单排序法)
        import math

        p99: dict[str, float] = {}
        for sym, vols in vols_by_sym.items():
            if len(vols) < 5:
                continue
            vols_sorted = sorted(vols)
            idx = min(math.ceil(0.99 * len(vols_sorted)) - 1, len(vols_sorted) - 1)
            p99[sym] = float(vols_sorted[idx])
        return p99
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline.compute_historical_p99.fail", error=str(e))
        return {}


def _is_mv_stale(latest: date | None, staleness_limit: date) -> bool:
    """5.3 [4.3]: 判断物化视图是否落后。

    latest 为 mv_screener_top100 的 MAX(trade_date)。
    - None(空表)或 < staleness_limit(今天-1天)→ stale
    - 周末/节假日允许最新为最近交易日(=今天-1天)不报
    """
    if latest is None:
        return True
    return latest < staleness_limit


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
    force_refresh: bool = False,
) -> PipelineReport:
    """M1 末 → M2 流水线主入口。

    V1.6.0: 使用 DataProviderManager 多源降级框架取数。
    V1.6.1: 添加 --force-refresh 支持(DELETE + re-insert)。

    Args:
        trade_date: 计算当日
        skip_yahoo: True 时跳过 yfinance 拉取(便于回测 / 离线场景)
        skip_sec: True 时跳过 SEC 拉取(stub 阶段)
        force_refresh: True 时先删除目标日期数据再重新插入
    """
    from etl.finra_short import run as finra_run
    from etl.market_data_provider import DataProviderManager
    from etl.symbol_seed import DEFAULT_SEEDS

    # V1.6.0 多源管理器
    provider_mgr = DataProviderManager()

    report = PipelineReport(trade_date=trade_date)

    # V1.6.1: --force-refresh 先删除目标日期数据
    if force_refresh:
        log.warning("pipeline.force_refresh", trade_date=str(trade_date))
        try:
            from sqlalchemy import delete as sa_delete

            from app.core.database import AsyncSessionLocal
            from app.models import Symbol as _Sym

            _mutable_tables = ["daily_price", "short_volume", "options_chain"]
            async with AsyncSessionLocal() as _fr_sess:
                for _tbl_name in _mutable_tables:
                    _tbl = _Sym.__table__.metadata.tables.get(_tbl_name)
                    if _tbl is not None:
                        await _fr_sess.execute(
                            sa_delete(_tbl).where(_tbl.c.trade_date == trade_date)
                        )
                await _fr_sess.commit()
            report.stage("force_refresh", deleted_tables=_mutable_tables)
        except Exception as e:  # noqa: BLE001
            log.error("pipeline.force_refresh.fail", error=str(e))
            report.add_error("force_refresh", str(e))

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
                    result = await provider_mgr.fetch_daily_bars(
                        seed["ticker"],
                        trade_date - timedelta(days=10),
                        trade_date,
                    )
                    bars = result.data
                    if not bars:
                        log.warning(
                            "provider.daily_bars.empty",
                            sym=seed["ticker"],
                            source=result.source,
                            fallback=result.is_fallback,
                        )
                        continue
                except Exception as e:  # noqa: BLE001
                    log.warning("provider.eod.fail", sym=seed["ticker"], error=str(e))
                    continue
                # V1.6.0 数据校验
                from etl.validation import validate_daily_price

                vr = validate_daily_price(bars)
                if not vr.is_valid:
                    # 断裂点 1: 验证失败必须阻止入库(此前只 mark_failed 仍继续 load)
                    log.warning(
                        "validation.daily_price.critical",
                        sym=seed["ticker"],
                        outliers=vr.outlier_count,
                    )
                    await mark_failed(
                        trade_date,
                        "yfinance_eod",
                        error=f"validation failed: {vr.outlier_count} outliers ({seed['ticker']})",
                    )
                    total["failures"] += vr.outlier_count
                    continue
                res = await _load_dp(bars)
                total["attempted"] += res.attempted
                total["inserted"] += res.inserted
                total["skipped"] += res.skipped
                total["failures"] += res.failures
            # 断裂点 2: 行数对账 — 检测 daily_price 静默丢失
            rc = _reconcile_loaded_rows(
                total["attempted"], total["inserted"], total["failures"], stage="load_daily_price"
            )
            await mark_ready(
                trade_date,
                "yfinance_eod",
                detail={"attempted": total["attempted"], "inserted": total["inserted"], "reconcile": rc.ok},
            )
            if not rc.ok:
                log.warning("reconcile.daily_price", message=rc.message)
                report.add_error("load_daily_price", rc.message)
            report.stage("load_daily_price", **total, reconcile=rc.ok)
        except Exception as e:  # noqa: BLE001
            report.add_error("load_daily_price", str(e))
            await mark_failed(trade_date, "yfinance_eod", error=str(e))

    # ---- 2) FINRA 做空落库(V1.7.6+: 入库前强制 validate_short_volume) ----
    try:
        rows = await finra_run(trade_date)

        # V1.7.6 数据质量门控: 入库前强制校验做空量
        # 传入 historical_p99 使统计离群检测生效
        historical_p99 = await _compute_historical_short_p99(trade_date)
        vr_short = validate_short_volume(rows, historical_p99=historical_p99 or None)
        if vr_short.warnings:
            log.warning(
                "validation.short_volume.warnings",
                trade_date=str(trade_date),
                outliers=vr_short.outlier_count,
                critical=sum(1 for w in vr_short.warnings if w.severity == "critical"),
            )

        # Owner 决策(2026-08-02): 不做整批 abort(critical 不再跳过整批)。
        # 改为: 剔除 critical 行(标记暂缓), 好行照常入库。
        # 统计离群(warning)行保留入库。
        bad_symbols = vr_short.bad_symbols()
        if bad_symbols:
            log.error(
                "validation.short_volume.exclude_bad_rows",
                trade_date=str(trade_date),
                checked=vr_short.checked_count,
                excluded_symbols=sorted(bad_symbols),
                n_excluded=len(bad_symbols),
                summary=vr_short.summary(),
            )
            good_rows = [r for r in rows if r.symbol not in bad_symbols]
            for sym in bad_symbols:
                try:
                    await mark_pending(
                        trade_date,
                        "finra",
                        symbol=sym,
                        reason=f"validation critical: {vr_short.summary()}",
                    )
                except Exception:  # noqa: BLE001
                    pass
            rows = good_rows

        if not rows:
            log.warning("load_short_volume.empty_after_exclusion", trade_date=str(trade_date))
        else:
            res = await load_short_volume(rows)
            # 断裂点 2: 行数对账 — short_volume 静默丢失检测
            rc = _reconcile_loaded_rows(
                res.attempted, res.inserted, res.failures, stage="load_short_volume"
            )
            await mark_ready(
                trade_date,
                "finra",
                detail={
                    "attempted": res.attempted,
                    "inserted": res.inserted,
                    "excluded_symbols": sorted(bad_symbols) if bad_symbols else [],
                    "reconcile": rc.ok,
                },
            )
            if not rc.ok:
                log.warning("reconcile.short_volume", message=rc.message)
                report.add_error("load_short_volume", rc.message)
            report.stage(
                "load_short_volume",
                attempted=res.attempted,
                inserted=res.inserted,
                skipped=res.skipped,
                failures=res.failures,
                reconcile=rc.ok,
                excluded_symbols=sorted(bad_symbols) if bad_symbols else [],
            )
    except Exception as e:  # noqa: BLE001
        report.add_error("load_short_volume", str(e))
        await mark_failed(trade_date, "finra", error=str(e))

    # ---- 3) ATS 周报(M2 接真实 CSV, V1.5.9 加 fallback 爬虫)----
    # 注意:FINRA Daily Short Volume 不是 ATS Transparency Data(后者是周报制含 venue_pool)。
    # 此阶段还无 ATS 周报源,跳过 load_ats_short,短仓比只用 FINRA daily。
    try:
        report.stage("load_ats_short", status="skipped", reason="no ATS weekly source yet")
        await mark_ready(trade_date, "finra_ats", detail={"status": "skipped"})
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
                    # 3.2 (AQ-02): 正常盘后采集限 0-7 DTE, 省 ~70% API 配额
                    result = await provider_mgr.fetch_options_chain(
                        seed["ticker"], max_dte=settings.options_cron_dte_max
                    )
                    rows = result.data
                    if not rows:
                        log.warning(
                            "provider.options.empty",
                            sym=seed["ticker"],
                            source=result.source,
                        )
                        continue
                except Exception as e:  # noqa: BLE001
                    log.warning("provider.opt.fail", sym=seed["ticker"], error=str(e))
                    continue
                # V1.6.0 数据校验 → V1.7.6 强制门控: critical 时跳过本批次入库
                vr_opt = validate_options_chain(rows)
                if not vr_opt.is_valid:
                    log.error(
                        "validation.options_chain.critical.skip_batch",
                        sym=seed["ticker"],
                        trade_date=str(trade_date),
                        checked=vr_opt.checked_count,
                        outliers=vr_opt.outlier_count,
                        summary=vr_opt.summary(),
                    )
                    total["failures"] += vr_opt.checked_count
                    continue
                if vr_opt.warnings:
                    log.warning(
                        "validation.options_chain.warnings",
                        sym=seed["ticker"],
                        outliers=vr_opt.outlier_count,
                    )
                res = await load_options_chain(rows, trade_date=trade_date)
                total["attempted"] += res.attempted
                total["inserted"] += res.inserted
                total["skipped"] += res.skipped
                total["failures"] += res.failures
            # 断裂点 2: 行数对账 — options_chain 静默丢失检测
            rc = _reconcile_loaded_rows(
                total["attempted"], total["inserted"], total["failures"], stage="load_options_chain"
            )
            await mark_ready(
                trade_date,
                "yfinance_options",
                detail={"attempted": total["attempted"], "inserted": total["inserted"], "reconcile": rc.ok},
            )
            if not rc.ok:
                log.warning("reconcile.options_chain", message=rc.message)
                report.add_error("load_options_chain", rc.message)
            report.stage("load_options_chain", **total, reconcile=rc.ok)

            # 末日 Put 异常合约
            ar = await compute_option_anomaly(trade_date)
            report.stage(
                "compute_option_anomaly",
                attempted=ar.attempted,
                candidates=ar.candidates,
                hits=ar.hits,
                inserted=ar.inserted,
            )

            # V1.5.9: PCR + Gamma 聚集 + OTM 刺客
            from etl.load_options_chain import compute_pcr_gamma, warm_options_cache
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import select
            from app.models import Symbol

            # V1.7.5.2: pipeline 默认只算 is_universe=True,这里改拿所有 options_chain 当天有 contracts 的 tickers.
            # 不限定 universe 因为 warm_options_cache 需要推全部 Redis keys(用户查询的 ticker 不一定 in universe)
            options_table = Symbol.__table__.metadata.tables["options_chain"]
            async with AsyncSessionLocal() as _opt_sess:
                _rs = await _opt_sess.execute(
                    select(options_table.c.symbol)
                    .where(options_table.c.trade_date == trade_date)
                    .distinct()
                )
                _all_tickers = [r[0] for r in _rs.all() if len(r[0]) <= 5]

            pg_results = await compute_pcr_gamma(trade_date, symbols=_all_tickers)
            report.stage(
                "compute_pcr_gamma",
                symbols=len(pg_results),
                high_signals=sum(1 for r in pg_results if r.signal_strength == "HIGH"),
            )
            # 缓存预热推入 Redis(TTL=40min)
            warmed = await warm_options_cache(trade_date, pg_results)
            report.stage("warm_options_cache", warmed=warmed)
        except Exception as e:  # noqa: BLE001
            report.add_error("options_chain_or_anomaly", str(e))
            await mark_failed(trade_date, "yfinance_options", error=str(e))

    # ---- 5) SEC Form 4 + Buyback ----
    if not skip_sec:
        try:
            from etl.sec_form4 import run as sec_run
            from app.services.insider import BuybackEvent

            # M2 (2026-07-28): 真实 CIK 解析 + universe Form 4 抓取
            from etl.sec_form4 import run_universe as sec_run_universe
            form_rows = await sec_run_universe(trade_date)
            res_f4 = await load_form4(form_rows)
            res_bb = await load_buyback([])  # M2 接 8-K 解析后才有 BuybackEvent
            # 断裂点 2: 行数对账 — form4 静默丢失检测
            rc_f4 = _reconcile_loaded_rows(
                res_f4.attempted, res_f4.inserted, res_f4.failures, stage="load_form4"
            )
            await mark_ready(
                trade_date,
                "sec_form4",
                detail={"attempted": res_f4.attempted, "inserted": res_f4.inserted, "reconcile": rc_f4.ok},
            )
            if not rc_f4.ok:
                log.warning("reconcile.form4", message=rc_f4.message)
                report.add_error("load_form4", rc_f4.message)
            report.stage("load_form4", attempted=res_f4.attempted, inserted=res_f4.inserted, skipped_etf=res_f4.skipped_etf, reconcile=rc_f4.ok)
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

    # ---- 9) V1.6.0: 刷新 Screener 物化视图 ----
    try:
        from sqlalchemy import text as _t

        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(
                _t("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_screener_top100")
            )
            await session.commit()

            # 5.3 [4.3]: 物化视图刷新监控 — 验证是否落后
            # 周末/节假日无行情, latest = 最近一个交易日, 允许最多落后 1 天自然日
            from datetime import timedelta as _td

            latest = await session.scalar(
                _t("SELECT MAX(trade_date) FROM mv_screener_top100")
            )
            staleness_limit = date.today() - _td(days=1)
            if _is_mv_stale(latest, staleness_limit):
                msg = f"mv_screener_top100 落后: latest={latest} (限 {staleness_limit})"
                log.error("mv.refresh.stale", message=msg)
                report.add_error("refresh_mv_screener", msg)
                report.stage("refresh_mv_screener", status="stale", latest=str(latest))
            else:
                report.stage("refresh_mv_screener", status="ok", latest=str(latest))
    except Exception as e:  # noqa: BLE001
        # 物化视图不存在时忽略(首次部署未执行 migration)
        log.warning("refresh_mv_screener.skip", error=str(e))

    # ---- 10) 4.5: 数据落库后失效前端 Redis 缓存 ----
    try:
        from app.core.redis_client import invalidate_caches

        patterns = ["cache:get_threat_score:*", "cache:get_screener:*", "cache:get_threat_history:*"]
        deleted = await invalidate_caches(patterns)
        report.stage("invalidate_caches", deleted=len(deleted))
        if deleted:
            log.info("cache.invalidated", patterns=patterns, deleted=len(deleted))
    except Exception as e:  # noqa: BLE001
        # 缓存失效失败不阻塞 ETL(下次请求自愈)
        log.warning("cache.invalidate.skip", error=str(e))

    return report


async def main() -> None:
    """CLI:`uv run python -m etl.pipeline [YYYY-MM-DD] [--force-refresh]`"""
    import asyncio
    import sys

    args = sys.argv[1:]
    force_refresh = "--force-refresh" in args
    positional = [a for a in args if not a.startswith("--")]
    target = date.fromisoformat(positional[0]) if positional else date.today()
    report = await run_daily_pipeline(target, force_refresh=force_refresh)
    print(report.summary())
    if not report.ok():
        import sys as _s

        _s.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
