"""M6-t5 沙箱自测:FE-081 订阅页面(/subscribe 路由)落地产物校验。

沙箱不实跑 vite build(无 pnpm install),只静态校验:
- /subscribe 路由 + 3 档价格卡片(Free / Pro 月付 / Pro 年付)
- api.ts 加 4 个订阅方法(getPlans / postCheckout / getMySubscription / postCancelSubscription)
- 3 个 DTO 类型(PlanDTO / MySubscriptionDTO / CheckoutSessionDTO)
- __root.tsx 导航加 /subscribe 链接
- zh-CN.json 补 subscribe 翻译段 + routes.subscribe
- 沙箱 mock:checkout 后跳转 sandbox-complete 端点,自动落 active 订阅
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
ROUTES = SRC / "routes"
COMPONENTS = SRC / "components"
LIB = SRC / "lib"
I18N = SRC / "i18n" / "zh-CN.json"

ROUTE_FILE = ROUTES / "subscribe.tsx"
ROOT_TSX = ROUTES / "__root.tsx"
API_TS = LIB / "api.ts"

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
section("1. /subscribe 路由存在 + createRoute 注册")

t("t01_route_file_exists", ROUTE_FILE.exists(), f"path={ROUTE_FILE}")

route_text = ROUTE_FILE.read_text(encoding="utf-8") if ROUTE_FILE.exists() else ""

t("t02_route_create_route_registered",
  "createRoute" in route_text and "/subscribe" in route_text and "RootRoute" in route_text)

t("t03_route_component_export",
  "export const Route" in route_text and "component: SubscribePage" in route_text)


# ---------------------------------------------------------------------------
section("2. 3 档价格卡片 + Pro 月付 / Pro 年付字段")

required_features = [
    "pro_monthly",
    "pro_yearly",
    "subscribe.free",
    "subscribe.proMonthly",
    "subscribe.proYearly",
]
ok_features = sum(1 for k in required_features if k in route_text)
t("t04_3_plans_in_route", ok_features >= 4, f"matched={ok_features}/5")

t("t05_plans_use_query",
  'useQuery' in route_text and '["subscriptions", "plans"]' in route_text)

t("t06_me_use_query",
  '["subscriptions", "me"]' in route_text)

t("t07_checkout_mutation",
  "useMutation" in route_text and "postCheckout" in route_text)

t("t08_cancel_mutation",
  "useMutation" in route_text and "postCancelSubscription" in route_text)


# ---------------------------------------------------------------------------
section("3. api.ts 加 4 个订阅方法")

api_text = API_TS.read_text(encoding="utf-8") if API_TS.exists() else ""

required_methods = [
    "getPlans",
    "postCheckout",
    "getMySubscription",
    "postCancelSubscription",
]
missing_methods = [m for m in required_methods if m not in api_text]
t("t09_api_4_subscription_methods", len(missing_methods) == 0, f"missing={missing_methods}")

# 端点路径
required_paths = [
    "/subscriptions/plans",
    "/subscriptions/checkout",
    "/subscriptions/me",
    "/subscriptions/cancel",
]
missing_paths = [p for p in required_paths if p not in api_text]
t("t10_api_subscription_paths", len(missing_paths) == 0, f"missing={missing_paths}")

# 3 个 DTO 类型导出
required_dtos = ["PlanDTO", "MySubscriptionDTO", "CheckoutSessionDTO"]
missing_dtos = [d for d in required_dtos if f"export type {d}" not in api_text]
t("t11_api_3_subscription_dtos", len(missing_dtos) == 0, f"missing={missing_dtos}")


# ---------------------------------------------------------------------------
section("4. __root.tsx 导航加 /subscribe")

root_text = ROOT_TSX.read_text(encoding="utf-8") if ROOT_TSX.exists() else ""

t("t12_root_nav_subscribe_link",
  re.search(r'to="/subscribe"', root_text) is not None)

t("t13_root_translate_routes_subscribe",
  't("routes.subscribe")' in root_text)


# ---------------------------------------------------------------------------
section("5. zh-CN.json 补 subscribe 翻译段")


def _has_nested(obj: dict, dotted: str, sub: str) -> bool:
    """检查 i18n_obj[dotted_path] 含 sub 字符串。"""
    cur: object = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return False
        cur = cur.get(part)
    if isinstance(cur, str):
        return sub in cur
    if isinstance(cur, list):
        return any(sub in str(x) for x in cur)
    return False


i18n_text = I18N.read_text(encoding="utf-8") if I18N.exists() else ""
try:
    i18n_obj = json.loads(i18n_text)
except Exception as e:
    i18n_obj = {}
    print(f"  {FAIL} i18n_json_invalid — {e}")
    failures += 1

t("t14_i18n_routes_subscribe",
  i18n_obj.get("routes", {}).get("subscribe") is not None,
  f"value={i18n_obj.get('routes', {}).get('subscribe')}")

subscribe_obj = i18n_obj.get("subscribe", {})
required_subscribe_keys = [
    "title",
    "subtitle",
    "currentPlan",
    "cta",
    "cancelBtn",
    "free",
    "proMonthly",
    "proYearly",
]
missing_keys = [k for k in required_subscribe_keys if k not in subscribe_obj]
t("t15_i18n_subscribe_segment", len(missing_keys) == 0, f"missing={missing_keys}")

# 必备价格 / 周期关键词
required_keywords = {
    "title": "Pro",
    "subtitle": "免费版",
    "free.title": "Free",
    "proMonthly.feature1": "无限",
    "proYearly.feature1": "Pro 月付",
}
missing_kw = [
    k for k, kw in required_keywords.items()
    if not _has_nested(subscribe_obj, k, kw)
]
t("t16_i18n_keywords_present", len(missing_kw) == 0, f"missing={missing_kw}")


# ---------------------------------------------------------------------------
section("6. 沙箱 mock 行为标记")

t("t17_sandbox_checkout_jump",
  "sandbox" in route_text and ("checkout_url" in route_text or "sandbox-complete" in route_text))

t("t18_disclaimer_footer_present",
  "common.disclaimer" in route_text or "仅供参考" in route_text or "投资建议" in route_text)


# ---------------------------------------------------------------------------
print()
if failures == 0:
    print("[m6t5] ALL 18 SUBSCRIBE-PAGE (ROUTE + API + ROOT-NAV + i18n) TESTS PASSED")
    sys.exit(0)
else:
    print(f"[m6t5] {failures} TEST(S) FAILED")
    sys.exit(1)