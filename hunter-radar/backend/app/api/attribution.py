"""§3.6 信号归因分析端点（V1.6.0 Attribution）。

GET /symbols/{ticker}/attribution
- 读 threat_score_daily 当日数据
- 调用 compute_attribution() 计算各模块加权贡献
- 返回瀑布图数据(前端可视化用)
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.attribution import compute_attribution

router = APIRouter()


@router.get(
    "/symbols/{ticker}/attribution",
    summary="§3.6 信号归因分析(V1.6.0 瀑布图数据)",
)
async def get_attribution(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """返回 Threat Score 的归因分析(各模块 weight × score 贡献)。

    用途:前端 Symbol Detail 展示"为什么是红灯"的瀑布图。
    """
    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="invalid ticker")
    t = ticker.upper()

    # 找最新一日的 threat_score
    rs = await session.execute(
        _text(
            "SELECT trade_date FROM threat_score_daily WHERE symbol = :sym ORDER BY trade_date DESC LIMIT 1"
        ),
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
                      total, total_raw
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

    # 解析 weights(可能是 JSON 字符串或 dict)
    weights_raw = d[6] or {}
    if isinstance(weights_raw, str):
        import json
        try:
            weights = json.loads(weights_raw)
        except Exception:
            weights = {"options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15}
    else:
        weights = dict(weights_raw)

    # 计算归因
    result = compute_attribution(
        trade_date=target_date,
        symbol=t,
        symbol_type=d[1] or "stock",
        module_options=float(d[2] or 0),
        module_short=float(d[3] or 0),
        module_divergence=float(d[4] or 0),
        module_insider=float(d[5] or 0),
        weights=weights,
        total_score=float(d[7] or 0),
        total_raw=float(d[8] or 0),
    )

    return result.to_dict()
