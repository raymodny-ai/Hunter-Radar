"""§6.3 配额服务 — no-op: always returns unlimited Pro (payment features removed).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

from app.core.auth import Tier


@dataclass(slots=True, frozen=True)
class QuotaState:
    """Always-unlimited quota state."""
    tier: Literal["free", "pro"] = "pro"
    used: int = 0
    limit: int = -1
    remaining: int = -1
    reset_at: str = "2038-01-01T00:00:00+00:00"
    is_sandbox: bool = False
    source: Literal["memory", "sandbox_default"] = "sandbox_default"

    def to_dict(self) -> dict:
        return asdict(self)


def get_quota_state(user_id: str, tier: Tier) -> QuotaState:
    return QuotaState()


def try_consume(user_id: str, tier: Tier, amount: int = 1) -> tuple[bool, QuotaState]:
    return True, QuotaState()


def peek_remaining(user_id: str, tier: Tier) -> int:
    return -1


def reset_for_testing() -> None:
    pass


__all__ = [
    "FREE_DAILY_LIMIT",
    "QuotaState",
    "get_quota_state",
    "try_consume",
    "peek_remaining",
    "reset_for_testing",
]

# For backward compat
FREE_DAILY_LIMIT = -1
