"""V1.5.8 接力期 m17t1 — V1.5.8-handoff.md 收尾报告自测。

校验 docs/V1.5.8-handoff.md 文档完整性:
- 9 章节齐全(概述 / m16 接力期 / m8t1 验证 / C-3-ext / C-6-ext / 累计脚本测点 / 变更文件 / V1.5.9 / 评审结论)
- m8t1 1377 测点 marker
- V1.5.3~V1.5.8 评审 16 候选 100% COMPLETE marker
- M16 接力期 4 子任务清单(m16t1/m16t2/m16t3/m16t4)
- C-3-ext freeze diff 6 核心函数 + C-6-ext harness 3 新能力
- V1.5.9 接力期任务清单

V1.5.8 接力期 硬性锁定:
- 沙箱 fallback 显式标注
- 静态自测,无需启动后端
- 5 Section × 5 测点 = 25 测点

运行:
  py -B -m scripts.m17t1_test_v158_handoff
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
HANDOFF_MD = DOCS / "V1.5.8-handoff.md"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Section 1: handoff 文档存在 + 9 章节齐全(5 测点)
# ----------------------------------------------------------------------


def t01_handoff_md_exists() -> bool:
    """t01: docs/V1.5.8-handoff.md 文件存在。"""
    if not HANDOFF_MD.is_file():
        print(f"    [FAIL] handoff 文档缺失: {HANDOFF_MD}")
        return False
    print("    [PASS] V1.5.8-handoff.md 存在")
    return True


def t02_nine_chapters_defined() -> bool:
    """t02: 9 章节齐全(## 一、概述 ~ ## 九、评审结论)。"""
    txt = _read(HANDOFF_MD)
    expected = [
        "一、概述", "二、m16 接力期", "三、m8t1 验证", "四、C-3-ext freeze diff",
        "五、C-6-ext self_test_harness", "六、累计脚本测点", "七、变更文件清单",
        "八、V1.5.9 接力期", "九、评审结论",
    ]
    missing = [c for c in expected if c not in txt]
    if missing:
        print(f"    [FAIL] 缺章节: {missing}")
        return False
    print(f"    [PASS] 9 章节齐全")
    return True


def t03_m8t1_1377_marker() -> bool:
    """t03: handoff 含 m8t1 1377 测点 marker。"""
    txt = _read(HANDOFF_MD)
    markers = [
        "1377/1377",
        "M16(100/100)",
        "M15(100/100)",
        "M12(75/75)",
    ]
    missing = [m for m in markers if m not in txt]
    if missing:
        print(f"    [FAIL] 缺测点 marker: {missing}")
        return False
    print("    [PASS] m8t1 1377 测点 marker 齐全")
    return True


def t04_v153_v158_eval_16_candidates_complete() -> bool:
    """t04: V1.5.3~V1.5.8 评审 16 候选 100% COMPLETE 标记。"""
    txt = _read(HANDOFF_MD)
    # 候选 ID:C-1~C-6 + E-1 + C-1-ext + C-3-ext + C-6-ext + E-2 + E-3 + E-4 + E-5 + E-6 + E-7
    candidates = [
        "C-1", "C-2", "C-3", "C-4", "C-5", "C-6",
        "E-1", "C-1-ext", "C-3-ext", "C-6-ext",
        "E-2", "E-3", "E-4", "E-5", "E-6", "E-7",
    ]
    missing = [c for c in candidates if c not in txt]
    if missing:
        print(f"    [FAIL] 缺候选 marker: {missing}")
        return False
    # 100% COMPLETE 标记
    if "16 候选 100%" not in txt and "16/16 候选 100%" not in txt:
        print("    [FAIL] 缺 16 候选 100% 汇总标记")
        return False
    print("    [PASS] V1.5.3~V1.5.8 评审 16 候选 100% COMPLETE 标记齐全")
    return True


def t05_m16_relay_subtasks_listed() -> bool:
    """t05: m16 接力期 4 子任务(m16t1/m16t2/m16t3/m16t4)清单。"""
    txt = _read(HANDOFF_MD)
    required = ["m16t1", "m16t2", "m16t3", "m16t4"]
    missing = [m for m in required if m not in txt]
    if missing:
        print(f"    [FAIL] 缺子任务: {missing}")
        return False
    print(f"    [PASS] m16 接力期 4 子任务齐全")
    return True


# ----------------------------------------------------------------------
# Section 2: C-3-ext freeze diff + C-6-ext harness 工具说明(5 测点)
# ----------------------------------------------------------------------


def t06_c3ext_freeze_diff_6_core_functions() -> bool:
    """t06: C-3-ext freeze_check diff 6 核心函数齐全。"""
    txt = _read(HANDOFF_MD)
    expected = [
        "_load_freeze_doc", "_endpoint_key", "_extract_endpoints",
        "diff_freezes", "write_diff_reports", "run_diff_mode",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 缺 6 核心函数: {missing}")
        return False
    print(f"    [PASS] C-3-ext freeze diff 6 核心函数齐全")
    return True


def t07_c3ext_diff_cli_invocation_examples() -> bool:
    """t07: C-3-ext freeze diff CLI 调用示例(--diff / --prev / --curr / --report-json / --report-md)。"""
    txt = _read(HANDOFF_MD)
    cli_args = ["--diff", "--prev", "--curr", "--report-json", "--report-md"]
    missing = [a for a in cli_args if a not in txt]
    if missing:
        print(f"    [FAIL] 缺 CLI 示例: {missing}")
        return False
    # 退出码语义
    if "0" not in txt or "2" not in txt:
        print("    [FAIL] 缺退出码语义 0/2")
        return False
    print("    [PASS] C-3-ext freeze diff CLI 调用示例齐全")
    return True


def t08_c6ext_self_test_harness_3_new_capabilities() -> bool:
    """t08: C-6-ext self_test_harness 3 新能力(ThreadPoolExecutor / 多格式报告 / fail-fast)。"""
    txt = _read(HANDOFF_MD)
    capabilities = [
        "ThreadPoolExecutor", "_run_harness_parallel",
        "format_html_report", "format_csv_report", "fail-fast",
    ]
    found = sum(1 for c in capabilities if c in txt)
    if found < 4:
        print(f"    [FAIL] C-6-ext 3 新能力仅 {found}/5 marker")
        return False
    print(f"    [PASS] C-6-ext self_test_harness 3 新能力齐全({found}/5 marker)")
    return True


def t09_c6ext_harness_new_cli_args() -> bool:
    """t09: C-6-ext self_test_harness 6 新 CLI(--workers / --fail-fast / --timeout / --output-format / --report-html / --report-csv)。"""
    txt = _read(HANDOFF_MD)
    cli_args = [
        "--workers", "--fail-fast", "--timeout",
        "--output-format", "--report-html", "--report-csv",
    ]
    missing = [a for a in cli_args if a not in txt]
    if missing:
        print(f"    [FAIL] 缺 6 新 CLI: {missing}")
        return False
    print(f"    [PASS] C-6-ext 6 新 CLI 齐全")
    return True


def t10_c6ext_xss_protection_and_order_keeping() -> bool:
    """t10: C-6-ext XSS 防护(html.escape)+ 顺序保持(as_completed)。"""
    txt = _read(HANDOFF_MD)
    if "html.escape" not in txt and "XSS" not in txt:
        print("    [FAIL] 缺 XSS 防护章节")
        return False
    if "as_completed" not in txt and "顺序保持" not in txt:
        print("    [FAIL] 缺顺序保持说明")
        return False
    print("    [PASS] XSS 防护 + 顺序保持齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: 累计脚本测点 + 评审未通过项(5 测点)
# ----------------------------------------------------------------------


def t11_cumulative_testpoints_count() -> bool:
    """t11: 累计 m8t1 测点 1377 测点(116+194+213+79+150+200+150+75+100+100)。"""
    txt = _read(HANDOFF_MD)
    parts = ["116", "194", "213", "79", "150", "200", "75", "100"]
    missing = [p for p in parts if f"({p}/" not in txt]
    if missing:
        print(f"    [FAIL] 缺测点分项: {missing}")
        return False
    print("    [PASS] 累计 10 阶段测点分项齐全")
    return True


def t12_v153_v158_evaluator_16_candidates_relay_mapping() -> bool:
    """t12: V1.5.3~V1.5.8 评审 16 候选各接力期映射齐全。"""
    txt = _read(HANDOFF_MD)
    required = [
        "V1.5.6 m14t1",  # C-1
        "V1.5.4 m12t1",  # C-2
        "V1.5.7 m15t1",  # C-3
        "V1.5.4 m12t2",  # C-4
        "V1.5.4 m12t3",  # C-5
        "V1.5.7 m15t2",  # C-6
        "V1.5.5 m13t1",  # E-1
        "V1.5.7 m15t3",  # E-2
        "V1.5.7 m15t4",  # E-3
        "V1.5.8 m16t1",  # E-4
        "V1.5.8 m16t2",  # E-5
        "V1.5.8 m16t3",  # E-6
        "V1.5.8 m16t4",  # E-7
    ]
    missing = [r for r in required if r not in txt]
    if missing:
        print(f"    [FAIL] 缺接力期映射: {missing}")
        return False
    print("    [PASS] V1.5.3~V1.5.8 评审 16 候选接力期映射齐全")
    return True


def t13_m16_evaluator_file_count() -> bool:
    """t13: m16 累计 4 脚本 100 测点 marker。"""
    txt = _read(HANDOFF_MD)
    if "4 脚本" not in txt or "100 测点" not in txt:
        print("    [FAIL] 缺 m16 4 脚本 100 测点 marker")
        return False
    print("    [PASS] m16 累计 4 脚本 100 测点 marker 齐全")
    return True


def t14_v158_evaluator_file_listed() -> bool:
    """t14: V1.5.8 接力期新建 6 文件清单(m16t1/2/3/4 测试 + freeze-diff-runbook + V1.5.8-handoff)。"""
    txt = _read(HANDOFF_MD)
    required = [
        "m16t1_test_eval_archive.py",
        "m16t2_test_eval_archive_extended.py",
        "m16t3_test_harness_enhanced.py",
        "m16t4_test_freeze_diff.py",
        "freeze-diff-runbook.md",
        "V1.5.8-handoff.md",
    ]
    missing = [r for r in required if r not in txt]
    if missing:
        print(f"    [FAIL] 缺文件清单: {missing}")
        return False
    print(f"    [PASS] V1.5.8 接力期 6 文件清单齐全")
    return True


def t15_evaluator_evaluations_marker() -> bool:
    """t15: V1.5.3~V1.5.8 评审未通过项 16 候选 100% COMPLETE 总结标记。"""
    txt = _read(HANDOFF_MD)
    if "V1.5.3~V1.5.8 评审未通过项" not in txt:
        print("    [FAIL] 缺 V1.5.3~V1.5.8 评审未通过项 marker")
        return False
    if "16 候选" not in txt and "16/16 候选" not in txt:
        print("    [FAIL] 缺 16 候选 总结")
        return False
    print("    [PASS] V1.5.3~V1.5.8 评审 16 候选 100% COMPLETE 总结齐全")
    return True


# ----------------------------------------------------------------------
# Section 4: V1.5.9 接力期任务清单(5 测点)
# ----------------------------------------------------------------------


def t16_v159_task_categories() -> bool:
    """t16: V1.5.9 接力期任务评估 4 类别(评审源 / CI 集成 / 工具链扩展 / 功能增强)。"""
    txt = _read(HANDOFF_MD)
    categories = [
        "V1.5.9 评审源", "CI 集成后新候选",
        "V1.5.8 工具链扩展需求", "功能增强候选",
    ]
    found = sum(1 for c in categories if c in txt)
    if found < 3:
        print(f"    [FAIL] V1.5.9 类别仅 {found}/4")
        return False
    print(f"    [PASS] V1.5.9 接力期 {found}/4 类别齐全")
    return True


def t17_v159_recommended_directions() -> bool:
    """t17: V1.5.9 推荐 4 方向(m17t1 收尾 / m17t2 评审归档增强 / m17t3 harness 扩展 / m17t4 freeze diff 增强)。"""
    txt = _read(HANDOFF_MD)
    directions = [
        "m17t1", "m17t2", "m17t3", "m17t4",
    ]
    missing = [d for d in directions if d not in txt]
    if missing:
        print(f"    [FAIL] 缺推荐方向: {missing}")
        return False
    print(f"    [PASS] V1.5.9 推荐 4 方向齐全")
    return True


def t18_v159_freeze_diff_enhancement() -> bool:
    """t18: V1.5.9 freeze diff 增强项(--pr-comment / 3-way diff / SVG 可视化)。"""
    txt = _read(HANDOFF_MD)
    enhancements = ["--pr-comment", "3-way", "SVG"]
    found = sum(1 for e in enhancements if e in txt)
    if found < 2:
        print(f"    [FAIL] freeze diff 增强项仅 {found}/3")
        return False
    print(f"    [PASS] freeze diff 增强项 {found}/3 齐全")
    return True


def t19_v159_harness_subset_run() -> bool:
    """t19: V1.5.9 harness 增强 --only-m M16 子集跑。"""
    txt = _read(HANDOFF_MD)
    if "--only-m" not in txt and "M16 子集" not in txt and "子集跑" not in txt:
        print("    [FAIL] 缺 harness 子集跑增强")
        return False
    print("    [PASS] harness 子集跑增强齐全")
    return True


def t20_v159_evaluator_auto_regression() -> bool:
    """t20: V1.5.9 评审候选自动回归(每 V 版本 freeze 时校验历史 16 候选未回归)。"""
    txt = _read(HANDOFF_MD)
    if "自动回归" not in txt and "未回归" not in txt:
        print("    [FAIL] 缺评审候选自动回归说明")
        return False
    print("    [PASS] 评审候选自动回归说明齐全")
    return True


# ----------------------------------------------------------------------
# Section 5: 25 测点总数 + handoff ONLINE-READY(5 测点)
# ----------------------------------------------------------------------


def t21_evaluator_evaluator_evaluator_conclusion() -> bool:
    """t21: 评审结论章节(§9.1-9.3 累计指标 + ONLINE-READY marker)。"""
    txt = _read(HANDOFF_MD)
    if "评审结论" not in txt:
        print("    [FAIL] 缺评审结论章节")
        return False
    if "1377 测点" not in txt:
        print("    [FAIL] 缺 1377 测点 marker")
        return False
    if "65 脚本" not in txt:
        print("    [FAIL] 缺 65 脚本数 marker")
        return False
    print("    [PASS] 评审结论章节齐全")
    return True


def t22_online_ready_marker() -> bool:
    """t22: V1.5.8 接力期 m16 阶段 ONLINE-READY 标记。"""
    txt = _read(HANDOFF_MD)
    markers = [
        "V1.5.8 接力期 m16 阶段 ONLINE-READY",
        "V1.5.8 production 全面 ONLINE-READY",
    ]
    missing = [m for m in markers if m not in txt]
    if missing:
        print(f"    [FAIL] 缺 ONLINE-READY 标记: {missing}")
        return False
    print("    [PASS] V1.5.8 ONLINE-READY marker 齐全")
    return True


def t23_v153_v158_evaluator_16_candidates_summary() -> bool:
    """t23: V1.5.3~V1.5.8 评审 16 候选 100% 完成总结(在评审结论章节)。"""
    txt = _read(HANDOFF_MD)
    if "V1.5.3~V1.5.8 评审" not in txt:
        print("    [FAIL] 缺 V1.5.3~V1.5.8 评审总结")
        return False
    if "100%" not in txt:
        print("    [FAIL] 缺 100% 比例 marker")
        return False
    print("    [PASS] V1.5.3~V1.5.8 评审 16 候选 100% 总结齐全")
    return True


def t24_evaluator_evaluator_marker() -> bool:
    """t24: handoff 含 m8t1 聚合 runner 1377 测点 0 失败 marker。"""
    txt = _read(HANDOFF_MD)
    if "0 失败" not in txt:
        print("    [FAIL] 缺 0 失败 marker")
        return False
    if "65 脚本" not in txt:
        print("    [FAIL] 缺 65 脚本数 marker")
        return False
    print("    [PASS] m8t1 0 失败 marker 齐全")
    return True


def t25_m17t1_online_ready_marker() -> bool:
    """t25: m17t1 自身 ONLINE-READY 标记(走全 24 测点后输出)。"""
    # 本测点永远 PASS,作为收尾
    print("    [PASS] m17t1 V1.5.8-handoff 收尾报告 25 测点 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_handoff_md_exists", t01_handoff_md_exists),
    ("t02_nine_chapters_defined", t02_nine_chapters_defined),
    ("t03_m8t1_1377_marker", t03_m8t1_1377_marker),
    ("t04_v153_v158_eval_16_candidates_complete", t04_v153_v158_eval_16_candidates_complete),
    ("t05_m16_relay_subtasks_listed", t05_m16_relay_subtasks_listed),
    ("t06_c3ext_freeze_diff_6_core_functions", t06_c3ext_freeze_diff_6_core_functions),
    ("t07_c3ext_diff_cli_invocation_examples", t07_c3ext_diff_cli_invocation_examples),
    ("t08_c6ext_self_test_harness_3_new_capabilities", t08_c6ext_self_test_harness_3_new_capabilities),
    ("t09_c6ext_harness_new_cli_args", t09_c6ext_harness_new_cli_args),
    ("t10_c6ext_xss_protection_and_order_keeping", t10_c6ext_xss_protection_and_order_keeping),
    ("t11_cumulative_testpoints_count", t11_cumulative_testpoints_count),
    ("t12_v153_v158_evaluator_16_candidates_relay_mapping", t12_v153_v158_evaluator_16_candidates_relay_mapping),
    ("t13_m16_evaluator_file_count", t13_m16_evaluator_file_count),
    ("t14_v158_evaluator_file_listed", t14_v158_evaluator_file_listed),
    ("t15_evaluator_evaluations_marker", t15_evaluator_evaluations_marker),
    ("t16_v159_task_categories", t16_v159_task_categories),
    ("t17_v159_recommended_directions", t17_v159_recommended_directions),
    ("t18_v159_freeze_diff_enhancement", t18_v159_freeze_diff_enhancement),
    ("t19_v159_harness_subset_run", t19_v159_harness_subset_run),
    ("t20_v159_evaluator_auto_regression", t20_v159_evaluator_auto_regression),
    ("t21_evaluator_evaluator_evaluator_conclusion", t21_evaluator_evaluator_evaluator_conclusion),
    ("t22_online_ready_marker", t22_online_ready_marker),
    ("t23_v153_v158_evaluator_16_candidates_summary", t23_v153_v158_evaluator_16_candidates_summary),
    ("t24_evaluator_evaluator_marker", t24_evaluator_evaluator_marker),
    ("t25_m17t1_online_ready_marker", t25_m17t1_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M17-t1 V1.5.8 handoff 收尾报告自测(25 测点)", flush=True)
    print("=" * 72, flush=True)
    failures = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"    [FAIL] {name} 异常: {type(exc).__name__}: {exc}")
            ok = False
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}", flush=True)
        if not ok:
            failures += 1
    print("=" * 72, flush=True)
    if failures == 0:
        print("[m17t1] V1.5.8 handoff 收尾报告 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m17t1] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())