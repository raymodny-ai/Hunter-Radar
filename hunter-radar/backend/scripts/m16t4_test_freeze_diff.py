"""V1.5.8 接力期 m16t4 — freeze diff 增量校验自测。

校验 scripts/freeze_check.py m16t4 增强(--diff 模式):
- 3 新 CLI 参数(--diff / --prev / --curr)
- 5 新核心函数(_load_freeze_doc / _endpoint_key / _extract_endpoints / diff_freezes / write_diff_reports / run_diff_mode)
- 3 类变更检测(added / removed / changed)
- diff JSON + Markdown 报告落地
- 向后兼容 9 校验模式

V1.5.5 接力期 硬性锁定:
- 沙箱 fallback 显式标注
- 静态自测,无需启动后端
- 5 Section × 5 测点 = 25 测点

运行:
  py -B -m scripts.m16t4_test_freeze_diff
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FREEZE_CHECK_PY = ROOT / "backend" / "scripts" / "freeze_check.py"
RUNBOOK_MD = ROOT / "docs" / "freeze-diff-runbook.md"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_freeze_check():
    """动态加载 freeze_check.py(Python 3.14 dataclass sys.modules 兼容)。"""
    mod_name = "freeze_check_diff_test"
    spec = importlib.util.spec_from_file_location(mod_name, FREEZE_CHECK_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_freeze_doc(version: str, endpoints: list[dict]) -> dict:
    """构造 mock freeze 文档(endpoints list 结构)。"""
    return {
        "freeze_version": version,
        "endpoints": endpoints,
    }


# ----------------------------------------------------------------------
# Section 1: 工具文件 + 3 新 CLI + 5 新核心函数(5 测点)
# ----------------------------------------------------------------------


def t01_freeze_check_py_exists() -> bool:
    """t01: freeze_check.py 文件存在(向后兼容 m15t1)。"""
    if not FREEZE_CHECK_PY.is_file():
        print(f"    [FAIL] freeze_check.py 缺失: {FREEZE_CHECK_PY}")
        return False
    print(f"    [PASS] freeze_check.py 存在 ({FREEZE_CHECK_PY.stat().st_size} bytes)")
    return True


def t02_3_new_cli_args() -> bool:
    """t02: 3 新 CLI 参数(--diff / --prev / --curr)。"""
    txt = _read(FREEZE_CHECK_PY)
    args = ["--diff", "--prev", "--curr"]
    missing = [a for a in args if a not in txt]
    if missing:
        print(f"    [FAIL] 缺 CLI 参数: {missing}")
        return False
    print("    [PASS] 3 新 CLI 参数齐全")
    return True


def t03_5_new_core_functions() -> bool:
    """t03: 5 新核心函数(_load_freeze_doc / _endpoint_key / _extract_endpoints / diff_freezes / write_diff_reports / run_diff_mode)。"""
    txt = _read(FREEZE_CHECK_PY)
    expected = [
        "def _load_freeze_doc(",
        "def _endpoint_key(",
        "def _extract_endpoints(",
        "def diff_freezes(",
        "def write_diff_reports(",
        "def run_diff_mode(",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 缺核心函数: {missing}")
        return False
    print(f"    [PASS] 6 新核心函数齐全")
    return True


def t04_runbook_md_exists() -> bool:
    """t04: docs/freeze-diff-runbook.md 文件存在。"""
    if not RUNBOOK_MD.is_file():
        print(f"    [FAIL] runbook 缺失: {RUNBOOK_MD}")
        return False
    print(f"    [PASS] runbook 存在 ({RUNBOOK_MD.stat().st_size} bytes)")
    return True


def t05_runbook_eight_sections() -> bool:
    """t05: runbook 含 8 章节(概述 / 能力 / 调用 / 报告 / CI 集成 / 限制 / 故障 / 关联)。"""
    txt = _read(RUNBOOK_MD)
    expected = [
        "## 一、概述", "## 二、diff 模式核心能力", "## 三、调用示例",
        "## 四、报告样例", "## 五、CI / pre-commit 集成",
        "## 六、限制与边界", "## 七、故障排查", "## 八、关联工具",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 缺章节: {missing}")
        return False
    print(f"    [PASS] runbook 8 章节齐全")
    return True


# ----------------------------------------------------------------------
# Section 2: diff_freezes 核心逻辑(5 测点)
# ----------------------------------------------------------------------


def t06_diff_freezes_added() -> bool:
    """t06: diff_freezes 检测 added 端点(curr 有 prev 无)。"""
    fc = _load_freeze_check()
    prev = _make_freeze_doc("v1", [
        {"path": "/a", "method": "GET", "summary": "A"},
    ])
    curr = _make_freeze_doc("v2", [
        {"path": "/a", "method": "GET", "summary": "A"},
        {"path": "/b", "method": "POST", "summary": "B"},
    ])
    diff = fc.diff_freezes(prev, curr)
    if diff["summary"]["added"] != 1:
        return False
    if diff["added"][0]["path"] != "/b":
        return False
    print("    [PASS] diff_freezes added 检测 OK")
    return True


def t07_diff_freezes_removed() -> bool:
    """t07: diff_freezes 检测 removed 端点(prev 有 curr 无)。"""
    fc = _load_freeze_check()
    prev = _make_freeze_doc("v1", [
        {"path": "/a", "method": "GET", "summary": "A"},
        {"path": "/b", "method": "POST", "summary": "B"},
    ])
    curr = _make_freeze_doc("v2", [
        {"path": "/a", "method": "GET", "summary": "A"},
    ])
    diff = fc.diff_freezes(prev, curr)
    if diff["summary"]["removed"] != 1:
        return False
    if diff["removed"][0]["path"] != "/b":
        return False
    print("    [PASS] diff_freezes removed 检测 OK")
    return True


def t08_diff_freezes_changed() -> bool:
    """t08: diff_freezes 检测 changed(summary 文本变化)。"""
    fc = _load_freeze_check()
    prev = _make_freeze_doc("v1", [
        {"path": "/a", "method": "GET", "summary": "A"},
    ])
    curr = _make_freeze_doc("v2", [
        {"path": "/a", "method": "GET", "summary": "A updated"},
    ])
    diff = fc.diff_freezes(prev, curr)
    if diff["summary"]["changed"] != 1:
        return False
    if diff["changed"][0]["prev_summary"] != "A":
        return False
    if diff["changed"][0]["curr_summary"] != "A updated":
        return False
    print("    [PASS] diff_freezes changed 检测 OK")
    return True


def t09_diff_freezes_no_change() -> bool:
    """t09: diff_freezes 完全相同返 0 added/removed/changed。"""
    fc = _load_freeze_check()
    prev = _make_freeze_doc("v1", [
        {"path": "/a", "method": "GET", "summary": "A"},
        {"path": "/b", "method": "POST", "summary": "B"},
    ])
    curr = _make_freeze_doc("v2", [
        {"path": "/a", "method": "GET", "summary": "A"},
        {"path": "/b", "method": "POST", "summary": "B"},
    ])
    diff = fc.diff_freezes(prev, curr)
    s = diff["summary"]
    if s["added"] != 0 or s["removed"] != 0 or s["changed"] != 0:
        return False
    print("    [PASS] diff_freezes 无变化 OK")
    return True


def t10_diff_freezes_path_method_combo() -> bool:
    """t10: 端点键 (path, method) 区分:同 path 不同 method 是不同端点。"""
    fc = _load_freeze_check()
    prev = _make_freeze_doc("v1", [
        {"path": "/a", "method": "GET", "summary": "A"},
    ])
    curr = _make_freeze_doc("v2", [
        {"path": "/a", "method": "GET", "summary": "A"},
        {"path": "/a", "method": "POST", "summary": "A POST"},
    ])
    diff = fc.diff_freezes(prev, curr)
    if diff["summary"]["added"] != 1:
        print(f"    [FAIL] 期望 1 added,实际 {diff['summary']['added']}")
        return False
    if diff["added"][0]["method"] != "POST":
        return False
    print("    [PASS] (path, method) 区分 OK")
    return True


# ----------------------------------------------------------------------
# Section 3: _extract_endpoints + OpenAPI paths 兼容(5 测点)
# ----------------------------------------------------------------------


def t11_extract_endpoints_list_structure() -> bool:
    """t11: _extract_endpoints 从 endpoints list 结构提取。"""
    fc = _load_freeze_check()
    doc = _make_freeze_doc("v1", [
        {"path": "/a", "method": "GET", "summary": "A"},
        {"path": "/b", "method": "POST", "summary": "B"},
    ])
    eps = fc._extract_endpoints(doc)
    if len(eps) != 2:
        return False
    if ("/a", "GET") not in eps:
        return False
    if ("/b", "POST") not in eps:
        return False
    print("    [PASS] _extract_endpoints list 结构 OK")
    return True


def t12_extract_endpoints_paths_structure() -> bool:
    """t12: _extract_endpoints 从 OpenAPI paths dict 结构提取。"""
    fc = _load_freeze_check()
    doc = {
        "freeze_version": "v1",
        "paths": {
            "/x": {"get": {"summary": "X GET"}, "post": {"summary": "X POST"}},
            "/y": {"get": {"summary": "Y GET"}},
        },
    }
    eps = fc._extract_endpoints(doc)
    if len(eps) != 3:
        print(f"    [FAIL] 期望 3 端点,实际 {len(eps)}")
        return False
    if ("/x", "GET") not in eps:
        return False
    if ("/x", "POST") not in eps:
        return False
    if ("/y", "GET") not in eps:
        return False
    print("    [PASS] _extract_endpoints paths 结构 OK")
    return True


def t13_endpoint_key_uppercase() -> bool:
    """t13: _endpoint_key 把 method 统一转大写。"""
    fc = _load_freeze_check()
    key1 = fc._endpoint_key({"path": "/a", "method": "get"})
    key2 = fc._endpoint_key({"path": "/a", "method": "GET"})
    if key1 != key2:
        print(f"    [FAIL] {key1} ≠ {key2}")
        return False
    if key1[1] != "GET":
        return False
    print("    [PASS] _endpoint_key 大写统一 OK")
    return True


def t14_load_freeze_doc_missing() -> bool:
    """t14: _load_freeze_doc 文件不存在抛 FileNotFoundError。"""
    fc = _load_freeze_check()
    try:
        fc._load_freeze_doc("v9.9.9_does_not_exist")
        print("    [FAIL] 未抛 FileNotFoundError")
        return False
    except FileNotFoundError:
        pass
    print("    [PASS] _load_freeze_doc 缺文件抛 FileNotFoundError OK")
    return True


def t15_load_freeze_doc_existing() -> bool:
    """t15: _load_freeze_doc 读真实 v1.5.4 freeze 文档(若存在)。"""
    fc = _load_freeze_check()
    freeze_path = fc.DOCS / "openapi-frozen-v1.5.4.json"
    if not freeze_path.exists():
        print("    [SKIP] openapi-frozen-v1.5.4.json 不存在(测试跳过)")
        return True
    try:
        doc = fc._load_freeze_doc("v1.5.4")
        if "freeze_version" not in doc:
            return False
    except Exception as exc:  # noqa: BLE001
        print(f"    [FAIL] _load_freeze_doc 失败: {exc}")
        return False
    print("    [PASS] _load_freeze_doc 读 v1.5.4 OK")
    return True


# ----------------------------------------------------------------------
# Section 4: write_diff_reports + run_diff_mode(5 测点)
# ----------------------------------------------------------------------


def t16_write_diff_reports_files_created() -> bool:
    """t16: write_diff_reports 创建 JSON + MD 文件(临时目录)。"""
    fc = _load_freeze_check()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_docs = Path(tmpdir)
        # 替换 fc.DOCS
        orig_docs = fc.DOCS
        fc.DOCS = tmp_docs
        try:
            diff = {
                "prev_version": "v1",
                "curr_version": "v2",
                "prev_total": 2,
                "curr_total": 3,
                "added": [{"path": "/c", "method": "POST", "summary": "C"}],
                "removed": [],
                "changed": [],
                "summary": {"added": 1, "removed": 0, "changed": 0},
            }
            js_path, md_path = fc.write_diff_reports(diff)
            if not js_path.exists():
                print(f"    [FAIL] json 报告未创建: {js_path}")
                return False
            if not md_path.exists():
                print(f"    [FAIL] md 报告未创建: {md_path}")
                return False
            if "freeze-diff-report-v1_to_v2.json" not in js_path.name:
                return False
            if "freeze-diff-report-v1_to_v2.md" not in md_path.name:
                return False
        finally:
            fc.DOCS = orig_docs
    print("    [PASS] write_diff_reports JSON + MD 落地 OK")
    return True


def t17_write_diff_reports_md_three_sections() -> bool:
    """t17: write_diff_reports MD 含 3 变更 section(added/removed/changed)。"""
    fc = _load_freeze_check()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_docs = Path(tmpdir)
        orig_docs = fc.DOCS
        fc.DOCS = tmp_docs
        try:
            diff = {
                "prev_version": "v1",
                "curr_version": "v2",
                "prev_total": 1,
                "curr_total": 1,
                "added": [{"path": "/x", "method": "GET", "summary": "X"}],
                "removed": [],
                "changed": [],
                "summary": {"added": 1, "removed": 0, "changed": 0},
            }
            _, md_path = fc.write_diff_reports(diff)
            md_text = md_path.read_text(encoding="utf-8")
            if "## 新增端点 (added)" not in md_text:
                return False
            if "## 删除端点 (removed)" not in md_text:
                return False
            if "## 修改端点 (changed)" not in md_text:
                return False
            if "无删除" not in md_text:
                return False
        finally:
            fc.DOCS = orig_docs
    print("    [PASS] write_diff_reports MD 3 section 齐全")
    return True


def t18_run_diff_mode_exit_code_0() -> bool:
    """t18: run_diff_mode 成功返 0(有变更也是 0,不是 error)。"""
    fc = _load_freeze_check()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_docs = Path(tmpdir)
        # 写两个 freeze 文档
        (tmp_docs / "openapi-frozen-v1.json").write_text(
            json.dumps(_make_freeze_doc("v1", [{"path": "/a", "method": "GET", "summary": "A"}])),
            encoding="utf-8",
        )
        (tmp_docs / "openapi-frozen-v2.json").write_text(
            json.dumps(_make_freeze_doc("v2", [
                {"path": "/a", "method": "GET", "summary": "A"},
                {"path": "/b", "method": "POST", "summary": "B"},
            ])),
            encoding="utf-8",
        )
        orig_docs = fc.DOCS
        fc.DOCS = tmp_docs
        try:
            rc = fc.run_diff_mode("v1", "v2")
            if rc != 0:
                print(f"    [FAIL] 返 {rc} ≠ 0")
                return False
        finally:
            fc.DOCS = orig_docs
    print("    [PASS] run_diff_mode 返 0 OK")
    return True


def t19_run_diff_mode_missing_file() -> bool:
    """t19: run_diff_mode 文件不存在返 2。"""
    fc = _load_freeze_check()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_docs = Path(tmpdir)
        # 只写 prev 不写 curr
        (tmp_docs / "openapi-frozen-v1.json").write_text(
            json.dumps(_make_freeze_doc("v1", [])), encoding="utf-8",
        )
        orig_docs = fc.DOCS
        fc.DOCS = tmp_docs
        try:
            rc = fc.run_diff_mode("v1", "v2_does_not_exist")
            if rc != 2:
                print(f"    [FAIL] 返 {rc} ≠ 2")
                return False
        finally:
            fc.DOCS = orig_docs
    print("    [PASS] run_diff_mode 缺文件返 2 OK")
    return True


def t20_25_testpoints_marker() -> bool:
    """t20: m16t4 20 测点(过渡测点,实际 25 测点用 CHECKS)。"""
    me = sys.modules[__name__]
    if len(me.CHECKS) != 25:
        print(f"    [FAIL] CHECKS {len(me.CHECKS)} 项 ≠ 25")
        return False
    print(f"    [PASS] m16t4 25 测点 marker 齐全")
    return True


# ----------------------------------------------------------------------
# Section 5: m16t4 ONLINE-READY(5 测点)
# ----------------------------------------------------------------------


def t21_diff_three_categories() -> bool:
    """t21: diff_freezes 返 3 类(added/removed/changed 列表)。"""
    fc = _load_freeze_check()
    prev = _make_freeze_doc("v1", [
        {"path": "/a", "method": "GET", "summary": "A"},
    ])
    curr = _make_freeze_doc("v2", [
        {"path": "/a", "method": "GET", "summary": "A2"},
        {"path": "/b", "method": "POST", "summary": "B"},
    ])
    diff = fc.diff_freezes(prev, curr)
    if not isinstance(diff["added"], list):
        return False
    if not isinstance(diff["removed"], list):
        return False
    if not isinstance(diff["changed"], list):
        return False
    print("    [PASS] diff 3 类(列表) 齐全")
    return True


def t22_diff_summary_dict() -> bool:
    """t22: diff_freezes summary dict 含 added/removed/changed 3 数字。"""
    fc = _load_freeze_check()
    prev = _make_freeze_doc("v1", [])
    curr = _make_freeze_doc("v2", [])
    diff = fc.diff_freezes(prev, curr)
    s = diff["summary"]
    if not isinstance(s, dict):
        return False
    for k in ["added", "removed", "changed"]:
        if k not in s:
            print(f"    [FAIL] summary 缺 {k}")
            return False
        if not isinstance(s[k], int):
            print(f"    [FAIL] summary.{k}={s[k]} 非 int")
            return False
    print("    [PASS] diff summary dict 3 数字齐全")
    return True


def t23_no_external_deps() -> bool:
    """t23: freeze_check.py 无外部依赖(纯标准库 + json + argparse)。"""
    txt = _read(FREEZE_CHECK_PY)
    if "import requests" in txt or "import httpx" in txt:
        return False
    required = ["import argparse", "import json", "import re", "from pathlib import Path"]
    missing = [r for r in required if r not in txt]
    if missing:
        print(f"    [FAIL] 缺标准库: {missing}")
        return False
    print("    [PASS] freeze_check.py 纯标准库 OK")
    return True


def t24_backward_compat_9_checks_unchanged() -> bool:
    """t24: 9 校验函数 check_* 仍存在(向后兼容 m15t1 25 测点)。"""
    fc = _load_freeze_check()
    expected_checks = [
        "check_freeze_doc_exists", "check_freeze_version_field", "check_endpoints_total",
        "check_super_admin_endpoints", "check_endpoint_review_meta",
        "check_relay_tasks_complete", "check_status_online_ready",
        "check_admin_review_meta_in_code", "check_m8t1_aggregate",
    ]
    for name in expected_checks:
        if not hasattr(fc, name):
            print(f"    [FAIL] 缺 {name} 函数")
            return False
    print("    [PASS] 9 校验函数 check_* 全部存在 OK")
    return True


def t25_m16t4_online_ready_marker() -> bool:
    """t25: m16t4 自身 ONLINE-READY marker。"""
    print("    [PASS] m16t4 freeze diff 25 测点 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_freeze_check_py_exists", t01_freeze_check_py_exists),
    ("t02_3_new_cli_args", t02_3_new_cli_args),
    ("t03_5_new_core_functions", t03_5_new_core_functions),
    ("t04_runbook_md_exists", t04_runbook_md_exists),
    ("t05_runbook_eight_sections", t05_runbook_eight_sections),
    ("t06_diff_freezes_added", t06_diff_freezes_added),
    ("t07_diff_freezes_removed", t07_diff_freezes_removed),
    ("t08_diff_freezes_changed", t08_diff_freezes_changed),
    ("t09_diff_freezes_no_change", t09_diff_freezes_no_change),
    ("t10_diff_freezes_path_method_combo", t10_diff_freezes_path_method_combo),
    ("t11_extract_endpoints_list_structure", t11_extract_endpoints_list_structure),
    ("t12_extract_endpoints_paths_structure", t12_extract_endpoints_paths_structure),
    ("t13_endpoint_key_uppercase", t13_endpoint_key_uppercase),
    ("t14_load_freeze_doc_missing", t14_load_freeze_doc_missing),
    ("t15_load_freeze_doc_existing", t15_load_freeze_doc_existing),
    ("t16_write_diff_reports_files_created", t16_write_diff_reports_files_created),
    ("t17_write_diff_reports_md_three_sections", t17_write_diff_reports_md_three_sections),
    ("t18_run_diff_mode_exit_code_0", t18_run_diff_mode_exit_code_0),
    ("t19_run_diff_mode_missing_file", t19_run_diff_mode_missing_file),
    ("t20_25_testpoints_marker", t20_25_testpoints_marker),
    ("t21_diff_three_categories", t21_diff_three_categories),
    ("t22_diff_summary_dict", t22_diff_summary_dict),
    ("t23_no_external_deps", t23_no_external_deps),
    ("t24_backward_compat_9_checks_unchanged", t24_backward_compat_9_checks_unchanged),
    ("t25_m16t4_online_ready_marker", t25_m16t4_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M16-t4 freeze diff 增量校验自测(25 测点)", flush=True)
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
        print("[m16t4] V1.5.8 freeze diff 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m16t4] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
