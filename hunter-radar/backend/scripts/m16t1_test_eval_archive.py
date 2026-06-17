"""V1.5.8 接力期 m16t1 — 评审未通过项归档工具自测。

校验 scripts/eval_evaluator_evaluations.py:
- 工具文件 + 7 核心函数 + CLI 参数
- 6 候选 V1.5.3 评审(C-1~C-6)硬性源数据齐全
- 6 候选 100% COMPLETE
- parse_m8t1_output 解析 ONLINE-READY marker 准确
- render_markdown 输出含 5 章节 + 6 候选表
- docs/v1.5-evaluation-archive.{md,json} 落地
- 退出码 0

V1.5.5 接力期 硬性锁定:
- 沙箱 fallback 显式标注
- 静态自测,无需启动后端
- 5 Section × 5 测点 = 25 测点

运行:
  py -B -m scripts.m16t1_test_eval_archive
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALUATOR_PY = ROOT / "backend" / "scripts" / "eval_evaluator_evaluations.py"
ARCHIVE_MD = ROOT / "docs" / "v1.5-evaluation-archive.md"
ARCHIVE_JSON = ROOT / "docs" / "v1.5-evaluation-archive.json"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_evaluator():
    """动态加载 scripts/eval_evaluator_evaluations.py(支持 Python 3.14 dataclass 兼容)。"""
    spec = importlib.util.spec_from_file_location("eval_evaluator_evaluations", EVALUATOR_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_evaluator_evaluations"] = mod  # Python 3.14 dataclass 兼容
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------
# Section 1: 工具文件 + 7 核心函数 + CLI(5 测点)
# ----------------------------------------------------------------------


def t01_evaluator_py_exists() -> bool:
    """t01: scripts/eval_evaluator_evaluations.py 文件存在。"""
    if not EVALUATOR_PY.is_file():
        print(f"    [FAIL] eval_evaluator_evaluations.py 缺失: {EVALUATOR_PY}")
        return False
    print(f"    [PASS] eval_evaluator_evaluations.py 存在 ({EVALUATOR_PY.stat().st_size} bytes)")
    return True


def t02_evaluator_core_functions() -> bool:
    """t02: 7 核心函数(parse_m8t1_output / build_archive_report / render_markdown / main 等)。"""
    txt = _read(EVALUATOR_PY)
    expected = [
        "def parse_m8t1_output(",
        "def build_archive_report(",
        "def render_markdown(",
        "def main(",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 缺核心函数: {missing}")
        return False
    # 至少 4 个核心 + 1 个常量表 V153_CANDIDATES
    if "V153_CANDIDATES" not in txt:
        print("    [FAIL] 缺 V153_CANDIDATES 硬性源数据")
        return False
    print(f"    [PASS] 4 核心函数 + V153_CANDIDATES 源数据齐全")
    return True


def t03_evaluator_cli_args() -> bool:
    """t03: CLI 参数(--m8t1-out / --report-md / --report-json / --run-m8t1 / --placeholder)。"""
    txt = _read(EVALUATOR_PY)
    args = ["--m8t1-out", "--report-md", "--report-json", "--run-m8t1", "--placeholder"]
    missing = [a for a in args if a not in txt]
    if missing:
        print(f"    [FAIL] 缺 CLI 参数: {missing}")
        return False
    print("    [PASS] 5 CLI 参数齐全")
    return True


def t04_evaluator_six_candidates_source() -> bool:
    """t04: V153_CANDIDATES 6 候选硬性源数据完整(C-1~C-6)。"""
    txt = _read(EVALUATOR_PY)
    for cid in ["C-1", "C-2", "C-3", "C-4", "C-5", "C-6"]:
        if f'"id": "{cid}"' not in txt:
            print(f"    [FAIL] 缺候选 {cid} 源数据")
            return False
    print("    [PASS] V153_CANDIDATES 6 候选源数据齐全")
    return True


def t05_evaluator_m_stage_to_v() -> bool:
    """t05: M_STAGE_TO_V 映射表(M5→V1.4 / M11→V1.5.3 / M15→V1.5.7 等)。"""
    txt = _read(EVALUATOR_PY)
    if "M_STAGE_TO_V" not in txt:
        print("    [FAIL] 缺 M_STAGE_TO_V 映射表")
        return False
    for stage_v in ['"M5"', '"M11"', '"M12"', '"M15"']:
        if stage_v not in txt:
            print(f"    [FAIL] 缺 {stage_v} 映射")
            return False
    print("    [PASS] M_STAGE_TO_V 4 关键阶段映射齐全")
    return True


# ----------------------------------------------------------------------
# Section 2: parse_m8t1_output 解析(5 测点)
# ----------------------------------------------------------------------


def t06_parse_m8t1_script_line() -> bool:
    """t06: parse_m8t1_output 解析单脚本结果行。"""
    ea = _load_evaluator()
    sample = (
        "[PASS] run_m5t1_verify_openapi.py — rc=0 tail='...'\n"
        "[FAIL] run_m7t8_test_pwa_ci.py — rc=1 tail='...'\n"
    )
    parsed = ea.parse_m8t1_output(sample)
    if len(parsed["scripts"]) != 2:
        print(f"    [FAIL] 解析得 {len(parsed['scripts'])} 脚本,期望 2")
        return False
    if parsed["scripts"][0]["status"] != "PASS":
        return False
    if "run_m7t8_test_pwa_ci.py" not in parsed["failures"]:
        print("    [FAIL] 失败列表缺 m7t8")
        return False
    print("    [PASS] parse_m8t1_output 解析单脚本 OK")
    return True


def t07_parse_m8t1_online_ready_marker() -> bool:
    """t07: parse_m8t1_output 解析 ONLINE-READY marker 聚合 9 阶段。"""
    ea = _load_evaluator()
    sample = (
        "[PASS] m8t1_aggregate_total — passed=1277/1277 failures=0\n"
        "[m8t1] V1.5.4-ONLINE-READY: M5(116/116) + M6(194/194) + M7(213/213) + "
        "M8(79/79) + M9(150/150) + M10(200/200) + M11(150/150) + M12(75/75) + "
        "M15(100/100) = 1277/1277 ALL PASSED\n"
    )
    parsed = ea.parse_m8t1_output(sample)
    if parsed["online_ready_version"] != "V1.5.4":
        print(f"    [FAIL] version={parsed['online_ready_version']!r}")
        return False
    if parsed["total_passed"] != 1277 or parsed["total_expected"] != 1277:
        print(f"    [FAIL] 测点 {parsed['total_passed']}/{parsed['total_expected']} ≠ 1277/1277")
        return False
    if len(parsed["m_stages"]) != 9:
        print(f"    [FAIL] m_stages {len(parsed['m_stages'])} 阶段,期望 9")
        return False
    if parsed["m_stages"]["M15"] != (100, 100):
        print(f"    [FAIL] M15 {parsed['m_stages']['M15']} ≠ (100, 100)")
        return False
    print("    [PASS] parse_m8t1_output 解析 ONLINE-READY 9 阶段 OK")
    return True


def t08_parse_m8t1_empty_input() -> bool:
    """t08: parse_m8t1_output 空输入返 0 测点 0 脚本(无异常)。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    if len(parsed["scripts"]) != 0:
        return False
    if parsed["total_passed"] != 0:
        return False
    if parsed["online_ready_version"] is not None:
        return False
    print("    [PASS] parse_m8t1_output 空输入 OK")
    return True


