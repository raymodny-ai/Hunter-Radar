"""§6 m5t3 BD-074 邮件推送自测(沙箱友好)。

push.py 不依赖 PG / Redis / app.core.config,纯标准库 + env。
沙箱模式(HR_PUSH_LIVE != 1 或 SMTP_HOST 未设)→ 全部 skipped_sandbox,
绝无外网请求。

测点(12):
01  send_email 沙箱(无 HR_PUSH_LIVE,无 SMTP_HOST)→ skipped_sandbox
02  send_email 沙箱(有 SMTP_HOST 但 HR_PUSH_LIVE 不开)→ skipped_sandbox
03  send_email 沙箱(HR_PUSH_LIVE=1 但无 SMTP_HOST)→ skipped_sandbox(双保险)
04  dispatch_event channels=["email"] + recipient → delivery_status[email] skipped_sandbox
05  dispatch_event channels=[] → 返空 dict
06  dispatch_event channels=["log"] → status=sent
07  dispatch_event channels=["silent"] → status=sent
08  dispatch_event channels=["webpush"] → skipped_not_implemented
09  dispatch_event channels=["unknown_xxx"] → unsupported_channel
10  dispatch_event channels=["email"] + recipient=None → skipped_no_recipient
11  dispatch_event 5 通道混合 → 5 个 keys 都在(全 JSON 兼容)
12  _render_subject / _render_body 包含 ticker / score / lifecycle
"""
from __future__ import annotations

import importlib
import json
import os
import sys

# 沙箱断网:清掉可能的环境变量,保证走 skipped_sandbox
for _k in (
    "HR_PUSH_LIVE",
    "HR_SMTP_HOST",
    "HR_SMTP_PORT",
    "HR_SMTP_USER",
    "HR_SMTP_PASSWORD",
    "HR_SMTP_FROM",
    "HR_SMTP_USE_TLS",
):
    os.environ.pop(_k, None)

# 把 backend/ 加入 sys.path 以便 import app.services.push
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import app.services.push as push  # noqa: E402

# import 后,因为 push.py 在模块级读 env,若想测"有 SMTP_HOST 但无 LIVE"需 reload
# 测 02 单独 reload 用

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


def t01_sandbox_default() -> None:
    out = push.send_email("a@b.com", "subj", "body")
    assert out["channel"] == "email"
    assert out["status"] == "skipped_sandbox"
    assert out["provider_msg_id"] is None
    assert out["error"] is None
    assert out["to"] == "a@b.com"


def t02_smtp_set_but_live_off() -> None:
    # 模拟:HR_SMTP_HOST 已设,但 HR_PUSH_LIVE 未开
    os.environ["HR_SMTP_HOST"] = "smtp.example.com"
    os.environ["HR_SMTP_PORT"] = "587"
    importlib.reload(push)
    out = push.send_email("a@b.com", "subj", "body")
    assert out["status"] == "skipped_sandbox", f"got {out['status']}"
    # 清理
    del os.environ["HR_SMTP_HOST"]
    del os.environ["HR_SMTP_PORT"]
    importlib.reload(push)


def t03_live_on_but_no_host() -> None:
    # HR_PUSH_LIVE=1 但 SMTP_HOST 未设
    os.environ["HR_PUSH_LIVE"] = "1"
    importlib.reload(push)
    out = push.send_email("a@b.com", "subj", "body")
    assert out["status"] == "skipped_sandbox", f"got {out['status']}"
    del os.environ["HR_PUSH_LIVE"]
    importlib.reload(push)


def t04_dispatch_email_with_recipient() -> None:
    out = push.dispatch_event(
        channels=["email"],
        recipient_email="user@example.com",
        event_payload={
            "ticker": "AAPL",
            "ema_score": 75.0,
            "lifecycle": "red",
            "trade_date": "2026-06-15",
            "rationale": "score>=70",
        },
    )
    assert "email" in out
    assert out["email"]["status"] == "skipped_sandbox"
    assert out["email"]["to"] == "user@example.com"


def t05_dispatch_empty_channels() -> None:
    out = push.dispatch_event(
        channels=[],
        recipient_email="user@example.com",
        event_payload={"ticker": "AAPL"},
    )
    assert out == {}, f"expected empty dict, got {out}"


def t06_dispatch_log_channel() -> None:
    out = push.dispatch_event(
        channels=["log"],
        recipient_email=None,
        event_payload={"ticker": "TSLA", "ema_score": 80.0, "lifecycle": "red"},
    )
    assert "log" in out
    assert out["log"]["status"] == "sent"
    assert out["log"]["error"] is None


