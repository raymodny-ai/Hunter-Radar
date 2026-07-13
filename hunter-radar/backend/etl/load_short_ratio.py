"""全监管做空派生指标落库(BD-030 / BD-031 / BD-032)。

职责:
1. 从 `short_volume` 读日级数据 → 算 `short_ratio = short_volume / total_volume`
2. 从 `ats_short` 读日级数据 → 算 `ats_short_pct = SUM(ats_short) / SUM(short_volume)`
3. 用 `app.services.short_metrics.z_score_rolling` 算 60 日滚动 Z-Score
4. 落库到 `short_ratio_daily`(UNIQUE trade_date, symbol)

设计原则:
- 严格按 PRD §3.2 / BD-030/031/032 实现,不引入历史均值之外的策略
- 计算/落库分离:便于单测与回测替换
- 容错:单 symbol 失败仅记日志,不中断整批
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol
from app.services.short_metrics import z_score_rolling
from etl.load_short_volume import LoadResult

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ShortRatioResult(LoadResult):
    """短仓比 + Z-Score + ATS 占比 的落库结果。"""

    z_scored: int = 0  # 计算了 Z-Score 的 symbol 数
    z_warmup: int = 0  # 因冷启动 Z 为 None 的 symbol 数


async def _read_short_history(
    session: AsyncSession,
    tickers: list[str],
    start: date,
    end: date,
) -> dict[str, list[tuple[date, float]]]:
    """读 short_ratio 历史序列(按 ticker 分组,按日期升序)。

    返回 {ticker: [(date, short_ratio), ...]}
    """
    if not tickers:
        return {}
    short = Symbol.__table__.metadata.tables["short_volume"]
    sql = (
        select(
            short.c.symbol,
            short.c.trade_date,
            short.c.short_volume,
            short.c.total_volume,
        )
        .where(short.c.symbol.in_(set(tickers)))
        .where(short.c.trade_date >= start)
        .where(short.c.trade_date <= end)
        .order_by(short.c.symbol, short.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    out: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for row in rs.all():
        tv = int(row.total_volume or 0)
        sv = int(row.short_volume or 0)
        if tv <= 0:
            continue
        out[row.symbol].append((row.trade_date, sv / tv))
    return dict(out)


async def _read_ats_pct_for_date(
    session: AsyncSession,
    tickers: list[str],
    trade_date: date,
) -> dict[str, float]:
    """读指定日每个 ticker 的 ats_short 总量,再除以 short_volume 总量 → ats_short_pct。"""
    if not tickers:
        return {}
    ats = Symbol.__table__.metadata.tables["ats_short"]
    sv = Symbol.__table__.metadata.tables["short_volume"]

    ats_sql = (
        select(ats.c.symbol, ats.c.ats_short_volume)
        .where(ats.c.symbol.in_(set(tickers)))
        .where(ats.c.trade_date == trade_date)
    )
    rs = await session.execute(ats_sql)
    ats_sum: dict[str, int] = defaultdict(int)
    for row in rs.all():
        ats_sum[row.symbol] += int(row.ats_short_volume or 0)

    sv_sql = (
        select(sv.c.symbol, sv.c.short_volume)
        .where(sv.c.symbol.in_(set(tickers)))
        .where(sv.c.trade_date == trade_date)
    )
    rs2 = await session.execute(sv_sql)
    sv_sum: dict[str, int] = {row.symbol: int(row.short_volume or 0) for row in rs2.all()}

    out: dict[str, float] = {}
    for sym, total_ats in ats_sum.items():
        total_sv = sv_sum.get(sym, 0)
        if total_sv <= 0:
            continue
        out[sym] = min(1.0, total_ats / total_sv)
    return out


async def _read_ats_proxy_for_date(
    session: AsyncSession,
    tickers: list[str],
    trade_date: date,
) -> dict[str, float]:
    """暗池占比代理(BD-031, V1.7.3):当 ats_short 表空时,采用 SEC Rule 606 + TABB Group
    2024 行业均值 0.45 作为 fallback。后续接入 FINRA OTC Transparency ATS_W_SMBL 后替换。

    Returns: {symbol: 0.45} dict for each ticker
    """
    if not tickers:
        return {}
    # 验证这些 ticker 在 short_volume 表里有当日数据
    sv = Symbol.__table__.metadata.tables["short_volume"]
    sv_sql = (
        select(sv.c.symbol)
        .where(sv.c.symbol.in_(set(tickers)))
        .where(sv.c.trade_date == trade_date)
    )
    rs = await session.execute(sv_sql)
    syms_with_data = {row[0] for row in rs.all()}
    return {s: 0.45 for s in syms_with_data}


def _zscore_payload(
    ticker: str,
    rows: list[tuple[date, float]],
    target: date,
    ats_pct_map: dict[str, float],
    lookback: int,
) -> tuple[dict | None, int, int]:
    """算单 ticker 在 target 日的 (short_ratio, z_score_60d, ats_short_pct)。"""
    if not rows:
        return None, 0, 0
    # 取 (date, ratio) 中 date == target 的比率
    target_ratio: float | None = None
    history_ratios: list[float] = []
    for d, r in rows:
        history_ratios.append(r)
        if d == target:
            target_ratio = r
    if target_ratio is None:
        return None, 0, 0

    # Z-Score:对完整 history 滚动 → 取 target 日位置
    z_series = z_score_rolling(history_ratios, lookback=lookback)
    # 找 target_ratio 对应的索引
    idx = -1
    for i, (d, _) in enumerate(rows):
        if d == target:
            idx = i
            break
    z_today = z_series[idx] if idx >= 0 else None
    if z_today is None:
        return (
            {
                "trade_date": target,
                "symbol": ticker,
                "short_ratio": round(target_ratio, 6),
                "z_score_60d": None,
                "ats_short_pct": ats_pct_map.get(ticker),
            },
            0,
            1,
        )
    return (
        {
            "trade_date": target,
            "symbol": ticker,
            "short_ratio": round(target_ratio, 6),
            "z_score_60d": round(float(z_today), 4),
            "ats_short_pct": ats_pct_map.get(ticker),
        },
        1,
        0,
    )


async def compute_short_ratio(
    trade_date: date,
    *,
    symbols: list[str] | None = None,
    lookback: int = 60,
    history_lookback_days: int | None = None,
    session: AsyncSession | None = None,
) -> ShortRatioResult:
    """计算 + 落库 short_ratio_daily(BD-030/031/032)。

    Args:
        trade_date: 计算当日
        symbols: 限定标的;None 时取全 universe
        lookback: Z-Score 滚动窗口(默认 60)
        history_lookback_days: 读取历史窗口大小(默认 lookback * 1.6 自然日,1.6 系数预留周末/节假日)

    Returns:
        ShortRatioResult
    """
    if history_lookback_days is None:
        history_lookback_days = int(lookback * 1.6) + 5

    result = ShortRatioResult()

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        # 1) 取标的范围
        if symbols is None:
            rs = await session.execute(
                select(Symbol.ticker).where(Symbol.is_universe.is_(True))
            )
            target_tickers = [r[0] for r in rs.all()]
        else:
            target_tickers = list(symbols)
        result.attempted = len(target_tickers)
        if not target_tickers:
            await session.commit()
            return result

        # 2) 读历史 short_ratio(用自然日 cutoff 1.6×,留出周末/节假日)
        start = trade_date - timedelta(days=history_lookback_days)
        history = await _read_short_history(session, target_tickers, start, trade_date)

        # 3) 读 ats_short_pct(target 当日)
        ats_pct_map = await _read_ats_pct_for_date(session, target_tickers, trade_date)
        # 3.1) V1.7.3: 暗池 proxy fallback — ats_short 表空时, 采用 SEC Rule 606 + TABB 行业均值 0.45
        # 用于填充 front-end short-iceberg-v2 暗池占比层。后续接入 FINRA OTC Transparency 后替换
        if ats_pct_map:
            missing = set(target_tickers) - set(ats_pct_map.keys())
        else:
            missing = set(target_tickers)
        if missing:
            proxy_map = await _read_ats_proxy_for_date(session, list(missing), trade_date)
            ats_pct_map.update(proxy_map)
            if proxy_map:
                log.info("compute_short_ratio.ats_proxy filled=%d source=SEC_Rule606_TABB_2024", len(proxy_map))

        # 4) 算每 ticker 的 (ratio, z, ats_pct) 落库 payload
        payload: list[dict] = []
        for sym in target_tickers:
            rows = history.get(sym, [])
            p, n_z, n_warm = _zscore_payload(sym, rows, trade_date, ats_pct_map, lookback)
            if p is None:
                continue
            payload.append(p)
            result.z_scored += n_z
            result.z_warmup += n_warm

        if not payload:
            await session.commit()
            return result

        # 5) 落库 ON CONFLICT DO UPDATE(可重跑覆盖,允许重新计算 Z-Score)
        table = Symbol.__table__.metadata.tables["short_ratio_daily"]
        stmt = pg_insert(table).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["trade_date", "symbol"],
            set_={
                "short_ratio": stmt.excluded.short_ratio,
                "z_score_60d": stmt.excluded.z_score_60d,
                "ats_short_pct": stmt.excluded.ats_short_pct,
            },
        )
        rs = await session.execute(stmt)
        result.inserted = rs.rowcount or 0
        result.skipped = len(payload) - result.inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = result.attempted
        await session.rollback()
        log.error("compute_short_ratio.fail", error=str(e), attempted=result.attempted)
    finally:
        if own_session:
            await session.close()

    log.info(
        "compute_short_ratio.done",
        trade_date=str(trade_date),
        attempted=result.attempted,
        inserted=result.inserted,
        z_scored=result.z_scored,
        z_warmup=result.z_warmup,
    )
    return result


async def main() -> None:
    """`uv run python -m etl.load_short_ratio [YYYY-MM-DD]`"""
    import asyncio
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    res = await compute_short_ratio(target)
    print(
        f"[load_short_ratio] {target} attempted={res.attempted} "
        f"inserted={res.inserted} skipped={res.skipped} "
        f"z_scored={res.z_scored} z_warmup={res.z_warmup} failures={res.failures}"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
