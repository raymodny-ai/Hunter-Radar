"""M6 灰度发布端点 — 供前端 useFeatureFlag hook 拉取。

- GET /api/v1/feature-flags            返当前用户的全部 flag 快照
- GET /api/v1/feature-flags/{flag_key}  返单个 flag 的判定结果

匿名访客(无 JWT)返 default 状态;登录用户返基于 user_id 的判定结果。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import TUser, get_current_user
from app.services.feature_flag import is_enabled, snapshot_for_user

router = APIRouter()


def _snapshot_to_dict(snap) -> dict:
    return {"enabled": snap.enabled, "reason": snap.reason}


@router.get("/feature-flags", summary="当前用户全部 flag 快照(M6 灰度)")
async def get_all_flags(
    user: TUser = Depends(get_current_user),
) -> dict:
    """返 {flag_key: {enabled, reason}}。"""
    snap = snapshot_for_user(str(user.user_id))
    return {"flags": {k: _snapshot_to_dict(v) for k, v in snap.items()}}


@router.get("/feature-flags/{flag_key}", summary="单个 flag 判定")
async def get_flag(
    flag_key: str,
    user: TUser = Depends(get_current_user),
) -> dict:
    """返 {flag_key, enabled, reason}。"""
    snap = is_enabled(flag_key, str(user.user_id))
    return {"flag_key": flag_key, **_snapshot_to_dict(snap)}