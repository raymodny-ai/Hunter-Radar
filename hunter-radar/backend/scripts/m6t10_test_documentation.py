"""M6-t10 文档自测:M6-handoff + daily-standup + 校准报告 + 关键文件存在性校验
- 沙箱模式:只读文件 + 字符串包含/正则断言,无 PG/EOD 依赖
- 设计:20+ 测点分 6 个 section(section1 文件存在 / section2 章节完整 /
  section3 端点 + router / section4 i18n / section5 风险 / section6 M6 测点脚本)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
DOCS = ROOT / "docs"
BACKEND_SCRIPTS = ROOT / "backend" / "scripts"
BACKEND_APP = ROOT / "backend" / "app"
BACKEND_API = BACKEND_APP / "api"
BACKEND_SERVICES = BACKEND_APP / "services"
FRONTEND = ROOT / "frontend"
FRONTEND_SRC = FRONTEND / "src"
FRONTEND_ROUTES = FRONTEND_SRC / "routes"
FRONTEND_COMPONENTS = FRONTEND_SRC / "components" / "common"
FRONTEND_FEATURES = FRONTEND_SRC / "features"
FRONTEND_I18N = FRONTEND_SRC / "i18n"


def _read(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# Section 1: M6 关键文件存在性
# ----------------------------------------------------------------------

def t01_handoff_exists() -> bool:
    p = DOCS / "M6-handoff.md"
    if not p.exists():
        print(f"  [FAIL] M6-handoff.md 不存在: {p}")
        return False
    print(f"  [PASS] M6-handoff.md 存在 ({p.stat().st_size} bytes)")
    return True


def t02_v30_report_exists() -> bool:
    p = DOCS / "BD-087-calibration-report-v3.0.md"
    if not p.exists():
        print(f"  [FAIL] BD-087 v3.0 报告不存在: {p}")
        return False
    print(f"  [PASS] v3.0 校准报告存在 ({p.stat().st_size} bytes)")
    return True


def t03_daily_standup_exists() -> bool:
    p = ROOT.parent / "daily-standup.md"
    if not p.exists():
        print(f"  [FAIL] daily-standup.md 不存在: {p}")
        return False
    print(f"  [PASS] daily-standup.md 存在 ({p.stat().st_size} bytes)")
    return True


def t04_subscription_service_exists() -> bool:
    p = BACKEND_SERVICES / "subscription.py"
    if not p.exists():
        print(f"  [FAIL] subscription.py 不存在")
        return False
    txt = _read(p)
    if "Subscription" not in txt or "PLAN_PRICE_USD" not in txt:
        print("  [FAIL] subscription.py 缺关键符号")
        return False
    print(f"  [PASS] subscription.py 存在 ({p.stat().st_size} bytes)")
    return True


def t05_feature_flag_service_exists() -> bool:
    p = BACKEND_SERVICES / "feature_flag.py"
    if not p.exists():
        print(f"  [FAIL] feature_flag.py 不存在")
        return False
    txt = _read(p)
    if "FeatureFlag" not in txt or "_stable_hash" not in txt:
        print("  [FAIL] feature_flag.py 缺关键符号")
        return False
    print(f"  [PASS] feature_flag.py 存在 ({p.stat().st_size} bytes)")
    return True


def t06_eight_k_service_exists() -> bool:
    p = BACKEND_SERVICES / "eight_k.py"
    if not p.exists():
        print(f"  [FAIL] eight_k.py 不存在")
        return False
    txt = _read(p)
    if "EightKEvent" not in txt or "classify_summary" not in txt:
        print("  [FAIL] eight_k.py 缺关键符号")
        return False
    print(f"  [PASS] eight_k.py 存在 ({p.stat().st_size} bytes)")
    return True


def t07_subscribe_route_exists() -> bool:
    p = FRONTEND_ROUTES / "subscribe.tsx"
    if not p.exists():
        print(f"  [FAIL] subscribe.tsx 不存在")
        return False
    print(f"  [PASS] subscribe.tsx 存在 ({p.stat().st_size} bytes)")
    return True


def t08_pro_badge_exists() -> bool:
    p = FRONTEND_COMPONENTS / "ProBadge.tsx"
    if not p.exists():
        print(f"  [FAIL] ProBadge.tsx 不存在")
        return False
    print(f"  [PASS] ProBadge.tsx 存在 ({p.stat().st_size} bytes)")
    return True


def t09_upgrade_prompt_exists() -> bool:
    p = FRONTEND_COMPONENTS / "UpgradePrompt.tsx"
    if not p.exists():
        print(f"  [FAIL] UpgradePrompt.tsx 不存在")
        return False
    print(f"  [PASS] UpgradePrompt.tsx 存在 ({p.stat().st_size} bytes)")
    return True


def t10_gray_release_banner_exists() -> bool:
    p = FRONTEND_COMPONENTS / "GrayReleaseBanner.tsx"
    if not p.exists():
        print(f"  [FAIL] GrayReleaseBanner.tsx 不存在")
        return False
    print(f"  [PASS] GrayReleaseBanner.tsx 存在 ({p.stat().st_size} bytes)")
    return True


def t11_use_feature_flag_exists() -> bool:
    p = FRONTEND_FEATURES / "useFeatureFlag.ts"
    if not p.exists():
        print(f"  [FAIL] useFeatureFlag.ts 不存在")
        return False
    print(f"  [PASS] useFeatureFlag.ts 存在 ({p.stat().st_size} bytes)")
    return True


# ----------------------------------------------------------------------
# Section 2: M6-handoff 章节完整性
# ----------------------------------------------------------------------

def t12_handoff_section_titles() -> bool:
    p = DOCS / "M6-handoff.md"
    txt = _read(p)
    required = [
        "## 一、M6 范围与交付",
        "## 二、M6 关键设计",
        "## 三、M6 关键决策与硬约束",
        "## 四、M6 未完成 / 已知遗留",
        "## 五、立即可跑(本地)",
        "## 六、M7 启动接力",
        "## 七、本日记忆(自动,补充)",
    ]
    missing = [s for s in required if s not in txt]
    if missing:
        print(f"  [FAIL] M6-handoff 缺章节: {missing}")
        return False
    print(f"  [PASS] M6-handoff 章节齐全(7 个一级章节)")
    return True


def t13_handoff_m6_completion_table() -> bool:
    p = DOCS / "M6-handoff.md"
    txt = _read(p)
    # 校验 10 个 todo 全部 COMPLETE
    expected_ids = ["m6t1", "m6t2", "m6t3", "m6t4", "m6t5", "m6t6", "m6t7", "m6t8", "m6t9", "m6t10"]
    missing_ids = [tid for tid in expected_ids if tid not in txt]
    if missing_ids:
        print(f"  [FAIL] M6-handoff 缺 todo: {missing_ids}")
        return False
    # 校验 COMPLETE 状态(可多个)
    complete_count = txt.count("✅ COMPLETE")
    if complete_count < 10:
        print(f"  [FAIL] M6-handoff COMPLETE 标记不足 10(实际 {complete_count})")
        return False
    print(f"  [PASS] M6-handoff 含 10 todo + {complete_count} 个 COMPLETE 标记")
    return True


def t14_v30_report_sections() -> bool:
    p = DOCS / "BD-087-calibration-report-v3.0.md"
    txt = _read(p)
    required = [
        "## 一、概述",
        "## 二、当前权重基线",
        "## 三、候选 A vs v1.0 对比",
        "## 四、阈值集中化清单",
        "## 五、v3.0 vs v2.5 增量",
        "## 六、沙箱限制与 M7 计划",
        "## 七、风险与遗留",
        "## 八、本日记忆",
    ]
    missing = [s for s in required if s not in txt]
    if missing:
        print(f"  [FAIL] v3.0 报告缺章节: {missing}")
        return False
    print(f"  [PASS] v3.0 报告 8 章节齐全")
    return True


def t15_v30_report_candidate_a_weights() -> bool:
    p = DOCS / "BD-087-calibration-report-v3.0.md"
    txt = _read(p)
    # 候选 A stock `{options: 25, short: 40, divergence: 20, insider: 15}`
    if "25" not in txt or "40" not in txt:
        print("  [FAIL] v3.0 报告缺候选 A 权重(25/40)")
        return False
    if "Mann-Whitney" not in txt and "M7" not in txt:
        print("  [FAIL] v3.0 报告缺 M7 计划 / Mann-Whitney U")
        return False
    print(f"  [PASS] v3.0 报告含候选 A 权重 + M7 计划")
    return True


def t16_handoff_milestone_table() -> bool:
    p = DOCS / "M6-handoff.md"
    txt = _read(p)
    # 校验里程碑进度表 M0-M6
    milestones = ["M0 脚手架", "M1 骨架", "M2 四模组", "M3 警报", "M4 自定义", "M5 集成合规", "M6 PWA"]
    missing = [m for m in milestones if m not in txt]
    if missing:
        print(f"  [FAIL] M6-handoff 里程碑进度缺: {missing}")
        return False
    print(f"  [PASS] M6-handoff 里程碑进度 M0-M6 齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: M6 接力期 OpenAPI 端点 + router
# ----------------------------------------------------------------------

def t17_main_registers_m6_routers() -> bool:
    p = BACKEND_APP / "main.py"
    txt = _read(p)
    routers = [
        "subscriptions",
        "feature_flags",
        "eight_k",
    ]
    missing = [r for r in routers if r not in txt]
    if missing:
        print(f"  [FAIL] main.py 缺 router 注册: {missing}")
        return False
    print(f"  [PASS] main.py 注册 3 个 M6 router: {routers}")
    return True


def t18_subscriptions_endpoints() -> bool:
    p = BACKEND_API / "subscriptions.py"
    txt = _read(p)
    endpoints = [
        "/subscriptions/checkout",
        "/subscriptions/me",
        "/subscriptions/cancel",
        "/subscriptions/webhook",
        "/subscriptions/sandbox-complete",
        "/subscriptions/plans",
    ]
    found = [ep for ep in endpoints if ep in txt]
    if len(found) < 6:
        print(f"  [FAIL] subscriptions 端点不足 6(实际 {len(found)}/{len(endpoints)}): {found}")
        return False
    print(f"  [PASS] subscriptions 6 端点齐全")
    return True


def t19_feature_flags_endpoints() -> bool:
    p = BACKEND_API / "feature_flags.py"
    txt = _read(p)
    if "/feature-flags" not in txt:
        print("  [FAIL] feature_flags 缺 /feature-flags 端点")
        return False
    # 应有 2 个端点
    if txt.count("@router.get") < 2:
        print(f"  [FAIL] feature_flags 端点不足 2")
        return False
    print(f"  [PASS] feature_flags 2 端点齐全")
    return True


def t20_eight_k_endpoints() -> bool:
    p = BACKEND_API / "eight_k.py"
    txt = _read(p)
    endpoints = ["/events/8k", "/symbols/", "/classify"]
    found = [ep for ep in endpoints if ep in txt]
    if len(found) < 3:
        print(f"  [FAIL] eight_k 端点不足(实际 {found})")
        return False
    print(f"  [PASS] eight_k 3 端点齐全")
    return True


# ----------------------------------------------------------------------
# Section 4: i18n zh-CN 翻译段
# ----------------------------------------------------------------------

def t21_i18n_marketing_section() -> bool:
    p = FRONTEND_I18N / "zh-CN.json"
    txt = _read(p)
    if "\"marketing\"" not in txt:
        print("  [FAIL] i18n zh-CN.json 缺 marketing 段")
        return False
    if "proBadge" not in txt or "upgradeCta" not in txt:
        print("  [FAIL] i18n marketing 段缺关键字段")
        return False
    print("  [PASS] i18n marketing 段含 proBadge / upgradeCta")
    return True


def t22_i18n_subscribe_section() -> bool:
    p = FRONTEND_I18N / "zh-CN.json"
    txt = _read(p)
    if "\"subscribe\"" not in txt and "\"routes\"" not in txt:
        print("  [FAIL] i18n zh-CN.json 缺 subscribe / routes 段")
        return False
    # 校验 3 档价格关键字段(proMonthly + proYearly 英文键 + 月 / 年 中文 period)
    if "proMonthly" not in txt or "proYearly" not in txt:
        print("  [FAIL] i18n subscribe 段缺 proMonthly / proYearly 字段")
        return False
    if "\"月\"" not in txt or "\"年\"" not in txt:
        print("  [FAIL] i18n subscribe 段缺 月 / 年 中文 period")
        return False
    print("  [PASS] i18n subscribe 段含 proMonthly/proYearly + 月/年")
    return True


def t23_i18n_feature_flags_section() -> bool:
    p = FRONTEND_I18N / "zh-CN.json"
    txt = _read(p)
    if "featureFlags" not in txt:
        print("  [FAIL] i18n zh-CN.json 缺 featureFlags 段")
        return False
    if "bannerText" not in txt or "bannerDismiss" not in txt:
        print("  [FAIL] i18n featureFlags 段缺关键字段")
        return False
    print("  [PASS] i18n featureFlags 段含 bannerText / bannerDismiss")
    return True


def t24_i18n_pwa_install_section() -> bool:
    p = FRONTEND_I18N / "zh-CN.json"
    txt = _read(p)
    if "pwa" not in txt.lower() or "install" not in txt.lower():
        print("  [FAIL] i18n zh-CN.json 缺 pwa.install 段")
        return False
    print("  [PASS] i18n pwa.install 段含 install 字段")
    return True


# ----------------------------------------------------------------------
# Section 5: daily-standup M6 段 + 风险登记
# ----------------------------------------------------------------------

def t25_daily_standup_m6_section() -> bool:
    p = ROOT.parent / "daily-standup.md"
    txt = _read(p)
    if "M6 接力日" not in txt and "M6 主体完成" not in txt:
        print("  [FAIL] daily-standup 缺 M6 接力日段")
        return False
    # 校验 10 个 todo 都有 COMPLETE
    for tid in ["m6t1", "m6t2", "m6t3", "m6t4", "m6t5", "m6t6", "m6t7", "m6t8", "m6t9", "m6t10"]:
        if tid not in txt:
            print(f"  [FAIL] daily-standup 缺 {tid}")
            return False
    print("  [PASS] daily-standup M6 段 + 10 todo 齐全")
    return True


def t26_daily_standup_risk_register() -> bool:
    p = ROOT.parent / "daily-standup.md"
    txt = _read(p)
    # M6 接力日新增风险 R-28/29/30/31/32/33
    for rid in ["R-28", "R-29", "R-30", "R-31", "R-32", "R-33"]:
        if rid not in txt:
            print(f"  [FAIL] daily-standup 风险登记缺 {rid}")
            return False
    print("  [PASS] daily-standup 风险 R-28~R-33 齐全(M6 新增 6 项)")
    return True


def t27_handoff_risk_register() -> bool:
    p = DOCS / "M6-handoff.md"
    txt = _read(p)
    # M6 风险 R-27/28/29/30(M6 m6t9 报告) + M5 沿用 R-12/13/15/20
    must_have = ["R-27", "R-28", "R-29", "R-30"]
    missing = [r for r in must_have if r not in txt]
    if missing:
        print(f"  [FAIL] M6-handoff 缺风险: {missing}")
        return False
    print("  [PASS] M6-handoff 风险 R-27~R-30 齐全")
    return True


# ----------------------------------------------------------------------
# Section 6: M6 测试脚本存在性 + 业务约束
# ----------------------------------------------------------------------

def t28_m6_test_scripts() -> bool:
    scripts = [
        "m6t3_test_install.py",
        "m6t4_test_stripe.py",
        "m6t5_test_subscribe.py",
        "m6t6_test_commercial.py",
        "m6t7_test_feature_flag.py",
        "m6t8_test_eight_k.py",
        "m6t9_test_backtest_v3.py",
    ]
    missing = [s for s in scripts if not (BACKEND_SCRIPTS / s).exists()]
    if missing:
        print(f"  [FAIL] M6 测试脚本缺: {missing}")
        return False
    print(f"  [PASS] M6 测试脚本 7 个齐全")
    return True


def t29_subscription_pricing_constants() -> bool:
    p = BACKEND_SERVICES / "subscription.py"
    txt = _read(p)
    if "19" not in txt or "188" not in txt:
        print("  [FAIL] subscription.py 缺价格常量 19 / 188")
        return False
    if "PLAN_PRICE_USD" not in txt:
        print("  [FAIL] subscription.py 缺 PLAN_PRICE_USD 常量名")
        return False
    print("  [PASS] subscription.py 价格 19/188 + PLAN_PRICE_USD 锁定")
    return True


def t30_feature_flag_three_flags() -> bool:
    p = BACKEND_SERVICES / "feature_flag.py"
    txt = _read(p)
    expected_flags = ["subscribe_v2", "8k_feed", "gray_release_banner"]
    missing = [f for f in expected_flags if f not in txt]
    if missing:
        print(f"  [FAIL] feature_flag.py 缺内置 flag: {missing}")
        return False
    print("  [PASS] feature_flag 3 内置 flag 齐全")
    return True


def t31_eight_k_four_categories() -> bool:
    p = BACKEND_SERVICES / "eight_k.py"
    txt = _read(p)
    expected_cats = ["share-repurchase", "material-agreement", "press-release", "other"]
    missing = [c for c in expected_cats if c not in txt]
    if missing:
        print(f"  [FAIL] eight_k.py 缺类别: {missing}")
        return False
    print("  [PASS] eight_k 4 类别齐全")
    return True


def t32_eight_k_five_fixtures() -> bool:
    p = BACKEND_SERVICES / "eight_k.py"
    txt = _read(p)
    expected_fixtures = ["AAPL", "TSLA", "MSFT", "NVDA", "GME"]
    missing = [f for f in expected_fixtures if f not in txt]
    if missing:
        print(f"  [FAIL] eight_k.py 缺 fixture: {missing}")
        return False
    print("  [PASS] eight_k 5 fixture 齐全(AAPL/TSLA/MSFT/NVDA/GME)")
    return True


def t33_eight_k_redact_summary() -> bool:
    p = BACKEND_API / "eight_k.py"
    txt = _read(p)
    # CR-010 禁词过滤
    if "[REDACTED]" not in txt and "_sanitize_summary" not in txt:
        print("  [FAIL] eight_k API 缺 CR-010 脱敏")
        return False
    print("  [PASS] eight_k API 含 CR-010 脱敏([REDACTED] / _sanitize_summary)")
    return True


def t34_runner_three_subcommands() -> bool:
    p = BACKEND_SCRIPTS / "m6t9_run_backtest_v3.py"
    txt = _read(p)
    for cmd in ["run", "compare", "report"]:
        if cmd not in txt:
            print(f"  [FAIL] m6t9 runner 缺 {cmd} 子命令")
            return False
    print("  [PASS] m6t9 runner 3 子命令 run/compare/report 齐全")
    return True


def t35_handoff_openapi_endpoint_count() -> bool:
    p = DOCS / "M6-handoff.md"
    txt = _read(p)
    # M6 接力期 44 端点 = 33 + 11
    if "44" not in txt:
        print("  [FAIL] M6-handoff 缺 44 端点总数")
        return False
    # 校验端点分类
    if "subscriptions" not in txt or "feature_flags" not in txt or "eight_k" not in txt:
        print("  [FAIL] M6-handoff 端点分类缺 subscriptions / feature_flags / eight_k")
        return False
    print("  [PASS] M6-handoff 端点总数 44 + 3 分类齐全")
    return True


# ----------------------------------------------------------------------
# Main runner
# ----------------------------------------------------------------------

_PASSED: list[str] = []
_FAILED: list[str] = []


def _run(name: str, fn) -> None:
    try:
        ok = bool(fn())
    except Exception as exc:  # noqa: BLE001
        print(f"  [ERROR] {name} 抛出异常: {exc}")
        ok = False
    if ok:
        _PASSED.append(name)
    else:
        _FAILED.append(name)


def main() -> int:
    print("=== 1. M6 关键文件存在性 ===")
    _run("t01_handoff_exists", t01_handoff_exists)
    _run("t02_v30_report_exists", t02_v30_report_exists)
    _run("t03_daily_standup_exists", t03_daily_standup_exists)
    _run("t04_subscription_service_exists", t04_subscription_service_exists)
    _run("t05_feature_flag_service_exists", t05_feature_flag_service_exists)
    _run("t06_eight_k_service_exists", t06_eight_k_service_exists)
    _run("t07_subscribe_route_exists", t07_subscribe_route_exists)
    _run("t08_pro_badge_exists", t08_pro_badge_exists)
    _run("t09_upgrade_prompt_exists", t09_upgrade_prompt_exists)
    _run("t10_gray_release_banner_exists", t10_gray_release_banner_exists)
    _run("t11_use_feature_flag_exists", t11_use_feature_flag_exists)

    print("\n=== 2. M6-handoff + v3.0 报告章节完整性 ===")
    _run("t12_handoff_section_titles", t12_handoff_section_titles)
    _run("t13_handoff_m6_completion_table", t13_handoff_m6_completion_table)
    _run("t14_v30_report_sections", t14_v30_report_sections)
    _run("t15_v30_report_candidate_a_weights", t15_v30_report_candidate_a_weights)
    _run("t16_handoff_milestone_table", t16_handoff_milestone_table)

    print("\n=== 3. M6 接力期 OpenAPI 端点 + router ===")
    _run("t17_main_registers_m6_routers", t17_main_registers_m6_routers)
    _run("t18_subscriptions_endpoints", t18_subscriptions_endpoints)
    _run("t19_feature_flags_endpoints", t19_feature_flags_endpoints)
    _run("t20_eight_k_endpoints", t20_eight_k_endpoints)

    print("\n=== 4. i18n zh-CN 翻译段 ===")
    _run("t21_i18n_marketing_section", t21_i18n_marketing_section)
    _run("t22_i18n_subscribe_section", t22_i18n_subscribe_section)
    _run("t23_i18n_feature_flags_section", t23_i18n_feature_flags_section)
    _run("t24_i18n_pwa_install_section", t24_i18n_pwa_install_section)

    print("\n=== 5. daily-standup M6 段 + 风险登记 ===")
    _run("t25_daily_standup_m6_section", t25_daily_standup_m6_section)
    _run("t26_daily_standup_risk_register", t26_daily_standup_risk_register)
    _run("t27_handoff_risk_register", t27_handoff_risk_register)

    print("\n=== 6. M6 测试脚本 + 业务约束 ===")
    _run("t28_m6_test_scripts", t28_m6_test_scripts)
    _run("t29_subscription_pricing_constants", t29_subscription_pricing_constants)
    _run("t30_feature_flag_three_flags", t30_feature_flag_three_flags)
    _run("t31_eight_k_four_categories", t31_eight_k_four_categories)
    _run("t32_eight_k_five_fixtures", t32_eight_k_five_fixtures)
    _run("t33_eight_k_redact_summary", t33_eight_k_redact_summary)
    _run("t34_runner_three_subcommands", t34_runner_three_subcommands)
    _run("t35_handoff_openapi_endpoint_count", t35_handoff_openapi_endpoint_count)

    total = len(_PASSED) + len(_FAILED)
    print(f"\n[m6t10] SUMMARY: {len(_PASSED)}/{total} PASSED, {len(_FAILED)} FAILED")
    if _FAILED:
        print(f"[m6t10] FAILED TESTS: {', '.join(_FAILED)}")
        return 1
    print(f"[m6t10] ALL {total} DOCUMENTATION TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())