"""数据状态灯(BD-011)。

每个 ETL 任务尾部写一行 data_ingestion_status,记录:
- trade_date / symbol(NULL = 全市场)
- data_source: 'finra' / 'sec_form4' / 'yfinance_eod' / 'yfinance_options' / 'finra_ats'
- status: 'ready' | 'pending_disclosure' | 'failed' | 'skipped'
- last_attempt_at: NOW
- detail: JSONB(失败原因、跳过原因、扫描行数等)

设计原则:
- 单一入口 `write_status()`,所有 ETL 模块尾部调用,避免每个 task 各自手写 UPSERT
- ON CONFLICT (trade_date, symbol, data_source) DO UPDATE
- 错误吞咽:状态灯本身永远不能阻塞主 ETL 流程
- 视图 `v_data_ingestion_latest`(sql/00_init.sql)按 (symbol, data_source) 取最新一条
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol

log = logging.getLogger(__name__)

VALID_STATUSES = ("ready", "pending_disclosure", "failed", "skipped")
VALID_SOURCES = (
    "finra",
    "finra_ats",
    "ats_fallback",
    "sec_form4",
    "yfinance_eod",
    "yfinance_options",
    "compute",
    "regime",
    "etf_proxy",
    "options_pcr",
    "options_gamma",
)


@dataclass(slots=True)
class StatusRow:
    """单条状态灯写入请求。"""

    trade_date: date
    data_source: str
    status: str
    symbol: str | None = None  # None = 全市场
    detail: dict[str, Any] | None = None


def _build_payload(row: StatusRow) -> dict:
    if row.status not in VALID_STATUSES:
        raise ValueError(f"status 必须是 {VALID_STATUSES}, got {row.status!r}")
    if row.data_source not in VALID_SOURCES:
        raise ValueError(f"data_source 必须是 {VALID_SOURCES}, got {row.data_source!r}")
    return {
        "trade_date": row.trade_date,
        "symbol": row.symbol,
        "data_source": row.data_source,
        "status": row.status,
        "last_attempt_at": datetime.now(timezone.utc),
        "detail": row.detail or {},
    }


async def write_status(
    row: StatusRow,
    *,
    session: AsyncSession | None = None,
) -> bool:
    """写入一条状态灯(UPSERT)。

    Returns:
        True 写入成功;False 失败(永不抛异常,以免阻塞主 ETL)
    """
    try:
        payload = _build_payload(row)
    except ValueError as e:
        log.warning("refresh_data_status.invalid", error=str(e), row=row)
        return False

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        table = Symbol.__table__.metadata.tables["data_ingestion_status"]
        stmt = (
            pg_insert(table)
            .values(payload)
            .on_conflict_do_update(
                index_elements=["trade_date", "symbol", "data_source"],
                set_={
                    "status": payload["status"],
                    "last_attempt_at": payload["last_attempt_at"],
                    "detail": payload["detail"],
                },
            )
        )
        await session.execute(stmt)
        if own_session:
            await session.commit()
        return True
    except SQLAlchemyError as e:
        log.warning(
            "refresh_data_status.fail",
            error=str(e),
            trade_date=str(row.trade_date),
            symbol=row.symbol,
            source=row.data_source,
        )
        if own_session:
            await session.rollback()
        return False
    finally:
        if own_session:
            await session.close()


async def write_many(rows: list[StatusRow], *, session: AsyncSession | None = None) -> int:
    """批量写;返回成功条数。"""
    n_ok = 0
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()
    try:
        for r in rows:
            if await write_status(r, session=session):
                n_ok += 1
        if own_session:
            await session.commit()
    finally:
        if own_session:
            await session.close()
    return n_ok


async def pending_sources(
    trade_date: date,
    *,
    data_sources: tuple[str, ...] = ("finra", "sec_form4", "yfinance_eod", "yfinance_options"),
) -> list[str]:
    """返回「指定日还没 ready 或 failed 的 data_source 列表」(给前端数据未到位门控用)。"""
    async with AsyncSessionLocal() as session:
        table = Symbol.__table__.metadata.tables["data_ingestion_status"]
        sql = (
            select(table.c.data_source, table.c.status)
            .where(table.c.trade_date == trade_date)
            .where(table.c.symbol.is_(None))
            .where(table.c.data_source.in_(data_sources))
        )
        rs = await session.execute(sql)
        seen = {row.data_source: row.status for row in rs.all()}
    return [s for s in data_sources if seen.get(s) not in ("ready",)]


# ---- 给 ETL 流程用的便捷包装 ----


async def mark_ready(
    trade_date: date,
    data_source: str,
    *,
    symbol: str | None = None,
    detail: dict[str, Any] | None = None,
) -> bool:
    return await write_status(
        StatusRow(
            trade_date=trade_date,
            symbol=symbol,
            data_source=data_source,
            status="ready",
            detail=detail,
        )
    )


async def mark_pending(
    trade_date: date,
    data_source: str,
    *,
    symbol: str | None = None,
    reason: str = "",
) -> bool:
    return await write_status(
        StatusRow(
            trade_date=trade_date,
            symbol=symbol,
            data_source=data_source,
            status="pending_disclosure",
            detail={"reason": reason} if reason else {},
        )
    )


async def mark_failed(
    trade_date: date,
    data_source: str,
    *,
    symbol: str | None = None,
    error: str = "",
) -> bool:
    return await write_status(
        StatusRow(
            trade_date=trade_date,
            symbol=symbol,
            data_source=data_source,
            status="failed",
            detail={"error": error[:500]} if error else {},
        )
    )


async def mark_skipped(
    trade_date: date,
    data_source: str,
    *,
    symbol: str | None = None,
    reason: str = "",
) -> bool:
    return await write_status(
        StatusRow(
            trade_date=trade_date,
            symbol=symbol,
            data_source=data_source,
            status="skipped",
            detail={"reason": reason} if reason else {},
        )
    )


# ---- CLI ----


async def main() -> None:
    """`uv run python -m etl.refresh_data_status check [YYYY-MM-DD]`"""
    import asyncio
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        target = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
        pending = await pending_sources(target)
        if not pending:
            print(f"✅ {target} 全部数据源已 ready")
        else:
            print(f"⏳ {target} 仍在等待: {', '.join(pending)}")
    elif cmd == "demo":
        # 演示四个状态
        target = date.today()
        await mark_ready(target, "finra", detail={"rows": 1234})
        await mark_pending(target, "sec_form4", reason="FINRA 18:00 后未发布")
        await mark_failed(target, "yfinance_eod", error="rate limit 429")
        await mark_skipped(target, "sec_form4", symbol="SPY", reason="BD-053 ETF 跳过")
        print(f"demo 状态灯已写入 {target}")
    else:
        print("用法: python -m etl.refresh_data_status {check|demo} [YYYY-MM-DD]")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
