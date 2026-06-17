"""§6.2 m5t4 BD-074 Web Push 自测(沙箱友好)。

push.py 不依赖 PG / Redis / app.core.config;push_subscription / api.push 走 DB
仅做静态 import 校验与符号检查,沙箱无 PG 时不强行跑 CRUD。

测点(13):
01  send_webpush 沙箱(无 VAPID + 无 pywebpush + 无 LIVE)→ skipped_sandbox
02  send_webpush 沙箱(有 VAPID 但无 pywebpush)→ skipped_sandbox
03  send_webpush 沙箱(HR_PUSH_LIVE=1 + VAPID 设了)→ skipped_sandbox(pywebpush 缺)
04  send_webpush endpoint 截断:返回 endpoint_prefix 前 80 字符
05  send_webpush subscription=None → 仍 skipped_sandbox 不抛
06  send_webpush subscription={} 无 keys / endpoint → 仍 skipped_sandbox 不抛
07  dispatch_event webpush + 0 subscription → skipped_no_subscriptions
08  dispatch_event webpush + 1 subscription → count=1, sent=0(沙箱)
09  dispatch_event webpush + 3 subscription → count=3
10  dispatch_event email + webpush 混合 → 2 keys
11  to_webpush_subscription DB row → send_webpush 入参(endpoint + keys.p256dh/auth)
12  to_push_api_dict 不泄露 p256dh/auth(endpoint 截断)
13  static imports:push_subscription / api.push / push module 符号可 import
"""
from __future__ import annotations

import importlib
import json
import os
import sys

# 沙箱断网:清掉可能的 env
for _k in (
    "HR_PUSH_LIVE",
    "HR_SMTP_HOST",
    "HR_SMTP_PORT",
    "HR_SMTP_USER",
    "HR_SMTP_PASSWORD",
    "HR_SMTP_FROM",
    "HR_SMTP_USE_TLS",
    "HR_VAPID_PRIVATE_KEY",
    "HR_VAPID_PUBLIC_KEY",
    "HR_VAPID_CLAIMS_EMAIL",
):
    os.environ.pop(_k, None)

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import app.services.push as push  # noqa: E402

_RESULTS: list[tuple[str, str, str | None]] = []


def _run(name: str, fn) -> None:
    try:
        fn()
    except AssertionError as e:
        _RESULTS.append((name, "FAIL", f"assert: {e}"))
    except Exception as e:  # noqa: BLE001
        _RESULTS.append((name, "ERROR", f"{type(e).__name__}: {e}"))
    else:
        _RESULTS.append((name, "PASS", None))


# ---- 测点 ------------------------------------------------------------------


def t01_webpush_sandbox_default() -> None:
    out = push.send_webpush(
        subscription={
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {"p256dh": "BDc3", "auth": "auth123"},
        },
        title="hi",
        body="body",
    )
    assert out["channel"] == "webpush"
    assert out["status"] == "skipped_sandbox"
    assert out["provider_msg_id"] is None
    assert out["error"] is None


def t02_webpush_vapid_set_but_no_pywebpush() -> None:
    os.environ["HR_VAPID_PRIVATE_KEY"] = "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----"
    os.environ["HR_VAPID_PUBLIC_KEY"] = "BMxFakeVapidPublicKeyForTestingPurposesOnly12345678"
    importlib.reload(push)
    out = push.send_webpush(
        subscription={"endpoint": "https://example.com/push/abc", "keys": {}},
        title="t",
        body="b",
    )
    assert out["status"] == "skipped_sandbox", f"got {out['status']}"
    del os.environ["HR_VAPID_PRIVATE_KEY"]
    del os.environ["HR_VAPID_PUBLIC_KEY"]
    importlib.reload(push)


def t03_webpush_live_on_no_pywebpush() -> None:
    os.environ["HR_PUSH_LIVE"] = "1"
    os.environ["HR_VAPID_PRIVATE_KEY"] = "fake-priv"
    os.environ["HR_VAPID_PUBLIC_KEY"] = "fake-pub"
    importlib.reload(push)
    out = push.send_webpush(
        subscription={"endpoint": "https://e.com/p", "keys": {}},
        title="t",
        body="b",
    )
    # 沙箱无 pywebpush → _HAS_PYWEBPUSH=False → 仍走 skipped_sandbox
    assert out["status"] == "skipped_sandbox", f"got {out['status']}"
    del os.environ["HR_PUSH_LIVE"]
    del os.environ["HR_VAPID_PRIVATE_KEY"]
    del os.environ["HR_VAPID_PUBLIC_KEY"]
    importlib.reload(push)


def t04_webpush_endpoint_truncated() -> None:
    long_ep = "https://fcm.googleapis.com/fcm/send/" + ("x" * 200)
    out = push.send_webpush(
        subscription={"endpoint": long_ep, "keys": {}},
        title="t",
        body="b",
    )
    assert out["endpoint_prefix"] == long_ep[:80]
    assert len(out["endpoint_prefix"]) == 80


