"""ATS Fallback Service(V1.5.9):合并主源 + 爬虫数据。

职责:
1. 为 API 端点提供统一入口:合并 ats_short(source='finra_ats') 和 ats_short(source='ats_fallback')
2. 优先返回主源数据;主源缺失时返回 fallback 数据
3. Redis 缓存层(TTL=6h)
4. 为 threat_score 提供 ATS 渗透率增强信号
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, text as _text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.redis_client import redis_client
from app.models import Symbol

log = logging.getLogger(__name__)

# Redis 缓存配置
ATS_CACHE_TTL = 21600  # 6h
ATS_CACHE_PREFIX = "ats"


@dataclass(slots=True)
class ATSSnapshot:
    """单日 ATS 数据快照。"""

    trade_date: date
    symbol: str
    ats_short_volume: int
    venue_pool: str
    source: str  # 'finra_ats' | 'ats_fallback'
    is_fallback: bool = False


@dataclass(slots=True)
class ATSSeriesPoint:
    """时间序列单点(给水位图用)。"""

    trade_date: date
    ats_short_volume: int
    source: str
    is_fallback: bool


def _cache_key(ticker: str, trade_date: date) -> str:
    return f"{ATS_CACHE_PREFIX}:{ticker.upper()}:{trade_date.isoformat()}"


async def get_ats_snapshot(
    ticker: str,
    trade_date: date | None = None,
    *,
    session: AsyncSession | None = None,
) -> ATSSnapshot | None:
    """获取指定 ticker 最新一日的 ATS 数据(优先主源,降级 fallback)。

    读取 Redis 缓存 → miss 则查 DB → 写入缓存。
    """
    t = ticker.upper()

    # 1) 查 Redis
    if trade_date:
        key = _cache_key(t, trade_date)
    else:
        key = f"{ATS_CACHE_PREFIX}:{t}:latest"

    try:
        cached = await redis_client.get(key)
        if cached is not None:
            data = json.loads(cached)
            return ATSSnapshot(
                trade_date=date.fromisoformat(data["trade_date"]),
                symbol=data["symbol"],
                ats_short_volume=data["ats_short_volume"],
                venue_pool=data["venue_pool"],
                source=data["source"],
                is_fallback=data.get("is_fallback", False),
            )
    except Exception:
        pass

    # 2) 查 DB
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        tbl = Symbol.__table__.metadata.tables.get("ats_short")
        if tbl is None:
            return None

        sql = (
            select(
                tbl.c.trade_date,
                tbl.c.symbol,
                tbl.c.ats_short_volume,
                tbl.c.venue_pool,
                tbl.c.source,
            )
            .where(tbl.c.symbol == t)
        )
        if trade_date:
            sql = sql.where(tbl.c.trade_date == trade_date)
        sql = sql.order_by(tbl.c.trade_date.desc(), tbl.c.source.asc()).limit(1)

        rs = await session.execute(sql)
        row = rs.first()
        if row is None:
            return None

        snap = ATSSnapshot(
            trade_date=row.trade_date,
            symbol=row.symbol,
            ats_short_volume=int(row.ats_short_volume or 0),
            venue_pool=row.venue_pool or "UNKNOWN",
            source=row.source,
            is_fallback=(row.source == "ats_fallback"),
        )

        # 3) 写入缓存
        try:
            await redis_client.set(
                _cache_key(t, snap.trade_date),
                json.dumps({
                    "trade_date": snap.trade_date.isoformat(),
                    "symbol": snap.symbol,
                    "ats_short_volume": snap.ats_short_volume,
                    "venue_pool": snap.venue_pool,
                    "source": snap.source,
                    "is_fallback": snap.is_fallback,
                }, default=str),
                ttl=ATS_CACHE_TTL,
            )
        except Exception:
            pass

        return snap
    finally:
        if own_session:
            await session.close()


async def get_ats_series(
    ticker: str,
    *,
    days: int = 30,
    session: AsyncSession | None = None,
) -> list[ATSSeriesPoint]:
    """获取 ATS 时间序列(主源 + fallback 合并,按日期升序)。"""
    t = ticker.upper()
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        tbl = Symbol.__table__.metadata.tables.get("ats_short")
        if tbl is None:
            return []

        cutoff = date.today() - timedelta(days=int(days * 1.6) + 5)
        sql = (
            select(
                tbl.c.trade_date,
                tbl.c.ats_short_volume,
                tbl.c.source,
            )
            .where(tbl.c.symbol == t)
            .where(tbl.c.trade_date >= cutoff)
            .order_by(tbl.c.trade_date.asc(), tbl.c.source.asc())
        )
        rs = await session.execute(sql)

        # 同一天可能有多条(finra_ats + ats_fallback),取第一条(优先主源)
        seen: dict[date, ATSSeriesPoint] = {}
        for row in rs.all():
            td = row.trade_date
            if td not in seen:
                seen[td] = ATSSeriesPoint(
                    trade_date=td,
                    ats_short_volume=int(row.ats_short_volume or 0),
                    source=row.source,
                    is_fallback=(row.source == "ats_fallback"),
                )

        return list(seen.values())
    finally:
        if own_session:
            await session.close()


async def warm_ats_cache(
    tickers: list[str],
    trade_date: date,
) -> int:
    """Cron 任务调用的缓存预热:主动将 ATS 数据推入 Redis。

    Returns:
        预热成功的 ticker 数量
    """
    warmed = 0
    for t in tickers:
        snap = await get_ats_snapshot(t, trade_date)
        if snap is not None:
            warmed += 1
    return warmed
