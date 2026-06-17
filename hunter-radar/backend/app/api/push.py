"""§6.2 Web Push 订阅端点(BD-074 m5t4)。

端点(全部 /api/v1 前缀):
- GET    /push/vapid-public-key   公开 VAPID 公钥(供前端订阅时用)
- POST   /push/subscriptions      新增/更新订阅(upsert by endpoint)
- GET    /push/subscriptions      列当前用户的 active 订阅
- DELETE /push/subscriptions/{id} 软删(is_active=False)

鉴权:BD-075 JWT(同其它端点);沙箱占位 UUID 也能调 list / delete 但
upsert 会强制以真 UUID 写入(sandbox 也不允许匿名加订阅)。
"""
from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    SANDBOX_PLACEHOLDER_USER_ID,
    TUser,
    get_current_user,
)
from app.core.database import get_session
from app.services import push_subscription as ps_svc

router = APIRouter()


# ---- DTO --------------------------------------------------------------------


class PushKeysDTO(BaseModel):
    p256dh: str = Field(..., min_length=1, max_length=512)
    auth: str = Field(..., min_length=1, max_length=64)


class PushSubscriptionCreateDTO(BaseModel):
    """标准 Web Push PushSubscription JSON 风格的子集。"""

    endpoint: str = Field(..., min_length=10, max_length=2048)
    keys: PushKeysDTO
    user_agent: str | None = Field(default=None, max_length=512)


class PushSubscriptionDTO(BaseModel):
    id: int
    endpoint_prefix: str
    user_agent: str | None
    is_active: bool
    created_at: str


class VAPIDPublicKeyDTO(BaseModel):
    vapid_public_key: str | None
    note: str


# ---- 端点 -------------------------------------------------------------------


@router.get(
    "/push/vapid-public-key",
    response_model=VAPIDPublicKeyDTO,
    summary="VAPID 公钥(供前端 PushManager.subscribe 用,无需鉴权)",
)
async def get_vapid_public_key() -> VAPIDPublicKeyDTO:
    pub = os.environ.get("HR_VAPID_PUBLIC_KEY")
    return VAPIDPublicKeyDTO(
        vapid_public_key=pub or None,
        note=(
            "m5t4 VAPID 占位:HR_VAPID_PUBLIC_KEY 未设时返 null,"
            "前端应回退到 in-app banner 而非 Web Push"
        ),
    )


@router.post(
    "/push/subscriptions",
    response_model=PushSubscriptionDTO,
    status_code=201,
    summary="新增/更新 Web Push 订阅(upsert by endpoint,BD-074 m5t4)",
)
async def upsert_push_subscription(
    payload: PushSubscriptionCreateDTO,
    user: TUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PushSubscriptionDTO:
    # 沙箱占位 UUID 拒绝 upsert(避免污染占位用户的订阅列表)
    if user.user_id == SANDBOX_PLACEHOLDER_USER_ID:
        raise HTTPException(
            status_code=401,
            detail="must be authenticated (BD-075 JWT) to subscribe to push",
        )
    sub_id = await ps_svc.upsert_subscription(
        session,
        user_id=user.user_id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=payload.user_agent,
    )
    if sub_id is None:
        raise HTTPException(
            status_code=503,
            detail="push_subscription.upsert failed(沙箱无 PG 或 schema 未初始化,设 HR_PG_OK=1 后重试)",
        )
    row = await ps_svc.get_subscription(session, sub_id, user.user_id)
    if row is None:
        raise HTTPException(
            status_code=500,
            detail="subscription vanished after upsert",
        )
    return PushSubscriptionDTO(**ps_svc.to_push_api_dict(row))


@router.get(
    "/push/subscriptions",
    response_model=list[PushSubscriptionDTO],
    summary="列当前用户的 active Web Push 订阅(BD-074 m5t4)",
)
async def list_push_subscriptions(
    user: TUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PushSubscriptionDTO]:
    rows = await ps_svc.list_subscriptions_by_user(session, user.user_id)
    if rows is None:
        raise HTTPException(
            status_code=503,
            detail="push_subscription.list failed(沙箱无 PG 或 schema 未初始化)",
        )
    return [PushSubscriptionDTO(**ps_svc.to_push_api_dict(r)) for r in rows]


@router.delete(
    "/push/subscriptions/{sub_id}",
    status_code=204,
    summary="软删 Web Push 订阅(is_active=False,BD-074 m5t4)",
)
async def delete_push_subscription(
    sub_id: int,
    user: TUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    ok = await ps_svc.soft_delete_subscription(session, sub_id, user.user_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"message": "subscription not found or not owned", "id": sub_id},
        )
