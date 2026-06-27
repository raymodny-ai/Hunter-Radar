"""§4.3 Screener 端点（BD-072,BD-080 缓存）。

M2 启动：从 `threat_score_daily` 当日读 Top N 危险标的。
- 字段映射：ranking / symbol / score / lifecycle / 模块活跃度
- 支持 stock / etf 类型过滤
- 真实 daily_screener 落库留待 M3 末（由 pipeline 统一调度）
- M4 接力期：12h Redis TTL（BD-080）；沙箱/Redis 不可达 → 走原函数降级
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.redis_client import cache_or_set_json
from app.models import Symbol

router = APIRouter()


class ScreenerRowDTO(BaseModel):
    rank: int
    symbol: str
    name: str
    symbol_type: str
    threat_score: float
    signal_lifecycle: str
    modules_active: list[str]
    nl_summary: str | None


class ScreenerDTO(BaseModel):
    trade_date: date
    rows: list[ScreenerRowDTO]
    total_scanned: int


def _pick_active_modules(modules: dict[str, float], threshold: float = 60.0) -> list[str]:
    """模块子评分 >= threshold 视为活跃（M3 终极警报判定一致）。"""
    return [name for name, score in modules.items() if score is not None and score >= threshold]


async def _compute_screener(
    top: int,
    symbol_type: str | None,
    trade_date: date | None,
    session: AsyncSession,
) -> ScreenerDTO:
    """实际取数（M4 拆出，便于 cache_or_set_json 包装）。

    V1.6.0: 当 trade_date 为最新且 top ≤ 100 时,从物化视图读取。
    """
    threat = Symbol.__table__.metadata.tables["threat_score_daily"]

    # 1) 找 trade_date（指定或最新）
    target_date: date | None = trade_date
    if target_date is None:
        rs_max = await session.execute(
            select(threat.c.trade_date).order_by(threat.c.trade_date.desc()).limit(1)
        )
        row_max = rs_max.first()
        if row_max is None:
            return ScreenerDTO(trade_date=date.today(), rows=[], total_scanned=0)
        target_date = row_max[0]

    # V1.6.0: 尝试从物化视图读取(最新日期 + top ≤ 100)
    use_mv = trade_date is None and top <= 100
    if use_mv:
        try:
            from sqlalchemy import text as _t

            mv_sql = """
                SELECT symbol, name, symbol_type, threat_score,
                       signal_lifecycle, module_options, module_short,
                       module_divergence, module_insider, nl_summary
                FROM mv_screener_top100
                WHERE 1=1
            """
            params: dict = {}
            if symbol_type is not None:
                mv_sql += " AND symbol_type = :st"
                params["st"] = symbol_type
            mv_sql += " ORDER BY threat_score DESC LIMIT :top"
            params["top"] = top

            rs = await session.execute(_t(mv_sql), params)
            raw_rows = rs.all()

            # 计数
            count_sql = "SELECT COUNT(*) FROM mv_screener_top100"
            if symbol_type is not None:
                count_sql += " WHERE symbol_type = :st"
            count_rs = await session.execute(_t(count_sql), params)
            total_scanned = count_rs.scalar() or 0

            rows: list[ScreenerRowDTO] = []
            for i, row in enumerate(raw_rows, start=1):
                modules = {
                    "options": float(row.module_options or 0),
                    "short": float(row.module_short or 0),
                    "divergence": float(row.module_divergence or 0),
                    "insider": float(row.module_insider or 0),
                }
                rows.append(
                    ScreenerRowDTO(
                        rank=i,
                        symbol=row.symbol,
                        name=row.name or row.symbol,
                        symbol_type=row.symbol_type,
                        threat_score=float(row.threat_score or 0),
                        signal_lifecycle=row.signal_lifecycle or "init",
                        modules_active=_pick_active_modules(modules),
                        nl_summary=row.nl_summary,
                    )
                )

            return ScreenerDTO(
                trade_date=target_date,
                rows=rows,
                total_scanned=total_scanned,
            )
        except Exception:  # noqa: BLE001
            # 物化视图不存在或查询失败 → 降级到原查询
            pass

    # 2) 联 symbol_master 取 name(原查询路径)
    sym = Symbol.__table__
    sql = (
        select(
            threat.c.symbol,
            sym.c.name,
            threat.c.symbol_type,
            threat.c.total,
            threat.c.signal_lifecycle,
            threat.c.module_options,
            threat.c.module_short,
            threat.c.module_divergence,
            threat.c.module_insider,
            threat.c.nl_summary,
        )
        .join(sym, sym.c.ticker == threat.c.symbol)
        .where(threat.c.trade_date == target_date)
        .order_by(threat.c.total.desc())
        .limit(top)
    )
    if symbol_type is not None:
        sql = sql.where(threat.c.symbol_type == symbol_type)

    rs = await session.execute(sql)
    raw_rows = rs.all()

    # 3) 计数（总扫描 = 当日 type 过滤下的行数）
    count_sql = select(threat.c.symbol).where(threat.c.trade_date == target_date)
    if symbol_type is not None:
        count_sql = count_sql.where(threat.c.symbol_type == symbol_type)
    count_rs = await session.execute(count_sql)
    total_scanned = len(count_rs.all())

    rows = []
    for i, row in enumerate(raw_rows, start=1):
        modules = {
            "options": float(row.module_options or 0),
            "short": float(row.module_short or 0),
            "divergence": float(row.module_divergence or 0),
            "insider": float(row.module_insider or 0),
        }
        rows.append(
            ScreenerRowDTO(
                rank=i,
                symbol=row.symbol,
                name=row.name or row.symbol,
                symbol_type=row.symbol_type,
                threat_score=float(row.total or 0),
                signal_lifecycle=row.signal_lifecycle or "init",
                modules_active=_pick_active_modules(modules),
                nl_summary=row.nl_summary,
            )
        )

    return ScreenerDTO(
        trade_date=target_date,
        rows=rows,
        total_scanned=total_scanned,
    )


@router.get("/screener", response_model=ScreenerDTO, summary="每日猎物榜单（BD-072,BD-080 12h 缓存）")
async def get_screener(
    top: int = Query(default=20, ge=1, le=100),
    symbol_type: str | None = Query(default=None, pattern="^(stock|etf)$"),
    trade_date: date | None = Query(default=None, description="指定交易日；None 时取最新一日"),
    session: AsyncSession = Depends(get_session),
) -> ScreenerDTO:
    """返回 Top N 危险标的。

    数据源：threat_score_daily（由 etl/load_threat_score 落库）。
    M4 接力期：12h Redis TTL 缓存（key 含 top + symbol_type + trade_date）。
    """
    cache_key = (
        f"cache:get_screener:{top}:{symbol_type or ''}:{trade_date.isoformat() if trade_date else ''}"
    )
    result, _hit = await cache_or_set_json(
        cache_key,
        settings.cache_ttl_report_seconds,
        lambda: _compute_screener(top, symbol_type, trade_date, session),
    )
    return result
