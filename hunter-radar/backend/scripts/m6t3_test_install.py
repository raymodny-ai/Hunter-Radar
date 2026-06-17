"""M6-t3 沙箱自测:BD-101 PWA 安装提示 hook + banner 落地产物校验。

沙箱不实跑 vite build / 浏览器(无 pnpm install / jsdom),只静态校验:
- usePWAInstall hook 暴露完整接口(installPrompt / isIOS / isStandalone / isDismissed / install / dismiss)
- 监听 beforeinstallprompt + appinstalled 双事件
- 7 天 dismiss 持久化 key = hr_pwa_dismissed_until
- PWAInstallBanner 组件 + shouldShowPWAInstall 纯函数 4 路径判定
- __root.tsx 挂载 PWAInstallBanner
- zh-CN.json 补 pwa.install 6 字段翻译
- 沙箱不弹规则(localhost / standalone / dismissed)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
HOOK = SRC / "features" / "usePWAInstall.ts"
BANNER = SRC / "components" / "common" / "PWAInstallBanner.tsx"
ROOT_TSX = SRC / "routes" / "__root.tsx"
I18N = SRC / "i18n" / "zh-CN.json"

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
section("1. usePWAInstall hook 存在 + 关键接口")

hook_text = HOOK.read_text(encoding="utf-8") if HOOK.exists() else ""
t("t01_hook_file_exists", HOOK.exists(), f"path={HOOK}")

# UsePWAInstallResult 接口六字段
required_fields = ["installPrompt", "isIOS", "isStandalone", "isDismissed", "install", "dismiss"]
missing_fields = [f for f in required_fields if f not in hook_text]
t("t02_hook_interface_complete", len(missing_fields) == 0, f"missing={missing_fields}")

# install() 返值类型
t("t03_install_return_type",
  '"accepted" | "dismissed" | "unavailable"' in hook_text,
  "outcome 三态")


# ---------------------------------------------------------------------------
section("2. 事件监听 + dismiss 持久化")

t("t04_listen_beforeinstallprompt",
  "beforeinstallprompt" in hook_text and "addEventListener" in hook_text)
t("t05_listen_appinstalled",
  "appinstalled" in hook_text)
t("t06_dismiss_key_constant",
  'DISMISS_KEY = "hr_pwa_dismissed_until"' in hook_text)
t("t07_dismiss_days_seven",
  "DISMISS_DAYS = 7" in hook_text or "DISMISS_DAYS = 7" in hook_text or
  "24 * 60 * 60 * 1000" in hook_text)
# localStorage 写读
t("t08_localstorage_persist",
  "localStorage.setItem(DISMISS_KEY" in hook_text and "localStorage.getItem(DISMISS_KEY" in hook_text)


# ---------------------------------------------------------------------------
section("3. iOS 识别 + standalone 判定")

t("t09_ios_ua_detection",
  "iPad|iPhone|iPod" in hook_text and "CriOS|FxiOS|EdgiOS" in hook_text)
t("t10_standalone_display_mode",
  "(display-mode: standalone)" in hook_text)
t("t11_standalone_navigator_ios",
  "navigator.standalone" in hook_text)


# ---------------------------------------------------------------------------
section("4. PWAInstallBanner 组件 + 判定函数")

banner_text = BANNER.read_text(encoding="utf-8") if BANNER.exists() else ""
t("t12_banner_file_exists", BANNER.exists(), f"path={BANNER}")
t("t13_banner_export_shouldshow",
  "export function shouldShowPWAInstall" in banner_text)

# shouldShowPWAInstall 4 路径
required_paths = [
    "pwa.isStandalone",
    "pwa.isDismissed",
    "pwa.installPrompt",
    "pwa.isIOS",
]
ok_paths = sum(1 for p in required_paths if p in banner_text)
t("t14_shouldshow_4_paths", ok_paths >= 4, f"matched={ok_paths}/4")

t("t15_banner_has_install_cta",
  "handleInstall" in banner_text and "pwa.install()" in banner_text)

t("t16_banner_ios_branch",
  "isIOS" in banner_text and ("iosHint" in banner_text or "iOS" in banner_text))


# ---------------------------------------------------------------------------
section("5. __root.tsx 挂载 PWAInstallBanner")

root_text = ROOT_TSX.read_text(encoding="utf-8") if ROOT_TSX.exists() else ""
t("t17_root_import_pwa_banner",
  "PWAInstallBanner" in root_text and ("@/components/common/PWAInstallBanner" in root_text))
t("t18_root_mount_pwa_banner",
  re.search(r"<PWAInstallBanner\s*/>", root_text) is not None or
  re.search(r"<PWAInstallBanner\s+/>", root_text) is not None or
  "<PWAInstallBanner" in root_text)
t("t19_root_has_disclaimer_footer",
  "<Disclaimer" in root_text and "footer" in root_text.lower())


# ---------------------------------------------------------------------------
section("6. zh-CN.json pwa.install 6 字段翻译")

i18n_text = I18N.read_text(encoding="utf-8") if I18N.exists() else ""
try:
    i18n_obj = json.loads(i18n_text)
except Exception as e:
    i18n_obj = {}
    print(f"  {FAIL} i18n_json_invalid — {e}")
    failures += 1

pwa_obj = i18n_obj.get("pwa", {})
install_obj = pwa_obj.get("install", {})

required_i18n_keys = ["ariaLabel", "hint", "iosHint", "cta", "dismiss", "dismissShort"]
missing_i18n = [k for k in required_i18n_keys if k not in install_obj]
t("t20_i18n_pwa_install_complete", len(missing_i18n) == 0, f"missing={missing_i18n}")

# 简体断言(不应含繁体「點擊/離線」)
install_text = json.dumps(install_obj, ensure_ascii=False)
has_traditional = any(c in install_text for c in ["點", "離線", "關閉", "安裝"])
t("t21_i18n_simplified_chinese",
  not has_traditional,
  f"text={install_text[:80]}...")

# 必备关键词
required_keywords = {
    "ariaLabel": "PWA 安装提示",
    "hint": "离线",
    "iosHint": "iOS",
    "cta": "安装",
}
missing_kw = [k for k, kw in required_keywords.items() if kw not in install_obj.get(k, "")]
t("t22_i18n_keywords_present", len(missing_kw) == 0, f"missing={missing_kw}")


# ---------------------------------------------------------------------------
section("7. 沙箱降级规则:standalone 不弹 / dismissed 不弹 + 无强制 localhost 屏蔽")

# hook 不应做强制 localhost 屏蔽(Chrome 自动行为即可),只校验无显式 hostname 比较
t("t23_hook_no_explicit_hostname_block",
  "location.hostname" not in hook_text,
  "Chrome 在 localhost 自动不触发 beforeinstallprompt,hook 无需强屏蔽")

t("t24_hook_standalone_check",
  "isStandaloneMode" in hook_text and "isStandaloneState" in hook_text)

t("t25_hook_dismissed_check",
  "isDismissed()" in hook_text and "isDismissedState" in hook_text)

# 沙箱无 window 时安全降级
t("t26_hook_window_undefined_guard",
  'typeof window === "undefined"' in hook_text)


# ---------------------------------------------------------------------------
print()
if failures == 0:
    print(f"[m6t3] ALL {sum(1 for _ in range(26))} PWA-INSTALL (HOOK + BANNER + i18n) TESTS PASSED")
    sys.exit(0)
else:
    print(f"[m6t3] {failures} TEST(S) FAILED")
    sys.exit(1)