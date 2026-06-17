"""§3.5 市场状态门控(BD-063)。

读 ^VIX + ^GSPC 当日 + SPX MA20 → 决定 normal/panic。
- 阈值走 `app.services.regime_history.RegimeConfig`(BD-087 可一行切换)
- 数据库走 `daily_price` 表(symbol_master 已有 ^VIX / ^GSPC 种子)
- VIX 缺失 / SPX 缺失 → 走「不充分数据」分支,默认 normal(BD-063 容错)
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol
from app.services.regime_history import (
    MarketSnapshot,
    RegimeConfig,
    decide_regime,
)

log = logging.getLogger(__name__)


@dataclass(slots=True)
class RegimeSnapshot:
    """M2 启动:BV 化的市场状态快照(扩展 services.regime_history.MarketSnapshot)。"""

    trade_date: date
    vix: float | None
    spx_close: float | None
    spx_ma20: float | None
    regime: str  # 'normal' | 'panic'
    threshold_red: int
    banner_text: str


def _build_banner_text(regime: str, threshold_red: int) -> str:
    """根据 regime 生成前端展示横幅文案(BD-063)。"""
    if regime == "panic":
        return (
            "市场整体波动剧烈,当前信号噪音可能增大;红灯阈值已上调至 "
            f"{threshold_red},仅供参考。"
        )
    return f"市场处于正常波动区间,红灯阈值 {threshold_red}。需注意:历史数据回测,非投资建议。"


async def _read_vix_close(session: AsyncSession, target: date) -> float | None:
    daily = Symbol.__table__.metadata.tables["daily_price"]
    sql = (
        select(daily.c.close)
        .where(daily.c.symbol == "^VIX")
        .where(daily.c.trade_date <= target)
        .order_by(daily.c.trade_date.desc())
        .limit(1)
    )
    rs = await session.execute(sql)
    row = rs.first()
    return float(row[0]) if row and row[0] is not None else None


async def _read_spx_close(
    session: AsyncSession, target: date, lookback: int
) -> tuple[float | None, float | None]:
    """读 ^GSPC 当日 close + 近 lookback 日 MA20。"""
    daily = Symbol.__table__.metadata.tables["daily_price"]
    sql = (
        select(daily.c.trade_date, daily.c.close)
        .where(daily.c.symbol == "^GSPC")
        .where(daily.c.trade_date <= target)
        .order_by(daily.c.trade_date.desc())
        .limit(lookback + 1)
    )
    rs = await session.execute(sql)
    rows = rs.all()
    if not rows:
        return None, None
    spx_close = float(rows[0][1]) if rows[0][1] is not None else None
    if spx_close is None:
        return None, None
    if len(rows) < 2:
        return spx_close, None
    closes: list[float] = [float(r[1]) for r in rows if r[1] is not None]
    # 取前 lookback 条(最近 20 个交易日)
    closes_20 = closes[1 : 1 + lookback]
    if not closes_20:
        return spx_close, None
    spx_ma20 = sum(closes_20) / len(closes_20)
    return spx_close, spx_ma20


async def compute_regime(
    trade_date: date,
    *,
    cfg: RegimeConfig | None = None,
    session: AsyncSession | None = None,
) -> RegimeSnapshot:
    """计算 + 返回市场状态(BD-063)。

    Args:
        trade_date: 计算当日
        cfg: 阈值配置;None 用默认

    Returns:
        RegimeSnapshot
    """
    cfg = cfg or RegimeConfig()
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()
    try:
        vix = await _read_vix_close(session, trade_date)
        spx_close, spx_ma20 = await _read_spx_close(
            session, trade_date, lookback=cfg.spx_ma20_window
        )
    finally:
        if own_session:
            await session.close()

    snap = MarketSnapshot(
        trade_date=trade_date,
        vix=vix,
        spx_close=spx_close,
        spx_ma20=spx_ma20,
    )
    regime, threshold_red = decide_regime(snap, cfg=cfg)
    return RegimeSnapshot(
        trade_date=trade_date,
        vix=vix,
        spx_close=spx_close,
        spx_ma20=spx_ma20,
        regime=regime,
        threshold_red=threshold_red,
        banner_text=_build_banner_text(regime, threshold_red),
    )


async def main() -> None:
    """`uv run python -m app.services.regime [YYYY-MM-DD]`"""
    import asyncio
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    snap = await compute_regime(target)
    print(
        f"[regime] {target} vix={snap.vix} spx={snap.spx_close} ma20={snap.spx_ma20} "
        f"regime={snap.regime} threshold_red={snap.threshold_red}"
    )
    print(snap.banner_text)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