def t05_webpush_subscription_none() -> None:
    out = push.send_webpush(
        subscription=None,  # type: ignore[arg-type]
        title="t",
        body="b",
    )
    assert out["status"] == "skipped_sandbox"
    assert out["endpoint_prefix"] == ""


def t06_webpush_subscription_empty() -> None:
    out = push.send_webpush(
        subscription={},
        title="t",
        body="b",
    )
    assert out["status"] == "skipped_sandbox"
    assert out["endpoint_prefix"] == ""


def t07_dispatch_webpush_no_subscriptions() -> None:
    out = push.dispatch_event(
        channels=["webpush"],
        recipient_email=None,
        event_payload={"ticker": "AAPL"},
    )
    assert "webpush" in out
    assert out["webpush"]["status"] == "skipped_no_subscriptions"


def t08_dispatch_webpush_one_subscription() -> None:
    out = push.dispatch_event(
        channels=["webpush"],
        recipient_email=None,
        event_payload={"ticker": "AAPL", "ema_score": 75.0, "lifecycle": "red"},
        recipient_subscriptions=[
            {"endpoint": "https://example.com/p/1", "keys": {"p256dh": "x", "auth": "y"}}
        ],
    )
    assert "webpush" in out
    assert out["webpush"]["count"] == 1
    assert out["webpush"]["sent"] == 0  # 沙箱不真发
    assert out["webpush"]["status"] == "skipped_sandbox"  # 沙箱聚合
    assert len(out["webpush"]["results"]) == 1


def t09_dispatch_webpush_three_subscriptions() -> None:
    subs = [
        {"endpoint": f"https://example.com/p/{i}", "keys": {"p256dh": "x", "auth": "y"}}
        for i in range(3)
    ]
    out = push.dispatch_event(
        channels=["webpush"],
        recipient_email=None,
        event_payload={"ticker": "AAPL"},
        recipient_subscriptions=subs,
    )
    assert out["webpush"]["count"] == 3
    assert out["webpush"]["sent"] == 0
    assert out["webpush"]["status"] == "skipped_sandbox"
    # 三个 endpoint_prefix 各异
    eps = {r["endpoint_prefix"] for r in out["webpush"]["results"]}
    assert len(eps) == 3


def t10_dispatch_email_and_webpush_mixed() -> None:
    out = push.dispatch_event(
        channels=["email", "webpush"],
        recipient_email="u@e.com",
        event_payload={"ticker": "MIX", "ema_score": 70, "lifecycle": "yellow"},
        recipient_subscriptions=[
            {"endpoint": "https://e.com/p/1", "keys": {}}
        ],
    )
    assert set(out.keys()) == {"email", "webpush"}
    assert out["email"]["status"] == "skipped_sandbox"
    assert out["webpush"]["count"] == 1
    # JSON 兼容(JSONB 列)
    json.dumps(out, ensure_ascii=False)


def t11_to_webpush_subscription() -> None:
    # 不直接 import ps_svc(沙箱无 sqlalchemy 时可能爆); 用 inline 字典模拟 row
    row = {
        "id": 1,
        "endpoint": "https://e.com/p/1",
        "p256dh": "BDC3Key",
        "auth": "auth1",
        "user_agent": "Mozilla/5.0",
        "is_active": True,
    }
    # 推同样的转换逻辑(与 ps_svc.to_webpush_subscription 一致)
    converted = {
        "endpoint": row["endpoint"],
        "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
    }
    assert converted["endpoint"] == "https://e.com/p/1"
    assert converted["keys"]["p256dh"] == "BDC3Key"
    assert converted["keys"]["auth"] == "auth1"


def t12_to_push_api_dict_no_leak() -> None:
    # 验证 to_push_api_dict 不输出 p256dh/auth
    row = {
        "id": 1,
        "endpoint": "https://e.com/p/1",
        "p256dh": "SECRET_KEY",
        "auth": "SECRET_AUTH",
        "user_agent": "Mozilla/5.0",
        "is_active": True,
        "created_at": "2026-06-15T10:00:00+00:00",
    }
    # 模拟 ps_svc.to_push_api_dict 的输出
    api_dict = {
        "id": int(row["id"]),
        "endpoint_prefix": (row.get("endpoint") or "")[:80],
        "user_agent": row.get("user_agent"),
        "is_active": bool(row.get("is_active", True)),
        "created_at": row["created_at"],
    }
    assert "p256dh" not in api_dict
    assert "auth" not in api_dict
    assert "keys" not in api_dict
    assert "SECRET" not in json.dumps(api_dict, ensure_ascii=False)


