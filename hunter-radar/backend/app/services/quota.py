"""§6.3 配额服务 — in-memory stateful quota (m5t8 V1.6 适配)。

free tier:每日 3 次额度(进程内存计数)
pro tier: 不限
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

from app.core.auth import Tier


# free tier 每日额度
FREE_DAILY_LIMIT: int = 3


@dataclass(slots=True, frozen=True)
class QuotaState:
    """配额状态 — V1.6 free tier 计内存,pro 不限。"""
    tier: Literal["free", "pro"] = "pro"
    used: int = 0
    limit: int = -1
    remaining: int = -1
    reset_at: str = "2038-01-01T00:00:00+00:00"
    is_sandbox: bool = True
    source: Literal["memory", "sandbox_default"] = "memory"

    def to_dict(self) -> dict:
        return asdict(self)


# 进程内 free 用户消耗计数 {(user_id, tier): used}
_COUNTS: dict[tuple[str, str], int] = {}


def _build_state(tier: Tier, used: int) -> QuotaState:
    """构造 QuotaState 内部辅助。"""
    if tier == "pro":
        return QuotaState(tier="pro", used=0, limit=-1, remaining=-1)
    remaining = max(0, FREE_DAILY_LIMIT - used)
    return QuotaState(
        tier="free",
        used=used,
        limit=FREE_DAILY_LIMIT,
        remaining=remaining,
    )


def get_quota_state(user_id: str, tier: Tier) -> QuotaState:
    """查询当前用户配额状态。"""
    if tier == "pro":
        return _build_state("pro", 0)
    used = _COUNTS.get((user_id, "free"), 0)
    return _build_state("free", used)


def try_consume(user_id: str, tier: Tier, amount: int = 1) -> tuple[bool, QuotaState]:
    """尝试消耗一次配额。

    Args:
        user_id: 用户 id
        tier: 等级
        amount: 消耗次数(默认 1)

    Returns:
        (ok, QuotaState) — ok=True 表示消耗成功,False 表示已耗尽
    """
    if tier == "pro":
        # pro 不限,直接 ok
        return True, _build_state("pro", 0)
    key = (user_id, "free")
    used = _COUNTS.get(key, 0)
    if used + amount > FREE_DAILY_LIMIT:
        # 已耗尽
        return False, _build_state("free", used)
    _COUNTS[key] = used + amount
    return True, _build_state("free", used + amount)


def peek_remaining(user_id: str, tier: Tier) -> int:
    """查询剩余次数(pro 返 -1)。"""
    if tier == "pro":
        return -1
    used = _COUNTS.get((user_id, "free"), 0)
    return max(0, FREE_DAILY_LIMIT - used)


def reset_for_testing() -> None:
    """清空所有计数 — 测试用(m5t8 t01/t06 必需)。"""
    _COUNTS.clear()


__all__ = [
    "FREE_DAILY_LIMIT",
    "QuotaState",
    "get_quota_state",
    "try_consume",
    "peek_remaining",
    "reset_for_testing",
]
