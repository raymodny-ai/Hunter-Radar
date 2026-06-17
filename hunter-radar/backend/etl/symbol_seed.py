"""symbol_master 种子数据导入(M1 启动器)。"""

from __future__ import annotations

import csv
import logging
import os
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
