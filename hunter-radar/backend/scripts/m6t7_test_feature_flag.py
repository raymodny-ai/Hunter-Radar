"""M6-t7 沙箱自测:M6 灰度发布 + FE-083 横幅落地产物校验。

沙箱不实跑 uvicorn(无 PG/Redis),只静态校验:
- feature_flag service:FeatureFlag / FlagSnapshot dataclass + _stable_hash + 3 内置 flag
- 2 个 API 端点(GET /feature-flags + GET /feature-flags/{key})
- main.py 注册 feature_flags router
- useFeatureFlag hook + pickFlag 纯函数
- GrayReleaseBanner 组件 + shouldShowGrayReleaseBanner 纯函数 + 7 天 dismiss
- api.ts 加 getAllFeatureFlags 方法
- __root.tsx 挂载 GrayReleaseBanner
- zh-CN.json 补 featureFlags 翻译段
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"
SRC = FRONTEND / "src"
COMPONENTS = SRC / "components" / "common"
FEATURES = SRC / "features"
ROUTES = SRC / "routes"
LIB = SRC / "lib"
I18N = SRC / "i18n" / "zh-CN.json"

SERVICE = BACKEND / "app" / "services" / "feature_flag.py"
ROUTER_BE = BACKEND / "app" / "api" / "feature_flags.py"
MAIN = BACKEND / "app" / "main.py"
HOOK = FEATURES / "useFeatureFlag.ts"
BANNER = COMPONENTS / "GrayReleaseBanner.tsx"
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
section("1. feature_flag service")

t("t01_service_module_exists", SERVICE.exists(), f"path={SERVICE}")

service_text = SERVICE.read_text(encoding="utf-8") if SERVICE.exists() else ""

t("t02_feature_flag_dataclass",
  "@dataclass" in service_text and "FeatureFlag" in service_text and "FlagSnapshot" in service_text)

t("t03_stable_hash_function",
  "sha256" in service_text and "_stable_hash" in service_text)

required_flags = ["subscribe_v2", "8k_feed", "gray_release_banner"]
missing_flags = [f for f in required_flags if f not in service_text]
t("t04_default_flags_3", len(missing_flags) == 0, f"missing={missing_flags}")

t("t05_whitelist_logic",
  "whitelist" in service_text and "user_id in flag.whitelist" in service_text)

t("t06_rollout_logic",
  "rollout_pct" in service_text and "bucket < flag.rollout_pct" in service_text)


# ---------------------------------------------------------------------------
section("2. router + main 注册")

t("t07_router_module_exists", ROUTER_BE.exists(), f"path={ROUTER_BE}")
router_text = ROUTER_BE.read_text(encoding="utf-8") if ROUTER_BE.exists() else ""

t("t08_get_all_flags_endpoint",
  re.search(r'@router\.get\("/feature-flags"', router_text) is not None)
t("t09_get_single_flag_endpoint",
  re.search(r'@router\.get\("/feature-flags/\{flag_key\}"', router_text) is not None)

main_text = MAIN.read_text(encoding="utf-8") if MAIN.exists() else ""

t("t10_main_imports_feature_flags",
  "from app.api import" in main_text and "feature_flags," in main_text)
t("t11_main_includes_feature_flags_router",
  "feature_flags.router" in main_text and "tags=[\"feature-flags\"]" in main_text)


# ---------------------------------------------------------------------------
section("3. useFeatureFlag hook")

t("t12_hook_file_exists", HOOK.exists(), f"path={HOOK}")
hook_text = HOOK.read_text(encoding="utf-8") if HOOK.exists() else ""

t("t13_hook_use_feature_flag",
  "export function useFeatureFlag" in hook_text and "useQuery" in hook_text)
t("t14_hook_pick_flag_pure",
  "export function pickFlag" in hook_text)
t("t15_hook_stale_5min",
  "staleTime: 5 * 60 * 1000" in hook_text or "staleTime:5 * 60 * 1000" in hook_text)


# ---------------------------------------------------------------------------
section("4. GrayReleaseBanner 组件")

t("t16_banner_file_exists", BANNER.exists(), f"path={BANNER}")
banner_text = BANNER.read_text(encoding="utf-8") if BANNER.exists() else ""

t("t17_banner_uses_useFeatureFlag",
  "useFeatureFlag" in banner_text and "@/features/useFeatureFlag" in banner_text)

t("t18_banner_shouldshow_pure",
  "shouldShowGrayReleaseBanner" in banner_text)

t("t19_banner_dismiss_7days",
  "DISMISS_DAYS = 7" in banner_text and "hr_gray_release_dismissed_until" in banner_text)

t("t20_banner_data_flag_reason",
  "data-flag-reason" in banner_text)


# ---------------------------------------------------------------------------
section("5. api.ts getAllFeatureFlags")

api_text = API_TS.read_text(encoding="utf-8") if API_TS.exists() else ""

t("t21_api_getAllFeatureFlags_method",
  "getAllFeatureFlags" in api_text and "/feature-flags" in api_text)


# ---------------------------------------------------------------------------
section("6. __root.tsx 挂载 GrayReleaseBanner")

root_text = ROOT_TSX.read_text(encoding="utf-8") if ROOT_TSX.exists() else ""

t("t22_root_import_banner",
  "GrayReleaseBanner" in root_text and "@/components/common/GrayReleaseBanner" in root_text)
t("t23_root_mount_banner",
  "<GrayReleaseBanner" in root_text)


# ---------------------------------------------------------------------------
section("7. zh-CN.json featureFlags 段")

i18n_text = I18N.read_text(encoding="utf-8") if I18N.exists() else ""
try:
    i18n_obj = json.loads(i18n_text)
except Exception as e:
    i18n_obj = {}
    print(f"  {FAIL} i18n_json_invalid — {e}")
    failures += 1

feature_flags_obj = i18n_obj.get("featureFlags", {})
required_ff_keys = ["bannerText", "bannerCta", "bannerDismiss", "bannerDismissShort"]
missing_ff = [k for k in required_ff_keys if k not in feature_flags_obj]
t("t24_i18n_feature_flags_segment", len(missing_ff) == 0, f"missing={missing_ff}")


# ---------------------------------------------------------------------------
print()
if failures == 0:
    print("[m6t7] ALL 24 FEATURE-FLAG (SERVICE + ROUTER + HOOK + BANNER + ROOT + i18n) TESTS PASSED")
    sys.exit(0)
else:
    print(f"[m6t7] {failures} TEST(S) FAILED")
    sys.exit(1)