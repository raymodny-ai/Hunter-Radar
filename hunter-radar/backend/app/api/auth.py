"""V1.6.1 JWT 认证端点: refresh token 轮换。

access token: 30min 过期 (settings.jwt_expire_minutes)
refresh token: 7 天过期 (settings.jwt_refresh_expire_days)
轮换策略: 每次 refresh 作废旧 jti,签发新 access + 新 refresh
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import decode_token, TUser, get_current_user
from app.core.config import settings

log = logging.getLogger(__name__)

router = APIRouter()


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


def _create_access_token(user_id: str, tier: str, role: str) -> str:
    """签发 access token (30min)。"""
    from app.core.auth import _manual_encode_jwt

    now = int(time.time())
    payload = {
        "sub": user_id,
        "tier": tier,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + settings.jwt_expire_minutes * 60,
    }
    return _manual_encode_jwt(payload, settings.secret_key, alg=settings.jwt_algorithm)


def _create_refresh_token(user_id: str, tier: str, role: str, jti: str) -> str:
    """签发 refresh token (7天)。"""
    from app.core.auth import _manual_encode_jwt

    now = int(time.time())
    payload = {
        "sub": user_id,
        "tier": tier,
        "role": role,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + settings.jwt_refresh_expire_days * 86400,
    }
    return _manual_encode_jwt(payload, settings.secret_key, alg=settings.jwt_algorithm)


def _get_redis():
    """Lazy import Redis client。"""
    try:
        from app.core.redis import get_redis_client
        return get_redis_client()
    except Exception:  # noqa: BLE001
        return None


@router.post("/auth/refresh", response_model=TokenPair, summary="刷新 access token (轮换)")
async def refresh_token_endpoint(req: RefreshRequest) -> TokenPair:
    """V1.6.1: refresh token 轮换。

    1. 验证 refresh_token 签名 + 过期
    2. 检查 type == "refresh"
    3. 检查 jti 未被撤销 (Redis)
    4. 撤销旧 jti
    5. 签发新 access + 新 refresh (新 jti)
    """
    # 1) 解码验证
    try:
        payload = decode_token(req.refresh_token)
    except (ValueError, Exception) as e:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {e}")

    # 2) 类型检查
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Missing sub in token")

    old_jti = payload.get("jti")
    tier = payload.get("tier", "free")
    role = payload.get("role", "user")

    # 3) 检查 jti 是否已撤销
    redis = _get_redis()
    if redis is not None and old_jti:
        try:
            revoked = await redis.get(f"refresh:revoked:{old_jti}")
            if revoked:
                raise HTTPException(status_code=401, detail="Refresh token has been revoked")
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001
            pass  # Redis 不可用时降级

    # 4) 撤销旧 jti
    if redis is not None and old_jti:
        try:
            ttl = settings.jwt_refresh_expire_days * 86400
            await redis.setex(f"refresh:revoked:{old_jti}", ttl, "1")
        except Exception:  # noqa: BLE001
            pass

    # 5) 签发新 token pair
    new_jti = str(uuid.uuid4())
    access = _create_access_token(sub, tier, role)
    refresh = _create_refresh_token(sub, tier, role, new_jti)

    log.info("auth.refresh", user=sub, old_jti=old_jti, new_jti=new_jti)

    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_expire_minutes * 60,
    )