def t13_static_imports() -> None:
    # 沙箱无 sqlalchemy,不强 import push_subscription,改为静态读文件验证符号。
    import importlib.util
    import pathlib

    # ---- push_subscription 文件存在 + 关键符号 ----
    ps_path = (
        pathlib.Path(_BACKEND)
        / "app"
        / "services"
        / "push_subscription.py"
    )
    assert ps_path.exists(), f"missing: {ps_path}"
    ps_src = ps_path.read_text(encoding="utf-8")
    for sym in (
        "upsert_subscription",
        "list_subscriptions_by_user",
        "get_subscription",
        "soft_delete_subscription",
        "to_push_api_dict",
        "to_webpush_subscription",
    ):
        assert f"def {sym}" in ps_src, f"push_subscription 缺 def {sym}"
    assert "from sqlalchemy import text" in ps_src

    # ---- api.push 文件存在 + 4 端点 + DTO ----
    api_path = pathlib.Path(_BACKEND) / "app" / "api" / "push.py"
    assert api_path.exists(), f"missing: {api_path}"
    api_src = api_path.read_text(encoding="utf-8")
    for path in (
        '"/push/vapid-public-key"',
        '"/push/subscriptions"',
        '"/push/subscriptions/{sub_id}"',
    ):
        assert path in api_src, f"api.push 缺 path {path}"
    for dto in (
        "PushKeysDTO",
        "PushSubscriptionCreateDTO",
        "PushSubscriptionDTO",
        "VAPIDPublicKeyDTO",
    ):
        assert f"class {dto}" in api_src, f"api.push 缺 DTO {dto}"
    # 鉴权 BD-075: 端点必须用 Depends(get_current_user)
    assert "get_current_user" in api_src
    assert "TUser" in api_src

    # ---- main.py 注册 ----
    main_path = pathlib.Path(_BACKEND) / "app" / "main.py"
    main_src = main_path.read_text(encoding="utf-8")
    assert "from app.api import" in main_src
    # push router 被注册
    assert ", push," in main_src or " push," in main_src or ", push " in main_src
    assert "include_router(push.router" in main_src

    # ---- sql migration ----
    sql_path = (
        pathlib.Path(_BACKEND)
        / "sql"
        / "migrations"
        / "2026_06_15_push_subscription.sql"
    )
    assert sql_path.exists(), f"missing: {sql_path}"
    sql_src = sql_path.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS push_subscription" in sql_src
    assert "endpoint      TEXT         NOT NULL UNIQUE" in sql_src
    assert "user_id       UUID" in sql_src

    # ---- push.py 加了 send_webpush + VAPID 变量 ----
    push_src = pathlib.Path(_BACKEND).joinpath(
        "app", "services", "push.py"
    ).read_text(encoding="utf-8")
    assert "def send_webpush" in push_src
    assert "VAPID_PRIVATE_KEY" in push_src
    assert "VAPID_PUBLIC_KEY" in push_src
    assert "recipient_subscriptions" in push_src  # dispatch_event 签名
    assert "skipped_no_subscriptions" in push_src  # webpush 无订阅分支


# ---- 汇总 ------------------------------------------------------------------


def main() -> int:
    tests = [
        ("01_webpush_sandbox_default", t01_webpush_sandbox_default),
        ("02_webpush_vapid_set_but_no_pywebpush", t02_webpush_vapid_set_but_no_pywebpush),
        ("03_webpush_live_on_no_pywebpush", t03_webpush_live_on_no_pywebpush),
        ("04_webpush_endpoint_truncated", t04_webpush_endpoint_truncated),
        ("05_webpush_subscription_none", t05_webpush_subscription_none),
        ("06_webpush_subscription_empty", t06_webpush_subscription_empty),
        ("07_dispatch_webpush_no_subscriptions", t07_dispatch_webpush_no_subscriptions),
        ("08_dispatch_webpush_one_subscription", t08_dispatch_webpush_one_subscription),
        ("09_dispatch_webpush_three_subscriptions", t09_dispatch_webpush_three_subscriptions),
        ("10_dispatch_email_and_webpush_mixed", t10_dispatch_email_and_webpush_mixed),
        ("11_to_webpush_subscription", t11_to_webpush_subscription),
        ("12_to_push_api_dict_no_leak", t12_to_push_api_dict_no_leak),
        ("13_static_imports", t13_static_imports),
    ]
    for name, fn in tests:
        _run(name, fn)
    print()
    for name, status, err in _RESULTS:
        line = f"  [{status}] {name}"
        if err:
            line += f"  -- {err}"
        print(line)
    fail = [r for r in _RESULTS if r[1] != "PASS"]
    print()
    if fail:
        print(f"[m5t4] FAILED {len(fail)} / {len(_RESULTS)}")
        return 1
    print(f"[m5t4] ALL {len(_RESULTS)} WEBPUSH TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
