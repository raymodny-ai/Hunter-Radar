"""§4 自定义分析 — 自选篮子 API(BD-070 / BD-071)。

端点(全部走 /api/v1 前缀):
- POST   /baskets                   创建
- GET    /baskets                   列表
- GET    /baskets/{id}              详情
- PUT    /baskets/{id}              改名/改描述
- DELETE /baskets/{id}              删除
- POST   /baskets/{id}/members      增成员
- DELETE /baskets/{id}/members/{t}  删成员
- GET    /baskets/{id}/members      列成员
- GET    /baskets/{id}/distribution 分布(BD-071,带落库)

M4 接力期 user_id 走 X-User-Id header(BD-075 替换为 JWT)。
"""
from __future__ import annotations

import os
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import SANDBOX_PLACEHOLDER_USER_ID, TUser, get_current_user
from app.services import basket as basket_svc

router = APIRouter()


# ---- DTO ----


class BasketCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class BasketDTO(BaseModel):
    id: int
    user_id: UUID
    name: str
    description: str | None
    member_count: int
    created_at: str
    updated_at: str


class BasketUpdateDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class BasketAddMembersDTO(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=200)


class BasketMemberDTO(BaseModel):
    ticker: str
    added_at: str


class BasketDistributionByTickerDTO(BaseModel):
    ticker: str
    latest: float | None
    mean: float
    max: float
    lifecycle: Literal["init", "red", "yellow", "gray", "green"]


class BasketDistributionDTO(BaseModel):
    basket_id: int
    trade_date: str  # ISO
    ticker_count: int
    day_count: int
    mean: float
    p25: float
    p50: float
    p75: float
    p90: float
    p99: float
    min_score: float
    max_score: float
    by_ticker: list[BasketDistributionByTickerDTO]


# ---- 内部辅助 ----


def _to_dto(s: basket_svc.BasketSummary) -> BasketDTO:
    return BasketDTO(
        id=s.id,
        user_id=s.user_id,
        name=s.name,
        description=s.description,
        member_count=s.member_count,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _to_distribution_dto(d: basket_svc.BasketDistribution) -> BasketDistributionDTO:
    return BasketDistributionDTO(
        basket_id=d.basket_id,
        trade_date=d.trade_date.isoformat(),
        ticker_count=d.ticker_count,
        day_count=d.day_count,
        mean=d.mean,
        p25=d.p25,
        p50=d.p50,
        p75=d.p75,
        p90=d.p90,
        p99=d.p99,
        min_score=d.min_score,
        max_score=d.max_score,
        by_ticker=[
            BasketDistributionByTickerDTO(
                ticker=x["ticker"],
                latest=x["latest"],
                mean=x["mean"],
                max=x["max"],
                lifecycle=x["lifecycle"],
            )
            for x in d.by_ticker
        ],
    )


# ---- 端点 ----


@router.post(
    "/baskets",
    response_model=BasketDTO,
    status_code=201,
    summary="创建自选篮子(BD-070)",
)
async def create_basket(
    payload: BasketCreateDTO,
    user: TUser = Depends(get_current_user),
) -> BasketDTO:
    bid = await basket_svc.create_basket(
        basket_svc.BasketCreatePayload(
            user_id=user.user_id,
            name=payload.name,
            description=payload.description,
        )
    )
    if bid is None:
        raise HTTPException(status_code=503, detail="basket.create failed")
    got = await basket_svc.get_basket(bid)
    if got is None:
        raise HTTPException(status_code=404, detail="basket not found after create")
    return _to_dto(got)


@router.get(
    "/baskets",
    response_model=list[BasketDTO],
    summary="列自选篮子(BD-070)",
)
async def list_baskets(
    user: TUser = Depends(get_current_user),
) -> list[BasketDTO]:
    use_filter = user.is_authenticated
    summaries = await basket_svc.list_baskets(user_id=user.user_id if use_filter else None)
    return [_to_dto(s) for s in summaries]


@router.get(
    "/baskets/{basket_id}",
    response_model=BasketDTO,
    summary="篮子详情(BD-070)",
)
async def get_basket(basket_id: int) -> BasketDTO:
    got = await basket_svc.get_basket(basket_id)
    if got is None:
        raise HTTPException(status_code=404, detail={"message": "basket not found", "id": basket_id})
    return _to_dto(got)


@router.put(
    "/baskets/{basket_id}",
    response_model=BasketDTO,
    summary="改名/改描述(BD-070)",
)
async def update_basket(basket_id: int, payload: BasketUpdateDTO) -> BasketDTO:
    ok = await basket_svc.update_basket(
        basket_id,
        name=payload.name,
        description=payload.description,
    )
    if not ok:
        raise HTTPException(status_code=404, detail={"message": "basket not found", "id": basket_id})
    got = await basket_svc.get_basket(basket_id)
    if got is None:
        raise HTTPException(status_code=404, detail="basket not found after update")
    return _to_dto(got)


@router.delete(
    "/baskets/{basket_id}",
    status_code=204,
    summary="删除篮子(级联删成员+快照,BD-070)",
)
async def delete_basket(basket_id: int) -> None:
    ok = await basket_svc.delete_basket(basket_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"message": "basket not found", "id": basket_id})


@router.post(
    "/baskets/{basket_id}/members",
    response_model=dict,
    summary="增篮子成员(BD-070)",
)
async def add_members(basket_id: int, payload: BasketAddMembersDTO) -> dict:
    inserted = await basket_svc.add_members(basket_id, payload.tickers)
    return {"basket_id": basket_id, "inserted": inserted, "submitted": len(payload.tickers)}


@router.delete(
    "/baskets/{basket_id}/members/{ticker}",
    status_code=204,
    summary="删篮子成员(BD-070)",
)
async def remove_member(basket_id: int, ticker: str) -> None:
    ok = await basket_svc.remove_member(basket_id, ticker)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"message": "member not found", "basket_id": basket_id, "ticker": ticker.upper()},
        )


@router.get(
    "/baskets/{basket_id}/members",
    response_model=list[BasketMemberDTO],
    summary="列篮子成员(BD-070)",
)
async def list_members(basket_id: int) -> list[BasketMemberDTO]:
    rows = await basket_svc.list_members(basket_id)
    return [BasketMemberDTO(ticker=r["ticker"], added_at=r["added_at"]) for r in rows]


@router.get(
    "/baskets/{basket_id}/distribution",
    response_model=BasketDistributionDTO,
    summary="篮子分布(BD-071,带落库 basket_snapshot)",
)
async def get_basket_distribution(
    basket_id: int,
    days: int = 30,
) -> BasketDistributionDTO:
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be 1..365")
    dist = await basket_svc.compute_basket_distribution(basket_id, days=days)
    if dist is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "no distribution(空篮子或无数据)", "basket_id": basket_id},
        )
    return _to_distribution_dto(dist)
