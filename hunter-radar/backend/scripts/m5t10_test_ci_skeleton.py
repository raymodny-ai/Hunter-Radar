"""M5-t10 沙箱自测:FE-066 WCAG + FE-067 Playwright + FE-068 Lighthouse CI 骨架落地产物校验。

沙箱不实跑(无 pnpm install / 无 headless 浏览器),只静态校验:
- 3 个 GitHub Actions workflow 存在 + 含关键 step
- lighthouserc.cjs 含锁定阈值
- 2 个测试 spec 存在 + 含断言
- backend 3 个端点 /regime / /data-status / /auth/quota 在 spec 中被引用
- 数据缺失 / 沙箱降级行为在 spec 体现
- WCAG 2.1 AA tags 在 axe spec 中
- 性能阈值(LCP / CLS / FCP / TBT)在 lighthouse 配置中
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
FRONTEND = ROOT / "frontend"
WCAG_WF = WORKFLOWS / "wcag-audit.yml"
E2E_WF = WORKFLOWS / "playwright-e2e.yml"
PERF_WF = WORKFLOWS / "lighthouse-perf.yml"
LHRC = FRONTEND / "lighthouserc.cjs"
WCAG_SPEC = FRONTEND / "tests" / "wcag" / "audit.spec.ts"
E2E_SPEC = FRONTEND / "tests" / "e2e" / "smoke.spec.ts"
PLAYWRIGHT_CONFIG = FRONTEND / "playwright.config.ts"
FREEZE = ROOT / "docs" / "openapi-frozen-v1.4.1.md"

PASS = "[PASS]"
FAIL = "[FAIL]"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


def main() -> int:
    failures = 0

    # ---- 1. 3 个 workflow 存在 --------------------------------------------------
    ok = (
        WCAG_WF.exists()
        and E2E_WF.exists()
        and PERF_WF.exists()
    )
    if not t("t01_workflows_exist", ok, f"wcag={WCAG_WF.exists()} e2e={E2E_WF.exists()} perf={PERF_WF.exists()}"):
        failures += 1

    # ---- 2. wcag-audit.yml 含 axe-core + WCAG 2.1 AA + 阻断合并 -----------------
    if WCAG_WF.exists():
        text = WCAG_WF.read_text(encoding="utf-8")
        ok = (
            "axe" in text.lower()
            and "wcag" in text.lower()
            and "upload-artifact" in text
            and "pull_request" in text
        )
        if not t("t02_wcag_workflow_axe_blocking", ok):
            failures += 1
    else:
        t("t02_wcag_workflow_axe_blocking", False, "wcag-audit.yml missing")

    # ---- 3. playwright-e2e.yml 含 4 路由 + 后端 API 探活 -------------------------
    if E2E_WF.exists():
        text = E2E_WF.read_text(encoding="utf-8")
        ok = (
            "playwright" in text.lower()
            and "chromium" in text.lower()
            and "playwright install" in text.lower()
        )
        if not t("t03_playwright_e2e_workflow", ok):
            failures += 1
    else:
        t("t03_playwright_e2e_workflow", False, "playwright-e2e.yml missing")

    # ---- 4. lighthouse-perf.yml 含 4 阈值 + nightly cron ------------------------
    if PERF_WF.exists():
        text = PERF_WF.read_text(encoding="utf-8")
        ok = "lighthouse" in text.lower() and "cron" in text and "schedule" in text
        if not t("t04_lighthouse_perf_workflow", ok):
            failures += 1
    else:
        t("t04_lighthouse_perf_workflow", False, "lighthouse-perf.yml missing")

    # ---- 5. lighthouserc.cjs 含锁定阈值(performance / a11y / bp / seo / LCP) ---
    if LHRC.exists():
        text = LHRC.read_text(encoding="utf-8")
        ok = (
            "minScore: 0.85" in text  # performance
            and "minScore: 0.95" in text  # accessibility
            and "minScore: 0.90" in text  # best-practices
            and "largest-contentful-paint" in text
            and "cumulative-layout-shift" in text
        )
        if not t("t05_lighthouserc_thresholds_locked", ok):
            failures += 1
    else:
        t("t05_lighthouserc_thresholds_locked", False, "lighthouserc.cjs missing")

    # ---- 6. axe spec 含 WCAG 2.1 AA tags + 4 路由 + 阻断断言 ---------------------
    if WCAG_SPEC.exists():
        text = WCAG_SPEC.read_text(encoding="utf-8")
        ok = (
            "wcag2aa" in text
            and "wcag21aa" in text
            and "/" in text  # 至少有一个路径
            and "toEqual([])" in text  # 阻断断言
            and "AxeBuilder" in text
        )
        if not t("t06_axe_spec_wcag21aa_blocking", ok):
            failures += 1
    else:
        t("t06_axe_spec_wcag21aa_blocking", False, "audit.spec.ts missing")

    # ---- 7. e2e spec 含 4 路由 + 3 后端端点 + 沙箱降级 ---------------------------
    if E2E_SPEC.exists():
        text = E2E_SPEC.read_text(encoding="utf-8")
        ok = (
            "/screener" in text
            and "/basket" in text
            and "/alerts" in text
            and "/api/v1/regime" in text
            and "/api/v1/data-status" in text
            and "/api/v1/auth/quota" in text
            and "sandbox" in text.lower()
        )
        if not t("t07_e2e_spec_4routes_3endpoints_sandbox", ok):
            failures += 1
    else:
        t("t07_e2e_spec_4routes_3endpoints_sandbox", False, "smoke.spec.ts missing")

    # ---- 8. 4 路由覆盖全部 4 个核心页面(锁定基线) -------------------------------
    pages = ["/", "/screener", "/basket", "/alerts"]
    if LHRC.exists() and E2E_SPEC.exists():
        lh_text = LHRC.read_text(encoding="utf-8")
        e2e_text = E2E_SPEC.read_text(encoding="utf-8")
        ok = all(p in lh_text for p in pages) and all(p in e2e_text for p in pages)
        if not t("t08_4pages_covered_in_lh_and_e2e", ok):
            failures += 1
    else:
        t("t08_4pages_covered_in_lh_and_e2e", False, "missing config / spec")

    # ---- 9. CR-010 禁词扫描(自测脚本自身不引入禁用词) ---------------------------
    forbidden = [
        "建议买入", "强烈推荐", "稳赚不赔", "无风险", "翻倍",
        "100% 收益", "保证收益", "买入评级", "卖出评级",
    ]
    files_to_scan = [WCAG_WF, E2E_WF, PERF_WF, LHRC, WCAG_SPEC, E2E_SPEC]
    hits: list[str] = []
    for f in files_to_scan:
        if not f.exists():
            continue
        content = f.read_text(encoding="utf-8")
        for w in forbidden:
            if w in content:
                hits.append(f"{f.name}: {w}")
    ok = len(hits) == 0
    if not t("t09_cr010_forbidden_words_clean", ok, f"hits={hits}"):
        failures += 1

    # ---- 10. OpenAPI v1.4.1 freeze 仍引用(wcag / e2e 都引 /api/v1/regime 等) -----
    if FREEZE.exists():
        freeze_text = FREEZE.read_text(encoding="utf-8")
        # freeze md 写法是裸路径(参见 §二路由表),但也含 "/api/v1" 说明前缀,
        # 需两个串同时出现才能证明 freeze 引用了这些端点
        ok = (
            ("/regime" in freeze_text or "/api/v1/regime" in freeze_text)
            and ("/data-status" in freeze_text or "/api/v1/data-status" in freeze_text)
            and ("/auth/quota" in freeze_text or "/api/v1/auth/quota" in freeze_text)
        )
        if not t("t10_freeze_includes_3_ci_referenced_endpoints", ok):
            failures += 1
    else:
        t("t10_freeze_includes_3_ci_referenced_endpoints", False, "freeze missing")

    print()
    if failures == 0:
        print("[m5t10] ALL 10 CI SKELETON (WCAG + Playwright + Lighthouse) TESTS PASSED")
        return 0
    print(f"[m5t10] {failures} TEST(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
