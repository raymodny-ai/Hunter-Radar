"""§3.7 市场环境切换时间轴端点（V1.6.0 Regime Timeline）。

GET /regime/timeline?days=365
- 读 daily_price 表 ^VIX + ^GSPC 近 N 天
- 用 decide_regime() 计算每日 regime
- 返回 [{date, regime, vix, spx_close, spx_ma20, is_transition}]
- is_transition=True 当 regime 从 normal→panic 或 panic→normal
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.regime_history import RegimeConfig, MarketSnapshot, decide_regime

router = APIRouter()


class RegimeTimelinePoint(BaseModel):
    """时间轴上单日的 regime 数据点。"""

    trade_date: date
    regime: str  # 'normal' | 'panic'
    vix: float | None
    spx_close: float | None
    spx_ma20: float | None
    is_transition: bool = False  # regime 切换点


class RegimeTimelineDTO(BaseModel):
    """完整时间轴响应。"""

    days: int
    points: list[RegimeTimelinePoint]
    transitions: int  # 总切换次数
    current_regime: str


@router.get(
    "/regime/timeline",
    response_model=RegimeTimelineDTO,
    summary="§3.7 市场环境切换时间轴(V1.6.0)",
)
async def get_regime_timeline(
    days: int = Query(default=365, ge=30, le=730, description="回溯天数"),
    session: AsyncSession = Depends(get_session),
) -> RegimeTimelineDTO:
    """可视化过去 N 天的 Normal↔Panic 切换点。

    读取 daily_price 表的 ^VIX + ^GSPC,逐日计算 regime。
    """
    cfg = RegimeConfig()
    cutoff = date.today() - timedelta(days=int(days * 1.6))  # 预留周末/节假日

    # 批量读 ^VIX
    vix_sql = """
        SELECT trade_date, close FROM daily_price
        WHERE symbol = '^VIX' AND trade_date >= :cutoff
        ORDER BY trade_date ASC
    """
    vix_rs = await session.execute(_text(vix_sql), {"cutoff": cutoff})
    vix_map: dict[date, float] = {}
    for row in vix_rs.all():
        if row[1] is not None:
            vix_map[row[0]] = float(row[1])

    # 批量读 ^GSPC
    spx_sql = """
        SELECT trade_date, close FROM daily_price
        WHERE symbol = '^GSPC' AND trade_date >= :cutoff
        ORDER BY trade_date ASC
    """
    spx_rs = await session.execute(_text(spx_sql), {"cutoff": cutoff})
    spx_rows: list[tuple[date, float]] = []
    for row in spx_rs.all():
        if row[1] is not None:
            spx_rows.append((row[0], float(row[1])))

    # 构建 SPX 的 MA20 滚动窗口
    spx_map: dict[date, float] = {d: c for d, c in spx_rows}
    spx_dates = sorted(spx_map.keys())
    ma20_map: dict[date, float] = {}
    for i, d in enumerate(spx_dates):
        window_start = max(0, i - cfg.spx_ma20_window + 1)
        window_vals = [spx_map[spx_dates[j]] for j in range(window_start, i + 1)]
        if window_vals:
            ma20_map[d] = sum(window_vals) / len(window_vals)

    # 收集所有有数据的日期(取 VIX 和 SPX 的并集)
    all_dates = sorted(set(vix_map.keys()) | set(spx_map.keys()))

    # 逐日计算 regime
    points: list[RegimeTimelinePoint] = []
    prev_regime: str | None = None
    transitions = 0

    for d in all_dates:
        vix = vix_map.get(d)
        spx_close = spx_map.get(d)
        spx_ma20 = ma20_map.get(d)

        snap = MarketSnapshot(
            trade_date=d,
            vix=vix,
            spx_close=spx_close,
            spx_ma20=spx_ma20,
        )
        regime, _ = decide_regime(snap, cfg=cfg)

        is_transition = False
        if prev_regime is not None and regime != prev_regime:
            is_transition = True
            transitions += 1

        points.append(
            RegimeTimelinePoint(
                trade_date=d,
                regime=regime,
                vix=vix,
                spx_close=spx_close,
                spx_ma20=spx_ma20,
                is_transition=is_transition,
            )
        )
        prev_regime = regime

    # 只保留最近 N 天
    if len(points) > days:
        points = points[-days:]

    current_regime = points[-1].regime if points else "normal"

    return RegimeTimelineDTO(
        days=days,
        points=points,
        transitions=transitions,
        current_regime=current_regime,
    )
