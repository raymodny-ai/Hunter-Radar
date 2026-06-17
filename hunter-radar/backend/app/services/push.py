"""§6 推送服务(BD-074)。

M5 接力期:
- m5t3:email 通道
- m5t4(本文件新增):webpush 通道(VAPID 占位 + 客户端订阅记录)
- 兼容 log / silent(留待 M6)

设计:
- 所有通道走环境变量配置;沙箱/未配置 → 全部 skipped_sandbox(写日志,绝不真发)
- 真发模式 HR_PUSH_LIVE=1 + 必填项齐全
- 返回 dict 与 alert_event.delivery_status JSONB 列直接对应
  (key=channel 标识, value={channel, status, provider_msg_id, error, to})

硬约束:
- 不在日志/响应里泄露 SMTP 密码 / VAPID private key / 收件人列表
- 失败必须 status=failed + error=字符串,严禁抛异常给上层(API 路径上 alert_event 必须落)
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

log = logging.getLogger("hunter_radar.push")

# ---- SMTP 配置(全部走 env;沙箱可全空) -------------------------------------
SMTP_HOST: str | None = os.environ.get("HR_SMTP_HOST") or None
SMTP_PORT: int = int(os.environ.get("HR_SMTP_PORT") or "587")
SMTP_USER: str | None = os.environ.get("HR_SMTP_USER") or None
SMTP_PASSWORD: str | None = os.environ.get("HR_SMTP_PASSWORD") or None
SMTP_FROM: str = os.environ.get("HR_SMTP_FROM") or "alerts@hunter-radar.example"
SMTP_USE_TLS: bool = os.environ.get("HR_SMTP_USE_TLS", "1") == "1"

# 沙箱总开关:HR_PUSH_LIVE=1 时尝试真发;否则一律 skipped_sandbox
_PUSH_LIVE: bool = os.environ.get("HR_PUSH_LIVE") == "1"

# ---- VAPID(留待 m5t4 / 客户端订阅) ----------------------------------------
VAPID_PRIVATE_KEY: str | None = os.environ.get("HR_VAPID_PRIVATE_KEY") or None
VAPID_PUBLIC_KEY: str | None = os.environ.get("HR_VAPID_PUBLIC_KEY") or None
VAPID_CLAIMS_EMAIL: str = (
    os.environ.get("HR_VAPID_CLAIMS_EMAIL") or "admin@hunter-radar.example"
)

# 沙箱中:无 pywebpush → _HAS_PYWEBPUSH = False
try:
    from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

    _HAS_PYWEBPUSH = True
except ImportError:  # noqa: BLE001
    _HAS_PYWEBPUSH = False
    WebPushException = Exception  # type: ignore[assignment,misc]


# ---- email 通道 ------------------------------------------------------------


def send_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """发邮件;沙箱 / 失败均返 dict(不抛)。

    Returns:
        {
          "channel": "email",
          "status": "sent" | "skipped_sandbox" | "failed",
          "provider_msg_id": str | None,
          "error": str | None,
          "to": str,
        }
    """
    if not _PUSH_LIVE or not SMTP_HOST:
        log.info(
            "[push.email] skipped (sandbox/live-off) to=%s subject=%r",
            to,
            subject,
        )
        return {
            "channel": "email",
            "status": "skipped_sandbox",
            "provider_msg_id": None,
            "error": None,
            "to": to,
        }

    # 真发路径
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=timeout) as srv:
            srv.ehlo()
            if SMTP_USE_TLS:
                srv.starttls(context=ctx)
                srv.ehlo()
            if SMTP_USER and SMTP_PASSWORD:
                srv.login(SMTP_USER, SMTP_PASSWORD)
            srv.sendmail(SMTP_FROM, [to], msg.as_string())
        msg_id = f"smtp-{int(time.time() * 1000)}"
        log.info(
            "[push.email] sent to=%s subject=%r id=%s", to, subject, msg_id
        )
        return {
            "channel": "email",
            "status": "sent",
            "provider_msg_id": msg_id,
            "error": None,
            "to": to,
        }
    except Exception as e:  # noqa: BLE001
        # 故意不抛,alert_event 必须落,不能因推送失败整条 eval 失败
        log.warning(
            "[push.email] failed to=%s err=%s: %s", to, type(e).__name__, e
        )
        return {
            "channel": "email",
            "status": "failed",
            "provider_msg_id": None,
            "error": f"{type(e).__name__}: {e}",
            "to": to,
        }


# ---- webpush 通道(m5t4) ---------------------------------------------------


def send_webpush(
    subscription: dict[str, Any],
    title: str,
    body: str,
    *,
    url: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """发 Web Push 通知(需 pywebpush + VAPID)。

    Args:
        subscription: 标准 PushSubscription JSON:
            {"endpoint": "https://...", "keys": {"p256dh": "...", "auth": "..."}}
        title: 通知标题
        body: 通知正文
        url: 点击后跳转 URL(可选,前端自行处理)
        timeout: HTTP 超时(秒)

    Returns:
        {
          "channel": "webpush",
          "status": "sent" | "skipped_sandbox" | "failed",
          "provider_msg_id": str | None,
          "error": str | None,
          "endpoint_prefix": str (前 80 字符,不外泄)
        }
    """
    endpoint = (subscription or {}).get("endpoint", "")
    endpoint_prefix = endpoint[:80]

    if not _PUSH_LIVE or not _HAS_PYWEBPUSH or not VAPID_PRIVATE_KEY:
        log.info(
            "[push.webpush] skipped (sandbox/no-pywebpush/no-vapid) endpoint=%r",
            endpoint_prefix,
        )
        return {
            "channel": "webpush",
            "status": "skipped_sandbox",
            "provider_msg_id": None,
            "error": None,
            "endpoint_prefix": endpoint_prefix,
        }

    # 真发路径
    payload = {"title": title, "body": body}
    if url:
        payload["url"] = url
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": f"mailto:{VAPID_CLAIMS_EMAIL}",
            },
            timeout=timeout,
        )
        msg_id = f"wp-{int(time.time() * 1000)}"
        log.info(
            "[push.webpush] sent endpoint=%r id=%s", endpoint_prefix, msg_id
        )
        return {
            "channel": "webpush",
            "status": "sent",
            "provider_msg_id": msg_id,
            "error": None,
            "endpoint_prefix": endpoint_prefix,
        }
    except WebPushException as e:  # type: ignore[misc]
        # 410 Gone:订阅失效,需要从 DB 删(留给 API 层处理)
        log.warning(
            "[push.webpush] WebPushException endpoint=%r err=%s",
            endpoint_prefix,
            e,
        )
        return {
            "channel": "webpush",
            "status": "failed",
            "provider_msg_id": None,
            "error": f"WebPushException: {e}",
            "endpoint_prefix": endpoint_prefix,
        }
    except Exception as e:  # noqa: BLE001
        log.warning(
            "[push.webpush] failed endpoint=%r err=%s: %s",
            endpoint_prefix,
            type(e).__name__,
            e,
        )
        return {
            "channel": "webpush",
            "status": "failed",
            "provider_msg_id": None,
            "error": f"{type(e).__name__}: {e}",
            "endpoint_prefix": endpoint_prefix,
        }


# ---- 聚合 dispatch ---------------------------------------------------------


def dispatch_event(
    channels: list[str],
    recipient_email: str | None,
    event_payload: dict[str, Any],
    *,
    recipient_subscriptions: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """按 channels 列表分发推送,聚合成 alert_event.delivery_status dict。

    支持的 channel:
    - "email"    → send_email,需 recipient_email
    - "log"      → 写 log.info,status=sent(本地调试用)
    - "silent"   → 静默,status=sent(不写日志不推)
    - "webpush"  → 遍历 recipient_subscriptions 调 send_webpush(m5t4 落地)
    - 其它       → status=unsupported_channel

    返回 dict 的结构:
    - 单实例 channel: out["email"] = {channel, status, ...}
    - webpush 多订阅: out["webpush"] = {
          "channel": "webpush",
          "status": "<聚合状态: sent_all | sent_partial | skipped_sandbox | failed_all>",
          "count": N,
          "sent": X,
          "results": [send_webpush 的返回, ...]
        }
    """
    out: dict[str, dict[str, Any]] = {}
    subject = _render_subject(event_payload)
    body_text = _render_body(event_payload)

    for raw_ch in channels:
        ch = (raw_ch or "").strip().lower()
        if not ch:
            continue
        if ch == "email":
            if not recipient_email:
                out[ch] = {
                    "channel": "email",
                    "status": "skipped_no_recipient",
                    "error": "user has no email on file",
                }
                continue
            out[ch] = send_email(
                to=recipient_email,
                subject=subject,
                body_text=body_text,
            )
        elif ch == "log":
            log.info(
                "[push.log] rule_id=%s ticker=%s ema=%s lifecycle=%s",
                event_payload.get("rule_id"),
                event_payload.get("ticker"),
                event_payload.get("ema_score"),
                event_payload.get("lifecycle"),
            )
            out[ch] = {"channel": "log", "status": "sent", "error": None}
        elif ch == "silent":
            out[ch] = {"channel": "silent", "status": "sent", "error": None}
        elif ch in ("webpush", "push"):
            subs = recipient_subscriptions or []
            if not subs:
                out[ch] = {
                    "channel": ch,
                    "status": "skipped_no_subscriptions",
                    "error": "user has no push subscriptions on file",
                }
                continue
            results = [
                send_webpush(
                    subscription=s,
                    title=subject,
                    body=body_text,
                )
                for s in subs
            ]
            statuses = {r["status"] for r in results}
            if statuses == {"sent"}:
                agg = "sent_all"
            elif statuses == {"skipped_sandbox"}:
                agg = "skipped_sandbox"
            elif "sent" in statuses and (
                "failed" in statuses or "skipped_sandbox" in statuses
            ):
                agg = "sent_partial"
            elif statuses == {"failed"}:
                agg = "failed_all"
            else:
                agg = "mixed"
            out[ch] = {
                "channel": ch,
                "status": agg,
                "count": len(results),
                "sent": sum(1 for r in results if r["status"] == "sent"),
                "results": results,
            }
        else:
            out[ch] = {
                "channel": ch,
                "status": "unsupported_channel",
                "error": f"unknown channel: {raw_ch!r}",
            }
    return out


# ---- 模板渲染(plain text 极简版) -------------------------------------------


def _render_subject(p: dict[str, Any]) -> str:
    ticker = p.get("ticker") or "?"
    score = p.get("ema_score")
    lifecycle = p.get("lifecycle") or "?"
    return (
        f"[Hunter Radar] {ticker} 触发预警 "
        f"(score={score}, lifecycle={lifecycle})"
    )


def _render_body(p: dict[str, Any]) -> str:
    return (
        "Hunter Radar 预警触发\n"
        "\n"
        f"  Ticker:     {p.get('ticker')}\n"
        f"  Trade date: {p.get('trade_date')}\n"
        f"  Rule id:    {p.get('rule_id')}\n"
        f"  EMA score:  {p.get('ema_score')}\n"
        f"  Raw score:  {p.get('raw_score')}\n"
        f"  Lifecycle:  {p.get('lifecycle')}\n"
        f"  Rationale:  {p.get('rationale')}\n"
        "\n"
        "—— 本邮件为系统通知,严禁构成投资建议(BD-075 鉴权发送)。\n"
        "—— Hunter Radar v1.4\n"
    )


__all__ = ["send_email", "send_webpush", "dispatch_event"]
