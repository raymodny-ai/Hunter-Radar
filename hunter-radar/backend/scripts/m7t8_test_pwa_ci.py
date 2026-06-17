"""M7-t8 自测:PWA + CI 实跑配置(V1.5 接力期)。

测试范围(22 测点):
- §1 .github/workflows/ci.yml 存在
- §2 CI 触发条件:push main/develop/m7/* + PR
- §3 CI 包含 6 jobs:backend / openapi-drift / frontend / secrets-check / webhook / docs
- §4 backend job: pytest + m7t1 regression + m7t6 webhook + m7t7 openapi
- §5 openapi-drift job: 跑 m7t7_dump_openapi + diff committed freeze
- §6 frontend job: pnpm install + build + Lighthouse + manifest/sw/offline 校验
- §7 secrets-check job: VAPID + Sentry schema 校验
- §8 webhook job: m7t6 self-test + doc sanity
- §9 docs job: M5/M6-handoff + openapi-frozen-v1.5 + BD-086/087 audit
- §10 vite.config.ts 含 VitePWA + autoUpdate
- §11 workbox runtimeCaching ≥5 类
- §12 workbox threat 接口 StaleWhileRevalidate 12h
- §13 workbox threat 接口 cacheableResponse statuses [0, 200]
- §14 workbox navigateFallback /offline.html
- §15 workbox navigateFallbackDenylist /api/
- §16 lighthouserc.cjs performance ≥0.85 / a11y ≥0.95 / best-practices ≥0.90
- §17 lighthouserc.cjs LCP ≤2500 / CLS ≤0.1
- §18 config.py vapid_private_key + vapid_public_key
- §19 config.py vapid_claims_email
- §20 config.py sentry_dsn
- §21 manifest icons 192 + 512 + maskable
- §22 pnpm dev 启动命令(startServerReadyPattern "ready in")
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
VITE_TS = ROOT / "frontend" / "vite.config.ts"
LH_CJS = ROOT / "frontend" / "lighthouserc.cjs"
CONFIG_PY = APP / "core" / "config.py"

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


# ---------- §1 .github/workflows/ci.yml 存在 ----------
def _t01_ci_workflow_exists():
    assert CI_YML.exists(), f"CI workflow 缺失: {CI_YML}"
    assert CI_YML.stat().st_size > 0, "CI workflow 文件空"


# ---------- §2 CI 触发条件 ----------
def _t02_ci_triggers():
    text = CI_YML.read_text(encoding="utf-8")
    for branch in ("main", "develop", "m7/*"):
        assert branch in text, f"触发分支缺 {branch}"
    assert "pull_request" in text, "应监听 PR"


# ---------- §3 CI 6 jobs ----------
def _t03_six_ci_jobs():
    text = CI_YML.read_text(encoding="utf-8")
    for job in ("backend:", "openapi-drift:", "frontend:", "secrets-check:", "webhook:", "docs:"):
        assert job in text, f"CI 缺 job {job}"


# ---------- §4 backend job 关键 step ----------
def _t04_backend_job_steps():
    text = CI_YML.read_text(encoding="utf-8")
    # 找 backend job 段
    idx = text.find("backend:")
    snippet = text[idx:idx + 3000]
    assert "pytest" in snippet, "backend job 应跑 pytest"
    assert "m7t1_test_regression" in snippet, "backend job 应跑 m7t1"
    assert "m7t6_test_stripe_webhook" in snippet, "backend job 应跑 m7t6"
    assert "m7t7_test_openapi_v15" in snippet, "backend job 应跑 m7t7"


# ---------- §5 openapi-drift 校验 ----------
def _t05_openapi_drift():
    text = CI_YML.read_text(encoding="utf-8")
    idx = text.find("openapi-drift:")
    snippet = text[idx:idx + 2000]
    assert "m7t7_dump_openapi" in snippet, "openapi-drift 应跑 dump"
    assert "git diff" in snippet, "openapi-drift 应 diff committed freeze"


# ---------- §6 frontend PWA + Lighthouse ----------
def _t06_frontend_pwa_lighthouse():
    text = CI_YML.read_text(encoding="utf-8")
    idx = text.find("frontend:")
    snippet = text[idx:idx + 4000]
    assert "pnpm install" in snippet, "frontend 应 pnpm install"
    assert "pnpm run build" in snippet or "pnpm build" in snippet, "frontend 应 pnpm build"
    assert "Lighthouse" in snippet or "lhci" in snippet or "@lhci/cli" in snippet, \
        "frontend 应跑 Lighthouse"
    assert "manifest.webmanifest" in snippet, "frontend 应校验 manifest"
    assert "sw.js" in snippet, "frontend 应校验 service worker"
    assert "offline.html" in snippet, "frontend 应校验 offline.html"


# ---------- §7 secrets-check job ----------
def _t07_secrets_check():
    text = CI_YML.read_text(encoding="utf-8")
    idx = text.find("secrets-check:")
    snippet = text[idx:idx + 2500]
    assert "vapid_private_key" in snippet, "secrets-check 应校验 VAPID 私钥"
    assert "vapid_public_key" in snippet, "secrets-check 应校验 VAPID 公钥"
    assert "SENTRY_DSN" in snippet or "sentry_dsn" in snippet, "secrets-check 应校验 Sentry DSN"


# ---------- §8 webhook job ----------
def _t08_webhook_job():
    text = CI_YML.read_text(encoding="utf-8")
    idx = text.find("webhook:")
    snippet = text[idx:idx + 2000]
    assert "m7t6_test_stripe_webhook" in snippet, "webhook job 应跑 m7t6"
    assert "signature_skipped" in snippet, "webhook job 应校验 doc 含 signature_skipped"


# ---------- §9 docs job ----------
def _t09_docs_job():
    text = CI_YML.read_text(encoding="utf-8")
    idx = text.find("docs:")
    snippet = text[idx:idx + 3000]
    for f in ("docs/M5-handoff.md", "docs/M6-handoff.md",
              "docs/openapi-frozen-v1.4.1.json", "docs/openapi-frozen-v1.5.json",
              "docs/BD-086-signoff-audit-log.md", "docs/BD-087-calibration-report-v3.0-final.md"):
        assert f in snippet, f"docs job 缺校验 {f}"


# ---------- §10 vite.config.ts 含 VitePWA ----------
def _t10_vite_pwa_plugin():
    text = VITE_TS.read_text(encoding="utf-8")
    assert "VitePWA" in text, "vite.config.ts 应含 VitePWA"
    assert "registerType" in text and "autoUpdate" in text, "应 registerType=autoUpdate"


# ---------- §11 workbox runtimeCaching ≥5 类 ----------
def _t11_workbox_runtime_caching():
    text = VITE_TS.read_text(encoding="utf-8")
    assert "runtimeCaching" in text, "workbox 应有 runtimeCaching"
    cache_count = text.count("urlPattern:")
    assert cache_count >= 5, f"runtimeCaching 应≥5 类, 实={cache_count}"


# ---------- §12 threat 接口 SWR 12h ----------
def _t12_threat_swr_12h():
    text = VITE_TS.read_text(encoding="utf-8")
    idx = text.find("symbols/.*/threat")
    snippet = text[idx:idx + 400]
    assert "StaleWhileRevalidate" in snippet, "threat 应 SWR"
    assert "12" in snippet and "60 * 60" in snippet, "threat TTL 应 12h"


# ---------- §13 cacheableResponse statuses [0, 200] ----------
def _t13_cacheable_status():
    text = VITE_TS.read_text(encoding="utf-8")
    assert "statuses: [0, 200]" in text, "cacheableResponse 应 statuses=[0, 200]"


# ---------- §14 workbox navigateFallback ----------
def _t14_navigate_fallback():
    text = VITE_TS.read_text(encoding="utf-8")
    assert "navigateFallback" in text, "应有 navigateFallback"
    assert "/offline.html" in text, "navigateFallback 应=/offline.html"


# ---------- §15 navigateFallbackDenylist /api/ ----------
def _t15_navigate_fallback_denylist():
    text = VITE_TS.read_text(encoding="utf-8")
    assert "navigateFallbackDenylist" in text, "应有 navigateFallbackDenylist"
    assert "/api/" in text, "denylist 应排除 /api/"


# ---------- §16 lighthouse thresholds ----------
def _t16_lighthouse_thresholds():
    text = LH_CJS.read_text(encoding="utf-8")
    assert "performance" in text and "0.85" in text, "performance 应 ≥0.85"
    assert "accessibility" in text and "0.95" in text, "accessibility 应 ≥0.95"
    assert "best-practices" in text and "0.90" in text, "best-practices 应 ≥0.90"
    assert "seo" in text and "0.80" in text, "seo 应 ≥0.80"


# ---------- §17 LCP/CLS 阈值 ----------
def _t17_lcp_cls_thresholds():
    text = LH_CJS.read_text(encoding="utf-8")
    assert "largest-contentful-paint" in text and "2500" in text, "LCP 应 ≤2500ms"
    assert "cumulative-layout-shift" in text and "0.1" in text, "CLS 应 ≤0.1"


# ---------- §18 vapid_private_key + vapid_public_key ----------
def _t18_vapid_keys():
    text = CONFIG_PY.read_text(encoding="utf-8")
    assert "vapid_private_key" in text, "config.py 应有 vapid_private_key"
    assert "vapid_public_key" in text, "config.py 应有 vapid_public_key"
    # 默认 None(沙箱安全)
    pk_line = [l for l in text.splitlines() if "vapid_private_key" in l][0]
    assert "None" in pk_line, f"vapid_private_key 默认应=None: {pk_line}"


# ---------- §19 vapid_claims_email ----------
def _t19_vapid_claims_email():
    text = CONFIG_PY.read_text(encoding="utf-8")
    assert "vapid_claims_email" in text, "config.py 应有 vapid_claims_email"
    email_line = [l for l in text.splitlines() if "vapid_claims_email" in l][0]
    assert "@" in email_line, f"vapid_claims_email 应是邮箱: {email_line}"


# ---------- §20 sentry_dsn ----------
def _t20_sentry_dsn():
    text = CONFIG_PY.read_text(encoding="utf-8")
    assert "sentry_dsn" in text, "config.py 应有 sentry_dsn"
    dsn_line = [l for l in text.splitlines() if "sentry_dsn" in l][0]
    assert "None" in dsn_line, f"sentry_dsn 默认应=None: {dsn_line}"


# ---------- §21 manifest icons ----------
def _t21_manifest_icons():
    text = VITE_TS.read_text(encoding="utf-8")
    assert "192" in text, "manifest 应有 192 图标"
    assert "512" in text, "manifest 应有 512 图标"
    assert "maskable" in text, "manifest 应有 maskable 用途"


# ---------- §22 pnpm dev ready pattern ----------
def _t22_pnpm_dev_pattern():
    text = LH_CJS.read_text(encoding="utf-8")
    assert "pnpm dev" in text, "应 pnpm dev 启动"
    assert "ready in" in text, "startServerReadyPattern 应='ready in'"


def main() -> int:
    tests = [
        ("t01_ci_workflow_exists", _t01_ci_workflow_exists),
        ("t02_ci_triggers", _t02_ci_triggers),
        ("t03_six_ci_jobs", _t03_six_ci_jobs),
        ("t04_backend_job_steps", _t04_backend_job_steps),
        ("t05_openapi_drift", _t05_openapi_drift),
        ("t06_frontend_pwa_lighthouse", _t06_frontend_pwa_lighthouse),
        ("t07_secrets_check", _t07_secrets_check),
        ("t08_webhook_job", _t08_webhook_job),
        ("t09_docs_job", _t09_docs_job),
        ("t10_vite_pwa_plugin", _t10_vite_pwa_plugin),
        ("t11_workbox_runtime_caching", _t11_workbox_runtime_caching),
        ("t12_threat_swr_12h", _t12_threat_swr_12h),
        ("t13_cacheable_status", _t13_cacheable_status),
        ("t14_navigate_fallback", _t14_navigate_fallback),
        ("t15_navigate_fallback_denylist", _t15_navigate_fallback_denylist),
        ("t16_lighthouse_thresholds", _t16_lighthouse_thresholds),
        ("t17_lcp_cls_thresholds", _t17_lcp_cls_thresholds),
        ("t18_vapid_keys", _t18_vapid_keys),
        ("t19_vapid_claims_email", _t19_vapid_claims_email),
        ("t20_sentry_dsn", _t20_sentry_dsn),
        ("t21_manifest_icons", _t21_manifest_icons),
        ("t22_pnpm_dev_pattern", _t22_pnpm_dev_pattern),
    ]
    print(f"开始 m7t8 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M7-T8 PWA + CI TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())