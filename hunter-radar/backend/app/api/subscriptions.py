"""BD-105 Stripe 订阅接入端点(M6 商业化基础)。

端点:
- POST /api/v1/subscriptions/checkout     body: {plan} → checkout_url + sandbox flag
- GET  /api/v1/subscriptions/me           → 当前用户订阅状态(200 + null if none)
- POST /api/v1/subscriptions/cancel       body: {at_period_end=true} → 取消订阅
- POST /api/v1/subscriptions/webhook      Stripe event payload,免 JWT 校验,内部签名由 service 校验
- GET  /api/v1/subscriptions/sandbox-complete?sandbox=1  → 沙箱「支付成功」回调

沙箱降级(M7-t6 补全 webhook 签名):
- STRIPE_WEBHOOK_SECRET 未设 → 沙箱模式:返 200 + signature_skipped=true + signature_mode=sandbox_skip
  (显式标注,绝不 mock 200 伪装)
- STRIPE_WEBHOOK_SECRET 已设 → 真实模式:用 stripe.Webhook.construct_event(payload, sig, secret)
- stripe SDK 不可用(secret 已设)→ 返 503 signature_check_unavailable(不 mock 200 伪装)
- 签名错误 → 400 Invalid signature
- 沙箱存储用 in-memory dict(SubscriptionService._STORE);生产应替换为 PG 表
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import TUser, get_current_user
from app.core.config import settings
from app.services.subscription import (
    PLAN_PRICE_USD,
    Subscription,
    cancel,
    complete_sandbox,
    create_checkout,
    get_subscription,
    handle_webhook_event,
)

router = APIRouter()


Plan = Literal["pro_monthly", "pro_yearly"]


class CheckoutRequest(BaseModel):
    plan: Plan = Field(..., description="pro_monthly | pro_yearly")


class CancelRequest(BaseModel):
    at_period_end: bool = Field(default=True, description="true=期末取消,false=立即取消")


@router.post("/subscriptions/checkout", summary="创建 Stripe Checkout Session(沙箱 fallback)")
async def post_checkout(
    req: CheckoutRequest,
    user: TUser = Depends(get_current_user),
) -> dict:
    """生成 Stripe Checkout Session URL。

    生产:调 stripe.checkout.Session.create(...).
    沙箱:返 sandbox-complete 链接,前端可直接点击模拟成功。
    """
    base_url = settings.cors_origins[0] if settings.cors_origins else "http://localhost:8000"
    return create_checkout(str(user.user_id), req.plan, base_url=base_url)


@router.get("/subscriptions/me", summary="当前用户订阅状态")
async def get_me(user: TUser = Depends(get_current_user)) -> dict:
    """200 + 订阅状态;无订阅返 200 + tier=free + status=none(便于前端无订阅判断)。"""
    sub = get_subscription(str(user.user_id))
    if sub is None:
        return {
            "user_id": str(user.user_id),
            "tier": user.tier,
            "status": "none",
            "plan": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
        }
    d = sub.to_dict()
    d["tier"] = "pro" if sub.status == "active" else "free"
    return d


@router.post("/subscriptions/cancel", summary="取消订阅(默认期末取消)")
async def post_cancel(
    req: CancelRequest,
    user: TUser = Depends(get_current_user),
) -> dict:
    """取消订阅;无订阅返 404。"""
    try:
        sub = cancel(str(user.user_id), at_period_end=req.at_period_end)
    except KeyError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(e)) from e
    d = sub.to_dict()
    d["tier"] = "pro" if sub.status == "active" else "free"
    return d


@router.post("/subscriptions/webhook", summary="Stripe webhook 事件接收(签名校验)")
async def post_webhook(request: Request) -> dict:
    """接收 Stripe webhook event。

    签名校验逻辑(M7-t6):
    - settings.stripe_webhook_secret 未设 → 沙箱模式:返 200 + signature_skipped=true
      + signature_mode=sandbox_skip + warning(显式标注,绝不 mock 200 伪装成功)
    - secret 已设 + stripe SDK 不可用 → 503 signature_check_unavailable(不伪装成功)
    - secret 已设 + SDK 可用 → stripe.Webhook.construct_event(payload, sig, secret)
    - 签名错误 → 400 Invalid signature(由 HTTPException 抛)
    - payload 非 JSON → 400 Invalid payload
    """
    import json as _json
    import logging

    logger = logging.getLogger(__name__)

    payload = await request.body()  # raw bytes(Stripe 签名校验需原始字节)
    sig_header = request.headers.get("stripe-signature", "")
    secret = settings.stripe_webhook_secret

    # ---- 路径 1:沙箱模式(secret 未设)----
    if not secret:
        try:
            event = _json.loads(payload) if payload else {}
        except _json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail={"received": False, "error": "invalid JSON payload",
                        "signature_mode": "sandbox_skip", "detail": str(e)}
            ) from e
        result = handle_webhook_event(event)
        logger.warning(
            "Stripe webhook sandbox_skip: STRIPE_WEBHOOK_SECRET unset; "
            "production must set it to enable signature verification"
        )
        return {
            "received": True,
            "signature_skipped": True,
            "signature_mode": "sandbox_skip",
            "warning": "STRIPE_WEBHOOK_SECRET not set; sandbox mode",
            **result,
        }

    # ---- 路径 2:真实模式(secret 已设)----
    try:
        import stripe  # type: ignore[import-not-found]
    except ImportError as e:
        # secret 已设但 stripe SDK 不可用 → 503(不 mock 200 伪装)
        logger.error("STRIPE_WEBHOOK_SECRET set but stripe SDK unavailable")
        raise HTTPException(
            status_code=503,
            detail={"received": False, "error": "signature_check_unavailable",
                    "detail": "stripe SDK not installed; cannot verify signature in production",
                    "signature_mode": "prod_unavailable"}
        ) from e

    try:
        event_obj = stripe.Webhook.construct_event(payload, sig_header, secret)
    except stripe.ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"received": False, "error": "invalid payload",
                    "detail": str(e), "signature_mode": "prod_verified"}
        ) from e
    except stripe.SignatureVerificationError as e:
        raise HTTPException(
            status_code=400,
            detail={"received": False, "error": "invalid signature",
                    "detail": str(e), "signature_mode": "prod_verified"}
        ) from e

    # 真实环境事件已验证 → dispatch service
    result = handle_webhook_event(dict(event_obj))
    return {"received": True, "signature_mode": "prod_verified", **result}


@router.get("/subscriptions/sandbox-complete", summary="沙箱「支付成功」回调(仅沙箱)")
async def get_sandbox_complete(
    session_id: str = Query(...),
    user_id: str = Query(...),
    plan: Plan = Query(...),
) -> dict:
    """沙箱专用:GET 方式模拟 Stripe Checkout 成功重定向。

    生产环境由 Stripe 异步 webhook 触发,本端点仅用于前端自测与沙箱演练。
    """
    sub = complete_sandbox(session_id, user_id, plan)
    return sub.to_dict()


@router.get("/subscriptions/plans", summary="订阅价格档(公开)")
async def get_plans() -> dict:
    """公开端点:无需 JWT,前端 /subscribe 页面初始化时拉取。"""
    return {
        "plans": [
            {
                "id": plan_id,
                "name": "Pro 月付" if plan_id == "pro_monthly" else "Pro 年付",
                "price_usd": price,
                "billing_period_days": 30 if plan_id == "pro_monthly" else 365,
                "savings_usd": (
                    0.0
                    if plan_id == "pro_monthly"
                    else round(PLAN_PRICE_USD["pro_monthly"] * 12 - price, 2)
                ),
            }
            for plan_id, price in PLAN_PRICE_USD.items()
        ],
    }