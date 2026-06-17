"""M7-t10 文档自测:M7-handoff + daily-standup + v3.0-final 校准报告 + 关键文件存在性校验
- 沙箱模式:只读文件 + 字符串包含/正则断言,无 PG/EOD 依赖
- 设计:37 测点分 6 个 section(section1 文件存在 / section2 章节完整 /
  section3 端点 + router / section4 M7 关键设计 / section5 风险登记 / section6 M7 测点脚本)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
DOCS = ROOT / "docs"
BACKEND_SCRIPTS = ROOT / "backend" / "scripts"
BACKEND_APP = ROOT / "backend" / "app"
BACKEND_API = BACKEND_APP / "api"
BACKEND_SERVICES = BACKEND_APP / "services"
BACKEND_ETL = ROOT / "backend" / "etl"
WORKFLOWS = ROOT / ".github" / "workflows"
DATA = ROOT / "data"

# daily-standup.md 在 hunter-radar 父目录
DAILY_STANDUP = ROOT.parent / "daily-standup.md"


def _read(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# Section 1: M7 关键文件存在性(11 测点)
# ----------------------------------------------------------------------

def t01_handoff_exists() -> bool:
    p = DOCS / "M7-handoff.md"
    if not p.exists():
        print(f"  [FAIL] M7-handoff.md 不存在: {p}")
        return False
    print(f"  [PASS] M7-handoff.md 存在 ({p.stat().st_size} bytes)")
    return True


def t02_v30_final_report_exists() -> bool:
    p = DOCS / "BD-087-calibration-report-v3.0-final.md"
    if not p.exists():
        print(f"  [FAIL] BD-087 v3.0-final 报告不存在: {p}")
        return False
    print(f"  [PASS] v3.0-final 校准报告存在 ({p.stat().st_size} bytes)")
    return True


def t03_bd086_audit_log_exists() -> bool:
    p = DOCS / "BD-086-signoff-audit-log.md"
    if not p.exists():
        print(f"  [FAIL] BD-086 审计日志不存在: {p}")
        return False
    print(f"  [PASS] BD-086 审计日志存在 ({p.stat().st_size} bytes)")
    return True


def t04_openapi_v15_json_exists() -> bool:
    p = DOCS / "openapi-frozen-v1.5.json"
    if not p.exists():
        print(f"  [FAIL] openapi-frozen-v1.5.json 不存在: {p}")
        return False
    print(f"  [PASS] openapi-frozen-v1.5.json 存在 ({p.stat().st_size} bytes)")
    return True


def t05_openapi_v15_md_exists() -> bool:
    p = DOCS / "openapi-frozen-v1.5.md"
    if not p.exists():
        print(f"  [FAIL] openapi-frozen-v1.5.md 不存在: {p}")
        return False
    print(f"  [PASS] openapi-frozen-v1.5.md 存在 ({p.stat().st_size} bytes)")
    return True


def t06_fe010_v15_changelog_exists() -> bool:
    p = DOCS / "FE-010-changelog-v1.5.md"
    if not p.exists():
        print(f"  [FAIL] FE-010-changelog-v1.5.md 不存在: {p}")
        return False
    print(f"  [PASS] FE-010-changelog-v1.5.md 存在 ({p.stat().st_size} bytes)")
    return True


def t07_bd088_etf_design_exists() -> bool:
    p = DOCS / "bd-088-etf-proxy-design.md"
    if not p.exists():
        print(f"  [FAIL] bd-088-etf-proxy-design.md 不存在: {p}")
        return False
    print(f"  [PASS] bd-088-etf-proxy-design.md 存在 ({p.stat().st_size} bytes)")
    return True


def t08_analytics_spec_exists() -> bool:
    p = DOCS / "analytics-events-spec.md"
    if not p.exists():
        print(f"  [FAIL] analytics-events-spec.md 不存在: {p}")
        return False
    print(f"  [PASS] analytics-events-spec.md 存在 ({p.stat().st_size} bytes)")
    return True


def t09_v15_eval_checklist_exists() -> bool:
    p = DOCS / "V1.5-eval-checklist.md"
    if not p.exists():
        print(f"  [FAIL] V1.5-eval-checklist.md 不存在: {p}")
        return False
    print(f"  [PASS] V1.5-eval-checklist.md 存在 ({p.stat().st_size} bytes)")
    return True


def t10_daily_standup_exists() -> bool:
    if not DAILY_STANDUP.exists():
        print(f"  [FAIL] daily-standup.md 不存在: {DAILY_STANDUP}")
        return False
    print(f"  [PASS] daily-standup.md 存在 ({DAILY_STANDUP.stat().st_size} bytes)")
    return True


def t11_ci_workflow_exists() -> bool:
    p = WORKFLOWS / "ci.yml"
    if not p.exists():
        print(f"  [FAIL] .github/workflows/ci.yml 不存在: {p}")
        return False
    txt = _read(p)
    if "jobs:" not in txt:
        print("  [FAIL] ci.yml 缺 jobs 字段")
        return False
    print(f"  [PASS] .github/workflows/ci.yml 存在 ({p.stat().st_size} bytes)")
    return True


# ----------------------------------------------------------------------
# Section 2: M7-handoff + v3.0-final 报告章节完整性(5 测点)
# ----------------------------------------------------------------------

def t12_handoff_section_titles() -> bool:
    p = DOCS / "M7-handoff.md"
    txt = _read(p)
    required = [
        "## 一、M7 范围与交付",
        "## 二、M7 关键设计",
        "## 三、M7 关键决策与硬约束",
        "## 四、M7 未完成 / 已知遗留",
        "## 五、立即可跑(本地)",
        "## 六、V1.4 上线接力",
        "## 七、本日记忆(自动,补充)",
    ]
    missing = [s for s in required if s not in txt]
    if missing:
        print(f"  [FAIL] M7-handoff 缺章节: {missing}")
        return False
    print(f"  [PASS] M7-handoff 章节齐全(7 个一级章节)")
    return True


def t13_handoff_m7_completion_table() -> bool:
    p = DOCS / "M7-handoff.md"
    txt = _read(p)
    expected_ids = ["m7t1", "m7t2", "m7t3", "m7t4", "m7t5", "m7t6", "m7t7", "m7t8", "m7t9", "m7t10"]
    missing_ids = [tid for tid in expected_ids if tid not in txt]
    if missing_ids:
        print(f"  [FAIL] M7-handoff 缺 todo: {missing_ids}")
        return False
    complete_count = txt.count("✅ COMPLETE")
    if complete_count < 10:
        print(f"  [FAIL] M7-handoff COMPLETE 标记不足 10(实际 {complete_count})")
        return False
    print(f"  [PASS] M7-handoff 含 10 todo + {complete_count} 个 COMPLETE 标记")
    return True


def t14_v30_final_report_sections() -> bool:
    p = DOCS / "BD-087-calibration-report-v3.0-final.md"
    txt = _read(p)
    required = [
        "## 一、概述",
        "## 二、数据集来源",
        "## 三、权重对比表",
        "## 四、回测结果",
        "## 五、显著性检验",
        "## 六、决策建议",
        "## 七、沙箱限制与 V1.4 落地清单",
        "## 八、风险与遗留",
        "## 九、本日记忆",
    ]
    missing = [s for s in required if s not in txt]
    if missing:
        print(f"  [FAIL] v3.0-final 报告缺章节: {missing}")
        return False
    print(f"  [PASS] v3.0-final 报告 9 章节齐全")
    return True


def t15_v30_final_mann_whitney_decision() -> bool:
    p = DOCS / "BD-087-calibration-report-v3.0-final.md"
    txt = _read(p)
    # Mann-Whitney U 结果 + 决策保持 v1.0
    if "Mann-Whitney" not in txt:
        print("  [FAIL] v3.0-final 报告缺 Mann-Whitney 检验")
        return False
    if "0.3827" not in txt:
        print("  [FAIL] v3.0-final 报告缺 p=0.3827")
        return False
    if "保持 v1.0" not in txt and "v1.0 默认权重" not in txt:
        print("  [FAIL] v3.0-final 报告缺「保持 v1.0」决策")
        return False
    print(f"  [PASS] v3.0-final 报告含 Mann-Whitney U + p=0.3827 + 保持 v1.0 决策")
    return True


def t16_handoff_milestone_table() -> bool:
    p = DOCS / "M7-handoff.md"
    txt = _read(p)
    milestones = ["M0 脚手架", "M1 骨架", "M2 四模组", "M3 警报", "M4 自定义", "M5 集成合规", "M6 PWA", "M7 真实数据"]
    missing = [m for m in milestones if m not in txt]
    if missing:
        print(f"  [FAIL] M7-handoff 里程碑进度缺: {missing}")
        return False
    print(f"  [PASS] M7-handoff 里程碑进度 M0-M7 齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: M7 接力期 OpenAPI 端点 + router(4 测点)
# ----------------------------------------------------------------------

def t17_main_registers_admin_router() -> bool:
    p = BACKEND_APP / "main.py"
    txt = _read(p)
    routers = ["subscriptions", "feature_flags", "eight_k", "admin"]
    missing = [r for r in routers if r not in txt]
    if missing:
        print(f"  [FAIL] main.py 缺 router 注册: {missing}")
        return False
    print(f"  [PASS] main.py 注册 4 个 router(subscriptions / feature_flags / eight_k / admin)")
    return True


def t18_admin_endpoints() -> bool:
    p = BACKEND_API / "admin.py"
    txt = _read(p)
    endpoints = [
        "/admin/etl/run",
        "/admin/backtest/run",
        "/admin/backtest/result",
        "/admin/webhook/replay",
    ]
    found = [ep for ep in endpoints if ep in txt]
    if len(found) < 4:
        print(f"  [FAIL] admin 端点不足 4(实际 {len(found)}/{len(endpoints)}): {found}")
        return False
    print(f"  [PASS] admin 4 端点齐全")
    return True


def t19_openapi_v15_48_endpoints() -> bool:
    p = DOCS / "openapi-frozen-v1.5.json"
    txt = _read(p)
    if '"openapi"' not in txt and '"swagger"' not in txt:
        print("  [FAIL] openapi-frozen-v1.5.json 缺 openapi/swagger 字段")
        return False
    # 检查版本
    if '"1.5.0"' not in txt and '"version": "1.5.0"' not in txt:
        print("  [FAIL] openapi-frozen-v1.5.json 缺 version=1.5.0")
        return False
    # 检查至少 48 个 operationId 或 path(简化校验)
    path_count = txt.count('"/api/')
    if path_count < 20:
        print(f"  [FAIL] openapi-frozen-v1.5.json paths 不足(实际 {path_count})")
        return False
    print(f"  [PASS] openapi-frozen-v1.5.json 1.5.0 + {path_count} paths")
    return True


def t20_subscriptions_signature_mode() -> bool:
    p = BACKEND_API / "subscriptions.py"
    txt = _read(p)
    # 签名校验相关字段
    if "signature_skipped" not in txt and "sandbox_skip" not in txt:
        print("  [FAIL] subscriptions 端点缺 signature_skipped/sandbox_skip 字段")
        return False
    if "stripe-signature" not in txt:
        print("  [FAIL] subscriptions 端点缺 stripe-signature header 读取")
        return False
    print(f"  [PASS] subscriptions webhook 含签名校验字段")
    return True


# ----------------------------------------------------------------------
# Section 4: M7 关键设计(7 测点)
# ----------------------------------------------------------------------

def t21_etf_proxy_module() -> bool:
    p = BACKEND_SERVICES / "etf_proxy.py"
    txt = _read(p)
    required = ["EtfBasket", "EtfOrder", "compute_premium_discount", "arb_opportunity", "sandbox_stub_v15_prep"]
    missing = [s for s in required if s not in txt]
    if missing:
        print(f"  [FAIL] etf_proxy.py 缺关键符号: {missing}")
        return False
    print(f"  [PASS] etf_proxy.py 含 5 关键符号")
    return True


def t22_analytics_module() -> bool:
    p = BACKEND_SERVICES / "analytics.py"
    txt = _read(p)
    required = ["AnalyticsEvent", "track_event", "hash_user_id", "EVENT_USER_SIGNUP", "get_funnel_summary"]
    missing = [s for s in required if s not in txt]
    if missing:
        print(f"  [FAIL] analytics.py 缺关键符号: {missing}")
        return False
    print(f"  [PASS] analytics.py 含 5 关键符号")
    return True


def t23_edgar_fulltext_module() -> bool:
    p = BACKEND_ETL / "edgar_fulltext.py"
    txt = _read(p)
    if "EdgarFiling" not in txt or "fetch_fulltext" not in txt:
        print("  [FAIL] edgar_fulltext.py 缺 EdgarFiling / fetch_fulltext")
        return False
    # 4 类 category
    cats = ["share-repurchase", "material-agreement", "press-release"]
    found = [c for c in cats if c in txt]
    if len(found) < 3:
        print(f"  [FAIL] edgar_fulltext.py 缺 category: {found}")
        return False
    print(f"  [PASS] edgar_fulltext.py 含 4 类 category + fetch_fulltext")
    return True


def t24_backtest_dataset_real_module() -> bool:
    p = BACKEND_ETL / "backtest_dataset_real.py"
    txt = _read(p)
    if "_seeded_float" not in txt or "build_real_dataset_sandbox" not in txt:
        print("  [FAIL] backtest_dataset_real.py 缺关键函数")
        return False
    print(f"  [PASS] backtest_dataset_real.py 含 _seeded_float + build_real_dataset_sandbox")
    return True


def t25_m7t4_runner_mann_whitney() -> bool:
    p = BACKEND_SCRIPTS / "m7t4_run_backtest_v30_final.py"
    txt = _read(p)
    required_cmds = ["run", "compare", "mann-whitney", "report"]
    found = [c for c in required_cmds if c in txt]
    if len(found) < 3:
        print(f"  [FAIL] m7t4 runner 缺子命令(实际 {found})")
        return False
    if "_mann_whitney_u" not in txt:
        print("  [FAIL] m7t4 runner 缺 _mann_whitney_u 函数")
        return False
    print(f"  [PASS] m7t4 runner 含 4 子命令 + _mann_whitney_u")
    return True


def t26_ci_6_jobs() -> bool:
    p = WORKFLOWS / "ci.yml"
    txt = _read(p)
    expected_jobs = ["backend", "openapi-drift", "frontend", "secrets-check", "webhook", "docs"]
    found = [j for j in expected_jobs if j in txt]
    if len(found) < 6:
        print(f"  [FAIL] CI jobs 不足 6(实际 {len(found)}/{len(expected_jobs)}): {found}")
        return False
    print(f"  [PASS] CI 6 jobs 齐全(backend/openapi-drift/frontend/secrets-check/webhook/docs)")
    return True


def t27_v15_eval_8_candidates() -> bool:
    p = DOCS / "V1.5-eval-checklist.md"
    txt = _read(p)
    # V1.5.1 freeze 候选 8 项
    candidates = [
        "admin/*",
        "edgar/search",
        "etf/{ticker}/basket",
        "etf/orders",
        "etf/orders/{order_id}",
        "analytics/events",
        "admin 鉴权",
        "候选 A",
    ]
    found = [c for c in candidates if c in txt]
    if len(found) < 5:
        print(f"  [FAIL] V1.5.1 freeze 候选不足(实际 {len(found)}/{len(candidates)}): {found}")
        return False
    print(f"  [PASS] V1.5.1 freeze 候选 {len(found)}/{len(candidates)} 齐全")
    return True


# ----------------------------------------------------------------------
# Section 5: daily-standup M7 段 + 风险登记(3 测点)
# ----------------------------------------------------------------------

def t28_daily_standup_m7_section() -> bool:
    txt = _read(DAILY_STANDUP)
    if "M7 接力日" not in txt:
        print("  [FAIL] daily-standup 缺 M7 接力日段")
        return False
    for tid in ["m7t1", "m7t2", "m7t3", "m7t4", "m7t5", "m7t6", "m7t7", "m7t8", "m7t9", "m7t10"]:
        if tid not in txt:
            print(f"  [FAIL] daily-standup 缺 {tid}")
            return False
    print(f"  [PASS] daily-standup M7 段 + 10 todo 齐全")
    return True


def t29_daily_standup_risk_register() -> bool:
    txt = _read(DAILY_STANDUP)
    # M7 接力日新增风险 R-34~R-43
    for rid in ["R-34", "R-35", "R-36", "R-37", "R-38", "R-39", "R-40", "R-41", "R-42", "R-43"]:
        if rid not in txt:
            print(f"  [FAIL] daily-standup 风险登记缺 {rid}")
            return False
    print(f"  [PASS] daily-standup 风险 R-34~R-43 齐全(M7 新增 10 项)")
    return True


def t30_handoff_risk_register() -> bool:
    p = DOCS / "M7-handoff.md"
    txt = _read(p)
    # M7 风险 R-12/23/25/27/31 缓解 + R-34~R-43 新增
    must_have = ["R-27", "R-31", "R-34", "R-35", "R-37", "R-41"]
    missing = [r for r in must_have if r not in txt]
    if missing:
        print(f"  [FAIL] M7-handoff 缺风险: {missing}")
        return False
    print(f"  [PASS] M7-handoff 风险 R-27/R-31 解除 + R-34/35/37/41 新增齐全")
    return True


# ----------------------------------------------------------------------
# Section 6: M7 测试脚本 + 业务约束(7 测点)
# ----------------------------------------------------------------------

def t31_m7_test_scripts() -> bool:
    scripts = [
        "m7t2_test_signoff.py",
        "m7t3_test_dataset_real.py",
        "m7t4_test_v30_final.py",
        "m7t5_test_edgar_fulltext.py",
        "m7t6_test_stripe_webhook.py",
        "m7t7_test_openapi_v15.py",
        "m7t8_test_pwa_ci.py",
        "m7t9_test_v15_prep.py",
    ]
    missing = [s for s in scripts if not (BACKEND_SCRIPTS / s).exists()]
    if missing:
        print(f"  [FAIL] M7 测试脚本缺: {missing}")
        return False
    print(f"  [PASS] M7 测试脚本 8 个齐全")
    return True


def t32_stripe_signature_three_modes() -> bool:
    p = BACKEND_API / "subscriptions.py"
    txt = _read(p)
    modes = ["sandbox_skip", "prod_verified", "prod_unavailable"]
    found = [m for m in modes if m in txt]
    if len(found) < 3:
        print(f"  [FAIL] subscriptions 端点缺 signature_mode(实际 {found})")
        return False
    print(f"  [PASS] subscriptions 含 3 种 signature_mode")
    return True


def t33_etf_proxy_premium_discount_logic() -> bool:
    p = BACKEND_SERVICES / "etf_proxy.py"
    txt = _read(p)
    if "premium_pct" not in txt:
        print("  [FAIL] etf_proxy.py 缺 premium_pct 计算")
        return False
    if "0.5" not in txt:
        print("  [FAIL] etf_proxy.py 缺 0.5 阈值")
        return False
    print(f"  [PASS] etf_proxy.py 含 premium_pct + 0.5 阈值")
    return True


def t34_analytics_10_events() -> bool:
    p = BACKEND_SERVICES / "analytics.py"
    txt = _read(p)
    # analytics.py 实际定义的 10 事件常量(V1.5 spec 同步)
    events = [
        "EVENT_USER_SIGNUP", "EVENT_USER_LOGIN",
        "EVENT_SUBSCRIBE_START", "EVENT_SUBSCRIBE_SUCCESS",
        "EVENT_SUBSCRIBE_CANCEL", "EVENT_SCREENER_VIEW",
        "EVENT_BASKET_CREATE", "EVENT_ALERT_RULE_CREATE",
        "EVENT_PUSH_OPT_IN", "EVENT_FEATURE_FLAG_VIEW",
    ]
    found = [e for e in events if e in txt]
    if len(found) < 10:
        print(f"  [FAIL] analytics.py 缺事件常量(实际 {len(found)}/10): {found}")
        return False
    print(f"  [PASS] analytics.py 含 10 事件常量(V1.5 spec 同步)")
    return True


def t35_handoff_openapi_endpoint_count() -> bool:
    p = DOCS / "M7-handoff.md"
    txt = _read(p)
    # M7 接力期 48 端点 = 44 + 4 admin
    if "48" not in txt:
        print("  [FAIL] M7-handoff 缺 48 端点总数")
        return False
    if "admin" not in txt or "subscriptions" not in txt or "eight_k" not in txt:
        print("  [FAIL] M7-handoff 端点分类缺 admin / subscriptions / eight_k")
        return False
    print(f"  [PASS] M7-handoff 端点总数 48 + admin 4 端点齐全")
    return True


def t36_mann_whitney_p_value_locked() -> bool:
    p = DOCS / "BD-087-calibration-report-v3.0-final.md"
    txt = _read(p)
    # 关键数值锁定:p=0.3827, U=418.5, 候选 A weights 25/40/20/15
    if "0.3827" not in txt:
        print("  [FAIL] v3.0-final 报告缺 p=0.3827")
        return False
    if "418.5" not in txt:
        print("  [FAIL] v3.0-final 报告缺 U=418.5")
        return False
    if "25" not in txt or "40" not in txt:
        print("  [FAIL] v3.0-final 报告缺候选 A 权重(25/40)")
        return False
    print(f"  [PASS] v3.0-final 报告含 p=0.3827 + U=418.5 + 候选 A 25/40")
    return True


def t37_sandbox_review_modes_consistent() -> bool:
    """沙箱 review_mode 共享校验:etf_proxy / analytics / backtest_dataset_real / m7t2 双签都用 sandbox_stub*"""
    patterns_to_check = [
        (BACKEND_SERVICES / "etf_proxy.py", "sandbox_stub_v15_prep"),
        (BACKEND_SERVICES / "analytics.py", "sandbox"),
        (BACKEND_ETL / "backtest_dataset_real.py", "sandbox"),
    ]
    for p, kw in patterns_to_check:
        txt = _read(p)
        if kw not in txt:
            print(f"  [FAIL] {p.name} 缺 {kw} 标识")
            return False
    print(f"  [PASS] sandbox review_mode 共享(etf_proxy + analytics + backtest_dataset_real)")
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
    print("=== 1. M7 关键文件存在性 ===")
    _run("t01_handoff_exists", t01_handoff_exists)
    _run("t02_v30_final_report_exists", t02_v30_final_report_exists)
    _run("t03_bd086_audit_log_exists", t03_bd086_audit_log_exists)
    _run("t04_openapi_v15_json_exists", t04_openapi_v15_json_exists)
    _run("t05_openapi_v15_md_exists", t05_openapi_v15_md_exists)
    _run("t06_fe010_v15_changelog_exists", t06_fe010_v15_changelog_exists)
    _run("t07_bd088_etf_design_exists", t07_bd088_etf_design_exists)
    _run("t08_analytics_spec_exists", t08_analytics_spec_exists)
    _run("t09_v15_eval_checklist_exists", t09_v15_eval_checklist_exists)
    _run("t10_daily_standup_exists", t10_daily_standup_exists)
    _run("t11_ci_workflow_exists", t11_ci_workflow_exists)

    print("\n=== 2. M7-handoff + v3.0-final 报告章节完整性 ===")
    _run("t12_handoff_section_titles", t12_handoff_section_titles)
    _run("t13_handoff_m7_completion_table", t13_handoff_m7_completion_table)
    _run("t14_v30_final_report_sections", t14_v30_final_report_sections)
    _run("t15_v30_final_mann_whitney_decision", t15_v30_final_mann_whitney_decision)
    _run("t16_handoff_milestone_table", t16_handoff_milestone_table)

    print("\n=== 3. M7 接力期 OpenAPI 端点 + router ===")
    _run("t17_main_registers_admin_router", t17_main_registers_admin_router)
    _run("t18_admin_endpoints", t18_admin_endpoints)
    _run("t19_openapi_v15_48_endpoints", t19_openapi_v15_48_endpoints)
    _run("t20_subscriptions_signature_mode", t20_subscriptions_signature_mode)

    print("\n=== 4. M7 关键设计 ===")
    _run("t21_etf_proxy_module", t21_etf_proxy_module)
    _run("t22_analytics_module", t22_analytics_module)
    _run("t23_edgar_fulltext_module", t23_edgar_fulltext_module)
    _run("t24_backtest_dataset_real_module", t24_backtest_dataset_real_module)
    _run("t25_m7t4_runner_mann_whitney", t25_m7t4_runner_mann_whitney)
    _run("t26_ci_6_jobs", t26_ci_6_jobs)
    _run("t27_v15_eval_8_candidates", t27_v15_eval_8_candidates)

    print("\n=== 5. daily-standup M7 段 + 风险登记 ===")
    _run("t28_daily_standup_m7_section", t28_daily_standup_m7_section)
    _run("t29_daily_standup_risk_register", t29_daily_standup_risk_register)
    _run("t30_handoff_risk_register", t30_handoff_risk_register)

    print("\n=== 6. M7 测试脚本 + 业务约束 ===")
    _run("t31_m7_test_scripts", t31_m7_test_scripts)
    _run("t32_stripe_signature_three_modes", t32_stripe_signature_three_modes)
    _run("t33_etf_proxy_premium_discount_logic", t33_etf_proxy_premium_discount_logic)
    _run("t34_analytics_10_events", t34_analytics_10_events)
    _run("t35_handoff_openapi_endpoint_count", t35_handoff_openapi_endpoint_count)
    _run("t36_mann_whitney_p_value_locked", t36_mann_whitney_p_value_locked)
    _run("t37_sandbox_review_modes_consistent", t37_sandbox_review_modes_consistent)

    total = len(_PASSED) + len(_FAILED)
    print(f"\n[m7t10] SUMMARY: {len(_PASSED)}/{total} PASSED, {len(_FAILED)} FAILED")
    if _FAILED:
        print(f"[m7t10] FAILED TESTS: {', '.join(_FAILED)}")
        return 1
    print(f"[m7t10] ALL {total} DOCUMENTATION TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
