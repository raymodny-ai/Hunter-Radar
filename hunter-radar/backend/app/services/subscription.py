"""BD-105 订阅 service — 沙箱 in-memory fallback(无 Stripe SDK / 无 PG)。

生产环境下应替换为:
- stripe.checkout.Session.create(...) → checkout_url
- stripe.Webhook.construct_event(payload, sig, webhook_secret) → 校验签名

沙箱降级:
- 无 stripe_secret_key 时:checkout 返 sandbox URL(同 host /sandbox-complete)
- webhook 无签名校验,直接接受事件
- in-memory dict 存 user_id → Subscription
- 状态机:active / canceled / past_due / incomplete
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

Plan = Literal["pro_monthly", "pro_yearly"]
Status = Literal["active", "canceled", "past_due", "incomplete", "none"]

PLAN_PRICE_USD = {
    "pro_monthly": 19.0,
    "pro_yearly": 188.0,
}

PLAN_PERIOD_DAYS = {
    "pro_monthly": 30,
    "pro_yearly": 365,
}


@dataclass
class Subscription:
    """订阅实体(沙箱 in-memory)。"""

    user_id: str
    plan: Plan
    status: Status
    stripe_customer_id: str = ""
    stripe_subscription_id: str = ""
    current_period_end: float = 0.0  # epoch seconds
    cancel_at_period_end: bool = False
    created_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["current_period_end_iso"] = (
            datetime.fromtimestamp(self.current_period_end, tz=timezone.utc).isoformat()
            if self.current_period_end
            else None
        )
        return d


# 模块级 in-memory store(沙箱)
_STORE: dict[str, Subscription] = {}


def _now() -> float:
    return time.time()


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def get_subscription(user_id: str) -> Subscription | None:
    """查用户当前订阅。无订阅返 None。"""
    sub = _STORE.get(user_id)
    if sub and sub.status == "active" and sub.current_period_end < _now():
        # 自动过期 → 标记 canceled
        sub.status = "canceled"
        _STORE[user_id] = sub
    return sub


def create_checkout(user_id: str, plan: Plan, *, base_url: str = "http://localhost:8000") -> dict:
    """创建 checkout session。

    生产:stripe.checkout.Session.create(...)
    沙箱:返同 host 的 sandbox-complete 链接,前端可直接点穿。
    """
    if plan not in PLAN_PRICE_USD:
        raise ValueError(f"unsupported plan: {plan}")
    session_id = _gen_id("cs_sandbox")
    price = PLAN_PRICE_USD[plan]
    period_days = PLAN_PERIOD_DAYS[plan]
    checkout_url = (
        f"{base_url}/api/v1/subscriptions/sandbox-complete"
        f"?session_id={session_id}&plan={plan}&user_id={user_id}"
    )
    return {
        "session_id": session_id,
        "checkout_url": checkout_url,
        "plan": plan,
        "price_usd": price,
        "period_days": period_days,
        "sandbox": True,
    }


def complete_sandbox(session_id: str, user_id: str, plan: Plan) -> Subscription:
    """沙箱「成功支付」回调 — 直接落 active 订阅。"""
    if plan not in PLAN_PRICE_USD:
        raise ValueError(f"unsupported plan: {plan}")
    period_days = PLAN_PERIOD_DAYS[plan]
    sub = Subscription(
        user_id=user_id,
        plan=plan,
        status="active",
        stripe_customer_id=_gen_id("cus_sandbox"),
        stripe_subscription_id=_gen_id("sub_sandbox"),
        current_period_end=_now() + period_days * 24 * 60 * 60,
        cancel_at_period_end=False,
    )
    _STORE[user_id] = sub
    return sub


def cancel(user_id: str, *, at_period_end: bool = True) -> Subscription:
    """取消订阅。

    at_period_end=True:状态保持 active,设 cancel_at_period_end=True(期末真正取消)
    at_period_end=False:立即 canceled
    """
    sub = get_subscription(user_id)
    if sub is None:
        raise KeyError(f"no active subscription for user {user_id}")
    if at_period_end:
        sub.cancel_at_period_end = True
    else:
        sub.status = "canceled"
    _STORE[user_id] = sub
    return sub


def handle_webhook_event(event: dict) -> dict:
    """处理 Stripe webhook event(sandbox 简化:信任 payload)。

    支持 event type:
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_failed
    """
    etype = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    user_id = data.get("metadata", {}).get("user_id")
    if not user_id:
        return {"handled": False, "reason": "missing metadata.user_id"}
    sub = _STORE.get(user_id)
    if sub is None:
        return {"handled": False, "reason": f"no subscription for user_id={user_id}"}
    if etype == "customer.subscription.updated":
        status = data.get("status", sub.status)
        period_end = data.get("current_period_end", sub.current_period_end)
        if status in ("active", "past_due", "canceled", "incomplete"):
            sub.status = status  # type: ignore[assignment]
        if isinstance(period_end, (int, float)) and period_end > 0:
            sub.current_period_end = float(period_end)
        sub.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
    elif etype == "customer.subscription.deleted":
        sub.status = "canceled"
        sub.cancel_at_period_end = False
    elif etype == "invoice.payment_failed":
        sub.status = "past_due"
    else:
        return {"handled": False, "reason": f"unhandled event type={etype}"}
    _STORE[user_id] = sub
    return {"handled": True, "event_type": etype, "user_id": user_id, "new_status": sub.status}


def reset_for_tests() -> None:
    """沙箱自测用:清空 in-memory store。"""
    _STORE.clear()