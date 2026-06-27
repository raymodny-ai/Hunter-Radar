"""BD-105 订阅 service — no-op (payment features removed).
"""
from __future__ import annotations

from typing import Literal

Plan = Literal["pro_monthly", "pro_yearly"]
Status = Literal["active", "canceled", "past_due", "incomplete", "none"]

PLAN_PRICE_USD: dict[str, float] = {}


def get_subscription(user_id: str) -> None:
    return None


def create_checkout(user_id: str, plan: Plan, *, base_url: str = "http://localhost:8000") -> dict:
    return {
        "session_id": "",
        "checkout_url": "",
        "plan": plan,
        "price_usd": 0,
        "period_days": 30,
        "sandbox": False,
    }


def complete_sandbox(session_id: str, user_id: str, plan: Plan) -> dict:
    return {"status": "free_for_all", "tier": "pro"}


def cancel(user_id: str, *, at_period_end: bool = True) -> dict:
    return {"status": "free_for_all", "tier": "pro"}


def handle_webhook_event(event: dict) -> dict:
    return {"handled": False, "reason": "payments removed"}


def reset_for_tests() -> None:
    pass