def t07_dispatch_silent_channel() -> None:
    out = push.dispatch_event(
        channels=["silent"],
        recipient_email=None,
        event_payload={"ticker": "TSLA"},
    )
    assert "silent" in out
    assert out["silent"]["status"] == "sent"
    assert out["silent"]["error"] is None


def t08_dispatch_webpush_no_subscriptions() -> None:
    # m5t4 演进:webpush 通道实际落地,无订阅时 status=skipped_no_subscriptions
    out = push.dispatch_event(
        channels=["webpush"],
        recipient_email=None,
        event_payload={"ticker": "TSLA"},
    )
    assert "webpush" in out
    assert out["webpush"]["status"] == "skipped_no_subscriptions"
    # 错误信息中文或英文都 OK(回退兼容)
    err = out["webpush"].get("error", "")
    assert "no push subscriptions" in err or "无订阅" in err or "m5t4" in err, (
        f"unexpected error string: {err!r}"
    )


def t09_dispatch_unknown_channel() -> None:
    out = push.dispatch_event(
        channels=["unknown_xxx"],
        recipient_email=None,
        event_payload={"ticker": "TSLA"},
    )
    assert "unknown_xxx" in out
    assert out["unknown_xxx"]["status"] == "unsupported_channel"
    assert "unknown_xxx" in out["unknown_xxx"]["error"]


def t10_dispatch_email_no_recipient() -> None:
    out = push.dispatch_event(
        channels=["email"],
        recipient_email=None,
        event_payload={"ticker": "TSLA"},
    )
    assert out["email"]["status"] == "skipped_no_recipient"
    assert out["email"]["error"] is not None


def t11_dispatch_mixed_channels_json_safe() -> None:
    out = push.dispatch_event(
        channels=["email", "log", "silent", "webpush", "unknown_xxx"],
        recipient_email="u@e.com",
        event_payload={"ticker": "MIX", "ema_score": 70, "lifecycle": "yellow"},
    )
    assert set(out.keys()) == {"email", "log", "silent", "webpush", "unknown_xxx"}
    # 必须能 JSON 序列化(alert_event.delivery_status 是 JSONB)
    blob = json.dumps(out, ensure_ascii=False)
    assert "email" in blob and "log" in blob
    # 5 个状态值都不同(确认 dispatch 走对了分支)
    statuses = {out[k]["status"] for k in out}
    # m5t4 演进后:webpush(无订阅) 走 skipped_no_subscriptions
    assert statuses == {
        "skipped_sandbox",  # email
        "sent",  # log + silent(去重)
        "skipped_no_subscriptions",  # webpush 无订阅
        "unsupported_channel",  # unknown_xxx
    }


def t12_template_contains_payload() -> None:
    p = {
        "ticker": "AAPL",
        "ema_score": 77.5,
        "lifecycle": "red",
        "trade_date": "2026-06-15",
        "rationale": "score>=70",
        "rule_id": 42,
    }
    subj = push._render_subject(p)
    body = push._render_body(p)
    assert "AAPL" in subj
    assert "77.5" in subj
    assert "red" in subj
    assert "AAPL" in body
    assert "2026-06-15" in body
    assert "score>=70" in body
    assert "42" in body
    # 合规文案收口(CR-010):禁止"建议买入"等出现在 body
    for forbidden in ("建议买入", "建议卖出", "建仓时机", "清仓", "必涨", "必跌"):
        assert forbidden not in body, f"forbidden word {forbidden!r} in body"


# ---- 汇总 ------------------------------------------------------------------


def main() -> int:
    tests = [
        ("01_sandbox_default", t01_sandbox_default),
        ("02_smtp_set_but_live_off", t02_smtp_set_but_live_off),
        ("03_live_on_but_no_host", t03_live_on_but_no_host),
        ("04_dispatch_email_with_recipient", t04_dispatch_email_with_recipient),
        ("05_dispatch_empty_channels", t05_dispatch_empty_channels),
        ("06_dispatch_log_channel", t06_dispatch_log_channel),
        ("07_dispatch_silent_channel", t07_dispatch_silent_channel),
        ("08_dispatch_webpush_no_subscriptions", t08_dispatch_webpush_no_subscriptions),
        ("09_dispatch_unknown_channel", t09_dispatch_unknown_channel),
        ("10_dispatch_email_no_recipient", t10_dispatch_email_no_recipient),
        ("11_dispatch_mixed_channels_json_safe", t11_dispatch_mixed_channels_json_safe),
        ("12_template_contains_payload", t12_template_contains_payload),
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
        print(f"[m5t3] FAILED {len(fail)} / {len(_RESULTS)}")
        return 1
    print(f"[m5t3] ALL {len(_RESULTS)} PUSH TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
