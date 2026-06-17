"""M10-t3 用户增长埋点 — V1.5.2 真实事件库接入(postHog / Plausible 双轨)。

数据源链路(生产 vs 沙箱):
- 生产:postHog(优先)→ POST {POSTHOG_HOST}/api/projects/{POSTHOG_PROJECT_ID}/events/
  或 Plausible(次选)→ GET {PLAUSIBLE_HOST}/api/v1/stats/events?site_id={PLAUSIBLE_SITE_ID}
- 沙箱:httpx 不可用 / 无 POSTHOG_API_KEY / 无 PLAUSIBLE_API_KEY / 4xx-5xx → fallback
  `app/services/analytics.py:get_recent_events()`(in-memory ring buffer,沿用 m9t6)

合规:
- 不返 mock 200 伪装成功(真实模式失败显式 sandbox=true + warning)
- PII 脱敏:user_id → SHA256 hash(沿用 m9t6 hash_user_id)
- 事件 schema 与 V1.5 spec 一致(10 事件常量)
- 真实事件库与 sandbox 事件 schema 标准化

环境变量:
- POSTHOG_API_KEY:postHog Personal API Key(必填)
- POSTHOG_PROJECT_ID:postHog 项目 ID(必填)
- POSTHOG_HOST:postHog Host(默认 https://us.i.posthog.com)
- PLAUSIBLE_API_KEY:Plausible API key(可选,fallback 用)
- PLAUSIBLE_SITE_ID:Plausible site ID(可选)
- PLAUSIBLE_HOST:Plausible Host(默认 https://plausible.io)
- ANALYTICS_TIMEOUT_SEC:默认 10.0
- ANALYTICS_PROVIDER:可选,默认 "posthog"(支持 "posthog" / "plausible" / "sandbox")
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

# 探测 httpx 是否可用(沙箱 fallback 用)
try:
    import httpx  # type: ignore[import-untyped]
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# 沿用 m9t6 sandbox 模块
from app.services.analytics import (  # noqa: E402
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
    get_recent_events,
    hash_user_id,
)

# 真实模式常量
PRODUCTION_REVIEW_MODE = "production_real"
SANDBOX_FALLBACK_REVIEW_MODE = "sandbox_stub_v15_prep"

# Provider 常量
PROVIDER_POSTHOG = "posthog"
PROVIDER_PLAUSIBLE = "plausible"
PROVIDER_SANDBOX = "sandbox"

# 配置
ANALYTICS_PROVIDER_DEFAULT = PROVIDER_POSTHOG
POSTHOG_HOST_DEFAULT = "https://us.i.posthog.com"
PLAUSIBLE_HOST_DEFAULT = "https://plausible.io"
ANALYTICS_TIMEOUT_DEFAULT = 10.0

# 10 事件名(从 sandbox 模块 import)
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


@dataclass
class AnalyticsRealFetchResult:
    """Analytics 真实事件库拉取结果(含 fallback 信息)。"""

    events: list[dict]
    count: int
    fetched_at: str
    fetch_source: str  # "posthog" | "plausible" | "sandbox"
    review_mode: str  # PRODUCTION_REVIEW_MODE | SANDBOX_FALLBACK_REVIEW_MODE
    sandbox: bool
    http_status: int | None = None
    latency_ms: int | None = None
    warning: str | None = None
    query_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def _normalize_posthog_event(ph_event: dict[str, Any]) -> dict[str, Any] | None:
    """标准化 postHog event → AnalyticsEvent dict 形态。"""
    event_name = ph_event.get("event")
    if not event_name or event_name not in ALL_EVENT_NAMES:
        return None
    distinct_id = ph_event.get("distinct_id", "anonymous")
    properties = ph_event.get("properties", {}) or {}
    timestamp = ph_event.get("timestamp")
    if not timestamp:
        return None
    # postHog timestamp 可能是 ISO string 或 epoch
    if isinstance(timestamp, str):
        ts = timestamp
    elif isinstance(timestamp, (int, float)):
        ts = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    else:
        return None
    return {
        "event_name": event_name,
        "user_id_hash": hash_user_id(str(distinct_id)),
        "properties": properties,
        "timestamp": ts,
        "session_id": properties.get("$session_id"),
        "source": properties.get("$source", "web"),
        "review_mode": PRODUCTION_REVIEW_MODE,
    }


def _normalize_plausible_event(pl_event: dict[str, Any]) -> dict[str, Any] | None:
    """标准化 Plausible event → AnalyticsEvent dict 形态。"""
    event_name = pl_event.get("name")
    if not event_name or event_name not in ALL_EVENT_NAMES:
        return None
    user_id = pl_event.get("user_id", "anonymous")
    timestamp = pl_event.get("timestamp")
    if not timestamp:
        return None
    return {
        "event_name": event_name,
        "user_id_hash": hash_user_id(str(user_id)),
        "properties": pl_event.get("props", {}) or {},
        "timestamp": timestamp,
        "session_id": None,
        "source": "web",
        "review_mode": PRODUCTION_REVIEW_MODE,
    }


async def fetch_analytics_real_events(
    *,
    event_name: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 50,
    provider: str | None = None,
    timeout: float | None = None,
) -> AnalyticsRealFetchResult:
    """Analytics 真实事件库拉取(postHog / Plausible 双轨,sandbox fallback 内嵌)。

    Args:
        event_name: 10 事件名之一(可选,过滤)
        from_ts / to_ts: ISO 8601 时间范围(可选)
        limit: 最多返回事件数(1-100,默认 50)
        provider: 数据源(默认 "posthog",可选 "plausible" / "sandbox" 强制沙箱)
        timeout: 超时秒数

    Returns:
        AnalyticsRealFetchResult(含 fetch_source / review_mode / warning)
    """
    provider = provider or _get_env("ANALYTICS_PROVIDER", ANALYTICS_PROVIDER_DEFAULT) or PROVIDER_POSTHOG
    timeout = timeout or float(_get_env("ANALYTICS_TIMEOUT_SEC", str(ANALYTICS_TIMEOUT_DEFAULT)))
    fetched_at = _now_iso()

    # 强制 sandbox 或 httpx 不可用 → fallback
    if provider == PROVIDER_SANDBOX or not HTTPX_AVAILABLE:
        return _build_result_sandbox(
            event_name, from_ts, to_ts, limit, fetched_at,
            reason="provider_sandbox" if provider == PROVIDER_SANDBOX else "httpx_unavailable",
            warning="provider 强制 sandbox 或 httpx 未安装,fallback 到 in-memory ring buffer",
        )

    started = datetime.now(timezone.utc)
    try:
        if provider == PROVIDER_POSTHOG:
            events = await _fetch_posthog_events(
                event_name=event_name, from_ts=from_ts, to_ts=to_ts, limit=limit, timeout=timeout,
            )
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            return AnalyticsRealFetchResult(
                events=events,
                count=len(events),
                fetched_at=fetched_at,
                fetch_source=PROVIDER_POSTHOG,
                review_mode=PRODUCTION_REVIEW_MODE,
                sandbox=False,
                http_status=200,
                latency_ms=latency_ms,
                warning=None,
                query_meta={"provider": provider, "event_name": event_name, "limit": limit},
            )
        elif provider == PROVIDER_PLAUSIBLE:
            events = await _fetch_plausible_events(
                event_name=event_name, from_ts=from_ts, to_ts=to_ts, limit=limit, timeout=timeout,
            )
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            return AnalyticsRealFetchResult(
                events=events,
                count=len(events),
                fetched_at=fetched_at,
                fetch_source=PROVIDER_PLAUSIBLE,
                review_mode=PRODUCTION_REVIEW_MODE,
                sandbox=False,
                http_status=200,
                latency_ms=latency_ms,
                warning=None,
                query_meta={"provider": provider, "event_name": event_name, "limit": limit},
            )
        else:
            return _build_result_sandbox(
                event_name, from_ts, to_ts, limit, fetched_at,
                reason="unknown_provider",
                warning=f"未知 provider '{provider}',fallback sandbox",
            )
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as e:
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return _build_result_sandbox(
            event_name, from_ts, to_ts, limit, fetched_at,
            reason=f"{provider}_error",
            latency_ms=latency_ms,
            warning=f"{provider} 异常({type(e).__name__}: {e}),fallback sandbox",
        )
    except Exception as e:  # noqa: BLE001
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return _build_result_sandbox(
            event_name, from_ts, to_ts, limit, fetched_at,
            reason="unknown_error",
            latency_ms=latency_ms,
            warning=f"未知异常({type(e).__name__}: {e}),fallback sandbox",
        )


async def _fetch_posthog_events(
    *,
    event_name: str | None,
    from_ts: str | None,
    to_ts: str | None,
    limit: int,
    timeout: float,
) -> list[dict[str, Any]]:
    """postHog events API 调用。"""
    api_key = _get_env("POSTHOG_API_KEY")
    project_id = _get_env("POSTHOG_PROJECT_ID")
    host = _get_env("POSTHOG_HOST", POSTHOG_HOST_DEFAULT)
    if not api_key or not project_id:
        raise ValueError("POSTHOG_API_KEY 或 POSTHOG_PROJECT_ID 未设")

    url = f"{host}/api/projects/{project_id}/events/"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # 时间范围默认最近 7 天
    if not to_ts:
        to_dt = datetime.now(timezone.utc)
    else:
        to_dt = datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
    if not from_ts:
        from_dt = to_dt - timedelta(days=7)
    else:
        from_dt = datetime.fromisoformat(from_ts.replace("Z", "+00:00"))

    params: dict[str, Any] = {
        "limit": min(limit, 100),
        "after": from_dt.isoformat(),
        "before": to_dt.isoformat(),
    }
    if event_name:
        params["event"] = event_name

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise httpx.HTTPError(f"postHog 返 HTTP {resp.status_code}")
        payload = resp.json()
        raw_events = payload.get("results", [])
        normalized: list[dict[str, Any]] = []
        for raw in raw_events:
            ev = _normalize_posthog_event(raw)
            if ev:
                normalized.append(ev)
        return normalized


async def _fetch_plausible_events(
    *,
    event_name: str | None,
    from_ts: str | None,
    to_ts: str | None,
    limit: int,
    timeout: float,
) -> list[dict[str, Any]]:
    """Plausible events API 调用(自定义事件需 self-hosted + events plugin)。"""
    api_key = _get_env("PLAUSIBLE_API_KEY")
    site_id = _get_env("PLAUSIBLE_SITE_ID")
    host = _get_env("PLAUSIBLE_HOST", PLAUSIBLE_HOST_DEFAULT)
    if not api_key or not site_id:
        raise ValueError("PLAUSIBLE_API_KEY 或 PLAUSIBLE_SITE_ID 未设")

    url = f"{host}/api/v1/stats/events"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    if not to_ts:
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        to_date = to_ts[:10]
    if not from_ts:
        from_dt = datetime.now(timezone.utc) - timedelta(days=7)
        from_date = from_dt.strftime("%Y-%m-%d")
    else:
        from_date = from_ts[:10]

    params: dict[str, Any] = {
        "site_id": site_id,
        "period": "custom",
        "date": f"{from_date},{to_date}",
        "limit": min(limit, 100),
    }
    if event_name:
        params["name"] = event_name

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise httpx.HTTPError(f"Plausible 返 HTTP {resp.status_code}")
        payload = resp.json()
        raw_events = payload.get("results", [])
        normalized: list[dict[str, Any]] = []
        for raw in raw_events:
            ev = _normalize_plausible_event(raw)
            if ev:
                normalized.append(ev)
        return normalized


def _build_result_sandbox(
    event_name: str | None,
    from_ts: str | None,
    to_ts: str | None,
    limit: int,
    fetched_at: str,
    *,
    reason: str,
    latency_ms: int | None = None,
    warning: str | None = None,
) -> AnalyticsRealFetchResult:
    """构造 sandbox 结果(沿用 m9t6 in-memory ring buffer)。"""
    events = get_recent_events(limit)
    # 应用 event_name 过滤
    if event_name:
        events = [e for e in events if e.get("event_name") == event_name]
    # 应用时间范围过滤
    if from_ts:
        events = [e for e in events if e.get("timestamp", "") >= from_ts]
    if to_ts:
        events = [e for e in events if e.get("timestamp", "") <= to_ts]
    return AnalyticsRealFetchResult(
        events=events,
        count=len(events),
        fetched_at=fetched_at,
        fetch_source=PROVIDER_SANDBOX,
        review_mode=SANDBOX_FALLBACK_REVIEW_MODE,
        sandbox=True,
        http_status=None,
        latency_ms=latency_ms,
        warning=warning or f"sandbox fallback(reason={reason})",
        query_meta={"reason": reason, "event_name": event_name, "limit": limit},
    )


def main() -> int:
    """CLI:拉 Analytics 真实事件(沙箱 fallback 演示)。"""
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(description="Analytics 真实事件库 real + sandbox fallback (m10t3)")
    parser.add_argument("--provider", type=str, default=None, help="posthog | plausible | sandbox")
    parser.add_argument("--event-name", type=str, default=None, help="10 事件名之一")
    parser.add_argument("--from-ts", type=str, default=None, help="ISO 8601")
    parser.add_argument("--to-ts", type=str, default=None, help="ISO 8601")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=ANALYTICS_TIMEOUT_DEFAULT)
    args = parser.parse_args()

    result = asyncio.run(fetch_analytics_real_events(
        event_name=args.event_name,
        from_ts=args.from_ts,
        to_ts=args.to_ts,
        limit=args.limit,
        provider=args.provider,
        timeout=args.timeout,
    ))
    print(_json.dumps({
        "result": result.to_dict(),
        "sample_events": result.events[:3],
        "httpx_available": HTTPX_AVAILABLE,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())