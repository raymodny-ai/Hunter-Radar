"""Yahoo Finance 日 K 落库(BD-008)。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol
from etl.load_short_volume import LoadResult
from etl.yfinance_pull import DailyBar

log = logging.getLogger(__name__)


def _build_payload(rows: list[DailyBar], source: str = "yfinance") -> list[dict]:
    return [
        {
            "trade_date": r.trade_date,
            "symbol": r.symbol,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "adj_close": r.adj_close,
            "volume": r.volume,
            "source": source,
        }
        for r in rows
    ]


async def _known_symbols(session: AsyncSession, tickers: set[str]) -> set[str]:
    if not tickers:
        return set()
    stmt = select(Symbol.ticker).where(Symbol.ticker.in_(tickers))
    rs = await session.execute(stmt)
    return {row[0] for row in rs.all()}


async def load_daily_price(
    rows: list[DailyBar],
    *,
    source: str = "yfinance",
    session: AsyncSession | None = None,
) -> LoadResult:
    """落库到 daily_price(BD-008)。

    daily_price UNIQUE(trade_date, symbol, source)→ ON CONFLICT DO NOTHING。
    """
    result = LoadResult(attempted=len(rows))
    if not rows:
        return result

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        known = await _known_symbols(session, {r.symbol for r in rows})
        payload = [p for p in _build_payload(rows, source=source) if p["symbol"] in known]
        result.unknown_symbols = len(rows) - len(payload)

        if payload:
            table = Symbol.__table__.metadata.tables["daily_price"]
            stmt = (
                pg_insert(table)
                .values(payload)
                .on_conflict_do_nothing(index_elements=["trade_date", "symbol", "source"])
            )
            rs = await session.execute(stmt)
            inserted = rs.rowcount or 0
            result.inserted = inserted
            result.skipped = len(payload) - inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = len(rows)
        await session.rollback()
        log.error("load_daily_price.fail", error=str(e), attempted=len(rows))
    finally:
        if own_session:
            await session.close()

    log.info(
        "load_daily_price.done",
        attempted=result.attempted,
        inserted=result.inserted,
        skipped=result.skipped,
        unknown=result.unknown_symbols,
        failures=result.failures,
    )
    return result


async def main() -> None:
    import asyncio
    import sys
    from datetime import timedelta

    from etl.symbol_seed import DEFAULT_SEEDS
    from etl.yfinance_pull import fetch_daily_bars

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    start = target - timedelta(days=5)
    total = LoadResult()
    for seed in DEFAULT_SEEDS:
        if not seed["is_universe"]:
            continue
        sym = seed["ticker"]
        try:
            bars = await fetch_daily_bars(sym, start, target)
        except Exception as e:  # noqa: BLE001
            log.warning("yfinance.pull.fail", sym=sym, error=str(e))
            continue
        res = await load_daily_price(bars)
        total += res
    print(
        f"[load_daily_price] {start}~{target} attempted={total.attempted} "
        f"inserted={total.inserted} skipped={total.skipped} failures={total.failures}"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
