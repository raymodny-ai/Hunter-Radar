"""Yahoo Finance 期权链落库 + 末日 Put 异常合约计算(BD-009 / BD-020 / BD-021 / BD-022)。

职责:
1. `load_options_chain`:把 `etl.yfinance_pull.fetch_options_chain` 拉到的合约落库到 options_chain
2. `compute_option_anomaly`:从 options_chain 读出当日合约 + 前日 OI,过滤出末日 Put 异常合约,
   落库到 option_anomaly

设计原则:
- ETL 与计算分离:落库层只负责把爬虫结果入库,不掺计算
- 异常计算层调 `services.options_anomaly`,**OQ-01 阈值集中于 AnomalyThresholds dataclass**
- ON CONFLICT DO NOTHING:options_chain UNIQUE(trade_date, contract, source);
  option_anomaly UNIQUE(trade_date, contract)
- 兼容 ETF 标的(由 underlying_type 字段决定 OTM 阈值)
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
from app.models import Symbol  # 复用 metadata 引用 options_chain / option_anomaly
from app.services.options_anomaly import (
    AnomalyThresholds,
    DynamicBaseline,
    GammaCluster,
    OptionCandidate,
    OptionsSignalSummary,
    SignalStrength,
    compute_dynamic_vol_min,
    compute_pcr,
    compute_signal_strength,
    detect_gamma_cluster,
    filter_top_anomaly_puts,
    is_otm_assassin,
    notional,
)
from etl.load_short_volume import LoadResult
from etl.yfinance_pull import OptionContract

log = logging.getLogger(__name__)


# ---- 1) 落库层 ----


async def _known_symbol_types(session: AsyncSession, tickers: Iterable[str]) -> dict[str, str]:
    """返回 {ticker: type},type ∈ {'stock','etf',...}。"""
    stmt = select(Symbol.ticker, Symbol.type).where(Symbol.ticker.in_(set(tickers)))
    rs = await session.execute(stmt)
    return {ticker: t for ticker, t in rs.all()}


def _build_options_payload(
    rows: list[OptionContract],
    spot_by_symbol: dict[str, float],
    trade_date: date,
    source: str = "yfinance",
) -> list[dict]:
    """把 OptionContract 转 options_chain 写入 payload。"""
    out: list[dict] = []
    for r in rows:
        spot = spot_by_symbol.get(r.underlying, 0.0)
        out.append(
            {
                "trade_date": trade_date,
                "symbol": r.underlying,
                "contract": r.contract,
                "underlying": r.underlying,
                "expiry": r.expiry,
                "strike": r.strike,
                "right": r.right,
                "last_price": r.last_price,
                "bid": r.bid,
                "ask": r.ask,
                "volume": r.volume,
                "open_interest": r.open_interest,
                "implied_vol": r.implied_vol,
                "in_the_money": r.in_the_money,
                "source": source,
            }
        )
    return out


async def load_options_chain(
    rows: list[OptionContract],
    *,
    trade_date: date,
    spot_by_symbol: dict[str, float] | None = None,
    source: str = "yfinance",
    session: AsyncSession | None = None,
) -> LoadResult:
    """落库到 options_chain(BD-009)。

    Args:
        rows: `etl.yfinance_pull.fetch_options_chain` 返回的合约
        trade_date: 拉取当日的交易日(同一批次合约属于同一日)
        spot_by_symbol: 当日标的价格 {ticker: spot};None 时后续回填(从 daily_price 取)
        source: 数据源
    """
    result = LoadResult(attempted=len(rows))
    if not rows:
        return result

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        tickers = {r.underlying for r in rows}
        _ = await _known_symbol_types(session, tickers)  # 仅校验存在性
        spot_map = spot_by_symbol or {}
        payload = _build_options_payload(rows, spot_map, trade_date, source=source)

        if payload:
            table = Symbol.__table__.metadata.tables["options_chain"]
            stmt = pg_insert(table).values(payload)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["trade_date", "contract", "source"]
            )
            rs = await session.execute(stmt)
            inserted = rs.rowcount or 0
            result.inserted = inserted
            result.skipped = len(payload) - inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = len(rows)
        await session.rollback()
        log.error("load_options_chain.fail", error=str(e), attempted=len(rows))
    finally:
        if own_session:
            await session.close()

    log.info(
        "load_options_chain.done",
        attempted=result.attempted,
        inserted=result.inserted,
        skipped=result.skipped,
        failures=result.failures,
    )
    return result


# ---- 2) 末日 Put 异常合约计算 ----


@dataclass(slots=True)
class AnomalyLoadResult:
    """异常合约计算 + 落库的结果。"""

    attempted: int = 0
    candidates: int = 0  # 候选合约数(DTE≤3 的 Put)
    hits: int = 0  # 满足全部条件的合约数
    inserted: int = 0
    skipped: int = 0
    failures: int = 0


async def _read_today_puts(
    session: AsyncSession, trade_date: date, symbol: str
) -> list[dict]:
    """读出指定交易日、symbol 的全部 Put 合约 + 前一日 OI(OI_prev)。"""
    table = Symbol.__table__.metadata.tables["options_chain"]
    sql = (
        select(
            table.c.contract,
            table.c.symbol,
            table.c.expiry,
            table.c.strike,
            table.c.right,
            table.c.last_price,
            table.c.volume,
            table.c.open_interest,
        )
        .where(table.c.trade_date == trade_date)
        .where(table.c.symbol == symbol)
        .where(table.c.right == "P")
    )
    rs = await session.execute(sql)
    today_rows = [dict(row._mapping) for row in rs.all()]

    # 前一日 OI(同 contract)
    if not today_rows:
        return []
    contracts = [r["contract"] for r in today_rows]
    prev_sql = (
        select(table.c.contract, table.c.open_interest, table.c.trade_date)
        .where(table.c.contract.in_(contracts))
        .where(table.c.trade_date < trade_date)
        .order_by(table.c.contract, table.c.trade_date.desc())
    )
    rs2 = await session.execute(prev_sql)
    prev_map: dict[str, int] = {}
    for row in rs2.all():
        if row.contract not in prev_map:
            prev_map[row.contract] = int(row.open_interest or 0)

    for r in today_rows:
        r["open_interest_prev"] = prev_map.get(r["contract"], 0)
    return today_rows


def _to_candidates(
    rows: list[dict], symbol_type_map: dict[str, str], spot_by_symbol: dict[str, float]
) -> list[OptionCandidate]:
    """dict 行 → OptionCandidate 列表,过滤 DTE≤3。"""
    out: list[OptionCandidate] = []
    for r in rows:
        spot = spot_by_symbol.get(r["symbol"], 0.0)
        if spot <= 0:
            continue
        # dte 优先取 compute_option_anomaly 调用方已注入的 r["dte"];
        # fallback:从 expiry - trade_date 推算(此时调用方未注入)
        dte_val = r.get("dte")
        if dte_val is None:
            td = r.get("trade_date")
            if td is not None:
                dte_val = (r["expiry"] - td).days
            else:
                dte_val = 0
        out.append(
            OptionCandidate(
                contract=r["contract"],
                underlying=r["symbol"],
                underlying_type=symbol_type_map.get(r["symbol"], "stock"),
                trade_date=r.get("trade_date", date.today()),
                expiry=r["expiry"],
                dte=dte_val,
                right=r["right"],
                strike=float(r["strike"]),
                last_price=float(r["last_price"] or 0.0),
                spot=spot,
                volume=int(r["volume"] or 0),
                open_interest=int(r["open_interest"] or 0),
                open_interest_prev=int(r.get("open_interest_prev") or 0),
            )
        )
    return out


async def _spot_by_symbol(
    session: AsyncSession, tickers: Iterable[str], trade_date: date
) -> dict[str, float]:
    """从 daily_price 取指定交易日 close 作为 spot。"""
    table = Symbol.__table__.metadata.tables["daily_price"]
    sql = select(table.c.symbol, table.c.close).where(
        table.c.symbol.in_(set(tickers)),
        table.c.trade_date == trade_date,
    )
    rs = await session.execute(sql)
    return {s: float(c) for s, c in rs.all()}


def _anomaly_payload(
    trade_date: date, hits: list[OptionCandidate], oi_5d: dict[str, list[float]]
) -> list[dict]:
    out: list[dict] = []
    for c in hits:
        out.append(
            {
                "trade_date": trade_date,
                "symbol": c.underlying,
                "contract": c.contract,
                "dte": c.dte,
                "oi_increase_pct": (
                    (c.open_interest - c.open_interest_prev) / c.open_interest_prev
                    if c.open_interest_prev > 0
                    else 0.0
                ),
                "volume_oi_ratio": (
                    c.volume / c.open_interest if c.open_interest > 0 else 0.0
                ),
                "notional": notional(c),
                "is_top10_notional": True,  # hits 已是 Top N
                "oi_5d_series": oi_5d.get(c.contract, []),
                "has_known_catalyst": False,
                "catalyst_note": None,
            }
        )
    return out


async def _read_oi_5d_series(
    session: AsyncSession, contracts: Iterable[str], trade_date: date
) -> dict[str, list[float]]:
    """近 5 日 OI 序列(BD-022)— 含 trade_date 当日。"""
    table = Symbol.__table__.metadata.tables["options_chain"]
    sql = (
        select(table.c.contract, table.c.trade_date, table.c.open_interest)
        .where(table.c.contract.in_(set(contracts)))
        .where(table.c.trade_date <= trade_date)
        .order_by(table.c.contract, table.c.trade_date.desc())
    )
    rs = await session.execute(sql)
    series: dict[str, list[float]] = {}
    for row in rs.all():
        if row.contract not in series:
            series[row.contract] = []
        if len(series[row.contract]) < 5:
            series[row.contract].append(float(row.open_interest or 0))
    # 翻转成时间升序
    for k in series:
        series[k].reverse()
    return series


async def compute_option_anomaly(
    trade_date: date,
    *,
    symbols: list[str] | None = None,
    thr: AnomalyThresholds | None = None,
    session: AsyncSession | None = None,
) -> AnomalyLoadResult:
    """从 options_chain 读出末日 Put 候选,过滤 → 落库到 option_anomaly(BD-020/021/022)。

    Args:
        trade_date: 计算当日
        symbols: 限定标的;None 时取全 universe 标的
        thr: OQ-01 阈值 dataclass;None 用默认
    """
    thr = thr or AnomalyThresholds()
    result = AnomalyLoadResult()

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        # 1) 取标的范围
        if symbols is None:
            rs = await session.execute(select(Symbol.ticker, Symbol.type).where(Symbol.is_universe.is_(True)))
            symbol_type_map: dict[str, str] = {t: ty for t, ty in rs.all()}
        else:
            symbol_type_map = await _known_symbol_types(session, symbols)

        if not symbol_type_map:
            return result

        # 2) 取 spot
        spot_map = await _spot_by_symbol(session, symbol_type_map.keys(), trade_date)

        # 3) 对每个 symbol 读当日 Put 合约 + 前日 OI
        all_candidates: list[OptionCandidate] = []
        for sym in symbol_type_map:
            rows = await _read_today_puts(session, trade_date, sym)
            # 注入 trade_date 与 dte
            for r in rows:
                r["trade_date"] = trade_date
                r["dte"] = (r["expiry"] - trade_date).days
            result.attempted += len(rows)
            all_candidates.extend(_to_candidates(rows, symbol_type_map, spot_map))

        # 4) 过滤 DTE≤3(仅这一项是分桶必备)
        pre_dte = [c for c in all_candidates if c.dte <= thr.dte_max]
        result.candidates = len(pre_dte)

        # 5) 用 services 算异常合约(集中 OQ-01 阈值)
        hits = filter_top_anomaly_puts(pre_dte, thr=thr)
        result.hits = len(hits)

        if not hits:
            await session.commit()
            return result

        # 6) 取 OI 5 日序列
        oi_5d = await _read_oi_5d_series(session, [c.contract for c in hits], trade_date)

        # 7) 落库
        payload = _anomaly_payload(trade_date, hits, oi_5d)
        table = Symbol.__table__.metadata.tables["option_anomaly"]
        stmt = pg_insert(table).values(payload)
        stmt = stmt.on_conflict_do_nothing(index_elements=["trade_date", "contract"])
        rs = await session.execute(stmt)
        result.inserted = rs.rowcount or 0
        result.skipped = len(payload) - result.inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = result.attempted
        await session.rollback()
        log.error("compute_option_anomaly.fail", error=str(e), attempted=result.attempted)
    finally:
        if own_session:
            await session.close()

    log.info(
        "compute_option_anomaly.done",
        trade_date=str(trade_date),
        attempted=result.attempted,
        candidates=result.candidates,
        hits=result.hits,
        inserted=result.inserted,
        skipped=result.skipped,
    )
    return result


# ---- V1.5.9: PCR + Gamma 聚集计算 ----


@dataclass(slots=True)
class PCRGammaResult:
    """PCR + Gamma 聚集计算结果。"""

    symbol: str
    pcr_total_put: int = 0
    pcr_total_call: int = 0
    pcr: float = 0.0
    pcr_z_score: float | None = None
    pcr_extreme: bool = False
    otm_assassin_count: int = 0
    gamma_clusters: list[dict] | None = None
    signal_strength: str = "NORMAL"
    signal_modules: list[str] | None = None


async def compute_pcr_gamma(
    trade_date: date,
    *,
    symbols: list[str] | None = None,
    session: AsyncSession | None = None,
) -> list[PCRGammaResult]:
    """计算 PCR + Gamma 聚集 + OTM 刺客 + signal_strength。

    从 options_chain 读出当日全部合约,按 symbol 分别计算。
    结果可缓存至 Redis(TTL=40min)。
    """
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    results: list[PCRGammaResult] = []

    try:
        # 1) 取标的范围
        if symbols is None:
            rs = await session.execute(
                select(Symbol.ticker, Symbol.type).where(Symbol.is_universe.is_(True))
            )
            symbol_type_map: dict[str, str] = {t: ty for t, ty in rs.all()}
        else:
            symbol_type_map = await _known_symbol_types(session, symbols)

        if not symbol_type_map:
            return results

        # 2) 取 spot
        spot_map = await _spot_by_symbol(session, symbol_type_map.keys(), trade_date)

        # 3) 对每个 symbol 读当日全部合约(Put + Call)
        table = Symbol.__table__.metadata.tables["options_chain"]
        for sym in symbol_type_map:
            sym_type = symbol_type_map.get(sym, "stock")

            # 读全部合约
            sql = (
                select(
                    table.c.contract,
                    table.c.symbol,
                    table.c.expiry,
                    table.c.strike,
                    table.c.right,
                    table.c.last_price,
                    table.c.volume,
                    table.c.open_interest,
                    table.c.implied_vol,
                )
                .where(table.c.trade_date == trade_date)
                .where(table.c.symbol == sym)
            )
            rs = await session.execute(sql)
            all_rows = [dict(r._mapping) for r in rs.all()]

            if not all_rows:
                continue

            # PCR 计算
            put_vol = sum(int(r["volume"] or 0) for r in all_rows if r["right"] == "P")
            call_vol = sum(int(r["volume"] or 0) for r in all_rows if r["right"] == "C")
            pcr_result = compute_pcr(put_vol, call_vol)

            # 构建 candidates(用于 Gamma 和 OTM 刺客)
            candidates = []
            spot = spot_map.get(sym, 0.0)
            if spot > 0:
                for r in all_rows:
                    dte_val = (r["expiry"] - trade_date).days if r["expiry"] else 0
                    candidates.append(
                        OptionCandidate(
                            contract=r["contract"],
                            underlying=sym,
                            underlying_type=sym_type,
                            trade_date=trade_date,
                            expiry=r["expiry"],
                            dte=dte_val,
                            right=r["right"],
                            strike=float(r["strike"]),
                            last_price=float(r["last_price"] or 0.0),
                            spot=spot,
                            volume=int(r["volume"] or 0),
                            open_interest=int(r["open_interest"] or 0),
                            open_interest_prev=0,
                        )
                    )

            # OTM 刺客(动态基准)
            avg_30d = sum(c.volume for c in candidates) / max(len(candidates), 1)
            dyn_vol_min = compute_dynamic_vol_min(sym_type, avg_30d)
            assassins = [c for c in candidates if is_otm_assassin(c, dyn_vol_min)]

            # Gamma 聚集
            gamma = detect_gamma_cluster(candidates)
            active_clusters = [gc for gc in gamma if gc.is_cluster]

            # signal_strength
            signal = compute_signal_strength(
                pcr=pcr_result,
                anomaly_count=0,  # 由 compute_option_anomaly 提供,此处不重复
                otm_assassins=len(assassins),
                gamma_clusters=gamma,
            )

            results.append(
                PCRGammaResult(
                    symbol=sym,
                    pcr_total_put=put_vol,
                    pcr_total_call=call_vol,
                    pcr=pcr_result.pcr,
                    pcr_z_score=pcr_result.pcr_z_score,
                    pcr_extreme=pcr_result.is_extreme,
                    otm_assassin_count=len(assassins),
                    gamma_clusters=[
                        {
                            "strike": gc.strike,
                            "volume": gc.total_volume,
                            "ratio": gc.cluster_ratio,
                            "is_cluster": gc.is_cluster,
                        }
                        for gc in active_clusters
                    ],
                    signal_strength=signal.signal_strength.value,
                    signal_modules=signal.high_signal_modules,
                )
            )

        await session.commit()
    except SQLAlchemyError as e:
        log.error("compute_pcr_gamma.fail", error=str(e))
    finally:
        if own_session:
            await session.close()

    log.info(
        "compute_pcr_gamma.done",
        trade_date=str(trade_date),
        symbols_computed=len(results),
        high_signals=sum(1 for r in results if r.signal_strength == "HIGH"),
    )
    return results


# ---- V1.5.9: Redis 缓存预热 ----


async def warm_options_cache(
    trade_date: date,
    pcr_gamma_results: list[PCRGammaResult],
    *,
    ttl: int = 2400,
) -> int:
    """将 PCR + Gamma 计算结果主动推入 Redis(ETL 预热)。

    API 端点只读 Redis,不回查 DB,确保前端响应极致平滑。
    TTL = 40min(> 30min 轮询周期)。

    Returns:
        预热成功的 symbol 数量
    """
    import json

    from app.core.redis_client import redis_client

    warmed = 0
    for r in pcr_gamma_results:
        key = f"opt:{r.symbol}:{trade_date.isoformat()}"
        try:
            await redis_client.set(
                key,
                json.dumps(
                    {
                        "symbol": r.symbol,
                        "trade_date": trade_date.isoformat(),
                        "pcr": r.pcr,
                        "pcr_total_put": r.pcr_total_put,
                        "pcr_total_call": r.pcr_total_call,
                        "pcr_z_score": r.pcr_z_score,
                        "pcr_extreme": r.pcr_extreme,
                        "otm_assassin_count": r.otm_assassin_count,
                        "gamma_clusters": r.gamma_clusters,
                        "signal_strength": r.signal_strength,
                        "signal_modules": r.signal_modules,
                    },
                    default=str,
                ),
                ttl=ttl,
            )
            warmed += 1
        except Exception as e:  # noqa: BLE001
            log.warning("warm_options_cache.fail", symbol=r.symbol, error=str(e))
    return warmed


# ---- CLI ----


async def main_chain() -> None:
    """`uv run python -m etl.load_options_chain chain AAPL`"""
    import asyncio
    import sys

    from etl.yfinance_pull import fetch_options_chain

    if len(sys.argv) < 2:
        print("用法: python -m etl.load_options_chain chain <TICKER> [YYYY-MM-DD]")
        return
    sym = sys.argv[1].upper()
    target = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    rows = await fetch_options_chain(sym)
    res = await load_options_chain(rows, trade_date=target)
    print(
        f"[load_options_chain] {sym} {target} attempted={res.attempted} "
        f"inserted={res.inserted} skipped={res.skipped} failures={res.failures}"
    )


async def main_anomaly() -> None:
    """`uv run python -m etl.load_options_chain anomaly [YYYY-MM-DD]`"""
    import asyncio
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    res = await compute_option_anomaly(target)
    print(
        f"[compute_option_anomaly] {target} attempted={res.attempted} "
        f"candidates={res.candidates} hits={res.hits} inserted={res.inserted} "
        f"skipped={res.skipped} failures={res.failures}"
    )


if __name__ == "__main__":
    import asyncio
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "anomaly"
    if cmd == "chain":
        asyncio.run(main_chain())
    elif cmd == "anomaly":
        asyncio.run(main_anomaly())
    else:
        print("用法: python -m etl.load_options_chain {chain|anomaly} [...]")
