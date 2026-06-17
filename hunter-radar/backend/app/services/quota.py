"""§6.3 用户查询配额服务(FE-064 / BD-076 落地)。

设计:
- 配额策略:免费版每日 N 次「查询类」请求(可消耗);pro 不限量
- 沙箱模式:无 PG/Redis 时,内存计数 + 进程级 UTC 日切;
  生产应切到 PG(api_quota_daily 表)+ Redis 缓存(见 §6.3 M6 TODO)
- 公开 API:
    - get_quota_state(user_id, tier) -> QuotaState(used / limit / remaining / reset_at / tier)
    - try_consume(user_id, tier) -> tuple[bool, QuotaState](ok 标志 + 状态)
    - peek_remaining(user_id, tier) -> int(只看不消耗)

配额键:`{user_id}|{YYYY-MM-DD(UTC)}`,进程内 dict 存 used count。

硬约束:
- tier=pro → limit=∞,永远 ok
- 沙箱无 PG/Redis → 不抛错,只走内存降级
- reset_at 取 UTC 次日 00:00:00
- 本服务不强制 HTTP 402(留给调用方;M6 Stripe 升级引导时再切)
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from app.core.auth import Tier

# ---- 常量 --------------------------------------------------------------------

# 免费版每日配额(M5 落地:M5 末前不调整,锁定 3)
FREE_DAILY_LIMIT = int(os.environ.get("HR_FREE_DAILY_LIMIT") or 3)

# 沙箱总开关:HR_QUOTA_LIVE != 1 → 走沙箱降级(允许前端调试)
_QUOTA_LIVE = os.environ.get("HR_QUOTA_LIVE") == "1"

# ---- 进程内计数 --------------------------------------------------------------

_lock = threading.RLock()  # 可重入:try_consume 内调 _peek_or_default 需要同线程二次 acquire
_counter: dict[str, int] = {}


def _quota_key(user_id: str, day_utc: date) -> str:
    return f"{user_id}|{day_utc.isoformat()}"


def _utc_today() -> date:
    return datetime.now(tz=timezone.utc).date()


def _next_utc_midnight_iso() -> str:
    """UTC 次日 00:00:00 ISO 字符串。"""
    tomorrow = datetime.combine(
        _utc_today() + timedelta(days=1), time.min, tzinfo=timezone.utc
    )
    return tomorrow.isoformat()


# ---- 数据类 ------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class QuotaState:
    """配额状态(对外序列化字段稳定)。"""

    tier: Literal["free", "pro"]
    used: int
    limit: int  # -1 代表无限(pro)
    remaining: int  # -1 代表无限(pro)
    reset_at: str  # ISO datetime(UTC)
    is_sandbox: bool
    source: Literal["memory", "sandbox_default"]

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---- 核心 API ----------------------------------------------------------------


def _peek_or_default(user_id: str, tier: Tier, day: date) -> QuotaState:
    """无副作用读取(不消耗)。"""
    if tier == "pro":
        return QuotaState(
            tier="pro",
            used=0,
            limit=-1,
            remaining=-1,
            reset_at=_next_utc_midnight_iso(),
            is_sandbox=not _QUOTA_LIVE,
            source="sandbox_default" if not _QUOTA_LIVE else "memory",
        )
    key = _quota_key(user_id, day)
    # 依赖 RLock:即便外层持锁(_peek_or_default 也可能在 try_consume 锁内被调)也不会死锁
    used = _counter.get(key, 0)
    return QuotaState(
        tier="free",
        used=used,
        limit=FREE_DAILY_LIMIT,
        remaining=max(FREE_DAILY_LIMIT - used, 0),
        reset_at=_next_utc_midnight_iso(),
        is_sandbox=not _QUOTA_LIVE,
        source="memory",
    )


def get_quota_state(user_id: str, tier: Tier) -> QuotaState:
    """无副作用查询当前配额。"""
    return _peek_or_default(user_id, tier, _utc_today())


def try_consume(user_id: str, tier: Tier, amount: int = 1) -> tuple[bool, QuotaState]:
    """尝试消耗配额。

    返回:
        (ok, state)
        - ok=True:消耗成功(仅在 free 层级 free - used >= amount 时)
        - ok=False:免费版当日已用完
        - tier=pro:永远 ok=True,used 不递增
    """
    if tier == "pro":
        return True, _peek_or_default(user_id, tier, _utc_today())
    if amount < 1:
        amount = 1
    day = _utc_today()
    key = _quota_key(user_id, day)
    with _lock:
        used = _counter.get(key, 0)
        if used + amount > FREE_DAILY_LIMIT:
            # 锁内直接构造 state,避免 _peek_or_default 二次 acquire(虽然 RLock 允许,但能省一次)
            return False, QuotaState(
                tier="free",
                used=used,
                limit=FREE_DAILY_LIMIT,
                remaining=max(FREE_DAILY_LIMIT - used, 0),
                reset_at=_next_utc_midnight_iso(),
                is_sandbox=not _QUOTA_LIVE,
                source="memory",
            )
        _counter[key] = used + amount
    return True, _peek_or_default(user_id, tier, day)


def peek_remaining(user_id: str, tier: Tier) -> int:
    """剩余配额(简版,只返 int)。pro 返 -1。"""
    state = get_quota_state(user_id, tier)
    return state.remaining


def reset_for_testing() -> None:  # pragma: no cover - 仅供单测
    """清空内存计数器(单测辅助;生产禁止调用)。"""
    with _lock:
        _counter.clear()


__all__ = [
    "FREE_DAILY_LIMIT",
    "QuotaState",
    "get_quota_state",
    "try_consume",
    "peek_remaining",
    "reset_for_testing",
]