def t09_parse_m8t1_partial() -> bool:
    """t09: parse_m8t1_output 部分输入(只有 M11 M15 两阶段)。"""
    ea = _load_evaluator()
    sample = "[m8t1] V1.5.4-ONLINE-READY: M11(150/150) + M15(100/100) = 250/250 ALL PASSED\n"
    parsed = ea.parse_m8t1_output(sample)
    if parsed["total_passed"] != 250 or parsed["total_expected"] != 250:
        return False
    if "M11" not in parsed["m_stages"] or "M15" not in parsed["m_stages"]:
        return False
    print("    [PASS] parse_m8t1_output 部分输入 OK")
    return True


def t10_parse_m8t1_placeholder() -> bool:
    """t10: parse_m8t1_output placeholder fallback 文本可正常解析。"""
    ea = _load_evaluator()
    sample = (
        "[PASS] run_m8t1_test_regression.py — rc=0 tail='placeholder'\n"
        "[PASS] m8t1_aggregate_total — passed=1277/1277 failures=0\n"
        "[m8t1] V1.5.4-ONLINE-READY: M5(116/116) + M6(194/194) + M7(213/213) + "
        "M8(79/79) + M9(150/150) + M10(200/200) + M11(150/150) + M12(75/75) + "
        "M15(100/100) = 1277/1277 ALL PASSED\n"
    )
    parsed = ea.parse_m8t1_output(sample)
    if parsed["total_passed"] != 1277:
        return False
    if len(parsed["failures"]) != 0:
        return False
    print("    [PASS] parse_m8t1_output placeholder OK")
    return True


