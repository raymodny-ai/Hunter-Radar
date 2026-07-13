"""§0 标的 CRUD + warmup 触发(V1.7.0 新增)。

设计意图:
- 新增标的(POST /symbols)→ 入库 + 后台自动 ETL 拉数,不再被动等 30 天
- 查询进度(GET /symbols/{t}/warmup)→ 前端 AMD Threat Score 卡 30 天的状态可读
- 强制重跑(POST /symbols/{t}/warmup)→ 调试用

数据流:
  客户端 POST /api/v1/symbols {ticker: "AMD"}
    → symbol_seed.upsert_symbol (入 symbol_master + 设 warmup_started_at)
    → symbol_warmup.schedule_warmup (后台 task 拉 yfinance + FINRA + 算 threat_score)
    → 前端立刻拿 200,可读 /warmup 查进度

依赖: etl.symbol_seed.upsert_symbol · app.services.symbol_warmup
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import Symbol
from app.services.symbol_warmup import (
    get_warmup_status,
    schedule_warmup,
)

router = APIRouter()


# ---- DTO ----
class SymbolCreateRequest(BaseModel):
    """新增标的请求体。"""

    ticker: str = Field(..., min_length=1, max_length=10, description="ticker code, 自动 upper")
    name: str | None = Field(default=None, max_length=200, description="可选显示名")
    type: Literal["stock", "etf", "index"] = Field(default="stock")
    exchange: str | None = Field(default=None, max_length=20)
    is_universe: bool = Field(default=False, description="是否纳入 screener 池")
    start_warmup: bool = Field(default=True, description="True 则入库即触发后台 ETL")


class SymbolCreateResponse(BaseModel):
    ticker: str
    name: str
    type: str
    exchange: str | None
    is_universe: bool
    warmup_started_at: date | None
    created: bool
    warmup: dict


# ---- 端点 ----
@router.post(
    "/symbols",
    response_model=SymbolCreateResponse,
    summary="§0.1 新增标的(V1.7.0 自动 warmup)",
)
async def create_symbol(
    body: SymbolCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> SymbolCreateResponse:
    """注册新标的,自动启动后台 ETL。

    - 标的已存在 → 不会重复创建,但若 `start_warmup=True` 且未启动过,会补设
      warmup_started_at 并再次触发 warmup
    - 标的全新 → 写入 symbol_master,设 warmup_started_at,触发后台 task
    - warmup 是 fire-and-forget;立刻返回 200,前端拿 ticker+状态轮询
    """
    from etl.symbol_seed import upsert_symbol

    try:
        sym, created = await upsert_symbol(
            body.ticker,
            name=body.name,
            sym_type=body.type,
            exchange=body.exchange,
            is_universe=body.is_universe,
            start_warmup=body.start_warmup,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    warmup_payload: dict = {}
    if body.start_warmup:
        warmup_payload = await schedule_warmup(sym.ticker)

    return SymbolCreateResponse(
        ticker=sym.ticker,
        name=sym.name,
        type=sym.type,
        exchange=sym.exchange,
        is_universe=bool(sym.is_universe),
        warmup_started_at=sym.warmup_started_at,
        created=created,
        warmup=warmup_payload,
    )


@router.get(
    "/symbols/{ticker}/warmup",
    summary="§0.2 查询标的 warmup 进度",
)
async def get_warmup(ticker: str) -> dict:
    """返回该标的最近一次 warmup 状态(Redis 读)。

    - 200 + status=never_run: 标的未触发过 warmup
    - 200 + status=running/done/partial/failed: 进度信息
    - 404: 标的根本不在 symbol_master
    """
    t = ticker.strip().upper()
    status = await get_warmup_status(t)
    return {
        "ticker": t,
        "warmup": status or {"status": "never_run", "message": "no warmup history"},
    }


@router.post(
    "/symbols/{ticker}/warmup",
    summary="§0.3 强制重跑 warmup(调试用)",
)
async def rerun_warmup(ticker: str, session: AsyncSession = Depends(get_session)) -> dict:
    """重新触发 warmup(不会清已存在数据,走 ON CONFLICT DO NOTHING)。

    - 404: 标的不在 symbol_master(请先 POST /symbols)
    - 200: 已加入调度队列 / 已在跑 / 完成
    """
    t = ticker.strip().upper()
    rs = await session.execute(select(Symbol).where(Symbol.ticker == t))
    sym = rs.scalar_one_or_none()
    if sym is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "symbol not found, call POST /symbols first", "ticker": t},
        )
    payload = await schedule_warmup(t)
    return {"ticker": t, "warmup": payload}


@router.get(
    "/symbols/{ticker}/warmup-state",
    summary="§0.4 查询 symbol_master 静态 warmup 字段(从 DB)",
)
async def get_warmup_state(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """从 symbol_master 直接读 warmup_started_at / metadata_json。"""
    t = ticker.strip().upper()
    rs = await session.execute(select(Symbol).where(Symbol.ticker == t))
    sym = rs.scalar_one_or_none()
    if sym is None:
        raise HTTPException(status_code=404, detail={"ticker": t, "message": "symbol not found"})
    return {
        "ticker": t,
        "warmup_started_at": sym.warmup_started_at.isoformat() if sym.warmup_started_at else None,
        "is_universe": bool(sym.is_universe),
        "metadata": dict(sym.metadata_json or {}),
    }
