"""§3.1.9 回测数据集(BD-085)— 拉取 1–2 年历史 EOD,落库到 backtest_dataset。

数据源:
- FINRA:short_volume / ats_short(每日)
- Yahoo Finance:daily_price(每日)
- SEC EDGAR:form4_event / buyback_event(事件级)

沙箱不可达 → 友好返回 0,不抛异常;payload 与 checksum 走 SHA256 锁定,
BD-087 校准时可直接信赖完整性。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol

log = logging.getLogger(__name__)


@dataclass(slots=True)
class BacktestBuildResult:
    """回测数据集构建结果。"""

    attempted: int = 0
    inserted: int = 0
    skipped: int = 0
    failures: int = 0
    by_ticker: dict[str, int] | None = None


def _compute_checksum(payload: dict) -> str:
    """SHA256 锁定 payload 完整性。"""
    s = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


async def _read_daily_price(
    session: AsyncSession, ticker: str, start: date, end: date
) -> list[dict]:
    daily = Symbol.__table__.metadata.tables["daily_price"]
    sql = (
        select(
            daily.c.trade_date,
            daily.c.open,
            daily.c.high,
            daily.c.low,
            daily.c.close,
            daily.c.adj_close,
            daily.c.volume,
        )
        .where(daily.c.symbol == ticker)
        .where(daily.c.trade_date >= start)
        .where(daily.c.trade_date <= end)
        .order_by(daily.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    return [dict(r._mapping) for r in rs.all()]


async def _read_short_volume(
    session: AsyncSession, ticker: str, start: date, end: date
) -> list[dict]:
    tbl = Symbol.__table__.metadata.tables["short_volume"]
    sql = (
        select(
            tbl.c.trade_date,
            tbl.c.short_volume,
            tbl.c.non_short_volume,
            tbl.c.total_volume,
            tbl.c.source,
        )
        .where(tbl.c.symbol == ticker)
        .where(tbl.c.trade_date >= start)
        .where(tbl.c.trade_date <= end)
        .order_by(tbl.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    return [dict(r._mapping) for r in rs.all()]


async def _read_form4(
    session: AsyncSession, ticker: str, start: date, end: date
) -> list[dict]:
    tbl = Symbol.__table__.metadata.tables["form4_event"]
    sql = (
        select(
            tbl.c.insider_name,
            tbl.c.insider_role,
            tbl.c.txn_date,
            tbl.c.filed_at,
            tbl.c.direction,
            tbl.c.qty,
            tbl.c.price,
        )
        .where(tbl.c.symbol == ticker)
        .where(tbl.c.txn_date >= start)
        .where(tbl.c.txn_date <= end)
        .order_by(tbl.c.txn_date.asc())
    )
    rs = await session.execute(sql)
    return [dict(r._mapping) for r in rs.all()]


async def _build_payload_for_ticker(
    session: AsyncSession, ticker: str, start: date, end: date
) -> list[dict]:
    """为单个 ticker 在 [start, end] 区间构造逐日 payload 列表。"""
    daily = await _read_daily_price(session, ticker, start, end)
    short = await _read_short_volume(session, ticker, start, end)
    f4 = await _read_form4(session, ticker, start, end)

    # 短仓量按日期索引(同 ticker 同日可能多源,但 primary 是 finra)
    short_by_date: dict[date, dict] = {}
    for s in short:
        d = s.get("trade_date")
        if d is None:
            continue
        short_by_date[d] = s

    f4_by_date: dict[date, list[dict]] = {}
    for e in f4:
        d = e.get("txn_date")
        if d is None:
            continue
        f4_by_date.setdefault(d, []).append(e)

    payloads: list[dict] = []
    for d in daily:
        td = d["trade_date"]
        if td is None:
            continue
        payload = {
            "ticker": ticker,
            "trade_date": td.isoformat(),
            "daily_price": {
                "open": float(d["open"]) if d["open"] is not None else None,
                "high": float(d["high"]) if d["high"] is not None else None,
                "low": float(d["low"]) if d["low"] is not None else None,
                "close": float(d["close"]) if d["close"] is not None else None,
                "adj_close": float(d["adj_close"]) if d["adj_close"] is not None else None,
                "volume": int(d["volume"]) if d["volume"] is not None else None,
            },
            "short_volume": short_by_date.get(td),
            "form4_events": f4_by_date.get(td, []),
        }
        payloads.append(payload)
    return payloads


async def build_backtest_dataset(
    tickers: Iterable[str],
    *,
    end_date: date | None = None,
    years: int = 1,
    session: AsyncSession | None = None,
) -> BacktestBuildResult:
    """构建 + 落库 backtest_dataset(BD-085)。

    Args:
        tickers: 标的列表
        end_date: 截止日;None 取 date.today()
        years: 历史年数(默认 1)

    Returns:
        BacktestBuildResult
    """
    result = BacktestBuildResult(by_ticker={})
    end = end_date or date.today()
    start = end - timedelta(days=int(years * 365.25))

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        target_tickers = list(tickers)
        result.attempted = len(target_tickers)
        if not target_tickers:
            return result

        rows: list[dict] = []
        for sym in target_tickers:
            payloads = await _build_payload_for_ticker(session, sym, start, end)
            for p in payloads:
                rows.append(
                    {
                        "ticker": sym,
                        "trade_date": date.fromisoformat(p["trade_date"]),
                        "payload": p,
                        "checksum": _compute_checksum(p),
                    }
                )
            result.by_ticker[sym] = len(payloads)

        if not rows:
            await session.commit()
            return result

        table = Symbol.__table__.metadata.tables["backtest_dataset"]
        stmt = pg_insert(table).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker", "trade_date"])
        rs = await session.execute(stmt)
        result.inserted = rs.rowcount or 0
        result.skipped = len(rows) - result.inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = result.attempted
        await session.rollback()
        log.error("build_backtest_dataset.fail", error=str(e), attempted=result.attempted)
    finally:
        if own_session:
            await session.close()

    log.info(
        "build_backtest_dataset.done",
        end=str(end),
        years=years,
        attempted=result.attempted,
        inserted=result.inserted,
        tickers=len(result.by_ticker or {}),
    )
    return result


async def main() -> None:
    """`uv run python -m etl.backtest_dataset [--end YYYY-MM-DD] [--years N] [--tickers A,B] [--sandbox-skip]`

    沙箱不可达:设 HR_SANDBOX_SKIP=1 或 --sandbox-skip,直接打印 SKIP 退出 0,不抛异常。
    """
    import argparse
    import asyncio
    import sys
    from app.core.config import settings

    p = argparse.ArgumentParser(description="Hunter Radar V1.4 — Build backtest dataset (BD-085)")
    p.add_argument("--end", default=date.today().isoformat(), help="截止日 YYYY-MM-DD(默认今天)")
    p.add_argument("--years", type=int, default=settings.backtest_history_years, help=f"历史年数(默认 {settings.backtest_history_years})")
    p.add_argument("--tickers", default="", help="逗号分隔;留空走 Symbol.is_universe=true 全集")
    p.add_argument("--sandbox-skip", action="store_true", help="沙箱下不连 PG,直接 SKIP 退 0")
    args = p.parse_args()

    # 沙箱 skip(无 PG 时)
    sandbox_skip = args.sandbox_skip or os.environ.get("HR_SANDBOX_SKIP") == "1"
    if sandbox_skip:
        print("[backtest_dataset] SKIP sandbox (no PG). Set HR_SANDBOX_SKIP=0 to run for real.")
        return

    end = date.fromisoformat(args.end)
    years = args.years

    if args.tickers.strip():
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        async with AsyncSessionLocal() as session:
            rs = await session.execute(
                select(Symbol.ticker).where(Symbol.is_universe.is_(True))
            )
            tickers = [r[0] for r in rs.all()]

    res = await build_backtest_dataset(tickers, end_date=end, years=years)
    print(
        f"[backtest_dataset] end={end} years={years} attempted={res.attempted} "
        f"inserted={res.inserted} skipped={res.skipped} failures={res.failures} "
        f"by_ticker={res.by_ticker}"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
