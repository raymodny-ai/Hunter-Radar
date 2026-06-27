"""Threat Score 计算 + 落库(BD-060 / BD-061 / BD-062 / BD-062b)。

职责:
1. 从 4 个模组派生表(option_anomaly / short_ratio_daily / divergence_window / form4_event)读当日子评分
2. 调 `app.services.threat_score.compute_threat_score` 算 raw + EMA(BD-062b)
3. 调 `app.services.threat_score.decide_lifecycle` 决定 5 态信号灯(BD-062)
4. 调 `app.services.insider.insider_sell_pressure_score` + `cover_up_score` 算模块四子评分
5. 落库到 `threat_score_daily`(UNIQUE trade_date, symbol)

设计原则:
- 阈值集中:BD-061 默认权重走 `app.core.config.settings.threat_weights_default`
- 红灯阈值:normal=70, panic=80(由 regime 决定;M3 串接;M2 默认 normal)
- EMA 半衰期:走 `settings.ema_halflife_days` 默认 2 交易日(OQ-02 决策)
- 状态机:严格按 EMA 后分判定,严禁用 raw 触发(BD-062 决策)
- 历史窗口:默认 30 日,够 2 个半衰期 EMA
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Symbol
from app.services.divergence import DivergenceVerdict, divergence_to_score
from app.services.insider import (
    BuybackEvent,
    Form4Event,
    cover_up_alert,
    cover_up_score,
    insider_sell_pressure_score,
)
from app.services.short_metrics import z_to_anomaly_score
from app.services.threat_score import (
    compute_threat_score,
    consecutive_business_days_above,
    decide_lifecycle,
    reallocate_weights,
)
from etl.load_short_volume import LoadResult

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ThreatScoreLoadResult(LoadResult):
    """Threat Score 落库结果。"""

    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0


# ---- 子评分映射(BD-060) ----


def _options_module_score(hit_count: int, top_n: int = 10) -> float:
    """末日 Put 异常合约命中数 → 0-100。

    命中数 / top_n 满档 100;零命中 30(中性偏低)。
    """
    if hit_count <= 0:
        return 30.0
    if hit_count >= top_n:
        return 100.0
    return 30.0 + (hit_count / top_n) * 70.0


def _short_module_score(z: float | None) -> float:
    """Z-Score → 0-100(用 services.short_metrics.z_to_anomaly_score)。"""
    return z_to_anomaly_score(z)


def _divergence_module_score(p_price: float, p_volume: float, is_divergent: bool) -> float:
    """量价背离 → 0-100(用 services.divergence.divergence_to_score)。"""
    v = DivergenceVerdict(
        is_divergent=is_divergent,
        p_price=p_price,
        p_volume=p_volume,
        rationale="",
    )
    return divergence_to_score(v)


def _insider_module_score(
    sells: list[Form4Event],
    buybacks: list[BuybackEvent],
    asof: date,
) -> float:
    """内部人抛压 + 掩护配对 → 0-100(混合分)。"""
    press = insider_sell_pressure_score(sells, asof=asof)
    pairs = cover_up_alert(sells, buybacks, asof=asof)
    cover = cover_up_score(pairs)
    # 加权:抛压 60% + 掩护 40%(掩护更严重,权略高)
    return round(press * 0.6 + cover * 0.4, 2)


# ---- 读取辅助 ----


async def _read_options_hits(
    session: AsyncSession,
    tickers: list[str],
    trade_date: date,
) -> dict[str, int]:
    """读指定日每个 ticker 的 option_anomaly 命中数。"""
    if not tickers:
        return {}
    tbl = Symbol.__table__.metadata.tables["option_anomaly"]
    sql = (
        select(tbl.c.symbol)
        .where(tbl.c.symbol.in_(set(tickers)))
        .where(tbl.c.trade_date == trade_date)
    )
    rs = await session.execute(sql)
    counts: dict[str, int] = defaultdict(int)
    for row in rs.all():
        counts[row.symbol] += 1
    return dict(counts)


async def _read_short_module(
    session: AsyncSession,
    tickers: list[str],
    trade_date: date,
) -> dict[str, float | None]:
    """读 short_ratio_daily 当日 z_score_60d。"""
    if not tickers:
        return {}
    tbl = Symbol.__table__.metadata.tables["short_ratio_daily"]
    sql = (
        select(tbl.c.symbol, tbl.c.z_score_60d)
        .where(tbl.c.symbol.in_(set(tickers)))
        .where(tbl.c.trade_date == trade_date)
    )
    rs = await session.execute(sql)
    out: dict[str, float | None] = {}
    for row in rs.all():
        out[row.symbol] = float(row.z_score_60d) if row.z_score_60d is not None else None
    return out


async def _read_divergence(
    session: AsyncSession,
    tickers: list[str],
    trade_date: date,
) -> dict[str, tuple[float, float, bool]]:
    """读 divergence_window 当日 (p_price, p_short, is_divergent)。"""
    if not tickers:
        return {}
    tbl = Symbol.__table__.metadata.tables["divergence_window"]
    sql = (
        select(tbl.c.symbol, tbl.c.p_price, tbl.c.p_short, tbl.c.divergence_state)
        .where(tbl.c.symbol.in_(set(tickers)))
        .where(tbl.c.trade_date == trade_date)
    )
    rs = await session.execute(sql)
    out: dict[str, tuple[float, float, bool]] = {}
    for row in rs.all():
        is_div = row.divergence_state in ("rising", "confirmed")
        out[row.symbol] = (
            float(row.p_price or 0.5),
            float(row.p_short or 0.5),
            is_div,
        )
    return out


async def _read_form4_sells(
    session: AsyncSession,
    tickers: list[str],
    asof: date,
    lookback_days: int = 20,
) -> dict[str, list[Form4Event]]:
    """读 form4_event 关键内部人 S 事件(近 20 个自然日内)。"""
    if not tickers:
        return {}
    tbl = Symbol.__table__.metadata.tables["form4_event"]
    cutoff = asof - timedelta(days=int(lookback_days * 1.6) + 1)
    sql = (
        select(
            tbl.c.symbol,
            tbl.c.insider_name,
            tbl.c.insider_role,
            tbl.c.txn_date,
            tbl.c.filed_at,
            tbl.c.direction,
            tbl.c.qty,
            tbl.c.price,
            tbl.c.form_url,
        )
        .where(tbl.c.symbol.in_(set(tickers)))
        .where(tbl.c.direction == "sell")
        .where(tbl.c.txn_date >= cutoff)
        .where(tbl.c.txn_date <= asof)
        .order_by(tbl.c.symbol, tbl.c.txn_date.desc())
    )
    rs = await session.execute(sql)
    out: dict[str, list[Form4Event]] = defaultdict(list)
    for row in rs.all():
        # 关键内部人过滤(BD-050)
        if row.insider_role not in ("CEO", "CFO", "Director", "10% Holder"):
            continue
        out[row.symbol].append(
            Form4Event(
                symbol=row.symbol,
                insider_name=row.insider_name,
                insider_role=row.insider_role,
                txn_date=row.txn_date,
                filed_at=row.filed_at,
                direction=row.direction,
                qty=int(row.qty or 0),
                price=float(row.price) if row.price is not None else None,
                form_url=row.form_url or "",
            )
        )
    return dict(out)


async def _read_buybacks(
    session: AsyncSession,
    tickers: list[str],
    asof: date,
    lookback_days: int = 60,
) -> dict[str, list[BuybackEvent]]:
    """读 buyback_event(近 60 个自然日,掩护判定窗口)。"""
    if not tickers:
        return {}
    tbl = Symbol.__table__.metadata.tables["buyback_event"]
    cutoff = asof - timedelta(days=int(lookback_days * 1.6) + 1)
    sql = (
        select(
            tbl.c.symbol,
            tbl.c.form_type,
            tbl.c.announced_at,
            tbl.c.amount_usd,
            tbl.c.execution_window,
            tbl.c.source_url,
        )
        .where(tbl.c.symbol.in_(set(tickers)))
        .where(tbl.c.announced_at >= cutoff)
        .where(tbl.c.announced_at <= asof)
    )
    rs = await session.execute(sql)
    out: dict[str, list[BuybackEvent]] = defaultdict(list)
    for row in rs.all():
        # execution_window 是 "30d" 字符串;粗略拆解
        try:
            dur = int((row.execution_window or "0d").rstrip("d"))
        except ValueError:
            dur = 0
        out[row.symbol].append(
            BuybackEvent(
                symbol=row.symbol,
                announce_date=row.announced_at,
                amount_usd=float(row.amount_usd or 0),
                duration_days=dur,
                form_url=row.source_url or "",
            )
        )
    return dict(out)


async def _read_history_scores(
    session: AsyncSession,
    tickers: list[str],
    end: date,
    days: int,
) -> dict[str, list[dict]]:
    """读历史 N 日 threat_score_daily(用于 EMA)。"""
    if not tickers:
        return {}
    tbl = Symbol.__table__.metadata.tables["threat_score_daily"]
    cutoff = end - timedelta(days=int(days * 1.6) + 1)
    sql = (
        select(
            tbl.c.symbol,
            tbl.c.trade_date,
            tbl.c.module_options,
            tbl.c.module_short,
            tbl.c.module_divergence,
            tbl.c.module_insider,
        )
        .where(tbl.c.symbol.in_(set(tickers)))
        .where(tbl.c.trade_date >= cutoff)
        .where(tbl.c.trade_date < end)
        .order_by(tbl.c.symbol, tbl.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    out: dict[str, list[dict]] = defaultdict(list)
    for row in rs.all():
        out[row.symbol].append(
            {
                "trade_date": row.trade_date,
                "module_options": float(row.module_options or 0),
                "module_short": float(row.module_short or 0),
                "module_divergence": float(row.module_divergence or 0),
                "module_insider": float(row.module_insider or 0),
            }
        )
    return dict(out)


def _is_data_warmup(short_z: float | None, history: list[dict]) -> bool:
    """数据暖启动判定(BD-090 / OQ-22):Z-Score 缺失 或 历史 < 60 日。"""
    if short_z is None:
        return True
    if len(history) < 30:
        return True
    return False


async def _read_options_signals(
    session: AsyncSession,
    tickers: list[str],
    trade_date: date,
) -> dict[str, str]:
    """读 V1.5.9 Options signal_strength(供动态权重重分配)。

    优先读 Redis(opt:{ticker}:{date});miss 则查 option_pcr_daily 表;
    全部 miss 则返回 NORMAL。
    """
    import json

    signals: dict[str, str] = {}

    # 1) 优先 Redis
    try:
        from app.core.redis_client import redis_client
        for t in tickers:
            key = f"opt:{t}:{trade_date.isoformat()}"
            raw = await redis_client.get(key)
            if raw is not None:
                data = json.loads(raw)
                signals[t] = data.get("signal_strength", "NORMAL")
    except Exception:
        pass

    # 2) 未命中的 ticker 查 option_pcr_daily 表
    missing = [t for t in tickers if t not in signals]
    if missing:
        try:
            tbl = Symbol.__table__.metadata.tables.get("option_pcr_daily")
            if tbl is not None:
                sql = (
                    select(tbl.c.symbol, tbl.c.signal_strength)
                    .where(tbl.c.symbol.in_(set(missing)))
                    .where(tbl.c.trade_date == trade_date)
                )
                rs = await session.execute(sql)
                for row in rs.all():
                    signals[row.symbol] = row.signal_strength or "NORMAL"
        except Exception:
            pass

    # 3) 填充默认 NORMAL
    for t in tickers:
        if t not in signals:
            signals[t] = "NORMAL"

    return signals


# ---- 入口 ----


async def compute_threat_scores(
    trade_date: date,
    *,
    symbols: list[str] | None = None,
    ema_halflife_days: int | None = None,
    history_days: int = 30,
    session: AsyncSession | None = None,
) -> ThreatScoreLoadResult:
    """计算 + 落库 threat_score_daily(BD-060/061/062/062b)。

    Args:
        trade_date: 计算当日
        symbols: 限定标的;None 时取全 universe
        ema_halflife_days: EMA 半衰期;None 时走 settings(默认 2)
        history_days: EMA 历史窗口(默认 30)

    Returns:
        ThreatScoreLoadResult
    """
    halflife = ema_halflife_days or settings.ema_halflife_days
    weights_default = settings.threat_weights_default
    result = ThreatScoreLoadResult()

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        # 1) 标的范围 + 类型
        if symbols is None:
            rs = await session.execute(
                select(Symbol.ticker, Symbol.type).where(Symbol.is_universe.is_(True))
            )
            ticker_type: dict[str, str] = {t: ty for t, ty in rs.all()}
        else:
            rs2 = await session.execute(
                select(Symbol.ticker, Symbol.type).where(Symbol.ticker.in_(set(symbols)))
            )
            ticker_type = {t: ty for t, ty in rs2.all()}
        target_tickers = list(ticker_type.keys())
        result.attempted = len(target_tickers)
        if not target_tickers:
            await session.commit()
            return result

        # 2) 读 4 模组 + 内部人
        options_hits = await _read_options_hits(session, target_tickers, trade_date)
        short_z = await _read_short_module(session, target_tickers, trade_date)
        div_data = await _read_divergence(session, target_tickers, trade_date)
        f4_sells = await _read_form4_sells(session, target_tickers, trade_date)
        buybacks = await _read_buybacks(session, target_tickers, trade_date)

        # 3) 读历史
        history = await _read_history_scores(session, target_tickers, trade_date, history_days)

        # 4) 算每 ticker
        payload: list[dict] = []
        # 读 V1.5.9 Options signal_strength(供动态权重重分配)
        options_signals = await _read_options_signals(session, target_tickers, trade_date)

        for sym in target_tickers:
            sym_type = ticker_type[sym]
            is_etf = sym_type == "etf"

            mod_opts = _options_module_score(options_hits.get(sym, 0))
            mod_short = _short_module_score(short_z.get(sym))
            p_price, p_vol, is_div = div_data.get(sym, (0.5, 0.5, False))
            mod_div = _divergence_module_score(p_price, p_vol, is_div)

            if is_etf:
                mod_insider = 0.0
                weights = weights_default["etf"]
            else:
                mod_insider = _insider_module_score(
                    f4_sells.get(sym, []), buybacks.get(sym, []), trade_date
                )
                weights = weights_default["stock"]

            # V1.5.9 动态权重重分配: Options HIGH → 权重提升至 0.40
            opt_signal = options_signals.get(sym, "NORMAL")
            if opt_signal == "HIGH":
                signals = {"options": "HIGH", "short": "NORMAL", "divergence": "NORMAL"}
                if not is_etf:
                    signals["insider"] = "NORMAL"
                weights = reallocate_weights(
                    signals,
                    base_weights=weights,
                    symbol_type=sym_type,
                )

            # 调 services 算 raw + EMA(Min(Score,100) 已在 compute_threat_score 内)
            hist = history.get(sym, [])
            score = compute_threat_score(
                module_options=mod_opts,
                module_short=mod_short,
                module_divergence=mod_div,
                module_insider=mod_insider,
                weights=weights,
                ema_halflife_days=halflife,
                history=hist,
            )
            raw = score["raw"]
            ema = score["ema"]

            # 5 态(red 阈值 M2 默认 70;M3 接 regime 后调整为 80)
            red_thr = settings.threat_red_threshold
            lifecycle = decide_lifecycle(ema, red_threshold=float(red_thr))

            # 连续 ≥ N 日高分 → 升级(此处只记 base,不直接生成终极警报;留给 BD-062 状态机)
            # 仅统计
            if lifecycle == "red":
                result.red_count += 1
            elif lifecycle == "yellow":
                result.yellow_count += 1
            elif lifecycle == "green":
                result.green_count += 1

            # 暖启动(BD-090)
            warmup = _is_data_warmup(short_z.get(sym), hist)

            payload.append(
                {
                    "trade_date": trade_date,
                    "symbol": sym,
                    "symbol_type": sym_type,
                    "module_options": round(mod_opts, 2),
                    "module_short": round(mod_short, 2),
                    "module_divergence": round(mod_div, 2),
                    "module_insider": round(mod_insider, 2),
                    "weights": weights,
                    "total": ema,  # EMA 后
                    "total_raw": raw,
                    "ema_halflife": halflife,
                    "signal_lifecycle": lifecycle,
                    "nl_summary": None,  # BD-065 由 nl_summary service 后续填充
                    "regime": "normal",  # M3 接 BD-063 后改为 dynamic
                }
            )

        if not payload:
            await session.commit()
            return result

        # 5) 落库 ON CONFLICT DO UPDATE
        table = Symbol.__table__.metadata.tables["threat_score_daily"]
        stmt = pg_insert(table).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["trade_date", "symbol"],
            set_={
                "module_options": stmt.excluded.module_options,
                "module_short": stmt.excluded.module_short,
                "module_divergence": stmt.excluded.module_divergence,
                "module_insider": stmt.excluded.module_insider,
                "weights": stmt.excluded.weights,
                "total": stmt.excluded.total,
                "total_raw": stmt.excluded.total_raw,
                "ema_halflife": stmt.excluded.ema_halflife,
                "signal_lifecycle": stmt.excluded.signal_lifecycle,
            },
        )
        rs = await session.execute(stmt)
        result.inserted = rs.rowcount or 0
        result.skipped = len(payload) - result.inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = result.attempted
        await session.rollback()
        log.error("compute_threat_scores.fail", error=str(e), attempted=result.attempted)
    finally:
        if own_session:
            await session.close()

    log.info(
        "compute_threat_scores.done",
        trade_date=str(trade_date),
        attempted=result.attempted,
        inserted=result.inserted,
        red=result.red_count,
        yellow=result.yellow_count,
        green=result.green_count,
    )
    return result


async def main() -> None:
    """`uv run python -m etl.load_threat_score [YYYY-MM-DD]`"""
    import asyncio
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    res = await compute_threat_scores(target)
    print(
        f"[load_threat_score] {target} attempted={res.attempted} "
        f"inserted={res.inserted} skipped={res.skipped} "
        f"red={res.red_count} yellow={res.yellow_count} green={res.green_count} "
        f"failures={res.failures}"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
