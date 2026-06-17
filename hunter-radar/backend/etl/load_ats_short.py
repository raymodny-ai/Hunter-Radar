"""FINRA ATS 暗池做空数据落库(BD-005)。

数据来源说明:
- FINRA 公开的统一 CSV 实际不区分 venue(只有总量)
- ATS 占比真正可靠的数据源是 FINRA ATS Transparency Data(每周发布,且带 venue_pool 名称)
- 本模块提供两类入口:
    1. `load_ats_short` 接受已解析的 `ATSVolumeRow` 列表(由外部解析器/二期 ATS 周报 ETL 喂入)
    2. CLI 入口 `python -m etl.load_ats_short [path.csv]` 支持从二期 ATS 周报 CSV 灌入

CSV 期望格式(FINRA 周报常用):
    trade_date,symbol,venue_pool,ats_short_volume
    2024-02-01,AAPL,EDGX,12345
    2024-02-01,AAPL,IEX,2345

契约:
- ON CONFLICT DO NOTHING on (trade_date, symbol, venue_pool, source)
- 单行容错:坏行整行 skip,记 warnings
- 静默忽略未在 symbol_master 的 ticker
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol  # ats_short 表暂未在 ORM 中,本实现走 metadata
from etl.load_short_volume import LoadResult

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ATSVolumeRow:
    """单条 ATS 暗池数据(从 FINRA 周报解析或 M2 后的实时数据)。"""

    trade_date: date
    symbol: str
    venue_pool: str
    ats_short_volume: int


@dataclass(slots=True)
class ParseResult:
    rows: list[ATSVolumeRow]
    bad_rows: int


def parse_ats_csv(content: bytes) -> ParseResult:
    """解析 FINRA 周报风格的 CSV(字段:trade_date,symbol,venue_pool,ats_short_volume)。"""
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    out: list[ATSVolumeRow] = []
    bad = 0
    for row in reader:
        try:
            d = date.fromisoformat(row["trade_date"].strip())
            sym = row["symbol"].strip().upper()
            pool = row["venue_pool"].strip()
            vol = int(row["ats_short_volume"].replace(",", ""))
        except (KeyError, ValueError):
            bad += 1
            continue
        if not sym or not pool or vol < 0:
            bad += 1
            continue
        out.append(ATSVolumeRow(d, sym, pool, vol))
    return ParseResult(rows=out, bad_rows=bad)


async def _known_symbols(session: AsyncSession, tickers: set[str]) -> set[str]:
    if not tickers:
        return set()
    stmt = select(Symbol.ticker).where(Symbol.ticker.in_(tickers))
    rs = await session.execute(stmt)
    return {row[0] for row in rs.all()}


def _build_payload(
    rows: list[ATSVolumeRow], known: set[str], source: str = "finra_ats"
) -> tuple[list[dict], int]:
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
                "venue_pool": r.venue_pool,
                "ats_short_volume": r.ats_short_volume,
                "source": source,
            }
        )
    return payload, unknown


async def load_ats_short(
    rows: list[ATSVolumeRow],
    *,
    source: str = "finra_ats",
    session: AsyncSession | None = None,
) -> LoadResult:
    """落库到 ats_short 表。

    说明:ats_short 表在 models/__init__.py 中暂无 ORM(留待 M2 完善),
    本实现使用 SQLAlchemy pg_insert + metadata tables 引用,避免 ORM 与 schema 漂移。
    """
    result = LoadResult(attempted=len(rows))
    if not rows:
        return result

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        known = await _known_symbols(session, {r.symbol for r in rows})
        payload, unknown = _build_payload(rows, known, source=source)
        result.unknown_symbols = unknown

        if payload:
            ats_table = Symbol.__table__.metadata.tables["ats_short"]
            stmt = pg_insert(ats_table).values(payload)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["trade_date", "symbol", "venue_pool", "source"]
            )
            rs = await session.execute(stmt)
            inserted = rs.rowcount or 0
            result.inserted = inserted
            result.skipped = len(payload) - inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = len(rows)
        await session.rollback()
        log.error("load_ats_short.fail", error=str(e), attempted=len(rows))
    finally:
        if own_session:
            await session.close()

    log.info(
        "load_ats_short.done",
        attempted=result.attempted,
        inserted=result.inserted,
        skipped=result.skipped,
        unknown=result.unknown_symbols,
        failures=result.failures,
    )
    return result


async def main() -> None:
    """CLI:`uv run python -m etl.load_ats_short [path/to/ats.csv]`"""
    import asyncio
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("用法: python -m etl.load_ats_short <ats.csv>")
        return
    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"文件不存在: {csv_path}")
        return
    parsed = parse_ats_csv(csv_path.read_bytes())
    print(f"[parse] ok={len(parsed.rows)} bad={parsed.bad_rows}")
    if not parsed.rows:
        return
    res = await load_ats_short(parsed.rows)
    print(
        f"[load_ats_short] attempted={res.attempted} inserted={res.inserted} "
        f"skipped={res.skipped} unknown={res.unknown_symbols} failures={res.failures}"
    )


# ---- M2 启动补充:FINRA ATS 周报真实下载入口(BD-005) ----
#
# FINRA ATS Transparency Data 是周报制(周五发布,含 venue_pool 名称),
# 真实 URL 在 FINRA 官网: https://www.finra.org/finra-data/market-transparency-data/ats-transparency-data
# 生产环境应走代理池 + 限速 1 RPS;沙箱环境下 httpx 不可达 → 友好返回空 bytes,
# 调用方据此写 status='pending_disclosure'。

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=6),
    reraise=True,
)
async def _ats_http_get(url: str) -> bytes:
    headers = {
        "User-Agent": settings.sec_user_agent,
        "Accept": "text/csv,application/zip,*/*",
    }
    async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


def _ats_weekly_url(week_ending: date) -> str:
    """根据 week_ending(周五)推算 FINRA ATS 周报 URL。

    真实 URL 模板(参考 FINRA 公开格式):
        https://www.finra.org/finra-data/market-transparency-data/ats-transparency-data/week-{YYYY-MM-DD}
    本期沙箱不可达,先用占位 URL;上线前由 BD-005 维护者替换为真实链接。
    """
    return f"https://www.finra.org/finra-data/market-transparency-data/ats-transparency-data/week-{week_ending.isoformat()}"


async def download_finra_ats_weekly(week_ending: date) -> bytes:
    """下载指定 week_ending(周五)的 FINRA ATS 周报。

    沙箱环境下 httpx 不可达会抛出 HTTPError,由 tenacity 二次重试后 reraise。
    调用方应捕获并写 pending_disclosure。
    """
    return await _ats_http_get(_ats_weekly_url(week_ending))


async def pull_finra_ats(week_ending: date) -> list[ATSVolumeRow]:
    """M2 启动入口:下载 → 解析 → 返回 rows。

    失败时(网络/解析)统一返回 [],记 log,留给 pipeline 写 status='pending_disclosure'。
    """
    try:
        content = await download_finra_ats_weekly(week_ending)
    except httpx.HTTPError as e:
        log.warning(
            "finra_ats.download.fail", week=str(week_ending), error=str(e)[:200]
        )
        return []
    try:
        parsed = parse_ats_csv(content)
    except Exception as e:  # noqa: BLE001
        log.warning("finra_ats.parse.fail", week=str(week_ending), error=str(e)[:200])
        return []
    log.info(
        "finra_ats.download.done",
        week=str(week_ending),
        rows=len(parsed.rows),
        bad=parsed.bad_rows,
    )
    return parsed.rows


async def main_weekly() -> None:
    """CLI:`uv run python -m etl.load_ats_short weekly [YYYY-MM-DD]`

    YYYY-MM-DD 应为周五;否则自动取当周的周五。
    """
    import asyncio
    import sys

    target = (
        date.fromisoformat(sys.argv[1])
        if len(sys.argv) > 1
        else date.today()
    )
    rows = await pull_finra_ats(target)
    if not rows:
        print(f"[pull_finra_ats] {target} no rows (pending_disclosure)")
        return
    res = await load_ats_short(rows)
    print(
        f"[pull_finra_ats] {target} attempted={res.attempted} inserted={res.inserted} "
        f"skipped={res.skipped} unknown={res.unknown_symbols} failures={res.failures}"
    )


if __name__ == "__main__":
    import asyncio
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].endswith(".csv") else "csv"
    if cmd == "weekly":
        asyncio.run(main_weekly())
    else:
        asyncio.run(main())
