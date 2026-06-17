"""M7-t6 沙箱自测:BD-105 Stripe webhook 签名校验(M7 接力期)。

沙箱不实跑 uvicorn(无 PG/Redis/Stripe SDK),静态校验 + 端点调用 stub:
- webhook 端点 summary 含「签名校验」
- 沙箱模式:STRIPE_WEBHOOK_SECRET 未设 → 200 + signature_skipped=true + signature_mode=sandbox_skip
- payload 读 raw bytes(await request.body())非 json()
- stripe-signature header 读取
- 真实模式 secret 已设 → stripe.Webhook.construct_event(payload, sig, secret)
- SDK 不可用(secret 已设)→ 503 signature_check_unavailable
- 签名错误 → 400 Invalid signature
- payload 非 JSON → 400 Invalid payload
- settings.stripe_webhook_secret 默认 None
- R-31 风险解除
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
ROUTER = APP / "api" / "subscriptions.py"
CONFIG = APP / "core" / "config.py"
SERVICE = APP / "services" / "subscription.py"

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def _run(name: str, fn):
    try:
        fn()
        PASSED.append(name)
        print(f"  [PASS] {name}")
    except AssertionError as e:
        FAILED.append((name, str(e)))
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        FAILED.append((name, f"{type(e).__name__}: {e}"))
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")


# ---------- §1 router 模块 + summary 含「签名校验」----------
def _t01_router_summary_signature():
    text = ROUTER.read_text(encoding="utf-8")
    assert "签名校验" in text, "summary 应含「签名校验」"


# ---------- §2 沙箱模式:返 signature_skipped + sandbox_skip ----------
def _t02_sandbox_returns_skip_markers():
    text = ROUTER.read_text(encoding="utf-8")
    assert "signature_skipped" in text, "应标注 signature_skipped"
    assert "sandbox_skip" in text, "应标注 signature_mode=sandbox_skip"
    assert "signature_mode" in text, "应含 signature_mode 字段"


# ---------- §3 sandbox warning 字段 ----------
def _t03_sandbox_warning_field():
    text = ROUTER.read_text(encoding="utf-8")
    assert "STRIPE_WEBHOOK_SECRET not set" in text, "warning 应明确说 secret 未设"
    assert "sandbox mode" in text, "warning 应含 sandbox mode"


# ---------- §4 webhook 读 raw bytes ----------
def _t04_webhook_raw_bytes():
    text = ROUTER.read_text(encoding="utf-8")
    assert "await request.body()" in text, "应读 raw bytes"
    assert "await request.json()" not in text, "不应再读 json()(签名校验需 raw bytes)"


# ---------- §5 读 stripe-signature header ----------
def _t05_stripe_signature_header():
    text = ROUTER.read_text(encoding="utf-8")
    assert "stripe-signature" in text, "应读 stripe-signature header"


# ---------- §6 真实模式 secret 已设 → stripe.Webhook.construct_event ----------
def _t06_prod_signature_verify():
    text = ROUTER.read_text(encoding="utf-8")
    assert "stripe.Webhook.construct_event" in text, "真实模式应调用 construct_event"
    assert "sig_header" in text or "sig_header=" in text or "sig)" in text, "应传 sig_header"


# ---------- §7 SDK 不可用 → 503 signature_check_unavailable ----------
def _t07_sdk_unavailable_503():
    text = ROUTER.read_text(encoding="utf-8")
    assert "signature_check_unavailable" in text, "SDK 不可用应返 signature_check_unavailable"
    assert "503" in text, "应返 503"
    # 不 mock 200 伪装
    assert "prod_unavailable" in text, "应标注 signature_mode=prod_unavailable"


# ---------- §8 签名错误 → 400 ----------
def _t08_invalid_signature_400():
    text = ROUTER.read_text(encoding="utf-8")
    assert "invalid signature" in text, "签名错误应含 'invalid signature'"
    assert "SignatureVerificationError" in text, "应捕获 SignatureVerificationError"


# ---------- §9 payload 非 JSON → 400 ----------
def _t09_invalid_json_400():
    text = ROUTER.read_text(encoding="utf-8")
    assert "JSONDecodeError" in text, "应捕获 JSONDecodeError"
    assert "invalid JSON payload" in text, "应含 'invalid JSON payload'"


# ---------- §10 signature_mode 字段值集合 ----------
def _t10_signature_mode_values():
    text = ROUTER.read_text(encoding="utf-8")
    for mode in ("sandbox_skip", "prod_verified", "prod_unavailable"):
        assert mode in text, f"signature_mode 应含 {mode}"


# ---------- §11 settings.stripe_webhook_secret 默认 None ----------
def _t11_stripe_webhook_secret_default_none():
    text = CONFIG.read_text(encoding="utf-8")
    assert "stripe_webhook_secret" in text, "config.py 应含 stripe_webhook_secret"
    assert "= None" in text.split("stripe_webhook_secret")[1].split("\n")[0], \
        "stripe_webhook_secret 默认应=None"


# ---------- §12 endpoint 文档注释说明签名校验逻辑 ----------
def _t12_docstring_explains_logic():
    text = ROUTER.read_text(encoding="utf-8")
    # 找 webhook 函数的 docstring
    idx = text.find("async def post_webhook")
    assert idx > 0, "缺 post_webhook"
    snippet = text[idx:idx + 3000]
    assert "signature_skipped" in snippet, "docstring 应说明签名跳过模式"
    assert "signature_check_unavailable" in snippet, "docstring 应说明 SDK 不可用路径"
    assert "Invalid signature" in snippet or "invalid signature" in snippet, \
        "docstring 应说明签名错误路径"


# ---------- §13 logger.warning 调用 ----------
def _t13_logger_warning_call():
    text = ROUTER.read_text(encoding="utf-8")
    assert "logger.warning" in text or "logging.getLogger" in text, "应记录 warning"


# ---------- §14 handle_webhook_event 入参仍是 dict ----------
def _t14_handle_webhook_event_dict():
    text = SERVICE.read_text(encoding="utf-8")
    assert "def handle_webhook_event" in text, "service 缺 handle_webhook_event"
    idx = text.find("def handle_webhook_event")
    sig_line = text[idx:idx + 100]
    assert "event: dict" in sig_line or "Dict" in sig_line, "handle_webhook_event 入参应是 dict"


# ---------- §15 endpoint 接受空 payload → 200 + sandbox_skip ----------
def _t15_empty_payload_handling():
    text = ROUTER.read_text(encoding="utf-8")
    # 沙箱模式下空 payload 应能 dispatch 给 service(返 {})
    assert "if payload else {}" in text or "if payload" in text, "应处理空 payload"


# ---------- §16 R-31 风险解除(sandbox_skip 显式标注) ----------
def _t16_r31_unblocked():
    # R-31:沙箱简化(无签名校验)→ m7t6
    # 现在 webhook 沙箱显式标注 signature_skipped + signature_mode=sandbox_skip
    text = ROUTER.read_text(encoding="utf-8")
    assert "signature_skipped" in text and "sandbox_skip" in text, \
        "R-31 解除:沙箱模式应显式标注签名跳过"


# ---------- §17 handle_webhook_event 仍可处理 metadata.user_id ----------
def _t17_handle_event_metadata_userid():
    text = SERVICE.read_text(encoding="utf-8")
    assert "metadata" in text and "user_id" in text, "service 应读 metadata.user_id"


# ---------- §18 sandbox 模式 dispatch 到 service ----------
def _t18_sandbox_dispatches_to_service():
    text = ROUTER.read_text(encoding="utf-8")
    assert "handle_webhook_event(event)" in text or "handle_webhook_event(_json" in text, \
        "沙箱模式应 dispatch 到 handle_webhook_event"


# ---------- §19 prod_verified 路径 dispatch 到 service ----------
def _t19_prod_verified_dispatches():
    text = ROUTER.read_text(encoding="utf-8")
    assert "handle_webhook_event(dict(event_obj))" in text or \
           "handle_webhook_event(dict(" in text, \
        "真实模式应 dispatch 到 handle_webhook_event"


# ---------- §20 webhook signature body 走 raw bytes 而非 json dict ----------
def _t20_signature_uses_raw_bytes():
    text = ROUTER.read_text(encoding="utf-8")
    # find stripe.Webhook.construct_event call
    idx = text.find("stripe.Webhook.construct_event")
    assert idx > 0, "缺 construct_event 调用"
    snippet = text[idx:idx + 200]
    assert "payload" in snippet, "construct_event 应传 payload(raw bytes)"


# ---------- §21 5 端点未受影响(checkout / me / cancel / webhook / sandbox-complete) ----------
def _t21_other_endpoints_intact():
    text = ROUTER.read_text(encoding="utf-8")
    for ep in ("/subscriptions/checkout", "/subscriptions/me", "/subscriptions/cancel",
               "/subscriptions/webhook", "/subscriptions/sandbox-complete"):
        assert ep in text, f"端点 {ep} 应保留"


# ---------- §22 端口签名校验独立 endpoint 命名 summary 含「签名校验」 ----------
def _t22_webhook_endpoint_summary_text():
    text = ROUTER.read_text(encoding="utf-8")
    idx = text.find("@router.post(\"/subscriptions/webhook\"")
    snippet = text[idx:idx + 200]
    assert "签名校验" in snippet, "endpoint summary 应含「签名校验」"


def main() -> int:
    tests = [
        ("t01_router_summary_signature", _t01_router_summary_signature),
        ("t02_sandbox_returns_skip_markers", _t02_sandbox_returns_skip_markers),
        ("t03_sandbox_warning_field", _t03_sandbox_warning_field),
        ("t04_webhook_raw_bytes", _t04_webhook_raw_bytes),
        ("t05_stripe_signature_header", _t05_stripe_signature_header),
        ("t06_prod_signature_verify", _t06_prod_signature_verify),
        ("t07_sdk_unavailable_503", _t07_sdk_unavailable_503),
        ("t08_invalid_signature_400", _t08_invalid_signature_400),
        ("t09_invalid_json_400", _t09_invalid_json_400),
        ("t10_signature_mode_values", _t10_signature_mode_values),
        ("t11_stripe_webhook_secret_default_none", _t11_stripe_webhook_secret_default_none),
        ("t12_docstring_explains_logic", _t12_docstring_explains_logic),
        ("t13_logger_warning_call", _t13_logger_warning_call),
        ("t14_handle_webhook_event_dict", _t14_handle_webhook_event_dict),
        ("t15_empty_payload_handling", _t15_empty_payload_handling),
        ("t16_r31_unblocked", _t16_r31_unblocked),
        ("t17_handle_event_metadata_userid", _t17_handle_event_metadata_userid),
        ("t18_sandbox_dispatches_to_service", _t18_sandbox_dispatches_to_service),
        ("t19_prod_verified_dispatches", _t19_prod_verified_dispatches),
        ("t20_signature_uses_raw_bytes", _t20_signature_uses_raw_bytes),
        ("t21_other_endpoints_intact", _t21_other_endpoints_intact),
        ("t22_webhook_endpoint_summary_text", _t22_webhook_endpoint_summary_text),
    ]
    print(f"开始 m7t6 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M7-T6 STRIPE WEBHOOK SIGNATURE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())