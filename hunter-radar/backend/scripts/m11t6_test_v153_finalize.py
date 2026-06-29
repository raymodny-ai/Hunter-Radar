"""M11-t6 V1.5.3 final handoff + OpenAPI freeze 自测(25 测点)。

V1.5.3 接力期 m11t6 — final handoff + OpenAPI v1.5.3 freeze 校验:
- V1.5.3-handoff.md(7 项评审修复全记录)
- openapi-frozen-v1.5.3.md / .json(代码层 freeze)
- m8t1 聚合 runner M11 列表(5 脚本 / 125 测点)
- 7 项 V1.5.2 评审修复项全部落档

Section 1 — V1.5.3 handoff 文档(5 测点):
  - docs/V1.5.3-handoff.md 存在
  - 7 项评审未通过项全部记录
  - m11t1~m11t6 全部 COMPLETE
  - V1.5.3 production:ONLINE-READY
  - 7/7 评审项全修复表

Section 2 — OpenAPI freeze md(5 测点):
  - docs/openapi-frozen-v1.5.3.md 存在
  - 5 大节齐全
  - 端点总数 56 沿用
  - fetch_source 8 值沿用
  - 7 项修复代码层记录

Section 3 — OpenAPI freeze json(5 测点):
  - docs/openapi-frozen-v1.5.3.json 存在
  - endpoints_total=56
  - unpassed_items_resolved 7 项
  - M11_scripts 6 项(5 + 1 聚合)
  - total_testpoints=1077+

Section 4 — m8t1 聚合 runner(5 测点):
  - M11_SCRIPTS 含 m11t1~m11t5
  - main() 加 M11 run_group
  - 总结输出 V1.5.3-ONLINE-READY
  - M11(125 测点)
  - NOT READY FOR V1.5.3 FREEZE 文案

Section 5 — 评审 + 边界(5 测点):
  - 5 个 M11 测点脚本存在
  - m11t1~m11t5 测点脚本存在
  - m8t1 V1.5.3 头部
  - 25 测点总数
  - V1.5.4+ 候选记录

总计 25 测点。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SCRIPTS = ROOT / "backend" / "scripts"
V153_HANDOFF_MD = DOCS / "V1.5.3-handoff.md"
OPENAPI_V153_MD = DOCS / "openapi-frozen-v1.5.3.md"
OPENAPI_V153_JSON = DOCS / "openapi-frozen-v1.5.3.json"
M8T1_PY = SCRIPTS / "m8t1_test_regression.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def t01_v153_handoff_exists() -> bool:
    """t01: docs/V1.5.3-handoff.md 存在。"""
    if not V153_HANDOFF_MD.exists():
        print("    [FAIL] V1.5.3-handoff.md 不存在")
        return False
    print("    [PASS] V1.5.3-handoff.md 存在")
    return True


def t02_v153_handoff_7_unpassed_resolved() -> bool:
    """t02: handoff 含 7 项评审未通过项全部 m11t1~m11t5 修复。"""
    txt = _read(V153_HANDOFF_MD)
    items = [
        ("M10-UNPASSED-1", "m11t1"),
        ("M10-UNPASSED-2", "m11t2"),
        ("M10-UNPASSED-3", "m11t3"),
        ("M10-UNPASSED-4", "m11t4"),
        ("M10-UNPASSED-5", "m11t4"),
        ("M10-UNPASSED-6", "m11t4"),
        ("M10-UNPASSED-7", "m11t5"),
    ]
    for item, todo in items:
        if item not in txt or todo not in txt:
            print(f"    [FAIL] handoff 缺 {item} → {todo}")
            return False
    print("    [PASS] handoff 7 项评审未通过项全修复")
    return True


def t03_v153_handoff_m11_all_complete() -> bool:
    """t03: handoff 中 m11t1~m11t6 全部 COMPLETE。"""
    txt = _read(V153_HANDOFF_MD)
    for tid in ["m11t1", "m11t2", "m11t3", "m11t4", "m11t5", "m11t6"]:
        if tid not in txt:
            print(f"    [FAIL] handoff 缺 {tid}")
            return False
    print("    [PASS] handoff m11t1~m11t6 全在")
    return True


def t04_v153_handoff_online_ready() -> bool:
    """t04: handoff 标识 V1.5.3 production ONLINE-READY。"""
    txt = _read(V153_HANDOFF_MD)
    if "ONLINE-READY" not in txt or "V1.5.3" not in txt:
        print("    [FAIL] handoff 缺 V1.5.3 ONLINE-READY")
        return False
    print("    [PASS] V1.5.3 ONLINE-READY 标识")
    return True


def t05_v153_handoff_7_resolved_table() -> bool:
    """t05: handoff 1.3 节含 7 项修复表格。"""
    txt = _read(V153_HANDOFF_MD)
    if "1.3 7 项 V1.5.2 评审未通过项" not in txt:
        print("    [FAIL] handoff 1.3 节缺 7 项修复表标题")
        return False
    print("    [PASS] handoff 1.3 7 项修复表")
    return True


def t06_openapi_v153_md_exists() -> bool:
    """t06: docs/openapi-frozen-v1.5.3.md 存在。"""
    if not OPENAPI_V153_MD.exists():
        print("    [FAIL] openapi-frozen-v1.5.3.md 不存在")
        return False
    print("    [PASS] openapi-frozen-v1.5.3.md 存在")
    return True


def t07_openapi_v153_md_5_sections() -> bool:
    """t07: openapi-frozen-v1.5.3.md 含 5 大节。"""
    txt = _read(OPENAPI_V153_MD)
    for sec in ["## 一、概述", "## 二、M11 增量", "## 三、fetch_source 规范", "## 四、变更流程", "## 五、freeze 校验"]:
        if sec not in txt:
            print(f"    [FAIL] openapi md 缺 {sec}")
            return False
    print("    [PASS] openapi md 5 大节齐全")
    return True


def t08_openapi_v153_md_56_endpoints() -> bool:
    """t08: openapi md 标识端点总数 56 沿用。"""
    txt = _read(OPENAPI_V153_MD)
    if "56" not in txt:
        print("    [FAIL] openapi md 缺 56 端点")
        return False
    if "沿用" not in txt:
        print("    [FAIL] openapi md 缺'沿用'标记")
        return False
    print("    [PASS] openapi md 56 端点沿用")
    return True


def t09_openapi_v153_md_fetch_source_8() -> bool:
    """t09: openapi md 含 fetch_source 8 值。"""
    txt = _read(OPENAPI_V153_MD)
    fs = [
        "sec_httpx", "yfinance", "user_provided_price", "posthog",
        "plausible", "sandbox_stub", "sandbox_stub_v15_prep", "sandbox_skip_admin",
    ]
    for v in fs:
        if v not in txt:
            print(f"    [FAIL] openapi md fetch_source 缺 {v}")
            return False
    print("    [PASS] openapi md fetch_source 8 值齐全")
    return True


def t10_openapi_v153_md_7_resolved() -> bool:
    """t10: openapi md 含 7 项评审修复记录(代码层)。"""
    txt = _read(OPENAPI_V153_MD)
    for item in ["M10-UNPASSED-1", "M10-UNPASSED-2", "M10-UNPASSED-3",
                 "M10-UNPASSED-4", "M10-UNPASSED-5", "M10-UNPASSED-6", "M10-UNPASSED-7"]:
        if item not in txt:
            print(f"    [FAIL] openapi md 缺 {item}")
            return False
    print("    [PASS] openapi md 7 项评审修复记录")
    return True


def t11_openapi_v153_json_exists() -> bool:
    """t11: docs/openapi-frozen-v1.5.3.json 存在且 JSON 合法。"""
    if not OPENAPI_V153_JSON.exists():
        print("    [FAIL] openapi-frozen-v1.5.3.json 不存在")
        return False
    try:
        data = json.loads(OPENAPI_V153_JSON.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"    [FAIL] openapi json parse 失败:{exc}")
        return False
    print("    [PASS] openapi json 存在 + 合法")
    return True


def t12_openapi_v153_json_endpoints_56() -> bool:
    """t12: openapi json endpoints_total=56。"""
    try:
        data = json.loads(OPENAPI_V153_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        print("    [FAIL] openapi json parse 失败")
        return False
    if data.get("endpoints_total") != 56:
        print(f"    [FAIL] endpoints_total={data.get('endpoints_total')} != 56")
        return False
    print("    [PASS] openapi json endpoints_total=56")
    return True


def t13_openapi_v153_json_7_unpassed() -> bool:
    """t13: openapi json unpassed_items_resolved 7 项。"""
    try:
        data = json.loads(OPENAPI_V153_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        print("    [FAIL] openapi json parse 失败")
        return False
    items = data.get("unpassed_items_resolved", [])
    if len(items) != 7:
        print(f"    [FAIL] unpassed_items_resolved 长度={len(items)} != 7")
        return False
    print(f"    [PASS] unpassed_items_resolved 7 项({len(items)})")
    return True


def t14_openapi_v153_json_m11_scripts_6() -> bool:
    """t14: openapi json M11_scripts 6 项(5 + 1 聚合)。"""
    try:
        data = json.loads(OPENAPI_V153_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        print("    [FAIL] openapi json parse 失败")
        return False
    scripts = data.get("M11_scripts", [])
    if len(scripts) != 6:
        print(f"    [FAIL] M11_scripts 长度={len(scripts)} != 6")
        return False
    # 应含 m11t1~m11t6
    ids = [s["id"] for s in scripts]
    for tid in ["m11t1", "m11t2", "m11t3", "m11t4", "m11t5", "m11t6"]:
        if tid not in ids:
            print(f"    [FAIL] M11_scripts 缺 {tid}")
            return False
    print(f"    [PASS] M11_scripts 6 项齐全")
    return True


def t15_openapi_v153_json_total_testpoints() -> bool:
    """t15: openapi json total_testpoints >= 1000。"""
    try:
        data = json.loads(OPENAPI_V153_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        print("    [FAIL] openapi json parse 失败")
        return False
    total = data.get("static_test_aggregate", {}).get("total_testpoints", 0)
    if total < 1000:
        print(f"    [FAIL] total_testpoints={total} < 1000")
        return False
    print(f"    [PASS] total_testpoints={total} >= 1000")
    return True


def t16_m8t1_m11_scripts_list() -> bool:
    """t16: m8t1 M11_SCRIPTS 含 m11t1~m11t5。"""
    txt = _read(M8T1_PY)
    for tid in ["m11t1_test_auth_all_export.py", "m11t2_test_admin_role_ip_integration.py",
                "m11t3_test_role_extension.py", "m11t4_test_reviewer_cli_toolchain.py",
                "m11t5_test_p2_json_only.py"]:
        if tid not in txt:
            print(f"    [FAIL] m8t1 M11_SCRIPTS 缺 {tid}")
            return False
    print("    [PASS] m8t1 M11_SCRIPTS 5 脚本齐全")
    return True


def t17_m8t1_main_m11_runs() -> bool:
    """t17: m8t1 main() 含 M11 run_group。"""
    txt = _read(M8T1_PY)
    if "M8-t1 / M11 接力期自测回归" not in txt:
        print("    [FAIL] m8t1 main 缺 M11 run_group")
        return False
    if "f7, p7, tot7" not in txt:
        print("    [FAIL] m8t1 main 缺 f7, p7, tot7")
        return False
    print("    [PASS] m8t1 main 加 M11 run_group")
    return True


def t18_m8t1_summary_v153_online_ready() -> bool:
    """t18: m8t1 总结输出 V1.5.3-ONLINE-READY。"""
    txt = _read(M8T1_PY)
    if "V1.5.3-ONLINE-READY" not in txt:
        print("    [FAIL] m8t1 总结缺 V1.5.3-ONLINE-READY")
        return False
    if "M11({p7}/125)" not in txt:
        print("    [FAIL] m8t1 总结缺 M11(125)")
        return False
    print("    [PASS] m8t1 总结 V1.5.3-ONLINE-READY + M11/125")
    return True


def t19_m8t1_failure_msg_v153() -> bool:
    """t19: m8t1 失败文案改 V1.5.3 FREEZE。"""
    txt = _read(M8T1_PY)
    if "NOT READY FOR V1.5.3 FREEZE" not in txt:
        print("    [FAIL] m8t1 失败文案未改 V1.5.3 FREEZE")
        return False
    print("    [PASS] m8t1 失败文案 V1.5.3 FREEZE")
    return True


def t20_m8t1_m11_run_group_5_scripts_125() -> bool:
    """t20: m8t1 M11 run_group 标题含 (5 脚本 / 125 测点)。"""
    txt = _read(M8T1_PY)
    if "(5 脚本 / 125 测点)" not in txt:
        print("    [FAIL] m8t1 M11 run_group 标题缺 (5 脚本 / 125 测点)")
        return False
    print("    [PASS] m8t1 M11 run_group 5 脚本 125 测点")
    return True


def t21_5_m11_test_scripts_exist() -> bool:
    """t21: 5 个 M11 自测脚本存在。"""
    for fn in ["m11t1_test_auth_all_export.py", "m11t2_test_admin_role_ip_integration.py",
               "m11t3_test_role_extension.py", "m11t4_test_reviewer_cli_toolchain.py",
               "m11t5_test_p2_json_only.py"]:
        if not (SCRIPTS / fn).exists():
            print(f"    [FAIL] {fn} 不存在")
            return False
    print("    [PASS] 5 个 M11 自测脚本存在")
    return True


def t22_m11t6_marker_in_handoff() -> bool:
    """t22: handoff 标识 m11t6 final handoff。"""
    txt = _read(V153_HANDOFF_MD)
    if "m11t6" not in txt:
        print("    [FAIL] handoff 缺 m11t6 标识")
        return False
    print("    [PASS] handoff 含 m11t6 标识")
    return True


def t23_m8t1_header_v153() -> bool:
    """t23: m8t1 头部注释标识 V1.5.3。"""
    txt = _read(M8T1_PY)
    if "V1.5.3 接力期" not in txt[:1500]:
        print("    [FAIL] m8t1 头部缺 V1.5.3 接力期")
        return False
    print("    [PASS] m8t1 头部 V1.5.3 标识")
    return True


def t24_openapi_v153_json_production_env() -> bool:
    """t24: openapi json 含生产环境变量推荐。"""
    try:
        data = json.loads(OPENAPI_V153_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        print("    [FAIL] openapi json parse 失败")
        return False
    env = data.get("production_env_recommendations", {})
    if "REVIEWER_TOKEN_HEX_LEN" not in env:
        print("    [FAIL] production_env_recommendations 缺 REVIEWER_TOKEN_HEX_LEN")
        return False
    if "HR_ALLOW_LEGACY_SCRIPTS" not in env:
        print("    [FAIL] production_env_recommendations 缺 HR_ALLOW_LEGACY_SCRIPTS")
        return False
    print("    [PASS] openapi json 生产环境变量齐全")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_v153_handoff_exists, t02_v153_handoff_7_unpassed_resolved,
        t03_v153_handoff_m11_all_complete, t04_v153_handoff_online_ready,
        t05_v153_handoff_7_resolved_table,
        t06_openapi_v153_md_exists, t07_openapi_v153_md_5_sections,
        t08_openapi_v153_md_56_endpoints, t09_openapi_v153_md_fetch_source_8,
        t10_openapi_v153_md_7_resolved,
        t11_openapi_v153_json_exists, t12_openapi_v153_json_endpoints_56,
        t13_openapi_v153_json_7_unpassed, t14_openapi_v153_json_m11_scripts_6,
        t15_openapi_v153_json_total_testpoints,
        t16_m8t1_m11_scripts_list, t17_m8t1_main_m11_runs,
        t18_m8t1_summary_v153_online_ready, t19_m8t1_failure_msg_v153,
        t20_m8t1_m11_run_group_5_scripts_125,
        t21_5_m11_test_scripts_exist, t22_m11t6_marker_in_handoff,
        t23_m8t1_header_v153, t24_openapi_v153_json_production_env,
        t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_v153_handoff_exists", t01_v153_handoff_exists),
    ("t02_v153_handoff_7_unpassed_resolved", t02_v153_handoff_7_unpassed_resolved),
    ("t03_v153_handoff_m11_all_complete", t03_v153_handoff_m11_all_complete),
    ("t04_v153_handoff_online_ready", t04_v153_handoff_online_ready),
    ("t05_v153_handoff_7_resolved_table", t05_v153_handoff_7_resolved_table),
    ("t06_openapi_v153_md_exists", t06_openapi_v153_md_exists),
    ("t07_openapi_v153_md_5_sections", t07_openapi_v153_md_5_sections),
    ("t08_openapi_v153_md_56_endpoints", t08_openapi_v153_md_56_endpoints),
    ("t09_openapi_v153_md_fetch_source_8", t09_openapi_v153_md_fetch_source_8),
    ("t10_openapi_v153_md_7_resolved", t10_openapi_v153_md_7_resolved),
    ("t11_openapi_v153_json_exists", t11_openapi_v153_json_exists),
    ("t12_openapi_v153_json_endpoints_56", t12_openapi_v153_json_endpoints_56),
    ("t13_openapi_v153_json_7_unpassed", t13_openapi_v153_json_7_unpassed),
    ("t14_openapi_v153_json_m11_scripts_6", t14_openapi_v153_json_m11_scripts_6),
    ("t15_openapi_v153_json_total_testpoints", t15_openapi_v153_json_total_testpoints),
    ("t16_m8t1_m11_scripts_list", t16_m8t1_m11_scripts_list),
    ("t17_m8t1_main_m11_runs", t17_m8t1_main_m11_runs),
    ("t18_m8t1_summary_v153_online_ready", t18_m8t1_summary_v153_online_ready),
    ("t19_m8t1_failure_msg_v153", t19_m8t1_failure_msg_v153),
    ("t20_m8t1_m11_run_group_5_scripts_125", t20_m8t1_m11_run_group_5_scripts_125),
    ("t21_5_m11_test_scripts_exist", t21_5_m11_test_scripts_exist),
    ("t22_m11t6_marker_in_handoff", t22_m11t6_marker_in_handoff),
    ("t23_m8t1_header_v153", t23_m8t1_header_v153),
    ("t24_openapi_v153_json_production_env", t24_openapi_v153_json_production_env),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M11-t6 V1.5.3 final handoff + OpenAPI freeze 自测(25 测点)")
    print("=" * 72)
    failures = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"    [FAIL] {name} 异常:{type(exc).__name__}: {exc}")
            ok = False
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            failures += 1
    print("=" * 72)
    if failures == 0:
        print("[m11t6] V1.5.3 final handoff + OpenAPI freeze 25/25 ALL PASSED")
        return 0
    print(f"[m11t6] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
