"""§6.3 配额查询端点(FE-064 / BD-076 落地)。

GET /api/v1/auth/quota
  → 当前用户当日 quota 状态,前端 QuotaBanner / useApiQuota 数据源

不强制 402(仅查询,真实消费由调用方 try_consume)。
沙箱降级:无 PG/Redis 时仍可返 200 + 内存计数结果(便于前端调试 UI)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import TUser, get_current_user
from app.services.quota import get_quota_state

router = APIRouter()


@router.get("/auth/quota", summary="当前用户当日查询配额(FE-064)")
async def get_my_quota(
    user: TUser = Depends(get_current_user),
) -> dict:
    """返回当前 JWT/X-User-Id 对应用户的当日 quota 状态。

    字段与前端 QuotaDTO / QuotaState 保持一致,稳定不破坏。
    """
    state = get_quota_state(str(user.user_id), user.tier)
    return state.to_dict()
