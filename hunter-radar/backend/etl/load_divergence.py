"""量价背离分析落库(BD-040 / BD-041 / BD-042)。

职责:
1. 从 `daily_price` 读 close + volume 序列
2. 调 `app.services.divergence.detect_divergence` 计算斜率/分位/背离判定
3. 写入 `divergence_window`(UNIQUE trade_date, symbol)
4. 字段: price_slope_10d, short_slope_10d, p_price, p_short, divergence_state

设计原则:
- 计算与落库分离;BD-041 的 P_price/P_short 阈值集中在 services.divergence 内部
- 冷启动:数据不足时 p_price=p_short=0.5,state='none'(OQ-22)
- 单 symbol 失败仅记日志,不中断整批
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
from app.services.divergence import detect_divergence
from etl.load_short_volume import LoadResult

log = logging.getLogger(__name__)


@dataclass(slots=True)
class DivergenceLoadResult(LoadResult):
    """量价背离落库结果。"""

    warmup: int = 0  # 数据不足走暖启动的 symbol 数
    rising: int = 0  # state='rising' 的 symbol 数
    confirmed: int = 0  # state='confirmed' 的 symbol 数


def _resolve_state(p_price: float, p_volume: float, is_divergent: bool) -> str:
    """根据 PR §3.3 / BD-042 把 detect_divergence 的布尔结果映射到 3 态。"""
    if not is_divergent:
        return "none"
    # 'rising' = 单日刚触发;'confirmed' = 连续 ≥2 日
    # detect_divergence 内已含 consecutive_days 逻辑;直接由 caller 提供
    # 此处把 is_divergent=True 全部归为 'rising'。'confirmed' 由 caller 连续 2 日累加
    return "rising"


def _confirm_state(
    history_payload: dict[str, str], sym: str, base_state: str, consecutive_days: int
) -> str:
    """基于上一次结果连续 ≥2 日升级为 'confirmed'。"""
    if base_state != "rising":
        return base_state
    prev = history_payload.get(sym)
    if prev == "rising" and consecutive_days >= 2:
        return "confirmed"
    return base_state


async def _read_price_volume(
    session: AsyncSession,
    tickers: list[str],
    start: date,
    end: date,
) -> dict[str, list[tuple[date, float, int]]]:
    """从 daily_price 读 (symbol: [(date, close, volume), ...])。"""
    if not tickers:
        return {}
    daily = Symbol.__table__.metadata.tables["daily_price"]
    sql = (
        select(
            daily.c.symbol,
            daily.c.trade_date,
            daily.c.close,
            daily.c.volume,
        )
        .where(daily.c.symbol.in_(set(tickers)))
        .where(daily.c.trade_date >= start)
        .where(daily.c.trade_date <= end)
        .order_by(daily.c.symbol, daily.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    out: dict[str, list[tuple[date, float, int]]] = defaultdict(list)
    for row in rs.all():
        if row.close is None:
            continue
        out[row.symbol].append(
            (row.trade_date, float(row.close), int(row.volume or 0))
        )
    return dict(out)


async def _read_prev_state(
    session: AsyncSession,
    tickers: list[str],
    target: date,
) -> dict[str, str]:
    """读 target 日前一日的 divergence_state,用于连续 ≥2 日判定。"""
    if not tickers:
        return {}
    tbl = Symbol.__table__.metadata.tables["divergence_window"]
    cutoff = target - timedelta(days=int(1.6 * 4) + 1)  # 4 交易日内
    sql = (
        select(tbl.c.symbol, tbl.c.trade_date, tbl.c.divergence_state)
        .where(tbl.c.symbol.in_(set(tickers)))
        .where(tbl.c.trade_date < target)
        .where(tbl.c.trade_date >= cutoff)
        .order_by(tbl.c.symbol, tbl.c.trade_date.desc())
    )
    rs = await session.execute(sql)
    out: dict[str, str] = {}
    for row in rs.all():
        if row.symbol not in out:
            out[row.symbol] = row.divergence_state
    return out


async def compute_divergence(
    trade_date: date,
    *,
    symbols: list[str] | None = None,
    lookback: int = 10,
    history_lookback: int = 120,
    consecutive_days: int = 2,
    session: AsyncSession | None = None,
) -> DivergenceLoadResult:
    """计算 + 落库 divergence_window(BD-040/041/042)。

    Args:
        trade_date: 计算当日
        symbols: 限定标的;None 时取全 universe(stock + etf)
        lookback: 滚动回归窗口(默认 10)
        history_lookback: 历史分位背景窗口(默认 120)
        consecutive_days: 连续 ≥ N 日升级为 confirmed(默认 2)

    Returns:
        DivergenceLoadResult
    """
    result = DivergenceLoadResult()

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        # 1) 标的范围
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

        # 2) 读历史价格量能(自然日窗口 1.6×)
        window_days = (lookback + history_lookback) * 2  # 自然日兜底
        start = trade_date - timedelta(days=window_days)
        pv = await _read_price_volume(session, target_tickers, start, trade_date)

        # 3) 读前一日 state(用于连续 ≥2 日 → confirmed)
        prev_states = await _read_prev_state(session, target_tickers, trade_date)

        # 4) 计算每 ticker
        payload: list[dict] = []
        warmup = 0
        for sym in target_tickers:
            rows = pv.get(sym, [])
            closes = [c for _, c, _ in rows]
            volumes = [v for _, _, v in rows]
            v = detect_divergence(
                closes,
                volumes,
                lookback=lookback,
                history_lookback=history_lookback,
                consecutive_days=consecutive_days,
            )
            # 数据不足走暖启动
            if "数据不足" in v.rationale:
                warmup += 1
                continue

            base_state = _resolve_state(v.p_price, v.p_volume, v.is_divergent)
            final_state = _confirm_state(prev_states, sym, base_state, consecutive_days)

            # price_slope_10d / short_slope_10d:用最近 lookback 天线性回归
            from app.services.divergence import linear_regression_slope

            price_slope = (
                linear_regression_slope(closes[-lookback:]) if len(closes) >= lookback else 0.0
            )
            vol_slope = (
                linear_regression_slope([float(v) for v in volumes[-lookback:]])
                if len(volumes) >= lookback
                else 0.0
            )

            payload.append(
                {
                    "trade_date": trade_date,
                    "symbol": sym,
                    "price_slope_10d": price_slope,
                    "short_slope_10d": vol_slope,
                    "p_price": round(v.p_price, 6),
                    "p_short": round(v.p_volume, 6),
                    "divergence_state": final_state,
                }
            )
            if final_state == "rising":
                result.rising += 1
            elif final_state == "confirmed":
                result.confirmed += 1
        result.warmup = warmup

        if not payload:
            await session.commit()
            return result

        # 5) 落库 ON CONFLICT DO UPDATE(可重跑覆盖)
        table = Symbol.__table__.metadata.tables["divergence_window"]
        stmt = pg_insert(table).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["trade_date", "symbol"],
            set_={
                "price_slope_10d": stmt.excluded.price_slope_10d,
                "short_slope_10d": stmt.excluded.short_slope_10d,
                "p_price": stmt.excluded.p_price,
                "p_short": stmt.excluded.p_short,
                "divergence_state": stmt.excluded.divergence_state,
            },
        )
        rs = await session.execute(stmt)
        result.inserted = rs.rowcount or 0
        result.skipped = len(payload) - result.inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = result.attempted
        await session.rollback()
        log.error("compute_divergence.fail", error=str(e), attempted=result.attempted)
    finally:
        if own_session:
            await session.close()

    log.info(
        "compute_divergence.done",
        trade_date=str(trade_date),
        attempted=result.attempted,
        inserted=result.inserted,
        rising=result.rising,
        confirmed=result.confirmed,
        warmup=result.warmup,
    )
    return result


async def main() -> None:
    """`uv run python -m etl.load_divergence [YYYY-MM-DD]`"""
    import asyncio
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    res = await compute_divergence(target)
    print(
        f"[load_divergence] {target} attempted={res.attempted} "
        f"inserted={res.inserted} skipped={res.skipped} "
        f"rising={res.rising} confirmed={res.confirmed} warmup={res.warmup} "
        f"failures={res.failures}"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
