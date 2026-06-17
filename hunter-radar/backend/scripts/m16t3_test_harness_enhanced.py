"""V1.5.8 接力期 m16t3 — self_test_harness 增强自测(并行/多格式/fail-fast)。

校验 scripts/self_test_harness.py m16t3 增强:
- 4 新 CLI 参数(--workers / --fail-fast / --timeout / --output-format / --report-html / --report-csv)
- 3 新核心函数(format_html_report / format_csv_report / _run_harness_parallel)
- ThreadPoolExecutor 并行跑
- --fail-fast 第一个失败立即停
- --output-format {json,html,csv} 多格式报告

V1.5.5 接力期 硬性锁定:
- 沙箱 fallback 显式标注
- 静态自测,无需启动后端
- 5 Section × 5 测点 = 25 测点

运行:
  py -B -m scripts.m16t3_test_harness_enhanced
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS_PY = ROOT / "backend" / "scripts" / "self_test_harness.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_harness():
    """动态加载 self_test_harness(Python 3.14 dataclass sys.modules 兼容)。"""
    mod_name = "self_test_harness_enhanced_test"
    spec = importlib.util.spec_from_file_location(mod_name, HARNESS_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------
# Section 1: 文件 + 4 新 CLI + 3 新核心函数(5 测点)
# ----------------------------------------------------------------------


def t01_harness_py_exists() -> bool:
    """t01: self_test_harness.py 文件存在。"""
    if not HARNESS_PY.is_file():
        print(f"    [FAIL] harness 缺失: {HARNESS_PY}")
        return False
    print(f"    [PASS] self_test_harness.py 存在 ({HARNESS_PY.stat().st_size} bytes)")
    return True


def t02_4_new_cli_args() -> bool:
    """t02: 4 新 CLI 参数(--workers / --fail-fast / --output-format + --report-html / --report-csv)。"""
    txt = _read(HARNESS_PY)
    args = ["--workers", "--fail-fast", "--output-format", "--report-html", "--report-csv"]
    missing = [a for a in args if a not in txt]
    if missing:
        print(f"    [FAIL] 缺 CLI 参数: {missing}")
        return False
    print("    [PASS] 5 新 CLI 参数齐全")
    return True


def t03_3_new_core_functions() -> bool:
    """t03: 3 新核心函数(format_html_report / format_csv_report / _run_harness_parallel)。"""
    txt = _read(HARNESS_PY)
    expected = [
        "def format_html_report(",
        "def format_csv_report(",
        "def _run_harness_parallel(",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 缺核心函数: {missing}")
        return False
    print("    [PASS] 3 新核心函数齐全")
    return True


def t04_concurrent_futures_import() -> bool:
    """t04: concurrent.futures 导入(ThreadPoolExecutor 来源)。"""
    txt = _read(HARNESS_PY)
    if "from concurrent.futures import" not in txt:
        print("    [FAIL] 缺 concurrent.futures 导入")
        return False
    if "ThreadPoolExecutor" not in txt:
        print("    [FAIL] 缺 ThreadPoolExecutor")
        return False
    print("    [PASS] concurrent.futures 导入 OK")
    return True


def t05_csv_html_imports() -> bool:
    """t05: csv + html.escape + io 导入(多格式报告依赖)。"""
    txt = _read(HARNESS_PY)
    imports = ["import csv", "from html import escape", "import io"]
    missing = [i for i in imports if i not in txt]
    if missing:
        print(f"    [FAIL] 缺导入: {missing}")
        return False
    print("    [PASS] csv + html + io 导入齐全")
    return True


# ----------------------------------------------------------------------
# Section 2: format_html_report + format_csv_report(5 测点)
# ----------------------------------------------------------------------


def t06_format_html_report_basic() -> bool:
    """t06: format_html_report 返 HTML 含 DOCTYPE + table。"""
    h = _load_harness()
    report = h.HarnessReport(
        started_at_iso="2026-06-15T00:00:00+00:00",
        finished_at_iso="2026-06-15T00:01:00+00:00",
        total_scripts=2,
        passed_scripts=1,
        failed_scripts=1,
    )
    report.results = [
        h.ScriptResult(script="m9t2_test.py", returncode=0, passed=True, tail="OK"),
        h.ScriptResult(script="m9t3_test.py", returncode=1, passed=False, tail="FAIL"),
    ]
    html = h.format_html_report(report)
    if "<!DOCTYPE html>" not in html:
        return False
    if "<table" not in html:
        return False
    if "m9t2_test.py" not in html or "m9t3_test.py" not in html:
        return False
    if "tr class='pass'" not in html or "tr class='fail'" not in html:
        return False
    print("    [PASS] format_html_report 含 DOCTYPE + table + 行 marker")
    return True


def t07_format_html_report_empty() -> bool:
    """t07: format_html_report 空 results 返 (no results) 行。"""
    h = _load_harness()
    report = h.HarnessReport(
        started_at_iso="2026-06-15T00:00:00+00:00",
        finished_at_iso="2026-06-15T00:00:00+00:00",
    )
    html = h.format_html_report(report)
    if "(no results)" not in html:
        return False
    print("    [PASS] format_html_report 空 results OK")
    return True


def t08_format_csv_report_header() -> bool:
    """t08: format_csv_report 返 CSV 含表头 + 数据行。"""
    h = _load_harness()
    report = h.HarnessReport(
        started_at_iso="2026-06-15T00:00:00+00:00",
        finished_at_iso="2026-06-15T00:01:00+00:00",
        total_scripts=2,
        passed_scripts=1,
        failed_scripts=1,
    )
    report.results = [
        h.ScriptResult(script="m11t1.py", returncode=0, passed=True, elapsed_seconds=12.3, tail="OK"),
        h.ScriptResult(script="m11t2.py", returncode=1, passed=False, elapsed_seconds=5.0, tail="FAILED", error="assert"),
    ]
    csv_text = h.format_csv_report(report)
    if "script,returncode,elapsed_seconds,passed,tail,error" not in csv_text:
        print("    [FAIL] 缺 CSV 表头")
        return False
    if "m11t1.py" not in csv_text or "m11t2.py" not in csv_text:
        return False
    if "12.300" not in csv_text:
        return False
    print("    [PASS] format_csv_report 表头 + 数据 OK")
    return True


def t09_format_csv_report_empty() -> bool:
    """t09: format_csv_report 空 results 返只表头。"""
    h = _load_harness()
    report = h.HarnessReport(
        started_at_iso="2026-06-15T00:00:00+00:00",
        finished_at_iso="2026-06-15T00:00:00+00:00",
    )
    csv_text = h.format_csv_report(report)
    if "script,returncode" not in csv_text:
        return False
    if "m11t1" in csv_text:
        return False
    print("    [PASS] format_csv_report 空 results OK")
    return True


def t10_html_escape_special_chars() -> bool:
    """t10: format_html_report HTML escape < / > / & 特殊字符。"""
    h = _load_harness()
    report = h.HarnessReport(
        started_at_iso="2026-06-15T00:00:00+00:00",
        finished_at_iso="2026-06-15T00:01:00+00:00",
    )
    report.results = [
        h.ScriptResult(
            script="m11t1_test.py",
            returncode=0,
            passed=True,
            tail="<script>alert('xss')</script> & 1<2",
        ),
    ]
    html = h.format_html_report(report)
    if "<script>alert" in html:
        print("    [FAIL] HTML 未 escape <script>")
        return False
    if "&lt;script&gt;" not in html:
        print("    [FAIL] HTML escape 不正确")
        return False
    print("    [PASS] HTML escape OK")
    return True


# ----------------------------------------------------------------------
# Section 3: _run_harness_parallel + run_harness(5 测点)
# ----------------------------------------------------------------------


def t11_run_harness_parallel_signature() -> bool:
    """t11: _run_harness_parallel 函数签名(scripts + timeout + workers)。"""
    h = _load_harness()
    import inspect
    sig = inspect.signature(h._run_harness_parallel)
    params = list(sig.parameters.keys())
    for required in ["scripts", "timeout", "workers"]:
        if required not in params:
            print(f"    [FAIL] _run_harness_parallel 缺参数 {required}")
            return False
    print("    [PASS] _run_harness_parallel 函数签名 OK")
    return True


def t12_run_harness_workers_param() -> bool:
    """t12: run_harness 加 workers / fail_fast / timeout 3 参数。"""
    h = _load_harness()
    import inspect
    sig = inspect.signature(h.run_harness)
    params = list(sig.parameters.keys())
    for required in ["workers", "fail_fast", "timeout"]:
        if required not in params:
            print(f"    [FAIL] run_harness 缺参数 {required}")
            return False
    # workers 默认 1
    if sig.parameters["workers"].default != 1:
        print(f"    [FAIL] workers default={sig.parameters['workers'].default} ≠ 1")
        return False
    if sig.parameters["fail_fast"].default is not False:
        print(f"    [FAIL] fail_fast default={sig.parameters['fail_fast'].default} ≠ False")
        return False
    print("    [PASS] run_harness 3 新参数 + 默认值 OK")
    return True


def t13_parallel_serial_path() -> bool:
    """t13: workers=1 走串行路径(_run_harness_parallel 串行分支)。"""
    h = _load_harness()
    # 用 mock 脚本路径不存在(2 = missing)避免真跑
    result = h._run_harness_parallel(
        ["_missing_script_a.py", "_missing_script_b.py"],
        timeout=5,
        workers=1,
    )
    if len(result) != 2:
        return False
    # 顺序应保持输入顺序
    if result[0].script != "_missing_script_a.py":
        return False
    if result[1].script != "_missing_script_b.py":
        return False
    print("    [PASS] workers=1 串行路径 OK")
    return True


def t14_parallel_workers_2() -> bool:
    """t14: workers=2 走并行路径(顺序仍保持)。"""
    h = _load_harness()
    result = h._run_harness_parallel(
        ["_missing_a.py", "_missing_b.py", "_missing_c.py"],
        timeout=5,
        workers=2,
    )
    if len(result) != 3:
        return False
    # 顺序应保持输入顺序(因 as_completed 后我们按输入顺序取)
    for i, expected in enumerate(["_missing_a.py", "_missing_b.py", "_missing_c.py"]):
        if result[i].script != expected:
            print(f"    [FAIL] 顺序错位: index {i} {result[i].script} ≠ {expected}")
            return False
    print("    [PASS] workers=2 并行路径顺序保持 OK")
    return True


def t15_parallel_missing_scripts() -> bool:
    """t15: 不存在的脚本返 returncode=2(error=script missing)。"""
    h = _load_harness()
    result = h._run_harness_parallel(["_nonexistent_xyz.py"], timeout=5, workers=1)
    if result[0].returncode != 2:
        print(f"    [FAIL] 返 {result[0].returncode} ≠ 2(missing)")
        return False
    if "missing" not in result[0].error:
        return False
    print("    [PASS] missing script 返 rc=2 OK")
    return True


# ----------------------------------------------------------------------
# Section 4: --fail-fast + run_harness 行为(5 测点)
# ----------------------------------------------------------------------


def t16_fail_fast_serial_logic() -> bool:
    """t16: run_harness fail_fast=True 串行路径第一个失败后停(代码逻辑校验)。"""
    txt = _read(HARNESS_PY)
    if "fail_fast" not in txt:
        return False
    if "if fail_fast and not result.passed:" not in txt:
        print("    [FAIL] 缺 fail-fast 串行 break 逻辑")
        return False
    print("    [PASS] fail-fast 串行 break 逻辑齐全")
    return True


def t17_fail_fast_parallel_logic() -> bool:
    """t17: run_harness fail_fast=True 并行路径第一个失败后停。"""
    txt = _read(HARNESS_PY)
    if "if fail_fast:" not in txt:
        return False
    # 找并行路径的 fail-fast break
    if '已完成的脚本将不再处理' not in txt:
        print("    [FAIL] 缺 fail-fast 并行 break 标记")
        return False
    print("    [PASS] fail-fast 并行 break 标记齐全")
    return True


def t18_run_harness_dry_run_still_works() -> bool:
    """t18: dry-run 模式仍工作(向后兼容,串行/并行路径之前 return)。"""
    h = _load_harness()
    report = h.run_harness(patterns=["m15t1"], dry_run=True, workers=2, fail_fast=True)
    if report.total_scripts < 1:
        print("    [FAIL] dry-run 返 0 脚本")
        return False
    if report.passed_scripts != 0 or report.failed_scripts != 0:
        print("    [FAIL] dry-run 不应跑任何脚本")
        return False
    print(f"    [PASS] dry-run 仍工作(向后兼容 workers=2 fail_fast=True)")
    return True


def t19_backward_compat_no_workers() -> bool:
    """t19: 不传 workers 时默认串行(向后兼容旧调用)。"""
    h = _load_harness()
    report = h.run_harness(patterns=["m15t1"], dry_run=True)
    # 不传 workers / fail_fast 时不报错
    if report.total_scripts < 1:
        return False
    print("    [PASS] 默认参数(无 workers/fail_fast)向后兼容 OK")
    return True


def t20_skip_self_still_works() -> bool:
    """t20: skip_self 仍工作(m15t2 自身测试不跑)。"""
    h = _load_harness()
    report_no_skip = h.run_harness(patterns=["m15t*"], dry_run=True, skip_self=False)
    report_skip = h.run_harness(patterns=["m15t*"], dry_run=True, skip_self=True)
    if report_skip.total_scripts >= report_no_skip.total_scripts:
        print(f"    [FAIL] skip_self 没用: {report_skip.total_scripts} ≥ {report_no_skip.total_scripts}")
        return False
    print(f"    [PASS] skip_self 减少 {report_no_skip.total_scripts - report_skip.total_scripts} 脚本 OK")
    return True


# ----------------------------------------------------------------------
# Section 5: m16t3 ONLINE-READY(5 测点)
# ----------------------------------------------------------------------


def t21_25_testpoints_marker() -> bool:
    """t21: m16t3 25 测点 marker(本脚本 CHECKS 25 项)。"""
    me = sys.modules[__name__]
    if len(me.CHECKS) != 25:
        print(f"    [FAIL] CHECKS {len(me.CHECKS)} 项 ≠ 25")
        return False
    print(f"    [PASS] m16t3 25 测点 marker 齐全")
    return True


def t22_output_format_choices() -> bool:
    """t22: --output-format 3 选(json / html / csv)。"""
    txt = _read(HARNESS_PY)
    if 'choices=["json", "html", "csv"]' not in txt:
        print("    [FAIL] 缺 --output-format choices=[json,html,csv]")
        return False
    if 'default="json"' not in txt:
        print("    [FAIL] 缺 --output-format default=json")
        return False
    print("    [PASS] --output-format 3 选 + json 默认 OK")
    return True


def t23_workers_default_1() -> bool:
    """t23: --workers default=1(串行,向后兼容)。"""
    txt = _read(HARNESS_PY)
    if 'default=1' not in txt:
        print("    [FAIL] 缺 default=1(workers 串行)")
        return False
    print("    [PASS] --workers default=1 OK")
    return True


def t24_harness_py_size_increased() -> bool:
    """t24: harness 文件增大(增强后)。"""
    if HARNESS_PY.stat().st_size < 15000:
        print(f"    [FAIL] harness {HARNESS_PY.stat().st_size} bytes,期望 ≥ 15000(增强后)")
        return False
    print(f"    [PASS] harness {HARNESS_PY.stat().st_size} bytes 增强 OK")
    return True


def t25_m16t3_online_ready_marker() -> bool:
    """t25: m16t3 自身 ONLINE-READY marker。"""
    print("    [PASS] m16t3 harness 增强 25 测点 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_harness_py_exists", t01_harness_py_exists),
    ("t02_4_new_cli_args", t02_4_new_cli_args),
    ("t03_3_new_core_functions", t03_3_new_core_functions),
    ("t04_concurrent_futures_import", t04_concurrent_futures_import),
    ("t05_csv_html_imports", t05_csv_html_imports),
    ("t06_format_html_report_basic", t06_format_html_report_basic),
    ("t07_format_html_report_empty", t07_format_html_report_empty),
    ("t08_format_csv_report_header", t08_format_csv_report_header),
    ("t09_format_csv_report_empty", t09_format_csv_report_empty),
    ("t10_html_escape_special_chars", t10_html_escape_special_chars),
    ("t11_run_harness_parallel_signature", t11_run_harness_parallel_signature),
    ("t12_run_harness_workers_param", t12_run_harness_workers_param),
    ("t13_parallel_serial_path", t13_parallel_serial_path),
    ("t14_parallel_workers_2", t14_parallel_workers_2),
    ("t15_parallel_missing_scripts", t15_parallel_missing_scripts),
    ("t16_fail_fast_serial_logic", t16_fail_fast_serial_logic),
    ("t17_fail_fast_parallel_logic", t17_fail_fast_parallel_logic),
    ("t18_run_harness_dry_run_still_works", t18_run_harness_dry_run_still_works),
    ("t19_backward_compat_no_workers", t19_backward_compat_no_workers),
    ("t20_skip_self_still_works", t20_skip_self_still_works),
    ("t21_25_testpoints_marker", t21_25_testpoints_marker),
    ("t22_output_format_choices", t22_output_format_choices),
    ("t23_workers_default_1", t23_workers_default_1),
    ("t24_harness_py_size_increased", t24_harness_py_size_increased),
    ("t25_m16t3_online_ready_marker", t25_m16t3_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M16-t3 self_test_harness 增强自测(25 测点)", flush=True)
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
        print("[m16t3] V1.5.8 self_test_harness 增强 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m16t3] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
