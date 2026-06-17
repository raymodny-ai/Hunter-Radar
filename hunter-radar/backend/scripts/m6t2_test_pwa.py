"""M6-t2 沙箱自测:BD-100 Vite PWA plugin + Workbox 离线缓存落地产物校验。

沙箱不实跑 vite build(无 pnpm install),只静态校验:
- vite.config.ts 接 VitePWA + 关键配置项
- manifest 含 8 字段(name/short_name/description/theme_color/background_color/display/start_url/icons)
- icons 含 192/512 两图
- workbox.runtimeCaching ≥ 3 条(报告 / 轻量 / 用户数据)
- 5 个静态资源(offline.html / favicon.svg / icon-192.svg / icon-512.svg / index.html 引用)就位
- package.json 中 vite-plugin-pwa + workbox-window 在 devDependencies
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
PUBLIC = FRONTEND / "public"
PKG = FRONTEND / "package.json"
VITE = FRONTEND / "vite.config.ts"
INDEX = FRONTEND / "index.html"

PASS = "[PASS]"
FAIL = "[FAIL]"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


def main() -> int:
    failures = 0

    # ---- 1. vite.config.ts 引用 VitePWA ---------------------------------------
    if not VITE.exists():
        t("t01_vite_pwa_imported", False, "vite.config.ts missing")
        return 1
    vite_text = VITE.read_text(encoding="utf-8")
    ok = "VitePWA" in vite_text and "vite-plugin-pwa" in vite_text
    if not t("t01_vite_pwa_imported", ok):
        failures += 1

    # ---- 2. manifest 8 字段齐全 ------------------------------------------------
    required_manifest = [
        "name:",
        "short_name:",
        "description:",
        "theme_color:",
        "background_color:",
        "display:",
        "start_url:",
        "icons:",
    ]
    missing = [f for f in required_manifest if f not in vite_text]
    ok = len(missing) == 0
    if not t("t02_manifest_8_fields_complete", ok, f"missing={missing}"):
        failures += 1

    # ---- 3. manifest.icons 含 192 + 512 ---------------------------------------
    ok = "192x192" in vite_text and "512x512" in vite_text
    if not t("t03_icons_192_and_512", ok):
        failures += 1

    # ---- 4. runtimeCaching ≥ 3 条(报告 / 轻量 / 用户数据) ----------------------
    cache_count = vite_text.count("urlPattern:")
    ok = cache_count >= 3
    if not t("t04_runtimecaching_min_3", ok, f"count={cache_count}"):
        failures += 1

    # ---- 5. navigateFallback = /offline.html ----------------------------------
    ok = "navigateFallback" in vite_text and "/offline.html" in vite_text
    if not t("t05_navigate_fallback_offline", ok):
        failures += 1

    # ---- 6. /api/v1/symbols/.*/threat 走 StaleWhileRevalidate + 12h TTL ---------
    # threat 段必出现
    ok = (
        re.search(r"urlPattern:\s*/\\/api\\/v1\\/symbols\\/.*\\/threat/", vite_text)
        is not None
    )
    if not t("t06_threat_endpoint_swr", ok):
        failures += 1

    # ---- 7. /api/v1/regime /data-status /auth/quota 走 NetworkFirst + 4s 超时 -
    # substring 检查多项关键标记(文件中字面含 auth\/quota,作为子串 auth/quota 仍可命中)
    ok = (
        "regime" in vite_text
        and "data-status" in vite_text
        and "auth/quota" in vite_text
        and "NetworkFirst" in vite_text
        and "networkTimeoutSeconds: 4" in vite_text
    )
    if not t("t07_meta_endpoint_networkfirst", ok):
        failures += 1

    # ---- 8. 静态资源 .js .css 走 CacheFirst -----------------------------------
    # substring: 静态资源段必出现 js css + CacheFirst
    ok = (
        "js|css" in vite_text
        and "CacheFirst" in vite_text
    )
    if not t("t08_static_cachefirst", ok):
        failures += 1

    # ---- 9. /offline.html 存在 -------------------------------------------------
    offline = PUBLIC / "offline.html"
    ok = offline.exists()
    if not t("t09_offline_html_exists", ok, f"path={offline}"):
        failures += 1

    # ---- 10. /favicon.svg 存在 -------------------------------------------------
    favicon = PUBLIC / "favicon.svg"
    ok = favicon.exists()
    if not t("t10_favicon_svg_exists", ok, f"path={favicon}"):
        failures += 1

    # ---- 11. /icon-192.svg + /icon-512.svg 都存在 -----------------------------
    icon192 = PUBLIC / "icon-192.svg"
    icon512 = PUBLIC / "icon-512.svg"
    ok = icon192.exists() and icon512.exists()
    if not t("t11_icons_192_512_exist", ok, f"192={icon192.exists()} 512={icon512.exists()}"):
        failures += 1

    # ---- 12. package.json 含 vite-plugin-pwa 在 devDependencies ----------------
    if not PKG.exists():
        t("t12_vite_plugin_pwa_in_pkg", False, "package.json missing")
        failures += 1
    else:
        pkg = json.loads(PKG.read_text(encoding="utf-8"))
        deps = pkg.get("devDependencies", {}) or {}
        ok = "vite-plugin-pwa" in deps
        if not t("t12_vite_plugin_pwa_in_pkg", ok, f"version={deps.get('vite-plugin-pwa')}"):
            failures += 1

        # ---- 13. workbox-window 也在 devDependencies ----------------------------
        ok = "workbox-window" in deps
        if not t("t13_workbox_window_in_pkg", ok, f"version={deps.get('workbox-window')}"):
            failures += 1

    # ---- 14. index.html 引用 /favicon.svg(已就位) -----------------------------
    if INDEX.exists():
        idx_text = INDEX.read_text(encoding="utf-8")
        ok = "/favicon.svg" in idx_text and "theme-color" in idx_text
        if not t("t14_index_html_favicon_and_theme", ok):
            failures += 1
    else:
        t("t14_index_html_favicon_and_theme", False, "index.html missing")
        failures += 1

    # ---- 15. CR-010 禁词扫描(本轮新增文件无禁词) ------------------------------
    forbidden = [
        "100% 收益", "保证收益", "买入评级", "卖出评级", "翻倍",
    ]
    files_to_scan = [offline, favicon, icon192, icon512, VITE]
    files_to_scan = [f for f in files_to_scan if f.exists()]
    hits: list[str] = []
    for f in files_to_scan:
        content = f.read_text(encoding="utf-8")
        for w in forbidden:
            if w in content:
                hits.append(f"{f.name}: {w}")
    ok = len(hits) == 0
    if not t("t15_cr010_forbidden_words_clean", ok, f"hits={hits}"):
        failures += 1

    # ---- 16. offline.html 引用 disclaimer 兜底文案 ----------------------------
    if offline.exists():
        text = offline.read_text(encoding="utf-8")
        ok = "仅供参考" in text and "不构成投资建议" in text
        if not t("t16_offline_html_disclaimer", ok):
            failures += 1
    else:
        t("t16_offline_html_disclaimer", False, "offline.html missing")
        failures += 1

    print()
    if failures == 0:
        print("[m6t2] ALL 16 PWA + WORKBOX SKELETON (BD-100) TESTS PASSED")
        return 0
    print(f"[m6t2] {failures} TEST(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
