"""FINRA 做空量落库(BD-004)。

契约:
- 入参:`list[ShortVolumeRow]`(来自 `etl.finra_short.run`)
- 出参:写入 DB 的行数(inserted)+ skipped(rows 被 UNIQUE 冲突跳过)
- 用 `INSERT ... ON CONFLICT DO NOTHING`(schema UNIQUE(trade_date, symbol, source))
- 单条失败不阻塞整批(每条独立 try/except)
- 写库结束后 **不直接写状态灯**,由调用方串接 `etl.refresh_data_status.write_status` 统一处理

设计原则:
- 与爬虫解耦(输入是 dataclass 列表,不绑具体数据源)
- 容错:单条 insert 失败仅记日志 + 计入 failures,不抛异常中断
- 同步 ORM session 包装 async(项目用 asyncpg+SQLAlchemy 2.0 async)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import ShortVolume, Symbol
from etl.finra_short import ShortVolumeRow

log = logging.getLogger(__name__)


@dataclass(slots=True)
class LoadResult:
    """单次落库的结果统计。"""

    attempted: int = 0
    inserted: int = 0
    skipped: int = 0
    unknown_symbols: int = 0
    failures: int = 0

    def __iadd__(self, other: "LoadResult") -> "LoadResult":
        self.attempted += other.attempted
        self.inserted += other.inserted
        self.skipped += other.skipped
        self.unknown_symbols += other.unknown_symbols
        self.failures += other.failures
        return self


async def _known_symbols(session: AsyncSession, rows: list[ShortVolumeRow]) -> set[str]:
    """从 symbol_master 取一批 row 中出现过的 ticker 子集(避免全表扫描)。"""
    tickers = {r.symbol for r in rows}
    if not tickers:
        return set()
    stmt = select(Symbol.ticker).where(Symbol.ticker.in_(tickers))
    rs = await session.execute(stmt)
    return {row[0] for row in rs.all()}


def _build_payload(
    rows: list[ShortVolumeRow], known: set[str], source: str = "finra"
) -> tuple[list[dict], int]:
    """把爬虫 row 转换为 ORM 入参,过滤未在 symbol_master 的 ticker。"""
    payload: list[dict] = []
    unknown = 0
    for r in rows:
        if r.symbol not in known:
            unknown += 1
            continue
        payload.append(
            {
                "trade_date": r.trade_date,
                "symbol": r.symbol,
                "short_volume": r.short_volume,
                "non_short_volume": r.non_short_volume,
                "source": source,
            }
        )
    return payload, unknown


async def _bulk_insert(session: AsyncSession, payload: list[dict]) -> int:
    """批量 upsert 风格插入,使用 ON CONFLICT DO NOTHING。

    返回实际新插入的行数(postgres RETURNING 不可用,故用 rowcount)。
    """
    if not payload:
        return 0
    stmt = (
        pg_insert(ShortVolume)
        .values(payload)
        .on_conflict_do_nothing(index_elements=["trade_date", "symbol", "source"])
    )
    rs = await session.execute(stmt)
    # rowcount 在 ON CONFLICT 路径下,psycopg2/asyncpg 都返回真实插入数
    return rs.rowcount or 0


async def load_short_volume(
    rows: list[ShortVolumeRow],
    *,
    source: str = "finra",
    session: AsyncSession | None = None,
) -> LoadResult:
    """把 FINRA 解析结果落库到 short_volume。

    Args:
        rows: `etl.finra_short` 解析出的行
        source: 数据源标识(预留多源扩展)
        session: 外部传入则复用(便于在 Airflow Task 中串接事务);None 则自建

    Returns:
        LoadResult
    """
    result = LoadResult(attempted=len(rows))
    if not rows:
        return result

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        known = await _known_symbols(session, rows)
        payload, unknown = _build_payload(rows, known, source=source)
        result.unknown_symbols = unknown

        if payload:
            inserted = await _bulk_insert(session, payload)
            result.inserted = inserted
            result.skipped = len(payload) - inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = len(rows)
        await session.rollback()
        log.error("load_short_volume.fail", error=str(e), attempted=len(rows))
    finally:
        if own_session:
            await session.close()

    log.info(
        "load_short_volume.done",
        attempted=result.attempted,
        inserted=result.inserted,
        skipped=result.skipped,
        unknown=result.unknown_symbols,
        failures=result.failures,
    )
    return result


async def main() -> None:
    """CLI 入口:`uv run python -m etl.load_short_volume [YYYY-MM-DD]`"""
    import asyncio
    import sys
    from datetime import date

    from etl.finra_short import run as finra_run

    if len(sys.argv) > 1:
        target = date.fromisoformat(sys.argv[1])
    else:
        target = date.today()

    rows = await finra_run(target)
    res = await load_short_volume(rows)
    print(
        f"[load_short_volume] {target} attempted={res.attempted} "
        f"inserted={res.inserted} skipped={res.skipped} "
        f"unknown={res.unknown_symbols} failures={res.failures}"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
