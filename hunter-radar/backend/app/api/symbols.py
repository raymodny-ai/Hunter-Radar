"""§3 标的/报告端点(M0 阶段返回契约占位,M1 后逐步替换为真实实现)。"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.redis_client import cache_or_set_json
from app.models import Symbol

log = structlog.get_logger(__name__)

log = logging.getLogger(__name__)

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
    ats_data_quality: Literal["real", "proxy", "none"] = "none"


class DivergenceDTO(BaseModel):
    trade_date: date
    symbol: str
    p_price: float
    p_short: float
    state: Literal["none", "rising", "confirmed"]


@router.get(
    "/symbols/{ticker}/options-anomaly-v2",
    summary="§3.1 V1.5.9 Options 异动增强(PCR + Gamma + OTM 刺客,纯 Redis 读取)",
)
async def get_options_anomaly_v2(
    ticker: str,
) -> dict:
    """V1.5.9 Options 异动增强端点。

    纯 Redis 读取(ETL 预热推入,端点不做 DB 回查)。
    包含: PCR / Z-Score / OTM 刺客 / Gamma 聚集 / signal_strength。
    Cache miss 时返回空数据(不触发慢查询)。
    """
    import json
    from app.core.redis_client import redis_client

    t = ticker.upper()
    key = f"opt:{t}:{date.today().isoformat()}"
    try:
        raw = await redis_client.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception:
        pass
    # Cache miss → 返回空(不回查 DB)
    return {
        "symbol": t,
        "trade_date": date.today().isoformat(),
        "pcr": None,
        "pcr_z_score": None,
        "pcr_extreme": False,
        "otm_assassin_count": 0,
        "gamma_clusters": [],
        "signal_strength": "NORMAL",
        "signal_modules": [],
        "_cache": "miss",
    }


@router.get(
    "/symbols/{ticker}/short-iceberg-v2",
    summary="§3.2 V1.5.9 水位图增强(含 ATS fallback 数据)",
)
async def get_short_iceberg_v2(
    ticker: str,
    days: int = Query(default=20, ge=1, le=120),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """V1.5.9 水位图增强:合并主源 + ATS fallback 数据。"""
    from app.services.ats_fallback import get_ats_series

    t = ticker.upper()
    # 原有水位图数据
    original = await get_short_iceberg(t, days=days, session=session)
    # ATS fallback 系列
    ats_series = await get_ats_series(t, days=days, session=session)

    return {
        "symbol": t,
        "series": [s.model_dump(mode="json") for s in original],
        "ats_series": [
            {
                "trade_date": a.trade_date.isoformat(),
                "ats_short_volume": a.ats_short_volume,
                "source": a.source,
                "is_fallback": a.is_fallback,
            }
            for a in ats_series
        ],
    }


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
@router.get("/symbols/lookup", summary="搜索自动补全(原 BD-077)")
async def lookup_symbols(
    q: str = Query(..., min_length=1, max_length=10),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """输入「QQQ」返回 `{ticker, name, type, exchange}`。

    实现:
    - 优先从 symbol_master 查
    - 查不到则用 yfinance 轻量查询(ticker.info)
    - yfinance 也查询不到则当作一个未验证 ticker 返回, 后台 ETL 拉数时 upsert
    """
    t = q.upper().strip()

    # 1) 本地 symbol_master
    sym = (await session.execute(
        select(Symbol).where(Symbol.ticker == t)
    )).scalar_one_or_none()

    if sym is not None:
        return [
            {
                "ticker": sym.ticker,
                "name": sym.name or sym.ticker,
                "type": sym.type or "stock",
                "exchange": sym.exchange or "",
            }
        ]

    # 2) yfinance info 轻量补充
    try:
        import asyncio
        from etl.market_data_provider import _yfinance_info  # type: ignore
        info = await asyncio.to_thread(_yfinance_info, t)
        if info and (info.get("longName") or info.get("shortName") or info.get("symbol")):
            return [
                {
                    "ticker": t,
                    "name": info.get("longName") or info.get("shortName") or t,
                    "type": "etf" if info.get("quoteType") == "ETF" else "stock",
                    "exchange": info.get("exchange", ""),
                }
            ]
    except Exception as _yf_err:  # noqa: BLE001
        log.warning("lookup.yfinance.fail", ticker=t, error=str(_yf_err)[:200])

    # 3) 返个 unverified stub, 让前端允许输入, 后台 ETL 拉数时 upsert 到 symbol_master
    return [
        {
            "ticker": t,
            "name": f"{t} (unverified, 等待 ETL 拉数)",
            "type": "stock",
            "exchange": "",
        }
    ]


# ---- 按需初始化: 查不到数据时自动触发后台 ETL ----
async def _seed_ticker(sym: str, session) -> None:
    """V1.7.0 替换: 标的入库 + 后台 ETL 触发。

    不再塞随机假数据(原行为是占位 stub);改走 etl.symbol_seed.upsert_symbol +
    app.services.symbol_warmup.schedule_warmup。HTTP 响应立即返回,前端可轮询
    /symbols/{t}/warmup 看进度。
    """
    from etl.symbol_seed import upsert_symbol
    from app.services.symbol_warmup import schedule_warmup

    try:
        sym_obj, _created = await upsert_symbol(
            sym,
            name=sym,
            sym_type="stock",
            start_warmup=True,
            session=session,
        )
        await schedule_warmup(sym_obj.ticker)
    except Exception as e:  # noqa: BLE001
        log.warning("symbols._seed_ticker.fail", ticker=sym, error=str(e))


async def _compute_threat_score(ticker: str, session: AsyncSession) -> ThreatScoreDTO:
    """实际取数（M4 拆出，便于 cache_or_set_json 包装）。使用 raw SQL 避免 metadata.tables 列依赖。"""
    from sqlalchemy import text as _text

    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="invalid ticker")
    t = ticker.upper()

    # 取最新一日的 threat_score
    rs = await session.execute(
        _text("SELECT trade_date FROM threat_score_daily WHERE symbol = :sym ORDER BY trade_date DESC LIMIT 1"),
        {"sym": t},
    )
    row = rs.first()
    if row is None:
        # 按需初始化: 异步拉取 yfinance 并生成 35 天的模拟数据
        await _seed_ticker(t, session)
        # 重查
        rs = await session.execute(
            _text("SELECT trade_date FROM threat_score_daily WHERE symbol = :sym ORDER BY trade_date DESC LIMIT 1"),
            {"sym": t},
        )
        row = rs.first()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={"message": "no threat_score record", "ticker": t},
            )
    target_date = row[0]

    # 取详情
    rs2 = await session.execute(
        _text(
            """SELECT symbol, symbol_type, module_options, module_short,
                      module_divergence, module_insider, weights,
                      total, total_raw, ema_halflife, signal_lifecycle,
                      nl_summary, regime
               FROM threat_score_daily
               WHERE symbol = :sym AND trade_date = :td
               LIMIT 1"""
        ),
        {"sym": t, "td": target_date},
    )
    d = rs2.first()
    if d is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "no threat_score detail", "ticker": t},
        )

    # 冷启动检查
    warmup = False
    z_rs = await session.execute(
        _text("SELECT z_score_60d FROM short_ratio_daily WHERE symbol = :sym AND trade_date = :td LIMIT 1"),
        {"sym": t, "td": target_date},
    )
    z_row = z_rs.first()
    if z_row is None or z_row[0] is None:
        warmup = True

    def _g(idx): return d[idx]
    # SQL: symbol(0), symbol_type(1), module_options(2), module_short(3),
    #      module_divergence(4), module_insider(5), weights(6), total(7),
    #      total_raw(8), ema_halflife(9), signal_lifecycle(10), nl_summary(11), regime(12)
    return ThreatScoreDTO(
        trade_date=target_date,
        symbol=t,
        symbol_type=_g(1) or "stock",
        total=float(_g(7) or 0),
        total_raw=float(_g(8) or 0),
        ema_halflife=int(_g(9) or 2),
        module_options=float(_g(2) or 0),
        module_short=float(_g(3) or 0),
        module_divergence=float(_g(4) or 0),
        module_insider=float(_g(5) or 0),
        weights=dict(_g(6) or {}),
        signal_lifecycle=_g(10) or "init",
        regime=_g(12) or "normal",
        nl_summary=_g(11),
        data_warmup=False,
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
    # manual dump: Pydantic v2 model_dump with mode='json' for safe serialization
    if isinstance(result, ThreatScoreDTO):
        return result
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
    """读 short_ratio_daily(BD-030/031/032)。M1 末落库层未跑时,前端会拿到空数组。

    V1.7.6+: 动态计算 ats_data_quality — 检查 ats_short 表是否有真实数据。
    """
    t = ticker.upper()
    table = Symbol.__table__.metadata.tables["short_ratio_daily"]
    cutoff = date.today() - timedelta(days=int(days * 1.6) + 5)
    sql = (
        select(
            table.c.trade_date,
            table.c.short_ratio,
            table.c.ats_short_pct,
            table.c.z_score_60d,
        )
        .where(table.c.symbol == t)
        .where(table.c.trade_date >= cutoff)
        .order_by(table.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    rows = rs.all()
    if not rows:
        return []

    # V1.7.6+: 查 ats_short 表,判断哪些日期有真实 ATS 数据
    ats_dates: set[date] = set()
    try:
        ats_tbl = Symbol.__table__.metadata.tables["ats_short"]
        ats_sql = (
            select(ats_tbl.c.trade_date)
            .where(ats_tbl.c.symbol == t)
            .where(ats_tbl.c.trade_date >= cutoff)
            .distinct()
        )
        ats_rs = await session.execute(ats_sql)
        ats_dates = {row.trade_date for row in ats_rs.all()}
    except Exception:  # noqa: BLE001
        pass  # ats_short 表不存在时全部视为 proxy

    out: list[ShortIcebergDTO] = []
    for row in rows:
        z = row.z_score_60d
        # 动态判断 ats_data_quality
        if row.ats_short_pct is None:
            quality = "none"
        elif row.trade_date in ats_dates:
            quality = "real"
        else:
            quality = "proxy"
        out.append(
            ShortIcebergDTO(
                trade_date=row.trade_date,
                symbol=t,
                short_ratio=float(row.short_ratio or 0.0),
                ats_short_pct=float(row.ats_short_pct) if row.ats_short_pct is not None else None,
                z_score_60d=float(z) if z is not None else None,
                data_warmup=z is None,
                ats_data_quality=quality,
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
            "date": row.trade_date,
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
