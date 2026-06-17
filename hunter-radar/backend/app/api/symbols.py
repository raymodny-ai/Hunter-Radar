"""§3 标的/报告端点(M0 阶段返回契约占位,M1 后逐步替换为真实实现)。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.redis_client import cache_or_set_json
from app.models import Symbol

router = APIRouter()


# ---- 共用 DTO(M0 阶段先把契约立住,后续 M1/M2 替换 service) ----
class ThreatScoreDTO(BaseModel):
    trade_date: date
    symbol: str
    symbol_type: Literal["stock", "etf"]
    total: float = Field(..., ge=0, le=100)
    total_raw: float
    ema_halflife: int
    module_options: float
    module_short: float
    module_divergence: float
    module_insider: float
    weights: dict[str, float]
    signal_lifecycle: Literal["init", "red", "yellow", "gray", "green"]
    regime: Literal["normal", "panic"]
    nl_summary: str | None
    data_warmup: bool = False


class OptionsAnomalyDTO(BaseModel):
    trade_date: date
    contract: str
    dte: int
    oi_increase_pct: float
    volume_oi_ratio: float
    notional: float
    is_top10_notional: bool
    oi_5d_series: list[float] = []
    has_known_catalyst: bool
    catalyst_note: str | None = None


class ShortIcebergDTO(BaseModel):
    trade_date: date
    symbol: str
    short_ratio: float
    ats_short_pct: float | None
    z_score_60d: float | None
    data_warmup: bool = False


class DivergenceDTO(BaseModel):
    trade_date: date
    symbol: str
    p_price: float
    p_short: float
    state: Literal["none", "rising", "confirmed"]


class UltimateAlertDTO(BaseModel):
    """终极警报 DTO(BD-064 / FE-031)。

    严格规则:
    - triggered_at 必含(UTC ISO8601);前端用其与 dismissedAlertId 去重
    - 1 弹 1 次语义:后端以 (trade_date, symbol) UNIQUE 防重(走 ultimate_alert 表)
    - modules_active 是字符串列表(连续 ≥ 2 日高分的模块名)
    """

    triggered_at: str
    trade_date: date
    symbol: str
    threat_score: float
    raw_score: float
    ema_score: float
    modules_active: list[str]
    regime: Literal["normal", "panic"]
    consecutive_days: int


# ---- 端点 ----
@router.get("/symbols/lookup", summary="搜索自动补全(BD-077)")
async def lookup_symbols(q: str = Query(..., min_length=1, max_length=10)) -> list[dict]:
    """输入「QQQ」返回 `{ticker, name, type, exchange}`。"""
    # TODO(BD-077):对接 symbol_master 的 pg_trgm 索引
    return [
        {"ticker": q.upper(), "name": "(待 BD-077 实现)", "type": "stock", "exchange": "NASDAQ"}
    ]


async def _compute_threat_score(ticker: str, session: AsyncSession) -> ThreatScoreDTO:
    """实际取数（M4 拆出，便于 cache_or_set_json 包装）。"""
    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="invalid ticker")
    t = ticker.upper()

    threat = Symbol.__table__.metadata.tables["threat_score_daily"]
    sym = Symbol.__table__
    # 取最新一日的 threat_score
    latest_sql = (
        select(threat.c.trade_date)
        .where(threat.c.symbol == t)
        .order_by(threat.c.trade_date.desc())
        .limit(1)
    )
    rs = await session.execute(latest_sql)
    row = rs.first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "no threat_score record", "ticker": t},
        )
    target_date = row[0]

    detail_sql = (
        select(
            threat.c.symbol,
            threat.c.symbol_type,
            threat.c.module_options,
            threat.c.module_short,
            threat.c.module_divergence,
            threat.c.module_insider,
            threat.c.weights,
            threat.c.total,
            threat.c.total_raw,
            threat.c.ema_halflife,
            threat.c.signal_lifecycle,
            threat.c.nl_summary,
            threat.c.regime,
        )
        .where(threat.c.symbol == t)
        .where(threat.c.trade_date == target_date)
    )
    rs2 = await session.execute(detail_sql)
    d = rs2.first()
    if d is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "no threat_score record", "ticker": t},
        )

    # 冷启动（Z-Score 缺失 或 EMA 历史不足 30）→ data_warmup=True
    warmup = False
    short_z_sql = (
        select(Symbol.__table__.metadata.tables["short_ratio_daily"].c.z_score_60d)
        .where(
            Symbol.__table__.metadata.tables["short_ratio_daily"].c.symbol == t,
            Symbol.__table__.metadata.tables["short_ratio_daily"].c.trade_date == target_date,
        )
        .limit(1)
    )
    z_rs = await session.execute(short_z_sql)
    z_row = z_rs.first()
    if z_row is None or z_row[0] is None:
        warmup = True

    return ThreatScoreDTO(
        trade_date=target_date,
        symbol=t,
        symbol_type=d.symbol_type or "stock",
        total=float(d.total or 0),
        total_raw=float(d.total_raw or 0),
        ema_halflife=int(d.ema_halflife or 2),
        module_options=float(d.module_options or 0),
        module_short=float(d.module_short or 0),
        module_divergence=float(d.module_divergence or 0),
        module_insider=float(d.module_insider or 0),
        weights=dict(d.weights or {}),
        signal_lifecycle=d.signal_lifecycle or "init",
        regime=(d.regime or "normal"),
        nl_summary=d.nl_summary,
        data_warmup=warmup,
    )


@router.get(
    "/symbols/{ticker}/threat",
    response_model=ThreatScoreDTO,
    summary="最新 Threat Score（BD-080 12h 缓存）",
)
async def get_threat_score(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> ThreatScoreDTO:
    """返回最新一日的 Threat Score（从 threat_score_daily 表读）。

    M4 接力期：12h Redis TTL 缓存（key 含 ticker）。
    """
    cache_key = f"cache:get_threat_score:{ticker.upper()}"
    result, _hit = await cache_or_set_json(
        cache_key,
        settings.cache_ttl_report_seconds,
        lambda: _compute_threat_score(ticker, session),
    )
    return result


@router.get(
    "/symbols/{ticker}/options-anomaly",
    response_model=list[OptionsAnomalyDTO],
    summary="§3.1 末日 Put 异常合约列表(BD-020)",
)
async def get_options_anomaly(
    ticker: str,
    days: int = Query(default=1, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
) -> list[OptionsAnomalyDTO]:
    """读 option_anomaly 表。M1 末已接 ETL(etl/load_options_chain.compute_option_anomaly)。"""
    from app.models import Symbol  # noqa: F401  触发 metadata
    table = Symbol.__table__.metadata.tables["option_anomaly"]
    cutoff = date.today() - timedelta(days=days + 1)
    sql = (
        select(
            table.c.trade_date,
            table.c.contract,
            table.c.dte,
            table.c.oi_increase_pct,
            table.c.volume_oi_ratio,
            table.c.notional,
            table.c.is_top10_notional,
            table.c.oi_5d_series,
            table.c.has_known_catalyst,
            table.c.catalyst_note,
        )
        .where(table.c.symbol == ticker.upper())
        .where(table.c.trade_date >= cutoff)
        .order_by(table.c.trade_date.desc(), table.c.notional.desc())
    )
    rs = await session.execute(sql)
    return [
        OptionsAnomalyDTO(
            trade_date=row.trade_date,
            contract=row.contract,
            dte=int(row.dte),
            oi_increase_pct=float(row.oi_increase_pct or 0.0),
            volume_oi_ratio=float(row.volume_oi_ratio or 0.0),
            notional=float(row.notional or 0.0),
            is_top10_notional=bool(row.is_top10_notional),
            oi_5d_series=list(row.oi_5d_series or []),
            has_known_catalyst=bool(row.has_known_catalyst),
            catalyst_note=row.catalyst_note,
        )
        for row in rs.all()
    ]


@router.get(
    "/symbols/{ticker}/short-iceberg",
    response_model=list[ShortIcebergDTO],
    summary="§3.2 水位图(BD-033)",
)
async def get_short_iceberg(
    ticker: str,
    days: int = Query(default=20, ge=1, le=120),
    session: AsyncSession = Depends(get_session),
) -> list[ShortIcebergDTO]:
    """读 short_ratio_daily(BD-030/031/032)。M1 末落库层未跑时,前端会拿到空数组。"""
    table = Symbol.__table__.metadata.tables["short_ratio_daily"]
    cutoff = date.today() - timedelta(days=int(days * 1.6) + 5)
    sql = (
        select(
            table.c.trade_date,
            table.c.short_ratio,
            table.c.ats_short_pct,
            table.c.z_score_60d,
        )
        .where(table.c.symbol == ticker.upper())
        .where(table.c.trade_date >= cutoff)
        .order_by(table.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    out: list[ShortIcebergDTO] = []
    for row in rs.all():
        z = row.z_score_60d
        out.append(
            ShortIcebergDTO(
                trade_date=row.trade_date,
                symbol=ticker.upper(),
                short_ratio=float(row.short_ratio or 0.0),
                ats_short_pct=float(row.ats_short_pct) if row.ats_short_pct is not None else None,
                z_score_60d=float(z) if z is not None else None,
                data_warmup=z is None,
            )
        )
    return out


@router.get(
    "/symbols/{ticker}/divergence",
    response_model=list[DivergenceDTO],
    summary="§3.3 量价背离(BD-042)",
)
async def get_divergence(
    ticker: str,
    days: int = Query(default=30, ge=1, le=180),
    session: AsyncSession = Depends(get_session),
) -> list[DivergenceDTO]:
    """读 divergence_window 表(BD-040/041/042 落库产物)。"""
    t = ticker.upper()
    tbl = Symbol.__table__.metadata.tables["divergence_window"]
    cutoff = date.today() - timedelta(days=int(days * 1.6) + 5)
    sql = (
        select(
            tbl.c.trade_date,
            tbl.c.p_price,
            tbl.c.p_short,
            tbl.c.divergence_state,
        )
        .where(tbl.c.symbol == t)
        .where(tbl.c.trade_date >= cutoff)
        .order_by(tbl.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    return [
        DivergenceDTO(
            trade_date=row.trade_date,
            symbol=t,
            p_price=float(row.p_price or 0.5),
            p_short=float(row.p_short or 0.5),
            state=row.divergence_state or "none",
        )
        for row in rs.all()
    ]


async def _compute_threat_history(
    ticker: str, days: int, session: AsyncSession
) -> list[dict]:
    """实际取数（M4 拆出，便于 cache_or_set_json 包装）。"""
    t = ticker.upper()
    tbl = Symbol.__table__.metadata.tables["threat_score_daily"]
    cutoff = date.today() - timedelta(days=int(days * 1.6) + 5)
    sql = (
        select(
            tbl.c.trade_date,
            tbl.c.total,
            tbl.c.total_raw,
            tbl.c.signal_lifecycle,
        )
        .where(tbl.c.symbol == t)
        .where(tbl.c.trade_date >= cutoff)
        .order_by(tbl.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    return [
        {
            "trade_date": row.trade_date,
            "total": float(row.total or 0),
            "total_raw": float(row.total_raw or 0),
            "signal_lifecycle": row.signal_lifecycle or "init",
        }
        for row in rs.all()
    ]


@router.get(
    "/symbols/{ticker}/threat-history",
    summary="§3.5 90 日 Threat Score 轨迹（BD-066,BD-080 12h 缓存）",
)
async def get_threat_history(
    ticker: str,
    days: int = Query(default=90, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """读 threat_score_daily 近 N 日，输出 90 日轨迹（BD-066）。

    M4 接力期：12h Redis TTL 缓存（key 含 ticker + days）。
    """
    cache_key = f"cache:get_threat_history:{ticker.upper()}:{days}"
    result, _hit = await cache_or_set_json(
        cache_key,
        settings.cache_ttl_report_seconds,
        lambda: _compute_threat_history(ticker, days, session),
    )
    return result


@router.get(
    "/symbols/{ticker}/ultimate-alert",
    response_model=UltimateAlertDTO,
    summary="§3.5 该 ticker 最近一条终极警报(BD-064 / FE-031)",
    responses={404: {"description": "该 ticker 当日无活跃终极警报"}},
)
async def get_ultimate_alert(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> UltimateAlertDTO:
    """读 ultimate_alert 表,返回该 ticker 最近一条触发的终极警报。

    - 404:无警报(前端 useUltimateAlert 视为 null,不报错)
    - 5xx:数据库/服务故障(透传)
    """
    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="invalid ticker")
    t = ticker.upper()
    tbl = Symbol.__table__.metadata.tables["ultimate_alert"]
    sql = (
        select(
            tbl.c.triggered_at,
            tbl.c.trade_date,
            tbl.c.symbol,
            tbl.c.threat_score,
            tbl.c.raw_score,
            tbl.c.ema_score,
            tbl.c.modules_active,
            tbl.c.regime,
            tbl.c.consecutive_days,
        )
        .where(tbl.c.symbol == t)
        .order_by(tbl.c.triggered_at.desc())
        .limit(1)
    )
    rs = await session.execute(sql)
    row = rs.first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "no ultimate alert for this symbol", "ticker": t},
        )
    d = row._mapping
    return UltimateAlertDTO(
        triggered_at=d["triggered_at"].isoformat()
        if hasattr(d["triggered_at"], "isoformat")
        else str(d["triggered_at"]),
        trade_date=d["trade_date"],
        symbol=d["symbol"],
        threat_score=float(d["threat_score"] or 0),
        raw_score=float(d["raw_score"] or 0),
        ema_score=float(d["ema_score"] or 0),
        modules_active=list(d["modules_active"] or []),
        regime=(d["regime"] or "normal"),
        consecutive_days=int(d["consecutive_days"] or 0),
    )
