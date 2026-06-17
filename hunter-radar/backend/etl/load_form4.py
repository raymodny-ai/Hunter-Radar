"""SEC Form 4 落库(BD-006)+ 8-K/10-Q 回购公告落库(BD-051)。

Form 4 表唯一约束:(symbol, insider_name, txn_date, direction, qty, price)
Buyback 表唯一约束:(symbol, form_type, announced_at, source_url)

ETF 标的过滤(BD-053):Form 4 落库时跳过 type='etf' 的 ticker,
并在 data_ingestion_status 写一行 status='skipped' 备注原因,
由 refresh_data_status 串接。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol
from app.services.insider import BuybackEvent, Form4Event, is_key_insider
from etl.load_short_volume import LoadResult
from etl.sec_form4 import Form4Row

log = logging.getLogger(__name__)


# ---- 1) Form 4 落库 ----


@dataclass(slots=True)
class Form4LoadResult(LoadResult):
    skipped_etf: int = 0
    non_key_insider: int = 0


def _normalize_role(role: str) -> str:
    """SEC 报告的角色文本归一化到 services.insider.is_key_insider 期望的枚举。

    服务层判定的关键内部人集合:{'CEO', 'CFO', 'Director', '10% Holder'}。
    SEC 实际报告文本更杂,这里做大小写无关的子串匹配。
    """
    r = role.strip()
    upper = r.upper()
    if "CEO" in upper or "CHIEF EXECUTIVE" in upper:
        return "CEO"
    if "CFO" in upper or "CHIEF FINANCIAL" in upper or "CHIEF FINANCE" in upper:
        return "CFO"
    if "DIRECTOR" in upper or upper == "DIR":
        return "Director"
    if "10%" in upper or "10 %" in upper or "TEN PERCENT" in upper or "HOLDER" in upper:
        return "10% Holder"
    return r  # 透传,后续 is_key_insider 会判否


def _build_form4_payload(
    rows: list[Form4Row], known_etf: set[str]
) -> tuple[list[dict], int, int]:
    """转 form4_event 写入 payload。

    Returns:
        (payload, skipped_etf, non_key_insider)
    """
    payload: list[dict] = []
    skipped_etf = 0
    non_key = 0
    for r in rows:
        if r.symbol in known_etf:
            skipped_etf += 1
            continue
        role = _normalize_role(r.insider_role)
        if not is_key_insider(role):
            non_key += 1
            # 不写入(BD-050 仅保留关键内部人)
            continue
        payload.append(
            {
                "symbol": r.symbol,
                "insider_name": r.insider_name,
                "insider_role": role,
                "txn_date": r.txn_date,
                "filed_at": r.filed_at,
                "direction": r.direction,
                "qty": r.qty,
                "price": r.price,
                "classification": role.lower().replace(" ", "_").replace("%", "pct"),
                "form_url": r.form_url,
                "raw": {},
            }
        )
    return payload, skipped_etf, non_key


async def _known_etf_symbols(session: AsyncSession, tickers: set[str]) -> set[str]:
    if not tickers:
        return set()
    stmt = select(Symbol.ticker).where(Symbol.ticker.in_(tickers), Symbol.type == "etf")
    rs = await session.execute(stmt)
    return {row[0] for row in rs.all()}


async def load_form4(
    rows: list[Form4Row],
    *,
    session: AsyncSession | None = None,
) -> Form4LoadResult:
    """把 Form 4 行落库到 form4_event(BD-006/BD-050/BD-053)。

    ETF 标的(BD-053)→ 跳过 + 计 skipped_etf;
    非关键内部人(BD-050)→ 跳过 + 计 non_key_insider。
    """
    result = Form4LoadResult(attempted=len(rows))
    if not rows:
        return result

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        known_etf = await _known_etf_symbols(session, {r.symbol for r in rows})
        payload, skipped_etf, non_key = _build_form4_payload(rows, known_etf)
        result.skipped_etf = skipped_etf
        result.non_key_insider = non_key

        if payload:
            table = Symbol.__table__.metadata.tables["form4_event"]
            stmt = (
                pg_insert(table)
                .values(payload)
                .on_conflict_do_nothing(
                    index_elements=[
                        "symbol",
                        "insider_name",
                        "txn_date",
                        "direction",
                        "qty",
                        "price",
                    ]
                )
            )
            rs = await session.execute(stmt)
            inserted = rs.rowcount or 0
            result.inserted = inserted
            result.skipped = len(payload) - inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = len(rows)
        await session.rollback()
        log.error("load_form4.fail", error=str(e), attempted=len(rows))
    finally:
        if own_session:
            await session.close()

    log.info(
        "load_form4.done",
        attempted=result.attempted,
        inserted=result.inserted,
        skipped=result.skipped,
        skipped_etf=result.skipped_etf,
        non_key_insider=result.non_key_insider,
        failures=result.failures,
    )
    return result


# ---- 2) Buyback 落库 ----


@dataclass(slots=True)
class BuybackLoadResult(LoadResult):
    """Buyback 落库结果。"""


def _build_buyback_payload(rows: list[BuybackEvent], known: set[str]) -> tuple[list[dict], int]:
    """转 buyback_event 写入 payload。

    BuybackEvent 输入字段:
        symbol, announce_date, amount_usd, duration_days, form_url
    schema 字段:
        symbol, form_type('8-K'/'10-Q'/'10-K'), announced_at, amount_usd, pct_of_float,
        execution_window, source_url, raw
    """
    payload: list[dict] = []
    unknown = 0
    for r in rows:
        if r.symbol not in known:
            unknown += 1
            continue
        payload.append(
            {
                "symbol": r.symbol,
                "form_type": "8-K",  # 默认为 8-K;二期可扩展为参数
                "announced_at": r.announce_date,
                "amount_usd": int(r.amount_usd) if r.amount_usd else None,
                "pct_of_float": None,  # 二期解析 Item 8.01 详细字段
                "execution_window": f"{r.duration_days}d",
                "source_url": r.form_url,
                "raw": {},
            }
        )
    return payload, unknown


async def load_buyback(
    rows: list[BuybackEvent],
    *,
    session: AsyncSession | None = None,
) -> BuybackLoadResult:
    """把 BuybackEvent 列表落库到 buyback_event(BD-051)。

    ETFs 标的也允许(回购在 ETF 少见,但 buyback_event 表无 type 过滤约束)。
    """
    result = BuybackLoadResult(attempted=len(rows))
    if not rows:
        return result

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        tickers = {r.symbol for r in rows}
        stmt = select(Symbol.ticker).where(Symbol.ticker.in_(tickers))
        rs = await session.execute(stmt)
        known = {row[0] for row in rs.all()}

        payload, unknown = _build_buyback_payload(rows, known)
        result.unknown_symbols = unknown

        if payload:
            table = Symbol.__table__.metadata.tables["buyback_event"]
            stmt2 = pg_insert(table).values(payload)
            stmt2 = stmt2.on_conflict_do_nothing(
                index_elements=["symbol", "form_type", "announced_at", "source_url"]
            )
            rs2 = await session.execute(stmt2)
            inserted = rs2.rowcount or 0
            result.inserted = inserted
            result.skipped = len(payload) - inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = len(rows)
        await session.rollback()
        log.error("load_buyback.fail", error=str(e), attempted=len(rows))
    finally:
        if own_session:
            await session.close()

    log.info(
        "load_buyback.done",
        attempted=result.attempted,
        inserted=result.inserted,
        skipped=result.skipped,
        unknown=result.unknown_symbols,
        failures=result.failures,
    )
    return result


# ---- CLI ----


async def main_form4() -> None:
    import asyncio
    import sys

    from etl.sec_form4 import run as sec_run

    if len(sys.argv) < 2:
        print("用法: python -m etl.load_form4 <TICKER> [YYYY-MM-DD-SINCE]")
        return
    sym = sys.argv[1].upper()
    since = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2024, 1, 1)
    rows = await sec_run(sym, since)
    res = await load_form4(rows)
    print(
        f"[load_form4] {sym} attempted={res.attempted} inserted={res.inserted} "
        f"skipped={res.skipped} skipped_etf={res.skipped_etf} "
        f"non_key={res.non_key_insider} failures={res.failures}"
    )


async def main_buyback() -> None:
    """演示 CLI:接受 JSON 行(每行一个 BuybackEvent)从 stdin。"""
    import asyncio
    import json
    import sys

    rows: list[BuybackEvent] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        rows.append(
            BuybackEvent(
                symbol=d["symbol"],
                announce_date=date.fromisoformat(d["announce_date"]),
                amount_usd=float(d.get("amount_usd", 0)),
                duration_days=int(d.get("duration_days", 0)),
                form_url=d["form_url"],
            )
        )
    res = await load_buyback(rows)
    print(
        f"[load_buyback] attempted={res.attempted} inserted={res.inserted} "
        f"skipped={res.skipped} unknown={res.unknown_symbols} failures={res.failures}"
    )


if __name__ == "__main__":
    import asyncio
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "form4"
    if cmd == "form4":
        asyncio.run(main_form4())
    elif cmd == "buyback":
        asyncio.run(main_buyback())
    else:
        print("用法: python -m etl.load_form4 {form4|buyback} [...]")
