"""V1.5 接力期 m9t6 — Analytics events 端点。

复用 backend/app/services/analytics.py 的沙箱实现:
- track_event() — 记录埋点(in-memory ring buffer)
- get_recent_events() — 读最近 N 条
- get_funnel_summary() — 计算订阅漏斗
- 10 事件类型常量(EVENT_USER_SIGNUP / ... / EVENT_FEATURE_FLAG_VIEW)

端点(V1.5.1 freeze):
  GET /api/v1/analytics/events
    参数:
      event_name  str (可选) — 10 事件之一
      from_ts     str (可选, ISO 8601) — 时间下界
      to_ts       str (可选, ISO 8601) — 时间上界
      limit       int (可选, 1-100) — 最多返多少条
    返: { events: [...], count, sandbox, review_mode, query_meta }

  GET /api/v1/analytics/funnel
    返: { unique_users_signup, unique_users_subscribe_start,
          unique_users_subscribe_success, signup_to_subscribe_start,
          subscribe_start_to_success, sandbox, review_mode }

  GET /api/v1/analytics/event-names
    返: { event_names: [10 类], review_mode }

沙箱 fallback 显式标注:
  - 10 事件类型常量沿用 V1.5 spec
  - 沙箱 in-memory ring buffer(最近 1000 条)
  - review_mode="sandbox_stub_v15_prep" 始终在响应中显式
  - 严禁 mock 200 伪装(M5 锁定)

V1.5.1 freeze:
  - /api/v1/analytics/{events,funnel,event-names} 三路径
  - PII 脱敏沿用 hash_user_id(SHA256)
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.analytics import (
    EVENT_ALERT_RULE_CREATE,
    EVENT_BASKET_CREATE,
    EVENT_FEATURE_FLAG_VIEW,
    EVENT_PUSH_OPT_IN,
    EVENT_SCREENER_VIEW,
    EVENT_SUBSCRIBE_CANCEL,
    EVENT_SUBSCRIBE_START,
    EVENT_SUBSCRIBE_SUCCESS,
    EVENT_USER_LOGIN,
    EVENT_USER_SIGNUP,
    SANDBOX_REVIEW_MODE,
    get_funnel_summary,
    get_recent_events,
)
from app.services.analytics_real import (
    PRODUCTION_REVIEW_MODE,
    SANDBOX_FALLBACK_REVIEW_MODE,
    fetch_analytics_real_events,
)

router = APIRouter()

# 10 事件类型列表
ALL_EVENT_NAMES = (
    EVENT_USER_SIGNUP,
    EVENT_USER_LOGIN,
    EVENT_SUBSCRIBE_START,
    EVENT_SUBSCRIBE_SUCCESS,
    EVENT_SUBSCRIBE_CANCEL,
    EVENT_SCREENER_VIEW,
    EVENT_BASKET_CREATE,
    EVENT_ALERT_RULE_CREATE,
    EVENT_PUSH_OPT_IN,
    EVENT_FEATURE_FLAG_VIEW,
)


def _parse_iso_ts(s: str | None, *, name: str) -> str | None:
    """ISO 8601 UTC 字符串校验(可空)。"""
    if not s:
        return None
    from datetime import datetime
    try:
        # 接受 ...Z 或 ...+00:00
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(s)
        return dt.isoformat()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"{name} ISO 8601 格式错:{e}") from None


# ----------------------------------------------------------------------
# GET /events
# ----------------------------------------------------------------------

@router.get("/events", summary="读最近 N 条埋点事件(V1.5.2 双轨:postHog / Plausible)")
async def get_events(
    event_name: Optional[str] = Query(default=None, max_length=64, description="10 事件名之一(可空)"),
    from_ts: Optional[str] = Query(default=None, description="时间下界 ISO 8601 UTC(可空)"),
    to_ts: Optional[str] = Query(default=None, description="时间上界 ISO 8601 UTC(可空)"),
    limit: int = Query(default=50, ge=1, le=100, description="最多返多少条(1-100)"),
) -> dict:
    """读最近 N 条埋点事件(V1.5.2 升级)。

    V1.5.2 双轨:
    - 真实:postHog / Plausible(优先 postHog,需 POSTHOG_API_KEY / PLAUSIBLE_API_KEY)
    - 沙箱 fallback:in-memory ring buffer(沿用 m9t6,显式 fetch_source + warning)

    响应新增字段:fetch_source + http_status + latency_ms + warning,严禁 mock 200 伪装。
    """
    from_iso = _parse_iso_ts(from_ts, name="from_ts")
    to_iso = _parse_iso_ts(to_ts, name="to_ts")

    # 事件名校验(必须是 10 类之一)
    if event_name and event_name not in ALL_EVENT_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"event_name 必须是 {ALL_EVENT_NAMES} 之一,收到:{event_name}",
        )

    # V1.5.2 双轨:优先真实事件库,失败 fallback sandbox
    import asyncio as _asyncio

    real_result = _asyncio.run(fetch_analytics_real_events(
        event_name=event_name,
        from_ts=from_iso,
        to_ts=to_iso,
        limit=limit,
    ))

    return {
        "events": real_result.events,
        "count": real_result.count,
        "sandbox": real_result.sandbox,
        "review_mode": real_result.review_mode,
        "fetch_source": real_result.fetch_source,
        "http_status": real_result.http_status,
        "latency_ms": real_result.latency_ms,
        "warning": real_result.warning,
        "query_meta": {
            "event_name": event_name,
            "from_ts": from_iso,
            "to_ts": to_iso,
            "limit": limit,
            **(real_result.query_meta or {}),
        },
        "disclaimer": (
            "V1.5.2 双轨:postHog / Plausible 真实事件库(需 POSTHOG_API_KEY / PLAUSIBLE_API_KEY);"
            "失败自动 fallback sandbox_stub_v15_prep in-memory ring buffer,"
            "显式 fetch_source + warning 标注,严禁 mock 200 伪装。"
        ),
    }


# ----------------------------------------------------------------------
# GET /funnel
# ----------------------------------------------------------------------

@router.get("/funnel", summary="订阅漏斗摘要")
async def get_funnel() -> dict:
    """计算用户增长漏斗:signup → subscribe_start → subscribe_success。"""
    events = get_recent_events(1000)
    summary = get_funnel_summary(events)
    summary["sandbox"] = True
    summary["review_mode"] = SANDBOX_REVIEW_MODE
    summary["sample_size"] = len(events)
    return summary


# ----------------------------------------------------------------------
# GET /event-names
# ----------------------------------------------------------------------

@router.get("/event-names", summary="10 事件类型列表")
async def list_event_names() -> dict:
    """10 类 Analytics 事件名 + 用途说明(沿用 V1.5 spec)。"""
    descriptions = {
        EVENT_USER_SIGNUP: "新用户注册",
        EVENT_USER_LOGIN: "用户登录",
        EVENT_SUBSCRIBE_START: "订阅流程开始(进入 /subscribe 页)",
        EVENT_SUBSCRIBE_SUCCESS: "订阅成功(Stripe webhook confirmed)",
        EVENT_SUBSCRIBE_CANCEL: "订阅取消",
        EVENT_SCREENER_VIEW: "Screener 页查询触发",
        EVENT_BASKET_CREATE: "创建新 Basket",
        EVENT_ALERT_RULE_CREATE: "创建告警规则",
        EVENT_PUSH_OPT_IN: "Web Push 订阅成功",
        EVENT_FEATURE_FLAG_VIEW: "灰度发布 flag 触发曝光",
    }
    return {
        "event_names": list(ALL_EVENT_NAMES),
        "descriptions": descriptions,
        "review_mode": SANDBOX_REVIEW_MODE,
        "sandbox": True,
    }
