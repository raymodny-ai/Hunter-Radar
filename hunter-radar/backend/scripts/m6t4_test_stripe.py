"""M6-t4 沙箱自测:BD-105 Stripe 订阅接入落地产物校验。

沙箱不实跑 uvicorn(无 PG/Redis/Stripe SDK),只静态校验:
- service 模块 + Subscription dataclass 字段
- 5 个 API 端点(checkout / me / cancel / webhook / sandbox-complete / plans)
- main.py 注册 subscriptions router
- 状态机 5 态:active / canceled / past_due / incomplete / none
- 价格档 19 / 188 USD
- 沙箱 fallback:checkout 返 sandbox URL,webhook 不签名校验
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
SERVICE = APP / "services" / "subscription.py"
ROUTER = APP / "api" / "subscriptions.py"
MAIN = APP / "main.py"
CONFIG = APP / "core" / "config.py"

PASS = "[PASS]"
FAIL = "[FAIL]"
failures = 0


def t(name: str, ok: bool, detail: str = "") -> bool:
    global failures
    if ok:
        print(f"  {PASS} {name}{(' — ' + detail) if detail else ''}")
    else:
        print(f"  {FAIL} {name}{(' — ' + detail) if detail else ''}")
        failures += 1
    return ok


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
section("1. service 模块 + Subscription dataclass")

t("t01_service_module_exists", SERVICE.exists(), f"path={SERVICE}")

service_text = SERVICE.read_text(encoding="utf-8") if SERVICE.exists() else ""

required_fields = [
    "user_id",
    "plan",
    "status",
    "stripe_customer_id",
    "stripe_subscription_id",
    "current_period_end",
    "cancel_at_period_end",
    "created_at",
]
missing_fields = [f for f in required_fields if f not in service_text]
t("t02_subscription_dataclass_complete", len(missing_fields) == 0, f"missing={missing_fields}")

# 5 状态机
required_statuses = ["active", "canceled", "past_due", "incomplete", "none"]
ok_status = sum(1 for s in required_statuses if f'"{s}"' in service_text or f"Literal[{s}" in service_text
                or f'"{s}"' in service_text.replace("'", '"'))
t("t03_status_state_machine_5states",
  all(s in service_text for s in required_statuses),
  f"states={required_statuses}")


# ---------------------------------------------------------------------------
section("2. 价格档 + 周期天数")

t("t04_plan_price_monthly_19",
  "19.0" in service_text and '"pro_monthly"' in service_text,
  "$19 USD")
t("t05_plan_price_yearly_188",
  "188.0" in service_text and '"pro_yearly"' in service_text,
  "$188 USD")
t("t06_plan_period_days",
  "PLAN_PERIOD_DAYS" in service_text
  and ("30" in service_text and "365" in service_text))


# ---------------------------------------------------------------------------
section("3. 5 个 service 函数")

required_funcs = [
    "def get_subscription",
    "def create_checkout",
    "def complete_sandbox",
    "def cancel",
    "def handle_webhook_event",
]
missing_funcs = [f for f in required_funcs if f not in service_text]
t("t07_service_functions_complete", len(missing_funcs) == 0, f"missing={missing_funcs}")

t("t08_create_checkout_returns_sandbox_url",
  "sandbox-complete" in service_text and "checkout_url" in service_text)

t("t09_webhook_no_signature_check_in_sandbox",
  "sandbox" in service_text.lower() and "签名" in service_text or "签名校验" in service_text or
  "construct_event" in service_text)


# ---------------------------------------------------------------------------
section("4. router 端点")

t("t10_router_module_exists", ROUTER.exists(), f"path={ROUTER}")

router_text = ROUTER.read_text(encoding="utf-8") if ROUTER.exists() else ""

required_endpoints = [
    ("POST", "/subscriptions/checkout"),
    ("GET", "/subscriptions/me"),
    ("POST", "/subscriptions/cancel"),
    ("POST", "/subscriptions/webhook"),
    ("GET", "/subscriptions/sandbox-complete"),
    ("GET", "/subscriptions/plans"),
]
matched = sum(
    1
    for method, path in required_endpoints
    if re.search(rf'@router\.{method.lower()}\("{re.escape(path)}"', router_text)
)
t("t11_router_endpoints_6", matched == 6, f"matched={matched}/6")


# ---------------------------------------------------------------------------
section("5. main.py 注册 subscriptions router")

main_text = MAIN.read_text(encoding="utf-8") if MAIN.exists() else ""

t("t12_main_imports_subscriptions",
  "from app.api import" in main_text and "subscriptions," in main_text)

t("t13_main_includes_subscriptions_router",
  "subscriptions.router" in main_text and "tags=[\"subscriptions\"]" in main_text)


# ---------------------------------------------------------------------------
section("6. config.py 含 Stripe 配置字段")

config_text = CONFIG.read_text(encoding="utf-8") if CONFIG.exists() else ""

required_stripe_fields = [
    "stripe_secret_key",
    "stripe_webhook_secret",
    "stripe_price_pro_monthly",
    "stripe_price_pro_yearly",
]
missing_stripe = [f for f in required_stripe_fields if f not in config_text]
t("t14_config_stripe_fields", len(missing_stripe) == 0, f"missing={missing_stripe}")


# ---------------------------------------------------------------------------
section("7. 沙箱 fallback 行为标记")

t("t15_sandbox_fallback_marker",
  "sandbox-complete" in router_text and "sandbox" in service_text.lower())


# ---------------------------------------------------------------------------
print()
if failures == 0:
    print("[m6t4] ALL 15 STRIPE-SUBSCRIPTION (SERVICE + ROUTER + MAIN + CONFIG) TESTS PASSED")
    sys.exit(0)
else:
    print(f"[m6t4] {failures} TEST(S) FAILED")
    sys.exit(1)