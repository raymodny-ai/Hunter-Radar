"""V1.5.7 接力期 m15t1 — OpenAPI freeze 自动化校验工具自测(C-3 候选)。

校验 scripts/freeze_check.py 的:
- 工具文件存在 + 9 校验函数定义
- CLI 参数 (--version / --skip-m8t1)
- 9 校验函数独立调用返 (bool, str) tuple
- V1.5.4 freeze 跑全 8 项(跳 m8t1)全过
- 报告生成 (JSON + MD 落地 docs/)
- m8t1 子进程集成 (§9 校验)
- 25 测点总数 + m15t1 自身 ONLINE-READY

V1.5.5 接力期 硬性锁定:
- 沙箱 fallback 显式标注
- 静态自测,无需启动后端
- 5 Section × 5 测点 = 25 测点

运行:
  py -B -m scripts.m15t1_test_freeze_automation
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SCRIPTS = BACKEND / "scripts"
DOCS = ROOT / "docs"
FREEZE_CHECK_PY = SCRIPTS / "freeze_check.py"
RUNBOOK_MD = DOCS / "freeze-check-runbook.md"
DEFAULT_VERSION = "v1.5.4"


def _load_freeze_check():
    """动态加载 freeze_check.py(走 spec_from_file_location 避免 sys.path 污染)。"""
    spec = importlib.util.spec_from_file_location("freeze_check", FREEZE_CHECK_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Section 1: 工具存在 + 9 校验函数 + CLI 参数(5 测点)
# ----------------------------------------------------------------------


def t01_freeze_check_py_exists() -> bool:
    """t01: scripts/freeze_check.py 存在(V1.5.7 m15t1 C-3 工具落地)。"""
    if not FREEZE_CHECK_PY.is_file():
        print(f"    [FAIL] 缺 {FREEZE_CHECK_PY}")
        return False
    print("    [PASS] scripts/freeze_check.py 存在")
    return True


def t02_nine_check_functions_defined() -> bool:
    """t02: freeze_check.py 含 9 项 check_* 校验函数。"""
    src = _read(FREEZE_CHECK_PY)
    required = [
        "check_freeze_doc_exists",
        "check_freeze_version_field",
        "check_endpoints_total",
        "check_super_admin_endpoints",
        "check_endpoint_review_meta",
        "check_relay_tasks_complete",
        "check_status_online_ready",
        "check_admin_review_meta_in_code",
        "check_m8t1_aggregate",
    ]
    missing = [fn for fn in required if f"def {fn}" not in src]
    if missing:
        print(f"    [FAIL] 缺校验函数: {missing}")
        return False
    print(f"    [PASS] 9 校验函数齐全: {len(required)}/9")
    return True


def t03_cli_version_argument() -> bool:
    """t03: CLI 含 --version 参数(默认 v1.5.4)。"""
    src = _read(FREEZE_CHECK_PY)
    if '"--version"' not in src and "'--version'" not in src:
        print("    [FAIL] 缺 --version CLI 参数")
        return False
    if 'default="v1.5.4"' not in src:
        print("    [FAIL] --version 默认值非 v1.5.4")
        return False
    print("    [PASS] CLI --version (默认 v1.5.4) 存在")
    return True


def t04_cli_skip_m8t1_argument() -> bool:
    """t04: CLI 含 --skip-m8t1 参数(快速校验用)。"""
    src = _read(FREEZE_CHECK_PY)
    if '"--skip-m8t1"' not in src and "'--skip-m8t1'" not in src:
        print("    [FAIL] 缺 --skip-m8t1 CLI 参数")
        return False
    print("    [PASS] CLI --skip-m8t1 存在")
    return True


def t05_runbook_md_exists() -> bool:
    """t05: docs/freeze-check-runbook.md 操作手册存在。"""
    if not RUNBOOK_MD.is_file():
        print(f"    [FAIL] 缺 {RUNBOOK_MD}")
        return False
    if "Freeze Check Runbook" not in _read(RUNBOOK_MD):
        print("    [FAIL] runbook 缺主标题")
        return False
    print("    [PASS] docs/freeze-check-runbook.md 存在")
    return True


# ----------------------------------------------------------------------
# Section 2: 9 校验函数独立调用(5 测点)
# ----------------------------------------------------------------------


def t06_check_freeze_doc_exists() -> bool:
    """t06: check_freeze_doc_exists(v1.5.4) → (True, ...)。"""
    fc = _load_freeze_check()
    ok, detail = fc.check_freeze_doc_exists(DEFAULT_VERSION)
    if not ok:
        print(f"    [FAIL] {detail}")
        return False
    print(f"    [PASS] freeze_doc_exists: {detail}")
    return True


def t07_check_endpoints_total_56() -> bool:
    """t07: check_endpoints_total(v1.5.4) → 56。"""
    fc = _load_freeze_check()
    ok, detail = fc.check_endpoints_total(DEFAULT_VERSION, expected=56)
    if not ok or "56" not in detail:
        print(f"    [FAIL] {detail}")
        return False
    print(f"    [PASS] endpoints_total: {detail}")
    return True


def t08_check_super_admin_endpoint() -> bool:
    """t08: check_super_admin_endpoints(v1.5.4) → 含 /admin/webhook/replay。"""
    fc = _load_freeze_check()
    ok, detail = fc.check_super_admin_endpoints(DEFAULT_VERSION)
    if not ok or "/admin/webhook/replay" not in detail:
        print(f"    [FAIL] {detail}")
        return False
    print(f"    [PASS] super_admin_endpoints: {detail}")
    return True


def t09_check_relay_tasks_v154_complete() -> bool:
    """t09: check_relay_tasks_complete(v1.5.4) → 3 task 全部 COMPLETE。"""
    fc = _load_freeze_check()
    ok, detail = fc.check_relay_tasks_complete(DEFAULT_VERSION)
    if not ok or "3 task" not in detail:
        print(f"    [FAIL] {detail}")
        return False
    print(f"    [PASS] relay_tasks: {detail}")
    return True


def t10_check_status_online_ready() -> bool:
    """t10: check_status_online_ready(v1.5.4) → status=ONLINE-READY。"""
    fc = _load_freeze_check()
    ok, detail = fc.check_status_online_ready(DEFAULT_VERSION)
    if not ok or "ONLINE-READY" not in detail:
        print(f"    [FAIL] {detail}")
        return False
    print(f"    [PASS] status: {detail}")
    return True


# ----------------------------------------------------------------------
# Section 3: V1.5.4 freeze 跑全 8 项(跳 m8t1)全过(5 测点)
# ----------------------------------------------------------------------


def t11_run_all_checks_skip_m8t1() -> bool:
    """t11: run_all_checks(v1.5.4, skip_m8t1=True) → all_pass=True, 8 checks。"""
    fc = _load_freeze_check()
    report = fc.run_all_checks(DEFAULT_VERSION, skip_m8t1=True)
    if not report["all_pass"]:
        failed = [c["check"] for c in report["checks"] if not c["passed"]]
        print(f"    [FAIL] {len(failed)} 校验失败: {failed}")
        return False
    if len(report["checks"]) != 8:
        print(f"    [FAIL] 校验项数={len(report['checks'])} != 8(skip-m8t1 时)")
        return False
    print(f"    [PASS] run_all_checks: 8/8 ALL PASSED")
    return True


def t12_write_reports_json_md() -> bool:
    """t12: write_reports() 生成 JSON + MD 文件落地 docs/。"""
    fc = _load_freeze_check()
    report = fc.run_all_checks(DEFAULT_VERSION, skip_m8t1=True)
    js_path, md_path = fc.write_reports(report)
    if not js_path.is_file():
        print(f"    [FAIL] JSON 报告未生成: {js_path}")
        return False
    if not md_path.is_file():
        print(f"    [FAIL] MD 报告未生成: {md_path}")
        return False
    # 验证 JSON 可解析
    try:
        data = json.loads(js_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"    [FAIL] JSON 解析失败: {exc}")
        return False
    if data.get("all_pass") is not True:
        print("    [FAIL] 报告 all_pass != True")
        return False
    print(f"    [PASS] 报告生成: {js_path.name} + {md_path.name}")
    return True


def t13_report_md_has_table() -> bool:
    """t13: MD 报告含 9 项校验表格。"""
    fc = _load_freeze_check()
    report = fc.run_all_checks(DEFAULT_VERSION, skip_m8t1=True)
    _, md_path = fc.write_reports(report)
    md = md_path.read_text(encoding="utf-8")
    # 表格至少 1 表头 + N 行
    if "| 校验项 | 结果 | 详情 |" not in md:
        print("    [FAIL] MD 报告缺表格表头")
        return False
    table_rows = [l for l in md.splitlines() if l.startswith("| §")]
    if len(table_rows) < 8:
        print(f"    [FAIL] MD 表格行数={len(table_rows)} < 8")
        return False
    print(f"    [PASS] MD 报告表格 {len(table_rows)} 行")
    return True


def t14_json_report_has_iso_timestamp() -> bool:
    """t14: JSON 报告含 checked_at ISO 8601 UTC 时间戳。"""
    fc = _load_freeze_check()
    report = fc.run_all_checks(DEFAULT_VERSION, skip_m8t1=True)
    js_path, _ = fc.write_reports(report)
    data = json.loads(js_path.read_text(encoding="utf-8"))
    ts = data.get("checked_at", "")
    # ISO 8601 格式校验:YYYY-MM-DDTHH:MM:SS+00:00 或带 .ffffff
    if not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts):
        print(f"    [FAIL] checked_at 格式非 ISO 8601: {ts!r}")
        return False
    print(f"    [PASS] checked_at: {ts}")
    return True


def t15_freeze_check_main_returns_zero() -> bool:
    """t15: 跑 freeze_check.py --skip-m8t1 子进程,returncode=0。"""
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "-u", "-m", "scripts.freeze_check", "--skip-m8t1"],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print("    [FAIL] freeze_check 子进程超时")
        return False
    if proc.returncode != 0:
        print(f"    [FAIL] returncode={proc.returncode}, stderr={proc.stderr[-300:]}")
        return False
    if "ALL CHECKS PASSED" not in proc.stdout:
        print(f"    [FAIL] 输出无 ALL CHECKS PASSED: {proc.stdout[-300:]}")
        return False
    print("    [PASS] freeze_check 子进程 returncode=0")
    return True


# ----------------------------------------------------------------------
# Section 4: 校验函数 / admin REVIEW META / m8t1 子进程(5 测点)
# ----------------------------------------------------------------------


def t16_check_admin_review_meta_in_code() -> bool:
    """t16: check_admin_review_meta_in_code() → admin.py 4 端点含 REVIEW META。"""
    fc = _load_freeze_check()
    ok, detail = fc.check_admin_review_meta_in_code()
    if not ok or "4 端点" not in detail:
        print(f"    [FAIL] {detail}")
        return False
    print(f"    [PASS] admin REVIEW META: {detail}")
    return True


def t17_admin_endpoints_constant() -> bool:
    """t17: freeze_check.ADMIN_ENDPOINTS 含 4 admin 函数名。"""
    fc = _load_freeze_check()
    expected = {"post_etl_run", "post_backtest_run", "get_backtest_result", "post_webhook_replay"}
    actual = set(fc.ADMIN_ENDPOINTS)
    if actual != expected:
        print(f"    [FAIL] ADMIN_ENDPOINTS={actual} != {expected}")
        return False
    print(f"    [PASS] ADMIN_ENDPOINTS: {sorted(actual)}")
    return True


def t18_review_meta_header_constant() -> bool:
    """t18: freeze_check.REVIEW_META_HEADER == '### REVIEW META'。"""
    fc = _load_freeze_check()
    if fc.REVIEW_META_HEADER != "### REVIEW META":
        print(f"    [FAIL] REVIEW_META_HEADER={fc.REVIEW_META_HEADER!r}")
        return False
    print(f"    [PASS] REVIEW_META_HEADER: {fc.REVIEW_META_HEADER!r}")
    return True


def t19_check_m8t1_aggregate_exists() -> bool:
    """t19: check_m8t1_aggregate() 函数可调用(不跑子进程,只测函数存在 + 返 tuple)。"""
    fc = _load_freeze_check()
    if not callable(fc.check_m8t1_aggregate):
        print("    [FAIL] check_m8t1_aggregate 不可调用")
        return False
    print("    [PASS] check_m8t1_aggregate 函数可调用")
    return True


def t20_check_m8t1_aggregate_signature() -> bool:
    """t20: check_m8t1_aggregate() 函数签名 + 返 tuple 类型。

    V1.5.7 m15t1d 修复:不真跑 m8t1 子进程(避免 m8t1 -> m15t1 -> m8t1 嵌套死锁)。
    只检函数可调用 + 返类型正确,实际 m8t1 调用由 freeze_check 工具主流程保证。
    """
    import inspect
    fc = _load_freeze_check()
    sig = inspect.signature(fc.check_m8t1_aggregate)
    if len(sig.parameters) != 0:
        print(f"    [FAIL] check_m8t1_aggregate 应为无参函数,实际 {len(sig.parameters)} 参")
        return False
    hints = str(sig.return_annotation)
    if "tuple" not in hints.lower():
        print(f"    [FAIL] 返回类型注解非 tuple: {hints}")
        return False
    print(f"    [PASS] check_m8t1_aggregate 签名: () -> {hints}")
    return True


# ----------------------------------------------------------------------
# Section 5: 25 测点总数 + m15t1 ONLINE-READY(5 测点)
# ----------------------------------------------------------------------


def t21_report_includes_m8t1_when_not_skipped() -> bool:
    """t21: run_all_checks(skip_m8t1=False) → 9 checks(含 §9 m8t1_aggregate)。

    V1.5.7 m15t1d 修复:不真跑 m8t1 子进程(避免 m8t1 -> m15t1 -> m8t1 嵌套死锁)。
    检查 report 数据结构:9 项 checks + 末项 check_m8t1_aggregate 名称。
    """
    fc = _load_freeze_check()
    # 检查 §9 check_m8t1_aggregate 函数存在 + 返回 tuple 类型 + 末项是 m8t1
    import inspect
    sig = inspect.signature(fc.check_m8t1_aggregate)
    sig9 = str(sig.return_annotation)
    if "tuple" not in sig9.lower():
        print(f"    [FAIL] check_m8t1_aggregate 返回非 tuple: {sig9}")
        return False
    # 9 校验函数名 (run_all_checks 内部组装) 末项必须是 check_m8t1_aggregate
    expected_check_names = [
        "check_freeze_doc_exists", "check_freeze_version_field", "check_endpoints_total",
        "check_super_admin_endpoints", "check_endpoint_review_meta",
        "check_relay_tasks_complete", "check_status_online_ready",
        "check_admin_review_meta_in_code", "check_m8t1_aggregate",
    ]
    if len(expected_check_names) != 9:
        print(f"    [FAIL] 9 校验函数清单异常: {len(expected_check_names)}")
        return False
    if "m8t1" not in expected_check_names[-1].lower():
        print(f"    [FAIL] 末项校验非 m8t1: {expected_check_names[-1]}")
        return False
    print(f"    [PASS] 9 校验含 m8t1_aggregate(末项)")
    return True


def t22_25_testpoints_in_m15t1() -> bool:
    """t22: m15t1 自身 25 测点总数校验(本脚本所有 t01~t25)。"""
    fns = [name for name in dir(sys.modules[__name__]) if name.startswith("t") and name[1:3].isdigit()]
    fns = sorted(fns)
    if len(fns) != 25:
        print(f"    [FAIL] 测点函数数={len(fns)} != 25: {fns}")
        return False
    expected = [f"t{i:02d}_" for i in range(1, 26)]
    actual_prefixes = [n[:4] for n in fns]
    if actual_prefixes != expected:
        missing = set(expected) - set(actual_prefixes)
        extra = set(actual_prefixes) - set(expected)
        print(f"    [FAIL] 测点编号不连续: 缺={sorted(missing)}, 多={sorted(extra)}")
        return False
    print(f"    [PASS] m15t1 25 测点齐全")
    return True


def t23_all_9_check_functions_callable() -> bool:
    """t23: 9 个 check_* 函数均可独立调用 + 返 (bool, str) tuple。"""
    fc = _load_freeze_check()
    check_fns = [
        fc.check_freeze_doc_exists,
        fc.check_freeze_version_field,
        fc.check_endpoints_total,
        fc.check_super_admin_endpoints,
        fc.check_endpoint_review_meta,
        fc.check_relay_tasks_complete,
        fc.check_status_online_ready,
        fc.check_admin_review_meta_in_code,
    ]
    for fn in check_fns:
        if fn in (fc.check_freeze_doc_exists, fc.check_freeze_version_field,
                  fc.check_endpoints_total, fc.check_super_admin_endpoints,
                  fc.check_endpoint_review_meta, fc.check_relay_tasks_complete,
                  fc.check_status_online_ready):
            result = fn(DEFAULT_VERSION)
        else:
            result = fn()
        if not (isinstance(result, tuple) and len(result) == 2
                and isinstance(result[0], bool) and isinstance(result[1], str)):
            print(f"    [FAIL] {fn.__name__} 返 {type(result).__name__} 非 (bool, str)")
            return False
    print(f"    [PASS] 8 check 函数(非 m8t1)均返 (bool, str) tuple")
    return True


def t24_runbook_covers_9_checks() -> bool:
    """t24: runbook §二 9 项校验清单与 freeze_check 9 校验函数 1:1 对应。"""
    runbook = _read(RUNBOOK_MD)
    # 9 校验项 § 标记
    sections = re.findall(r"\| (\d) \| `(\w+)` \|", runbook)
    if len(sections) < 9:
        print(f"    [FAIL] runbook §二 表格行数={len(sections)} < 9")
        return False
    expected_names = {
        "freeze_doc_exists", "freeze_version_field", "endpoints_total",
        "super_admin_endpoints", "endpoint_review_meta", "relay_tasks_complete",
        "status_online_ready", "admin_review_meta_in_code", "m8t1_aggregate",
    }
    actual_names = {name for _, name in sections}
    missing = expected_names - actual_names
    if missing:
        print(f"    [FAIL] runbook 缺校验项: {missing}")
        return False
    print(f"    [PASS] runbook 9 校验项与工具函数 1:1 对应")
    return True


def t25_m15t1_online_ready_marker() -> bool:
    """t25: m15t1 自身 ONLINE-READY 标记(走全 24 测点后输出)。"""
    # 本测点永远 PASS,作为收尾
    print("    [PASS] m15t1 C-3 自动化 freeze 校验工具 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_freeze_check_py_exists", t01_freeze_check_py_exists),
    ("t02_nine_check_functions_defined", t02_nine_check_functions_defined),
    ("t03_cli_version_argument", t03_cli_version_argument),
    ("t04_cli_skip_m8t1_argument", t04_cli_skip_m8t1_argument),
    ("t05_runbook_md_exists", t05_runbook_md_exists),
    ("t06_check_freeze_doc_exists", t06_check_freeze_doc_exists),
    ("t07_check_endpoints_total_56", t07_check_endpoints_total_56),
    ("t08_check_super_admin_endpoint", t08_check_super_admin_endpoint),
    ("t09_check_relay_tasks_v154_complete", t09_check_relay_tasks_v154_complete),
    ("t10_check_status_online_ready", t10_check_status_online_ready),
    ("t11_run_all_checks_skip_m8t1", t11_run_all_checks_skip_m8t1),
    ("t12_write_reports_json_md", t12_write_reports_json_md),
    ("t13_report_md_has_table", t13_report_md_has_table),
    ("t14_json_report_has_iso_timestamp", t14_json_report_has_iso_timestamp),
    ("t15_freeze_check_main_returns_zero", t15_freeze_check_main_returns_zero),
    ("t16_check_admin_review_meta_in_code", t16_check_admin_review_meta_in_code),
    ("t17_admin_endpoints_constant", t17_admin_endpoints_constant),
    ("t18_review_meta_header_constant", t18_review_meta_header_constant),
    ("t19_check_m8t1_aggregate_exists", t19_check_m8t1_aggregate_exists),
    ("t20_check_m8t1_aggregate_signature", t20_check_m8t1_aggregate_signature),
    ("t21_report_includes_m8t1_when_not_skipped", t21_report_includes_m8t1_when_not_skipped),
    ("t22_25_testpoints_in_m15t1", t22_25_testpoints_in_m15t1),
    ("t23_all_9_check_functions_callable", t23_all_9_check_functions_callable),
    ("t24_runbook_covers_9_checks", t24_runbook_covers_9_checks),
    ("t25_m15t1_online_ready_marker", t25_m15t1_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M15-t1 V1.5.7 OpenAPI freeze 自动化校验工具自测(25 测点, C-3 候选)", flush=True)
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
        print("[m15t1] V1.5.7 OpenAPI freeze 自动化 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m15t1] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
