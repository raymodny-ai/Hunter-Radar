"""M6-t6 沙箱自测:FE-082 商业化文案 + Pro only 徽章 + 升级引导落地产物校验。

沙箱不实跑 vite build(无 pnpm install),只静态校验:
- ProBadge 组件:2 variant(compact / full)+ shouldShowProBadge 纯函数
- UpgradePrompt 组件:3 variant(inline / block / modal)+ shouldShowUpgradePrompt 纯函数
- QuotaBanner /pricing → /subscribe 修正 + i18n marketing.upgradeCta
- alerts.tsx 挂 ProBadge + UpgradePrompt
- zh-CN.json 补 marketing 段(proBadge / upgradeTitle / upgradeCta / alertsReason)+ quota 段
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
COMPONENTS = SRC / "components" / "common"
ROUTES = SRC / "routes"
LIB = SRC / "lib"
I18N = SRC / "i18n" / "zh-CN.json"

PRO_BADGE = COMPONENTS / "ProBadge.tsx"
UPGRADE = COMPONENTS / "UpgradePrompt.tsx"
QUOTA_BANNER = COMPONENTS / "QuotaBanner.tsx"
ALERTS = ROUTES / "alerts.tsx"

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
section("1. ProBadge 组件")

t("t01_probadge_file_exists", PRO_BADGE.exists(), f"path={PRO_BADGE}")
badge_text = PRO_BADGE.read_text(encoding="utf-8") if PRO_BADGE.exists() else ""

t("t02_probadge_export_function",
  "export function ProBadge" in badge_text)

t("t03_probadge_two_variants",
  '"compact"' in badge_text and '"full"' in badge_text)

t("t04_probadge_shouldshow_helper",
  "shouldShowProBadge" in badge_text)

t("t05_probadge_aria_label",
  'aria-label' in badge_text and ("Pro only" in badge_text or "仅 Pro" in badge_text))


# ---------------------------------------------------------------------------
section("2. UpgradePrompt 组件")

t("t06_upgrade_file_exists", UPGRADE.exists(), f"path={UPGRADE}")
upgrade_text = UPGRADE.read_text(encoding="utf-8") if UPGRADE.exists() else ""

t("t07_upgrade_export_function",
  "export function UpgradePrompt" in upgrade_text)

t("t08_upgrade_three_variants",
  '"inline"' in upgrade_text and '"block"' in upgrade_text and '"modal"' in upgrade_text)

t("t09_upgrade_default_href_subscribe",
  'href = "/subscribe"' in upgrade_text or '"/subscribe"' in upgrade_text)

t("t10_upgrade_shouldshow_helper",
  "shouldShowUpgradePrompt" in upgrade_text)

t("t11_upgrade_disclaimer_footer",
  "common.disclaimer" in upgrade_text or "仅供参考" in upgrade_text or "投资建议" in upgrade_text)


# ---------------------------------------------------------------------------
section("3. QuotaBanner 修 /pricing → /subscribe")

quota_text = QUOTA_BANNER.read_text(encoding="utf-8") if QUOTA_BANNER.exists() else ""

t("t12_quota_banner_no_pricing_link",
  "/pricing" not in quota_text,
  "已修 /pricing → /subscribe")

t("t13_quota_banner_subscribe_link",
  '"/subscribe"' in quota_text or 'href="/subscribe"' in quota_text)

t("t14_quota_banner_i18n_upgrade_cta",
  't("marketing.upgradeCta")' in quota_text)


# ---------------------------------------------------------------------------
section("4. alerts.tsx 挂 ProBadge + UpgradePrompt")

alerts_text = ALERTS.read_text(encoding="utf-8") if ALERTS.exists() else ""

t("t15_alerts_probadge_import",
  "ProBadge" in alerts_text and "@/components/common/ProBadge" in alerts_text)

t("t16_alerts_upgradeprompt_import",
  "UpgradePrompt" in alerts_text and "@/components/common/UpgradePrompt" in alerts_text)

t("t17_alerts_probadge_rendered",
  re.search(r"<ProBadge", alerts_text) is not None)

t("t18_alerts_upgrade_block_variant",
  'variant="block"' in alerts_text or 'variant={"block"}' in alerts_text)


# ---------------------------------------------------------------------------
section("5. zh-CN.json 补 marketing + quota 翻译段")

i18n_text = I18N.read_text(encoding="utf-8") if I18N.exists() else ""
try:
    i18n_obj = json.loads(i18n_text)
except Exception as e:
    i18n_obj = {}
    print(f"  {FAIL} i18n_json_invalid — {e}")
    failures += 1

marketing_obj = i18n_obj.get("marketing", {})
quota_obj = i18n_obj.get("quota", {})

required_marketing_keys = [
    "proBadge",
    "upgradeTitle",
    "upgradeCta",
    "alertsReason",
]
missing_marketing = [k for k in required_marketing_keys if k not in marketing_obj]
t("t19_i18n_marketing_segment", len(missing_marketing) == 0, f"missing={missing_marketing}")

required_quota_keys = ["exhausted", "remaining"]
missing_quota = [k for k in required_quota_keys if k not in quota_obj]
t("t20_i18n_quota_segment", len(missing_quota) == 0, f"missing={missing_quota}")

t("t21_i18n_marketing_disclaimer_align",
  "不构成投资建议" in json.dumps(i18n_obj, ensure_ascii=False))


# ---------------------------------------------------------------------------
section("6. CR-010 合规:无禁词")

full_text = "\n".join([
    badge_text, upgrade_text, quota_text, alerts_text, i18n_text,
])
# CR-010 红线词:保证收益 / 必涨 / 必跌 / 100% / 强烈推荐
forbidden = ["保证收益", "必涨", "必跌", "强烈推荐"]
violations = [w for w in forbidden if w in full_text]
t("t22_cr010_no_forbidden_words", len(violations) == 0, f"violations={violations}")


# ---------------------------------------------------------------------------
print()
if failures == 0:
    print("[m6t6] ALL 22 COMMERCIAL-COPY (PRO-BADGE + UPGRADE-PROMPT + QUOTA-FIX + i18n + CR-010) TESTS PASSED")
    sys.exit(0)
else:
    print(f"[m6t6] {failures} TEST(S) FAILED")
    sys.exit(1)