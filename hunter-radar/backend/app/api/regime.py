"""市场状态门控(BD-063)。"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.regime import compute_regime

router = APIRouter()


class RegimeDTO(BaseModel):
    trade_date: date
    regime: str
    vix: float | None
    spx_close: float | None
    spx_ma20: float | None
    threshold_red: int
    banner_text: str


@router.get("/regime", response_model=RegimeDTO, summary="市场状态门控(BD-063)")
async def get_regime(
    trade_date: date | None = Query(
        default=None, description="指定交易日;None 时取今日"
    )
) -> RegimeDTO:
    """VIX > 30 或 SPX < MA20 → panic,红灯阈值上调到 80。"""
    target = trade_date or date.today()
    snap = await compute_regime(target)
    return RegimeDTO(
        trade_date=snap.trade_date,
        regime=snap.regime,
        vix=snap.vix,
        spx_close=snap.spx_close,
        spx_ma20=snap.spx_ma20,
        threshold_red=snap.threshold_red,
        banner_text=snap.banner_text,
    )
