"""用户增长埋点 — V1.5 准备(M7 接力期)。

V1.5 待落地(V1.4 不暴露 API):
- 用户激活 / 付费转化 / 留存埋点
- 接 postHog / Plausible / 自建埋点
- PII 脱敏(用户 ID 哈希)

沙箱 stub 设计:
- 不发真实埋点(无 postHog SDK / 无后端写入)
- 接口定义完整,事件 schema 与 V1.5 spec 一致
- 沙箱模式下记录到 in-memory ring buffer + 标记 review_mode
"""
from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal

# 埋点事件类型(V1.5 spec,沿用至 V1.5+ 真实落地)
EVENT_USER_SIGNUP = "user_signup"
EVENT_USER_LOGIN = "user_login"
EVENT_SUBSCRIBE_START = "subscribe_start"
EVENT_SUBSCRIBE_SUCCESS = "subscribe_success"
EVENT_SUBSCRIBE_CANCEL = "subscribe_cancel"
EVENT_SCREENER_VIEW = "screener_view"
EVENT_BASKET_CREATE = "basket_create"
EVENT_ALERT_RULE_CREATE = "alert_rule_create"
EVENT_PUSH_OPT_IN = "push_opt_in"
EVENT_FEATURE_FLAG_VIEW = "feature_flag_view"

SANDBOX_REVIEW_MODE = "sandbox_stub_v15_prep"

# 沙箱 in-memory ring buffer(最近 1000 条)
_EVENT_BUFFER: deque = deque(maxlen=1000)


@dataclass
class AnalyticsEvent:
    """埋点事件。"""

    event_name: str
    user_id_hash: str  # SHA256 哈希,避免明文 PII
    properties: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str | None = None
    source: Literal["web", "ios", "android"] = "web"
    review_mode: str = SANDBOX_REVIEW_MODE

    def to_dict(self) -> dict:
        return asdict(self)


def hash_user_id(user_id: str) -> str:
    """SHA256 哈希用户 ID(避免明文 PII)。"""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def track_event(
    event_name: str,
    user_id: str,
    properties: dict | None = None,
    *,
    session_id: str | None = None,
    source: Literal["web", "ios", "android"] = "web",
) -> AnalyticsEvent:
    """记录埋点事件(V1.5 准备 stub)。

    沙箱 stub:in-memory ring buffer + 返 AnalyticsEvent。
    生产:V1.5+ 接入 postHog / Plausible / 自建 ClickHouse。
    """
    event = AnalyticsEvent(
        event_name=event_name,
        user_id_hash=hash_user_id(user_id),
        properties=properties or {},
        session_id=session_id,
        source=source,
    )
    _EVENT_BUFFER.append(event)
    return event


def get_recent_events(n: int = 100) -> list[dict]:
    """读最近 N 条事件(沙箱 stub 调试用)。"""
    return [e.to_dict() for e in list(_EVENT_BUFFER)[-n:]]


def get_funnel_summary(events: list[dict]) -> dict:
    """计算订阅漏斗摘要。

    Args:
        events: 埋点事件列表(应有 user_id_hash 字段)

    Returns:
        {
            "unique_users_signup": int,
            "unique_users_subscribe_start": int,
            "unique_users_subscribe_success": int,
            "signup_to_subscribe_start": float,  # 转化率
            "subscribe_start_to_success": float, # 转化率
        }
    """
    signup_users = {e["user_id_hash"] for e in events if e["event_name"] == EVENT_USER_SIGNUP}
    subscribe_start_users = {
        e["user_id_hash"] for e in events if e["event_name"] == EVENT_SUBSCRIBE_START
    }
    subscribe_success_users = {
        e["user_id_hash"] for e in events if e["event_name"] == EVENT_SUBSCRIBE_SUCCESS
    }
    s2ss = (
        len(subscribe_start_users & signup_users) / len(signup_users)
        if signup_users
        else 0.0
    )
    sss = (
        len(subscribe_success_users & subscribe_start_users) / len(subscribe_start_users)
        if subscribe_start_users
        else 0.0
    )
    return {
        "unique_users_signup": len(signup_users),
        "unique_users_subscribe_start": len(subscribe_start_users),
        "unique_users_subscribe_success": len(subscribe_success_users),
        "signup_to_subscribe_start": round(s2ss, 4),
        "subscribe_start_to_success": round(sss, 4),
    }


def reset_for_tests() -> None:
    """沙箱自测用:清空 ring buffer。"""
    _EVENT_BUFFER.clear()