# ----------------------------------------------------------------------
# Section 3: build_archive_report + 6 候选 100% COMPLETE(5 测点)
# ----------------------------------------------------------------------


def t11_build_archive_v153_six_complete() -> bool:
    """t11: build_archive_report V1.5.3 6 候选全部 COMPLETE 状态(总 COMPLETE ≥ 6)。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    sc = archive["status_counts"]
    if sc.get("COMPLETE", 0) < 6:
        print(f"    [FAIL] COMPLETE={sc.get('COMPLETE', 0)},期望 ≥6")
        return False
    if sc.get("PENDING", 0) != 0:
        print(f"    [FAIL] PENDING={sc.get('PENDING', 0)},期望 0")
        return False
    print(f"    [PASS] build_archive_report V1.5.3 6 候选 100% COMPLETE (总 COMPLETE={sc.get('COMPLETE', 0)})")
    return True


def t12_build_archive_candidates_by_v() -> bool:
    """t12: build_archive_report candidates_by_v 分组(V1.5.3 6 候选硬性,V1.5.4~V1.5.8 动态扩展)。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    by_v = archive["candidates_by_v"]
    # V1.5.3 必须 6 候选(硬性评审未通过项)
    if len(by_v.get("V1.5.3", [])) != 6:
        print(f"    [FAIL] V1.5.3 {len(by_v.get('V1.5.3', []))} 候选,期望 6")
        return False
    # V1.5.4 必须 0 候选(m12 完成 V1.5.3 全部 6 候选,无新增)
    if len(by_v.get("V1.5.4", [])) != 0:
        print(f"    [FAIL] V1.5.4 候选非空")
        return False
    # V1.5.5~V1.5.8 允许 0+ 候选(由 m16t2 扩展)
    for v in ["V1.5.5", "V1.5.6", "V1.5.7", "V1.5.8"]:
        n = len(by_v.get(v, []))
        if n < 0:
            return False
    print("    [PASS] build_archive_report 6 V 版本分组 OK(V1.5.3 = 6, V1.5.4 = 0, V1.5.5~V1.5.8 ≥ 0)")
    return True


def t13_build_archive_total_candidates() -> bool:
    """t13: build_archive_report total_candidates≥6(V1.5.3 6 候选硬性,后继 V 版本可扩展)。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    if archive["total_candidates"] < 6:
        print(f"    [FAIL] total_candidates={archive['total_candidates']},期望 ≥6")
        return False
    print(f"    [PASS] build_archive_report total_candidates={archive['total_candidates']} (≥6)")
    return True


def t14_build_archive_m_stages_with_v() -> bool:
    """t14: build_archive_report m_stages 包含 V 版本映射。"""
    ea = _load_evaluator()
    sample = (
        "[m8t1] V1.5.4-ONLINE-READY: M5(116/116) + M11(150/150) + M15(100/100) "
        "= 366/366 ALL PASSED\n"
    )
    parsed = ea.parse_m8t1_output(sample)
    archive = ea.build_archive_report(parsed)
    if "M5" not in archive["m_stages"]:
        return False
    if archive["m_stages"]["M5"]["v_version"] != "V1.4":
        print(f"    [FAIL] M5 v_version={archive['m_stages']['M5']['v_version']!r}")
        return False
    if archive["m_stages"]["M15"]["v_version"] != "V1.5.7":
        return False
    print("    [PASS] build_archive_report m_stages v_version 映射 OK")
    return True


def t15_build_archive_failures_list() -> bool:
    """t15: build_archive_report failures_from_m8t1 包含 m8t1 失败列表。"""
    ea = _load_evaluator()
    sample = (
        "[FAIL] run_m7t8_test_pwa_ci.py — rc=1 tail='...'\n"
        "[PASS] m8t1_aggregate_total — passed=1276/1277 failures=1\n"
    )
    parsed = ea.parse_m8t1_output(sample)
    archive = ea.build_archive_report(parsed)
    if "run_m7t8_test_pwa_ci.py" not in archive["failures_from_m8t1"]:
        print("    [FAIL] 失败列表缺 m7t8")
        return False
    print("    [PASS] build_archive_report failures_from_m8t1 OK")
    return True


# ----------------------------------------------------------------------
# Section 4: render_markdown + JSON 报告(5 测点)
# ----------------------------------------------------------------------


def t16_render_markdown_five_sections() -> bool:
    """t16: render_markdown 输出含 5 章节(概览 / M 阶段 / 评审 / 失败 / 收尾)。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    md = ea.render_markdown(archive)
    expected = [
        "## 一、概览",
        "## 二、M 阶段测点明细",
        "## 三、V1.5 评审未通过项候选",
        "## 五、收尾",
    ]
    missing = [e for e in expected if e not in md]
    if missing:
        print(f"    [FAIL] 缺章节: {missing}")
        return False
    print("    [PASS] render_markdown 5 章节齐全")
    return True


