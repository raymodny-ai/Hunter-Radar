"""§6.3 配额端点 — V1.6.1 Redis 计数器强制执行。

free tier: 每日 settings.free_tier_daily_quota 次
pro tier: 每日 settings.pro_tier_daily_quota 次( 사실상 无限)
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import TUser, get_current_user
from app.core.config import settings

log = logging.getLogger(__name__)

router = APIRouter()


def _get_redis():
    """Lazy import Redis client(沙箱环境无 Redis 时降级为内存计数)。"""
    try:
        from app.core.redis import get_redis_client
        return get_redis_client()
    except Exception:  # noqa: BLE001
        return None


@router.get("/auth/quota", summary="当前用户查询配额")
async def get_my_quota(user: TUser = Depends(get_current_user)) -> dict:
    tier = user.tier
    limit = settings.free_tier_daily_quota if tier == "free" else settings.pro_tier_daily_quota
    user_id = str(user.user_id)
    key = f"quota:{user_id}:{date.today().isoformat()}"

    redis = _get_redis()
    if redis is not None:
        try:
            used = int(await redis.get(key) or 0)
        except Exception:  # noqa: BLE001
            used = 0
    else:
        # 沙箱降级: 内存计数
        from app.services.quota import get_quota_state
        state = get_quota_state(user_id, tier)
        used = state.used

    remaining = max(0, limit - used) if limit > 0 else -1
    return {
        "tier": tier,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "is_sandbox": redis is None,
        "source": "redis" if redis else "memory_fallback",
    }


async def enforce_quota(user: TUser = Depends(get_current_user)) -> TUser:
    """配额强制依赖注入: 超额时返回 429。

    用法: 在需要计费的端点中添加 `Depends(enforce_quota)`。
    """
    tier = user.tier
    limit = settings.free_tier_daily_quota if tier == "free" else settings.pro_tier_daily_quota
    user_id = str(user.user_id)
    key = f"quota:{user_id}:{date.today().isoformat()}"

    redis = _get_redis()
    if redis is not None:
        try:
            used = int(await redis.get(key) or 0)
            if used >= limit:
                log.warning("quota.exceeded", user=user_id, tier=tier, used=used, limit=limit)
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily quota exceeded ({limit}/day for {tier} tier). Upgrade to Pro for more.",
                )
            await redis.incr(key)
            await redis.expire(key, 86400)
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001
            pass  # Redis 不可用时降级为无限制
    else:
        # 沙箱降级: 内存计数
        from app.services.quota import try_consume
        ok, _ = try_consume(user_id, tier)
        if not ok:
            raise HTTPException(status_code=429, detail="Daily quota exceeded (sandbox mode)")

    return user
