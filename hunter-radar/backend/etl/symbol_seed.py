"""symbol_master 种子数据导入(M1 启动器)。"""

from __future__ import annotations

import csv
import logging
import os
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol

log = logging.getLogger(__name__)

# 默认种子:标普 500 + 主流 ETF(列精简,正式版用 wikipedia/官方列表拉全)
DEFAULT_SEEDS: list[dict] = [
    # 主流 ETF
    {"ticker": "SPY",  "name": "SPDR S&P 500 ETF Trust",          "type": "etf",   "exchange": "NYSEARCA", "is_universe": True},
    {"ticker": "QQQ",  "name": "Invesco QQQ Trust",                "type": "etf",   "exchange": "NASDAQ",   "is_universe": True},
    {"ticker": "IWM",  "name": "iShares Russell 2000 ETF",         "type": "etf",   "exchange": "NYSEARCA", "is_universe": True},
    {"ticker": "VTI",  "name": "Vanguard Total Stock Market ETF",  "type": "etf",   "exchange": "NYSEARCA", "is_universe": True},
    {"ticker": "DIA",  "name": "SPDR Dow Jones Industrial Average","type": "etf",   "exchange": "NYSEARCA", "is_universe": True},
    # 知名个股
    {"ticker": "AAPL", "name": "Apple Inc.",                       "type": "stock", "exchange": "NASDAQ",   "is_universe": True},
    {"ticker": "MSFT", "name": "Microsoft Corporation",            "type": "stock", "exchange": "NASDAQ",   "is_universe": True},
    {"ticker": "NVDA", "name": "NVIDIA Corporation",               "type": "stock", "exchange": "NASDAQ",   "is_universe": True},
    {"ticker": "TSLA", "name": "Tesla, Inc.",                      "type": "stock", "exchange": "NASDAQ",   "is_universe": True},
    {"ticker": "AMZN", "name": "Amazon.com, Inc.",                 "type": "stock", "exchange": "NASDAQ",   "is_universe": True},
    {"ticker": "META", "name": "Meta Platforms, Inc.",             "type": "stock", "exchange": "NASDAQ",   "is_universe": True},
    {"ticker": "GOOGL","name": "Alphabet Inc. Class A",            "type": "stock", "exchange": "NASDAQ",   "is_universe": True},
    {"ticker": "GME",  "name": "GameStop Corp.",                   "type": "stock", "exchange": "NYSE",     "is_universe": True},
    {"ticker": "AMC",  "name": "AMC Entertainment Holdings",       "type": "stock", "exchange": "NYSE",     "is_universe": True},
    {"ticker": "BABA", "name": "Alibaba Group Holding",            "type": "stock", "exchange": "NYSE",     "is_universe": True},
    # 指数(用于门控)
    {"ticker": "^GSPC","name": "S&P 500 Index",                    "type": "index", "exchange": "CBOE",     "is_universe": False},
    {"ticker": "^VIX", "name": "CBOE Volatility Index",            "type": "index", "exchange": "CBOE",     "is_universe": False},
]


async def seed_defaults(session: AsyncSession) -> int:
    """使用 ON CONFLICT DO NOTHING 导入默认种子。"""
    stmt = (
        pg_insert(Symbol)
        .values(DEFAULT_SEEDS)
        .on_conflict_do_nothing(index_elements=["ticker"])
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def upsert_symbol(
    ticker: str,
    *,
    name: str | None = None,
    sym_type: str = "stock",
    exchange: str | None = None,
    is_universe: bool = False,
    start_warmup: bool = True,
    session: AsyncSession | None = None,
) -> tuple[Symbol, bool]:
    """注册新标的到 symbol_master,自动设 warmup_started_at。

    Args:
        ticker: 标的代码(自动 uppercase)
        name: 显示名,缺省 = ticker
        sym_type: stock / etf / index
        exchange: 交易所,缺省 = None(后续 ETL 拉数时不依赖)
        is_universe: 是否纳入 screener 池(默认 False,新加标的只观测不入池)
        start_warmup: True 则设 warmup_started_at=今天,触发后台 ETL
        session: 外部传入的 session(用于事务复用);None 则自管

    Returns:
        (Symbol, created) - created=True 表示本次新增,False 表示已存在
    """
    from app.core.database import AsyncSessionLocal as _ASL

    t = ticker.strip().upper()
    if not t or len(t) > 10:
        raise ValueError(f"invalid ticker: {ticker!r}")

    own_session = session is None
    if own_session:
        session = _ASL()

    try:
        rs = await session.execute(select(Symbol).where(Symbol.ticker == t))
        existing = rs.scalar_one_or_none()
        if existing is not None:
            # 已存在:如果还没有 warmup_started_at 且要求 start_warmup,则补设
            if start_warmup and existing.warmup_started_at is None:
                existing.warmup_started_at = date.today()
                await session.commit()
                log.info("upsert_symbol.warmup_started", ticker=t)
            return existing, False

        # 新增
        payload = {
            "ticker": t,
            "name": name or t,
            "type": sym_type,
            "exchange": exchange,
            "is_active": True,
            "is_universe": is_universe,
            "warmup_started_at": date.today() if start_warmup else None,
            "metadata_json": {},
        }
        stmt = (
            pg_insert(Symbol)
            .values(**payload)
            .on_conflict_do_nothing(index_elements=["ticker"])
            .returning(Symbol.ticker)
        )
        rs2 = await session.execute(stmt)
        await session.commit()
        inserted = rs2.scalar_one_or_none() is not None
        # 重新读(RETURNING 不一定带回完整行)
        rs3 = await session.execute(select(Symbol).where(Symbol.ticker == t))
        sym = rs3.scalar_one()
        log.info("upsert_symbol.created", ticker=t, started_warmup=start_warmup)
        return sym, inserted
    finally:
        if own_session:
            await session.close()


async def main() -> None:
    async with AsyncSessionLocal() as session:
        inserted = await seed_defaults(session)
        log.info("seed.done", inserted=inserted, total=len(DEFAULT_SEEDS))

        # 校验
        rs = await session.execute(select(Symbol).order_by(Symbol.ticker))
        rows = rs.scalars().all()
        for r in rows[:5]:
            print(f"  {r.ticker:8s} {r.type:6s} {r.name}")
        print(f"... total {len(rows)} symbols")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