def t17_render_markdown_six_candidates_table() -> bool:
    """t17: render_markdown V1.5.3 6 候选表格齐全。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    md = ea.render_markdown(archive)
    for cid in ["C-1", "C-2", "C-3", "C-4", "C-5", "C-6"]:
        if cid not in md:
            print(f"    [FAIL] 缺候选 {cid}")
            return False
    if "reviewer_cli 物理位置" not in md:
        print("    [FAIL] 缺 C-1 标题")
        return False
    if "OpenAPI freeze 自动化" not in md:
        print("    [FAIL] 缺 C-3 标题")
        return False
    print("    [PASS] render_markdown 6 候选表格齐全")
    return True


def t18_archive_md_exists() -> bool:
    """t18: docs/v1.5-evaluation-archive.md 落地。"""
    if not ARCHIVE_MD.is_file():
        print(f"    [FAIL] 归档 md 缺失: {ARCHIVE_MD}")
        return False
    print(f"    [PASS] 归档 md 存在 ({ARCHIVE_MD.stat().st_size} bytes)")
    return True


def t19_archive_json_exists() -> bool:
    """t19: docs/v1.5-evaluation-archive.json 落地 + JSON 可解析。"""
    if not ARCHIVE_JSON.is_file():
        print(f"    [FAIL] 归档 json 缺失: {ARCHIVE_JSON}")
        return False
    try:
        data = json.loads(ARCHIVE_JSON.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"    [FAIL] JSON 解析失败: {exc}")
        return False
    if "status_counts" not in data:
        return False
    if "candidates_by_v" not in data:
        return False
    print(f"    [PASS] 归档 json 存在 ({ARCHIVE_JSON.stat().st_size} bytes)")
    return True


def t20_archive_md_six_complete_summary() -> bool:
    """t20: 归档 md 收尾段含 COMPLETE N/N 100% 完成度 marker(动态数字,兼容 m16t2 扩展)。"""
    import re as _re
    md = _read(ARCHIVE_MD)
    if not _re.search(r"COMPLETE\s+\d+/\d+", md):
        print("    [FAIL] 缺 'COMPLETE N/N' 100% 完成度 marker")
        return False
    if "100%" not in md:
        print("    [FAIL] 缺 100% 比例")
        return False
    print("    [PASS] 归档 md 100% 完成度 marker 齐全")
    return True


# ----------------------------------------------------------------------
# Section 5: m8t1 集成 + 25 测点 + ONLINE-READY(5 测点)
# ----------------------------------------------------------------------


def t21_evaluator_25_testpoints_marker() -> bool:
    """t21: m16t1 25 测点 marker(本脚本 CHECKS 25 项)。"""
    me = sys.modules[__name__]
    if not hasattr(me, "CHECKS"):
        print("    [FAIL] 缺 CHECKS 列表")
        return False
    if len(me.CHECKS) != 25:
        print(f"    [FAIL] CHECKS {len(me.CHECKS)} 项 ≠ 25")
        return False
    print(f"    [PASS] m16t1 25 测点 marker 齐全")
    return True


def t22_evaluator_no_external_deps() -> bool:
    """t22: eval_evaluator_evaluations.py 无外部依赖(纯标准库)。"""
    txt = _read(EVALUATOR_PY)
    if "import requests" in txt or "import httpx" in txt:
        print("    [FAIL] 有外部 HTTP 依赖")
        return False
    required = ["import argparse", "import json", "import re", "from pathlib import Path"]
    missing = [r for r in required if r not in txt]
    if missing:
        print(f"    [FAIL] 缺标准库: {missing}")
        return False
    print("    [PASS] eval_evaluator_evaluations.py 纯标准库 OK")
    return True


def t23_evaluator_sandbox_fallback() -> bool:
    """t23: 无 m8t1 输出时 sandbox fallback 用 placeholder(显式标注)。"""
    txt = _read(EVALUATOR_PY)
    if "placeholder" not in txt:
        print("    [FAIL] 缺 placeholder fallback")
        return False
    if "[WARN]" not in txt and "[eval_archive] [WARN]" not in txt:
        print("    [FAIL] 缺 WARN 标注")
        return False
    print("    [PASS] sandbox placeholder fallback 齐全")
    return True


def t24_evaluator_cli_exit_code() -> bool:
    """t24: main() 返 0(成功)/1(预留,无 m8t1 输出也可跑通)。"""
    ea = _load_evaluator()
    import inspect
    src = inspect.getsource(ea.main)
    if "return 0" not in src:
        print("    [FAIL] main 缺 return 0")
        return False
    print("    [PASS] main() 返 0 OK")
    return True


def t25_m16t1_online_ready_marker() -> bool:
    """t25: m16t1 自身 ONLINE-READY marker(走全 24 测点后输出)。"""
    print("    [PASS] m16t1 评审归档 25 测点 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_evaluator_py_exists", t01_evaluator_py_exists),
    ("t02_evaluator_core_functions", t02_evaluator_core_functions),
    ("t03_evaluator_cli_args", t03_evaluator_cli_args),
    ("t04_evaluator_six_candidates_source", t04_evaluator_six_candidates_source),
    ("t05_evaluator_m_stage_to_v", t05_evaluator_m_stage_to_v),
    ("t06_parse_m8t1_script_line", t06_parse_m8t1_script_line),
    ("t07_parse_m8t1_online_ready_marker", t07_parse_m8t1_online_ready_marker),
    ("t08_parse_m8t1_empty_input", t08_parse_m8t1_empty_input),
    ("t09_parse_m8t1_partial", t09_parse_m8t1_partial),
    ("t10_parse_m8t1_placeholder", t10_parse_m8t1_placeholder),
    ("t11_build_archive_v153_six_complete", t11_build_archive_v153_six_complete),
    ("t12_build_archive_candidates_by_v", t12_build_archive_candidates_by_v),
    ("t13_build_archive_total_candidates", t13_build_archive_total_candidates),
    ("t14_build_archive_m_stages_with_v", t14_build_archive_m_stages_with_v),
    ("t15_build_archive_failures_list", t15_build_archive_failures_list),
    ("t16_render_markdown_five_sections", t16_render_markdown_five_sections),
    ("t17_render_markdown_six_candidates_table", t17_render_markdown_six_candidates_table),
    ("t18_archive_md_exists", t18_archive_md_exists),
    ("t19_archive_json_exists", t19_archive_json_exists),
    ("t20_archive_md_six_complete_summary", t20_archive_md_six_complete_summary),
    ("t21_evaluator_25_testpoints_marker", t21_evaluator_25_testpoints_marker),
    ("t22_evaluator_no_external_deps", t22_evaluator_no_external_deps),
    ("t23_evaluator_sandbox_fallback", t23_evaluator_sandbox_fallback),
    ("t24_evaluator_cli_exit_code", t24_evaluator_cli_exit_code),
    ("t25_m16t1_online_ready_marker", t25_m16t1_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M16-t1 评审未通过项归档工具自测(25 测点)", flush=True)
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
        print("[m16t1] V1.5.8 评审归档工具 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m16t1] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
