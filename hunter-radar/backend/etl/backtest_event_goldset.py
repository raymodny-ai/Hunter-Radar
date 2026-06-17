"""§3.1.9 金标准事件集(BD-086)。

「机构绞杀 / 财报季暴跌」事件清单(≥30 个)由 CR + 产品双人 review 签字,
作为 Threat Score 命中「金标准」。

字段(ticker, event_type, severity, t_window_start/end, source_url, reviewer_signoff, notes)
事件类型 event_type ∈ {'short_squeeze', 'earnings_crash', 'institutional_slaughter'}
严重度 severity ∈ {'low', 'medium', 'high', 'extreme'}

本期实现:
1. `add_event(...)` 单条添加,要求 reviewer_signoff 必填(CR + 产品 2 人)
2. `bulk_import_from_jsonl(path)` 从 JSONL 批量导入
3. `count_by_event_type()` 统计,前端/SOP 引用
4. `list_events(ticker=None)` 列表查询
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol

log = logging.getLogger(__name__)

VALID_EVENT_TYPES = ("short_squeeze", "earnings_crash", "institutional_slaughter")
VALID_SEVERITIES = ("low", "medium", "high", "extreme")


@dataclass(slots=True)
class GoldsetEvent:
    """单条金标准事件。"""

    ticker: str
    event_type: str
    severity: str
    t_window_start: date
    t_window_end: date
    source_url: str
    reviewer_signoff: dict  # 必须含 'cr' 与 'product' 两个签字
    notes: str | None = None


def _validate(event: GoldsetEvent) -> None:
    if event.event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"event_type 必须是 {VALID_EVENT_TYPES}")
    if event.severity not in VALID_SEVERITIES:
        raise ValueError(f"severity 必须是 {VALID_SEVERITIES}")
    if event.t_window_end < event.t_window_start:
        raise ValueError("t_window_end 必须 >= t_window_start")
    if "cr" not in event.reviewer_signoff or "product" not in event.reviewer_signoff:
        raise ValueError("reviewer_signoff 必须同时含 'cr' 与 'product' 签字")


def _to_payload(event: GoldsetEvent) -> dict:
    _validate(event)
    return {
        "ticker": event.ticker,
        "event_type": event.event_type,
        "severity": event.severity,
        "t_window_start": event.t_window_start,
        "t_window_end": event.t_window_end,
        "source_url": event.source_url,
        "reviewer_signoff": event.reviewer_signoff,
        "notes": event.notes,
    }


async def add_event(
    event: GoldsetEvent, *, session: AsyncSession | None = None
) -> bool:
    """添加单条金标准事件(BD-086)。

    Returns:
        True 成功;False 失败/校验失败
    """
    try:
        payload = _to_payload(event)
    except ValueError as e:
        log.warning("goldset.invalid", error=str(e))
        return False

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()
    try:
        table = Symbol.__table__.metadata.tables["backtest_event_goldset"]
        stmt = (
            pg_insert(table)
            .values(payload)
            .on_conflict_do_nothing(
                index_elements=["ticker", "event_type", "t_window_start", "t_window_end"]
            )
        )
        await session.execute(stmt)
        if own_session:
            await session.commit()
        return True
    except SQLAlchemyError as e:
        log.warning("goldset.add.fail", error=str(e), ticker=event.ticker)
        if own_session:
            await session.rollback()
        return False
    finally:
        if own_session:
            await session.close()


async def bulk_import_from_jsonl(
    path: str | Path, *, session: AsyncSession | None = None
) -> int:
    """从 JSONL 文件批量导入(每行一个 JSON 对象)。

    JSON 字段:
        ticker, event_type, severity, t_window_start(YYYY-MM-DD),
        t_window_end(YYYY-MM-DD), source_url, reviewer_signoff({"cr":..., "product":...}), notes
    """
    p = Path(path)
    if not p.exists():
        log.warning("goldset.bulk.file_missing", path=str(p))
        return 0

    n_ok = 0
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        with p.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    ev = GoldsetEvent(
                        ticker=d["ticker"],
                        event_type=d["event_type"],
                        severity=d["severity"],
                        t_window_start=date.fromisoformat(d["t_window_start"]),
                        t_window_end=date.fromisoformat(d["t_window_end"]),
                        source_url=d["source_url"],
                        reviewer_signoff=d["reviewer_signoff"],
                        notes=d.get("notes"),
                    )
                except (KeyError, ValueError) as e:
                    log.warning(
                        "goldset.bulk.parse.skip",
                        lineno=lineno,
                        error=str(e),
                    )
                    continue
                ok = await add_event(ev, session=session)
                if ok:
                    n_ok += 1
        if own_session:
            await session.commit()
    finally:
        if own_session:
            await session.close()
    return n_ok


async def count_by_event_type() -> dict[str, int]:
    """统计各 event_type 的事件数(用于 SOP 监控 ≥ 30 个目标)。"""
    async with AsyncSessionLocal() as session:
        tbl = Symbol.__table__.metadata.tables["backtest_event_goldset"]
        sql = select(tbl.c.event_type)
        rs = await session.execute(sql)
        from collections import Counter

        return dict(Counter(row[0] for row in rs.all()))


async def list_events(
    *, ticker: str | None = None, event_type: str | None = None
) -> list[dict]:
    """列表查询(返回 dict 列表,不给 ORM 对象,避免耦合)。"""
    async with AsyncSessionLocal() as session:
        tbl = Symbol.__table__.metadata.tables["backtest_event_goldset"]
        sql = select(
            tbl.c.ticker,
            tbl.c.event_type,
            tbl.c.severity,
            tbl.c.t_window_start,
            tbl.c.t_window_end,
            tbl.c.source_url,
            tbl.c.notes,
        )
        if ticker:
            sql = sql.where(tbl.c.ticker == ticker)
        if event_type:
            sql = sql.where(tbl.c.event_type == event_type)
        sql = sql.order_by(tbl.c.t_window_start.desc())
        rs = await session.execute(sql)
        return [dict(r._mapping) for r in rs.all()]


async def main() -> None:
    """CLI:
    - `python -m etl.backtest_event_goldset add <TICKER> <TYPE> <SEV> <START> <END> <URL> <CR> <PRODUCT> [NOTES]`
    - `python -m etl.backtest_event_goldset import <path.jsonl>`
    - `python -m etl.backtest_event_goldset count`
    - `python -m etl.backtest_event_goldset list [TICKER]`
    """
    import asyncio
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "count"
    if cmd == "add":
        if len(sys.argv) < 9:
            print(
                "用法: python -m etl.backtest_event_goldset add <TICKER> <TYPE> <SEV> "
                "<START> <END> <URL> <CR_SIGNER> <PRODUCT_SIGNER> [NOTES]"
            )
            return
        ev = GoldsetEvent(
            ticker=sys.argv[2].upper(),
            event_type=sys.argv[3],
            severity=sys.argv[4],
            t_window_start=date.fromisoformat(sys.argv[5]),
            t_window_end=date.fromisoformat(sys.argv[6]),
            source_url=sys.argv[7],
            reviewer_signoff={"cr": sys.argv[8], "product": sys.argv[9]},
            notes=sys.argv[10] if len(sys.argv) > 10 else None,
        )
        ok = await add_event(ev)
        print(f"add_event {ev.ticker}/{ev.event_type} → {'ok' if ok else 'failed'}")
    elif cmd == "import":
        if len(sys.argv) < 3:
            print("用法: python -m etl.backtest_event_goldset import <path.jsonl>")
            return
        n = await bulk_import_from_jsonl(sys.argv[2])
        print(f"imported {n} events from {sys.argv[2]}")
    elif cmd == "count":
        c = await count_by_event_type()
        total = sum(c.values())
        print(f"total={total} by_event_type={c}")
    elif cmd == "list":
        ticker = sys.argv[2] if len(sys.argv) > 2 else None
        evs = await list_events(ticker=ticker)
        for e in evs:
            print(
                f"  {e['ticker']:6s} {e['event_type']:24s} {e['severity']:8s} "
                f"{e['t_window_start']} ~ {e['t_window_end']} | {e['source_url']}"
            )
    else:
        print("用法: add | import | count | list")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
