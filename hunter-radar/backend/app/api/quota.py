"""§6.3 配额端点 — no-op: always returns unlimited Pro (payment features removed).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.services.quota import QuotaState

router = APIRouter()


@router.get("/auth/quota", summary="当前用户查询配额 (no-op)")
async def get_my_quota() -> dict:
    return QuotaState().to_dict()
