"""BD-105 订阅端点 — removed (payment features removed).
All endpoints return free-for-all status.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/subscriptions/checkout")
async def post_checkout() -> dict:
    return {"status": "free_for_all", "tier": "pro", "message": "Payments removed"}


@router.get("/subscriptions/me")
async def get_me() -> dict:
    return {"status": "free_for_all", "tier": "pro", "message": "Payments removed"}


@router.post("/subscriptions/cancel")
async def post_cancel() -> dict:
    return {"status": "free_for_all", "tier": "pro", "message": "Payments removed"}


@router.post("/subscriptions/webhook")
async def post_webhook() -> dict:
    return {"status": "free_for_all", "tier": "pro", "message": "Payments removed"}


@router.get("/subscriptions/sandbox-complete")
async def get_sandbox_complete() -> dict:
    return {"status": "free_for_all", "tier": "pro", "message": "Payments removed"}


@router.get("/subscriptions/plans")
async def get_plans() -> dict:
    return {"status": "free_for_all", "tier": "pro", "plans": []}
