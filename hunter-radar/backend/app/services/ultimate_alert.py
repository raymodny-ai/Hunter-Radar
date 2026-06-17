"""§3.5 信号生命周期状态机(BD-062)+ 终极警报触发(BD-064)。

职责:
- 读 threat_score_daily 当日 + 历史 → 判定 5 态与「连续 N 日高分」
- 触发终极警报的条件(BD-064):
  1. Score EMA ≥ 阈值(由 regime 决定;normal=70, panic=80)
  2. 至少 1 个核心模块在 EMA 平滑后连续 ≥2 个交易日(严格交易日)同时高分
  3. 24 小时内不重复触发(防抖)
  4. 严禁仅基于单日 EMA 前原始分触发
- 落库到 `ultimate_alert`(UNIQUE trade_date, symbol)

设计原则:
- 严格按 OQ-02 决策:连续 2 交易日 = EMA 后连续 ≥ 阈值
- 防抖:同 symbol 24h 内至多 1 次 → 检查 latest triggered_at
- 状态机文本化:便于回溯
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Symbol
from app.services.regime_history import RegimeConfig
from app.services.threat_score import consecutive_business_days_above

log = logging.getLogger(__name__)


@dataclass(slots=True)
class UltimateAlertRow:
    """单条终极警报记录(供 DB 写入)。"""

    triggered_at: datetime
    symbol: str
    trade_date: date
    threat_score: float
    modules_active: list[str]
    regime: str
    consecutive_days: int
    debounce_passed: bool
    raw_score: float
    ema_score: float


@dataclass(slots=True)
class UltimateAlertResult:
    """终极警报计算结果。"""

    attempted: int = 0
    triggered: int = 0
    skipped_debounce: int = 0
    skipped_no_continuous: int = 0
    skipped_below_threshold: int = 0
    rows: list[UltimateAlertRow] | None = None


# ---- 1) 读取历史(EMA 序列 + 模块子评分序列) ----


async def _read_history_series(
    session: AsyncSession,
    tickers: list[str],
    end: date,
    lookback: int = 5,
) -> dict[str, list[dict]]:
    """读每个 ticker 近 lookback 日的 threat_score_daily 行。"""
    if not tickers:
        return {}
    tbl = Symbol.__table__.metadata.tables["threat_score_daily"]
    cutoff = end - timedelta(days=int(lookback * 1.6) + 2)
    sql = (
        select(
            tbl.c.symbol,
            tbl.c.trade_date,
            tbl.c.module_options,
            tbl.c.module_short,
            tbl.c.module_divergence,
            tbl.c.module_insider,
            tbl.c.total,
            tbl.c.total_raw,
            tbl.c.signal_lifecycle,
            tbl.c.regime,
        )
        .where(tbl.c.symbol.in_(set(tickers)))
        .where(tbl.c.trade_date >= cutoff)
        .where(tbl.c.trade_date <= end)
        .order_by(tbl.c.symbol, tbl.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    out: dict[str, list[dict]] = {t: [] for t in tickers}
    for row in rs.all():
        d = row._mapping
        out.setdefault(d["symbol"], []).append(
            {
                "trade_date": d["trade_date"],
                "module_options": float(d["module_options"] or 0),
                "module_short": float(d["module_short"] or 0),
                "module_divergence": float(d["module_divergence"] or 0),
                "module_insider": float(d["module_insider"] or 0),
                "total_ema": float(d["total"] or 0),
                "total_raw": float(d["total_raw"] or 0),
                "signal_lifecycle": d["signal_lifecycle"] or "init",
                "regime": d["regime"] or "normal",
            }
        )
    return out


# ---- 2) 防抖:24h 内是否已触发 ----


async def _has_recent_alert(
    session: AsyncSession, symbol: str, before: datetime
) -> bool:
    """同一 symbol 在 before 前 24h 内是否已触发终极警报。"""
    tbl = Symbol.__table__.metadata.tables["ultimate_alert"]
    sql = (
        select(tbl.c.triggered_at)
        .where(tbl.c.symbol == symbol)
        .where(tbl.c.triggered_at > before - timedelta(hours=24))
        .order_by(tbl.c.triggered_at.desc())
        .limit(1)
    )
    rs = await session.execute(sql)
    return rs.first() is not None


# ---- 3) 主入口 ----


def _resolve_threshold(regime: str) -> int:
    """根据 regime 决定红灯阈值(BD-063/BD-064)。"""
    return (
        settings.threat_red_threshold_panic
        if regime == "panic"
        else settings.threat_red_threshold
    )


def _pick_active_modules(history: list[dict], module_thr: float = 60.0) -> list[str]:
    """当日(EMA 后)子评分 ≥ 阈值的模块名。"""
    if not history:
        return []
    today = history[-1]
    out: list[str] = []
    if today["module_options"] >= module_thr:
        out.append("options")
    if today["module_short"] >= module_thr:
        out.append("short")
    if today["module_divergence"] >= module_thr:
        out.append("divergence")
    if today["module_insider"] >= module_thr:
        out.append("insider")
    return out


async def evaluate_ultimate_alerts(
    trade_date: date,
    *,
    symbols: list[str] | None = None,
    regime_cfg: RegimeConfig | None = None,
    module_thr: float = 60.0,
    consecutive_days: int = 2,
    session: AsyncSession | None = None,
) -> UltimateAlertResult:
    """评估 + 触发 + 落库终极警报(BD-062/064)。

    Args:
        trade_date: 计算当日
        symbols: 限定标的;None 时取全 universe
        module_thr: 模块「高分」阈值(默认 60)
        consecutive_days: 连续 ≥ N 日(默认 2,严格交易日)

    Returns:
        UltimateAlertResult
    """
    result = UltimateAlertResult(rows=[])
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        # 1) 标的范围
        if symbols is None:
            rs = await session.execute(
                select(Symbol.ticker).where(Symbol.is_universe.is_(True))
            )
            target_tickers = [r[0] for r in rs.all()]
        else:
            target_tickers = list(symbols)
        result.attempted = len(target_tickers)
        if not target_tickers:
            await session.commit()
            return result

        # 2) 读历史
        history = await _read_history_series(session, target_tickers, trade_date, lookback=consecutive_days + 1)

        # 3) 评估每 ticker
        triggered_at = datetime.now(timezone.utc)
        to_insert: list[dict] = []
        for sym in target_tickers:
            rows = history.get(sym, [])
            if not rows:
                continue
            today = rows[-1]
            ema = today["total_ema"]
            raw = today["total_raw"]
            regime = today["regime"] or "normal"
            threshold = _resolve_threshold(regime)

            # 条件 1:Score ≥ 阈值
            if ema < threshold:
                result.skipped_below_threshold += 1
                continue

            # 条件 2:模块连续 ≥ N 日高分(EMA 后)
            active_today = _pick_active_modules(rows, module_thr=module_thr)
            # 对每个 active 模块,检查 EMA 子评分序列连续 ≥ module_thr 的日数
            continuous_hits: list[str] = []
            for mod in active_today:
                series = [r.get(f"module_{mod}", 0.0) for r in rows[-consecutive_days - 1 :]]
                cnt = consecutive_business_days_above(series, module_thr)
                if cnt >= consecutive_days:
                    continuous_hits.append(mod)
            if not continuous_hits:
                result.skipped_no_continuous += 1
                continue

            # 条件 3:24h 防抖
            if await _has_recent_alert(session, sym, triggered_at):
                result.skipped_debounce += 1
                continue

            # 写入
            row = UltimateAlertRow(
                triggered_at=triggered_at,
                symbol=sym,
                trade_date=trade_date,
                threat_score=ema,
                modules_active=continuous_hits,
                regime=regime,
                consecutive_days=consecutive_days,
                debounce_passed=True,
                raw_score=raw,
                ema_score=ema,
            )
            result.rows.append(row)
            to_insert.append(
                {
                    "triggered_at": triggered_at,
                    "symbol": sym,
                    "trade_date": trade_date,
                    "threat_score": ema,
                    "modules_active": continuous_hits,
                    "regime": regime,
                    "consecutive_days": consecutive_days,
                    "debounce_passed": True,
                    "raw_score": raw,
                    "ema_score": ema,
                }
            )

        if not to_insert:
            await session.commit()
            return result

        # 4) 落库 ON CONFLICT DO NOTHING
        tbl = Symbol.__table__.metadata.tables["ultimate_alert"]
        stmt = pg_insert(tbl).values(to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["trade_date", "symbol"])
        await session.execute(stmt)
        result.triggered = len(to_insert)
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        log.error("evaluate_ultimate_alerts.fail", error=str(e), attempted=result.attempted)
    finally:
        if own_session:
            await session.close()

    log.info(
        "evaluate_ultimate_alerts.done",
        trade_date=str(trade_date),
        attempted=result.attempted,
        triggered=result.triggered,
        skipped_debounce=result.skipped_debounce,
        skipped_no_continuous=result.skipped_no_continuous,
        skipped_below_threshold=result.skipped_below_threshold,
    )
    return result


async def main() -> None:
    """`uv run python -m app.services.ultimate_alert [YYYY-MM-DD]`"""
    import asyncio
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    res = await evaluate_ultimate_alerts(target)
    print(
        f"[ultimate_alert] {target} attempted={res.attempted} "
        f"triggered={res.triggered} "
        f"skipped_below_threshold={res.skipped_below_threshold} "
        f"skipped_no_continuous={res.skipped_no_continuous} "
        f"skipped_debounce={res.skipped_debounce}"
    )
    if res.rows:
        for r in res.rows:
            print(
                f"  {r.symbol:6s} trade_date={r.trade_date} ema={r.ema_score:.2f} "
                f"modules={r.modules_active} regime={r.regime}"
            )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
