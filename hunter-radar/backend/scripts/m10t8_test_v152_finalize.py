"""M10-t8 V1.5.2 final handoff + OpenAPI freeze 自测(25 测点)。

V1.5.2 接力期 m10t8 — V1.5.2 freeze 校验:
- V1.5.2-handoff.md 8/8 todo COMPLETE
- OpenAPI v1.5.2 freeze md + json 存在
- 3 端点响应字段增强(EDGAR + ETF + Analytics)
- 4 admin 端点公开评审
- 7 项 V1.5.3 待优化项
- 46 个脚本 / 933+ 测点静态回归

Section 1 — handoff 文档结构(5 测点):
  - V1.5.2-handoff.md 存在 + 标题正确
  - 8/8 todo 表格完整
  - 4 大节(交付 / 增量 / 变更 / 评审)
  - 8 todo marker
  - 7 V1.5.3 未通过项

Section 2 — OpenAPI freeze md(5 测点):
  - openapi-frozen-v1.5.2.md 存在
  - 5 大节(概述 / M10 增量 / fetch_source 规范 / 变更流程 / freeze 校验)
  - 3 端点字段增强清单
  - fetch_source 8 值表
  - 评审 m10t8

Section 3 — OpenAPI freeze json(5 测点):
  - openapi-frozen-v1.5.2.json 存在
  - openapi 3.0.3 + version 1.5.2
  - endpoints_total=56 + endpoints_modified=3
  - modified_modules 3 项
  - documented_endpoints 4 admin
  - unpassed_items 7 项
  - fetch_source_unified 8 值
  - r_risks_resolved 3 项

Section 4 — 评审文档(4 测点):
  - ADMIN_ROLE_V152.md 存在
  - REVIEWER_CLI_MIGRATION.md 存在
  - V1.5.2-handoff 引用 ≥5 文档
  - m10t8 自测脚本存在

Section 5 — 静态自测聚合(6 测点):
  - 46 脚本 / 933+ 测点
  - m8t1 M10_SCRIPTS 7 项齐全
  - 7 文档(V1.5.2 + openapi-v1.5.2 ×2 + ADMIN_ROLE_V152 + REVIEWER_CLI_MIGRATION + handoff + 既有)
  - 25 测点总数校验

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
HANDOFF_MD = DOCS / "V1.5.2-handoff.md"
OPENAPI_MD = DOCS / "openapi-frozen-v1.5.2.md"
OPENAPI_JSON = DOCS / "openapi-frozen-v1.5.2.json"
ADMIN_AUDIT_MD = DOCS / "ADMIN_ROLE_V152.md"
REVIEWER_MIG_MD = DOCS / "REVIEWER_CLI_MIGRATION.md"
M8T1_PY = SCRIPTS / "m8t1_test_regression.py"
M10T1_PY = SCRIPTS / "m10t1_test_edgar_real.py"
M10T2_PY = SCRIPTS / "m10t2_test_etf_real.py"
M10T3_PY = SCRIPTS / "m10t3_test_analytics_real.py"
M10T4_PY = SCRIPTS / "m10t4_test_admin_role_audit.py"
M10T5_PY = SCRIPTS / "m10t5_test_reviewer_cli_replace.py"
M10T6_PY = SCRIPTS / "m10t6_test_scipy_replace.py"
M10T7_PY = SCRIPTS / "m10t7_test_p2_merge.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def t01_handoff_exists_title() -> bool:
    """t01: V1.5.2-handoff.md 存在 + 标题正确。"""
    if not HANDOFF_MD.exists():
        print("    [FAIL] V1.5.2-handoff.md 缺失")
        return False
    txt = _read(HANDOFF_MD)
    if "V1.5.2 Handoff" not in txt:
        print("    [FAIL] 缺 V1.5.2 Handoff 标题")
        return False
    if "V1.5.2 接力期" not in txt:
        print("    [FAIL] 缺 V1.5.2 接力期")
        return False
    print("    [PASS] V1.5.2-handoff.md 存在 + 标题")
    return True


def t02_handoff_8_todos() -> bool:
    """t02: 8/8 todo 表格完整(m10t1~m10t8)。"""
    txt = _read(HANDOFF_MD)
    expected = [
        "**m10t1**",
        "**m10t2**",
        "**m10t3**",
        "**m10t4**",
        "**m10t5**",
        "**m10t6**",
        "**m10t7**",
        "**m10t8**",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 8 todo 缺:{missing}")
        return False
    if "8/8 = 100%" not in txt:
        print("    [FAIL] 缺 8/8 = 100% 标记")
        return False
    print("    [PASS] 8/8 todo 完整")
    return True


def t03_handoff_4_sections() -> bool:
    """t03: 4 大节(交付 / 增量 / 变更 / 评审)。"""
    txt = _read(HANDOFF_MD)
    expected = [
        "## 一、V1.5.2 接力期范围与交付",
        "## 二、V1.5.2 增量特性",
        "## 三、OpenAPI v1.5.2 freeze 变更摘要",
        "## 四、回归验证",
    ]
    missing = [s for s in expected if s not in txt]
    if missing:
        print(f"    [FAIL] 4 大节缺:{missing[:2]}")
        return False
    print("    [PASS] 4 大节齐全")
    return True


def t04_handoff_8_todo_marker() -> bool:
    """t04: 8 todo 状态 [DONE] 标记。

    V1.5.5 接力期 m13t6 修复:PowerShell GBK 编码 print emoji `✅` UnicodeEncodeError,
    改用 ASCII 标记 `[DONE]` + 表格列 `| [DONE] |` 计数。
    """
    txt = _read(HANDOFF_MD)
    # V1.5.5 m13t6:接受 emoji ✅ 与 ASCII [DONE] 两种形式
    n_emoji = txt.count("| ✅ |")
    n_ascii = txt.count("| [DONE] |")
    n = n_emoji + n_ascii
    if n < 10:  # 表格内 8 + 合计 1 + 其它 ≥1
        print(f"    [FAIL] done marker {n} < 10(emoji={n_emoji}, ascii={n_ascii})")
        return False
    print(f"    [PASS] done marker {n} 个(emoji={n_emoji}, ascii={n_ascii})")
    return True


def t05_handoff_7_unpassed() -> bool:
    """t05: 7 项 V1.5.3 未通过项。"""
    txt = _read(HANDOFF_MD)
    n = txt.count("M10-UNPASSED-")
    if n < 7:
        print(f"    [FAIL] V1.5.3 未通过项仅 {n} < 7")
        return False
    print(f"    [PASS] V1.5.3 未通过项 {n} 条")
    return True


def t06_openapi_md_exists() -> bool:
    """t06: openapi-frozen-v1.5.2.md 存在。"""
    if not OPENAPI_MD.exists():
        print("    [FAIL] openapi-frozen-v1.5.2.md 缺失")
        return False
    txt = _read(OPENAPI_MD)
    if "OpenAPI Freeze v1.5.2" not in txt:
        print("    [FAIL] 缺 OpenAPI Freeze v1.5.2 标题")
        return False
    print("    [PASS] openapi-frozen-v1.5.2.md 存在")
    return True


def t07_openapi_md_5_sections() -> bool:
    """t07: 5 大节(概述 / M10 增量 / fetch_source 规范 / 变更流程 / freeze 校验)。"""
    txt = _read(OPENAPI_MD)
    expected = [
        "## 一、概述",
        "## 二、M10 增量",
        "## 三、fetch_source 字段统一规范",
        "## 四、变更流程",
        "## 五、freeze 校验",
    ]
    missing = [s for s in expected if s not in txt]
    if missing:
        print(f"    [FAIL] 5 大节缺:{missing[:2]}")
        return False
    print("    [PASS] 5 大节齐全")
    return True


def t08_openapi_md_3_endpoints() -> bool:
    """t08: 3 端点响应字段增强清单(EDGAR + ETF + Analytics)。"""
    txt = _read(OPENAPI_MD)
    endpoints = [
        "/api/v1/edgar/search",
        "/api/v1/etf/premium-discount",
        "/api/v1/analytics/events",
    ]
    missing = [e for e in endpoints if e not in txt]
    if missing:
        print(f"    [FAIL] 3 端点缺:{missing}")
        return False
    print("    [PASS] 3 端点字段增强清单")
    return True


def t09_openapi_md_fetch_source_8() -> bool:
    """t09: fetch_source 8 值表(sec_httpx / yfinance / user_provided_price / posthog / plausible / sandbox_stub / sandbox_stub_v15_prep / sandbox_skip_admin)。"""
    txt = _read(OPENAPI_MD)
    values = [
        "sec_httpx",
        "yfinance",
        "user_provided_price",
        "posthog",
        "plausible",
        "sandbox_stub",
        "sandbox_stub_v15_prep",
        "sandbox_skip_admin",
    ]
    missing = [v for v in values if v not in txt]
    if missing:
        print(f"    [FAIL] fetch_source 8 值缺:{missing}")
        return False
    print("    [PASS] fetch_source 8 值齐全")
    return True


def t10_openapi_md_freeze_validation() -> bool:
    """t10: freeze 校验章节 m10t8_test_v152_finalize.py 25 测点。"""
    txt = _read(OPENAPI_MD)
    if "m10t8_test_v152_finalize.py" not in txt:
        print("    [FAIL] 缺 m10t8_test_v152_finalize.py 引用")
        return False
    if "25 测点" not in txt:
        print("    [FAIL] 缺 25 测点说明")
        return False
    print("    [PASS] freeze 校验章节完整")
    return True


def t11_openapi_json_exists() -> bool:
    """t11: openapi-frozen-v1.5.2.json 存在 + 可解析。"""
    if not OPENAPI_JSON.exists():
        print("    [FAIL] openapi-frozen-v1.5.2.json 缺失")
        return False
    try:
        data = json.loads(_read(OPENAPI_JSON))
    except json.JSONDecodeError as e:
        print(f"    [FAIL] JSON 解析失败:{e}")
        return False
    print("    [PASS] openapi-frozen-v1.5.2.json 存在 + 可解析")
    return True


def t12_openapi_json_metadata() -> bool:
    """t12: openapi 3.0.3 + version 1.5.2 + freeze_time。"""
    data = json.loads(_read(OPENAPI_JSON))
    if data.get("openapi") != "3.0.3":
        print(f"    [FAIL] openapi={data.get('openapi')} != 3.0.3")
        return False
    info = data.get("info", {})
    if info.get("version") != "1.5.2":
        print(f"    [FAIL] info.version={info.get('version')} != 1.5.2")
        return False
    if info.get("freeze_time") != "2026-06-15":
        print(f"    [FAIL] freeze_time={info.get('freeze_time')}")
        return False
    print("    [PASS] openapi 3.0.3 + version 1.5.2 + freeze_time")
    return True


def t13_openapi_json_endpoints_total() -> bool:
    """t13: endpoints_total=56 + endpoints_modified=3 + documented=4。"""
    data = json.loads(_read(OPENAPI_JSON))
    if data.get("endpoints_total") != 56:
        print(f"    [FAIL] endpoints_total={data.get('endpoints_total')} != 56")
        return False
    if data.get("endpoints_modified_in_v152") != 3:
        print(f"    [FAIL] endpoints_modified_in_v152={data.get('endpoints_modified_in_v152')} != 3")
        return False
    if data.get("endpoints_documented_in_v152") != 4:
        print(f"    [FAIL] endpoints_documented_in_v152={data.get('endpoints_documented_in_v152')} != 4")
        return False
    print("    [PASS] 端点计数正确")
    return True


def t14_openapi_json_modified_modules() -> bool:
    """t14: modified_modules 3 项(edgar + etf + analytics)。"""
    data = json.loads(_read(OPENAPI_JSON))
    mods = data.get("modified_modules", [])
    if len(mods) != 3:
        print(f"    [FAIL] modified_modules={len(mods)} != 3")
        return False
    paths = [m.get("path") for m in mods]
    expected_paths = ["edgar.py", "etf.py", "analytics.py"]
    missing = [p for p in expected_paths if not any(p in x for x in paths)]
    if missing:
        print(f"    [FAIL] 路径缺:{missing}")
        return False
    print("    [PASS] modified_modules 3 项齐全")
    return True


def t15_openapi_json_admin_documented() -> bool:
    """t15: documented_endpoints 4 admin。"""
    data = json.loads(_read(OPENAPI_JSON))
    doced = data.get("documented_endpoints", [])
    if not doced:
        print("    [FAIL] 缺 documented_endpoints")
        return False
    admin_doc = doced[0]
    eps = admin_doc.get("endpoints", [])
    if len(eps) != 4:
        print(f"    [FAIL] admin endpoints={len(eps)} != 4")
        return False
    if admin_doc.get("documentation") != "docs/ADMIN_ROLE_V152.md":
        print(f"    [FAIL] documentation={admin_doc.get('documentation')}")
        return False
    print("    [PASS] 4 admin 端点文档化")
    return True


def t16_openapi_json_unpassed_7() -> bool:
    """t16: unpassed_items_for_v153 7 项。"""
    data = json.loads(_read(OPENAPI_JSON))
    unpassed = data.get("unpassed_items_for_v153", [])
    if len(unpassed) != 7:
        print(f"    [FAIL] unpassed_items={len(unpassed)} != 7")
        return False
    print(f"    [PASS] unpassed_items {len(unpassed)} 条")
    return True


def t17_openapi_json_fetch_source_8() -> bool:
    """t17: fetch_source_unified 8 值。"""
    data = json.loads(_read(OPENAPI_JSON))
    fs = data.get("fetch_source_unified", [])
    if len(fs) != 8:
        print(f"    [FAIL] fetch_source_unified={len(fs)} != 8")
        return False
    print(f"    [PASS] fetch_source_unified {len(fs)} 值")
    return True


def t18_openapi_json_risks_resolved() -> bool:
    """t18: r_risks_resolved 3 项(R-37/38/39)。"""
    data = json.loads(_read(OPENAPI_JSON))
    risks = data.get("r_risks_resolved", [])
    if len(risks) != 3:
        print(f"    [FAIL] r_risks_resolved={len(risks)} != 3")
        return False
    ids = [r.get("id") for r in risks]
    if set(ids) != {"R-37", "R-38", "R-39"}:
        print(f"    [FAIL] risk IDs={ids}")
        return False
    print("    [PASS] R-37/38/39 解除")
    return True


def t19_admin_audit_doc() -> bool:
    """t19: ADMIN_ROLE_V152.md 评审文档存在。"""
    if not ADMIN_AUDIT_MD.exists():
        print("    [FAIL] ADMIN_ROLE_V152.md 缺失")
        return False
    print("    [PASS] ADMIN_ROLE_V152.md 存在")
    return True


def t20_reviewer_migration_doc() -> bool:
    """t20: REVIEWER_CLI_MIGRATION.md 迁移指南存在。"""
    if not REVIEWER_MIG_MD.exists():
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺失")
        return False
    print("    [PASS] REVIEWER_CLI_MIGRATION.md 存在")
    return True


def t21_handoff_references_5() -> bool:
    """t21: handoff 引用 ≥5 文档。"""
    txt = _read(HANDOFF_MD)
    refs = [
        "ADMIN_ROLE_V152.md",
        "REVIEWER_CLI_MIGRATION.md",
        "openapi-frozen-v1.5.2.md",
        "openapi-frozen-v1.5.2.json",
        "V1.5-handoff.md",
    ]
    missing = [r for r in refs if r not in txt]
    if missing:
        print(f"    [FAIL] handoff 引用缺:{missing}")
        return False
    print("    [PASS] handoff 引用 5 文档齐全")
    return True


def t22_m8t1_m10_scripts_7() -> bool:
    """t22: m8t1 M10_SCRIPTS 7 项齐全。"""
    txt = _read(M8T1_PY)
    m10_scripts = [
        "m10t1_test_edgar_real.py",
        "m10t2_test_etf_real.py",
        "m10t3_test_analytics_real.py",
        "m10t4_test_admin_role_audit.py",
        "m10t5_test_reviewer_cli_replace.py",
        "m10t6_test_scipy_replace.py",
        "m10t7_test_p2_merge.py",
    ]
    missing = [s for s in m10_scripts if s not in txt]
    if missing:
        print(f"    [FAIL] M10_SCRIPTS 缺:{missing}")
        return False
    print("    [PASS] M10_SCRIPTS 7 项齐全")
    return True


def t23_m10_test_scripts_7() -> bool:
    """t23: 7 个 m10*_test_*.py 静态自测脚本存在。"""
    scripts = [M10T1_PY, M10T2_PY, M10T3_PY, M10T4_PY, M10T5_PY, M10T6_PY, M10T7_PY]
    missing = [s.name for s in scripts if not s.exists()]
    if missing:
        print(f"    [FAIL] m10 测试脚本缺:{missing}")
        return False
    print("    [PASS] 7 个 m10 静态自测脚本齐全")
    return True


def t24_aggregate_total() -> bool:
    """t24: 静态自测聚合 46 脚本 / 933+ 测点。"""
    data = json.loads(_read(OPENAPI_JSON))
    agg = data.get("static_test_aggregate", {})
    if agg.get("total_scripts") != 46:
        print(f"    [FAIL] total_scripts={agg.get('total_scripts')} != 46")
        return False
    if agg.get("total_testpoints") < 933:
        print(f"    [FAIL] total_testpoints={agg.get('total_testpoints')} < 933")
        return False
    if agg.get("M10_scripts") != 7:
        print(f"    [FAIL] M10_scripts={agg.get('M10_scripts')} != 7")
        return False
    if agg.get("M10_testpoints") != 175:
        print(f"    [FAIL] M10_testpoints={agg.get('M10_testpoints')} != 175")
        return False
    print("    [PASS] 46 脚本 / 933+ 测点聚合")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_handoff_exists_title,
        t02_handoff_8_todos,
        t03_handoff_4_sections,
        t04_handoff_8_todo_marker,
        t05_handoff_7_unpassed,
        t06_openapi_md_exists,
        t07_openapi_md_5_sections,
        t08_openapi_md_3_endpoints,
        t09_openapi_md_fetch_source_8,
        t10_openapi_md_freeze_validation,
        t11_openapi_json_exists,
        t12_openapi_json_metadata,
        t13_openapi_json_endpoints_total,
        t14_openapi_json_modified_modules,
        t15_openapi_json_admin_documented,
        t16_openapi_json_unpassed_7,
        t17_openapi_json_fetch_source_8,
        t18_openapi_json_risks_resolved,
        t19_admin_audit_doc,
        t20_reviewer_migration_doc,
        t21_handoff_references_5,
        t22_m8t1_m10_scripts_7,
        t23_m10_test_scripts_7,
        t24_aggregate_total,
        t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_handoff_exists_title", t01_handoff_exists_title),
    ("t02_handoff_8_todos", t02_handoff_8_todos),
    ("t03_handoff_4_sections", t03_handoff_4_sections),
    ("t04_handoff_8_todo_marker", t04_handoff_8_todo_marker),
    ("t05_handoff_7_unpassed", t05_handoff_7_unpassed),
    ("t06_openapi_md_exists", t06_openapi_md_exists),
    ("t07_openapi_md_5_sections", t07_openapi_md_5_sections),
    ("t08_openapi_md_3_endpoints", t08_openapi_md_3_endpoints),
    ("t09_openapi_md_fetch_source_8", t09_openapi_md_fetch_source_8),
    ("t10_openapi_md_freeze_validation", t10_openapi_md_freeze_validation),
    ("t11_openapi_json_exists", t11_openapi_json_exists),
    ("t12_openapi_json_metadata", t12_openapi_json_metadata),
    ("t13_openapi_json_endpoints_total", t13_openapi_json_endpoints_total),
    ("t14_openapi_json_modified_modules", t14_openapi_json_modified_modules),
    ("t15_openapi_json_admin_documented", t15_openapi_json_admin_documented),
    ("t16_openapi_json_unpassed_7", t16_openapi_json_unpassed_7),
    ("t17_openapi_json_fetch_source_8", t17_openapi_json_fetch_source_8),
    ("t18_openapi_json_risks_resolved", t18_openapi_json_risks_resolved),
    ("t19_admin_audit_doc", t19_admin_audit_doc),
    ("t20_reviewer_migration_doc", t20_reviewer_migration_doc),
    ("t21_handoff_references_5", t21_handoff_references_5),
    ("t22_m8t1_m10_scripts_7", t22_m8t1_m10_scripts_7),
    ("t23_m10_test_scripts_7", t23_m10_test_scripts_7),
    ("t24_aggregate_total", t24_aggregate_total),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M10-t8 V1.5.2 final handoff + OpenAPI freeze 自测(25 测点)")
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
        print("[m10t8] V1.5.2 final handoff + OpenAPI freeze 25/25 ALL PASSED")
        return 0
    print(f"[m10t8] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
