"""ETF 折溢价率代理指标计算 + 落库(BD-032 / BD-088 PoC)。

数据源:
- 二级收盘价、20 日均量:从 daily_price 读
- IOPV(盘中资产净值):本期用 daily_price.close 当作代理(M3 接 CBOE INAV 数据源后再替换)
- proxy_signal 三档:creation_likely / redemption_likely / normal

落库到 etf_proxy_metrics(UNIQUE trade_date, symbol)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol
from app.services.short_metrics import (
    ETFProxyTick,
    etf_proxy_anomaly_score,
    premium_to_iopv,
    relative_volume,
)
from etl.load_short_volume import LoadResult

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ETFProxyResult(LoadResult):
    signals: dict[str, str] | None = None  # {ticker: signal}


def _classify_signal(tick: ETFProxyTick) -> str:
    """根据 premium 方向给出一级市场申赎方向。

    + 溢价 → 套利者会申购 AP → creation_likely
    - 折价 → 套利者会赎回 AP → redemption_likely
    """
    p = premium_to_iopv(tick)
    if p > 0.005:
        return "creation_likely"
    if p < -0.005:
        return "redemption_likely"
    return "normal"


async def _read_etf_snapshots(
    session: AsyncSession, trade_date: date
) -> list[ETFProxyTick]:
    """从 daily_price 读 ETF 标的当日 close + 20 日均量。"""
    daily = Symbol.__table__.metadata.tables["daily_price"]
    sym = Symbol.__table__.metadata.tables["symbol_master"]

    sql = (
        select(
            sym.c.ticker,
            sym.c.name,
            daily.c.trade_date,
            daily.c.close,
            daily.c.volume,
        )
        .join(daily, daily.c.symbol == sym.c.ticker)
        .where(sym.c.type == "etf")
        .where(sym.c.is_active.is_(True))
        .where(daily.c.trade_date == trade_date)
    )
    rs = await session.execute(sql)
    today_rows = [dict(r._mapping) for r in rs.all()]

    if not today_rows:
        return []

    tickers = [r["ticker"] for r in today_rows]
    # 20 日均量
    vol_sql = (
        select(daily.c.symbol, daily.c.volume)
        .where(daily.c.symbol.in_(tickers))
        .where(daily.c.trade_date <= trade_date)
        .order_by(daily.c.symbol, daily.c.trade_date.desc())
    )
    rs2 = await session.execute(vol_sql)
    by_sym: dict[str, list[int]] = {}
    for r in rs2.all():
        by_sym.setdefault(r.symbol, [])
        if len(by_sym[r.symbol]) < 20:
            by_sym[r.symbol].append(int(r.volume or 0))

    out: list[ETFProxyTick] = []
    for r in today_rows:
        vhist = by_sym.get(r["ticker"], [])
        v20 = int(sum(vhist) / len(vhist)) if vhist else 0
        close = float(r["close"])
        out.append(
            ETFProxyTick(
                trade_date=trade_date,
                symbol=r["ticker"],
                nav=close,  # 占位
                iopv=close,  # 暂用 close 代理(M3 接入 CBOE INAV)
                close=close,
                volume=int(r["volume"] or 0),
                volume_20d_avg=v20,
            )
        )
    return out


def _build_payload(ticks: list[ETFProxyTick]) -> tuple[list[dict], dict[str, str]]:
    payload: list[dict] = []
    signals: dict[str, str] = {}
    for t in ticks:
        signal = _classify_signal(t)
        score = etf_proxy_anomaly_score(t)
        signals[t.symbol] = signal
        payload.append(
            {
                "trade_date": t.trade_date,
                "symbol": t.symbol,
                "close": t.close,
                "inav": t.iopv,
                "premium_pct": premium_to_iopv(t) * 100.0,  # 存为百分比
                "volume_vs_ma20": relative_volume(t),
                "proxy_signal": signal,
            }
        )
        _ = score  # 留 M2 接入 Screener
    return payload, signals


async def compute_etf_proxy(
    trade_date: date,
    *,
    symbols: Iterable[str] | None = None,
    session: AsyncSession | None = None,
) -> ETFProxyResult:
    """计算 + 落库 ETF 代理指标(BD-032/BD-088)。

    Args:
        trade_date: 计算当日
        symbols: 限定 ETF 子集;None 时取所有 is_active etf
    """
    result = ETFProxyResult()

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        ticks = await _read_etf_snapshots(session, trade_date)
        if symbols is not None:
            allowed = set(symbols)
            ticks = [t for t in ticks if t.symbol in allowed]

        result.attempted = len(ticks)
        if not ticks:
            await session.commit()
            return result

        payload, signals = _build_payload(ticks)
        result.signals = signals

        table = Symbol.__table__.metadata.tables["etf_proxy_metrics"]
        stmt = (
            pg_insert(table)
            .values(payload)
            .on_conflict_do_nothing(index_elements=["trade_date", "symbol"])
        )
        rs = await session.execute(stmt)
        result.inserted = rs.rowcount or 0
        result.skipped = len(payload) - result.inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = result.attempted
        await session.rollback()
        log.error("compute_etf_proxy.fail", error=str(e), attempted=result.attempted)
    finally:
        if own_session:
            await session.close()

    log.info(
        "compute_etf_proxy.done",
        trade_date=str(trade_date),
        attempted=result.attempted,
        inserted=result.inserted,
        signals=result.signals or {},
    )
    return result


async def main() -> None:
    """`uv run python -m etl.load_etf_proxy [YYYY-MM-DD]`"""
    import asyncio
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    res = await compute_etf_proxy(target)
    print(
        f"[compute_etf_proxy] {target} attempted={res.attempted} "
        f"inserted={res.inserted} skipped={res.skipped} failures={res.failures}"
    )
    if res.signals:
        for sym, sig in sorted(res.signals.items()):
            print(f"  {sym:8s} {sig}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
