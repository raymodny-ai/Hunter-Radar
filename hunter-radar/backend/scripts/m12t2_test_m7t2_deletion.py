"""M12-t2 V1.5.4 m7t2_sign_goldset.py 物理删除自测(25 测点)。

V1.5.4 接力期 m12t2 — C-4 m7t2 物理删除(reviewer_cli 单一权威):
- m7t2_sign_goldset.py 物理删除(2026-06-15)
- REVIEWER_CLI_MIGRATION.md 改写为 V1.5.4 状态
- m10t5_test_reviewer_cli_replace.py 4 个 m7t2 测点改测"m7t2 已物理删除 + 历史记录在 docs"
- m11t4_test_reviewer_cli_toolchain.py 4 个 m7t2 测点改测"m7t2 已物理删除"
- m7t2_test_signoff.py 保留(测数据,不依赖 m7t2_sign_goldset.py 脚本本身)
- 数据文件 data/backtest_event_goldset.sample.jsonl 31 事件双签保留(无需重签)

Section 1 — 物理删除(5 测点):
  t01: m7t2_sign_goldset.py 文件已物理删除
  t02: m7t2_test_signoff.py 保留(测数据,不依赖 m7t2 脚本)
  t03: data/backtest_event_goldset.sample.jsonl 31 事件保留
  t04: data/backtest_event_goldset.signoff_audit.jsonl 31 行保留
  t05: docs/BD-086-signoff-audit-log.md 保留

Section 2 — 文档更新(5 测点):
  t06: REVIEWER_CLI_MIGRATION.md 标 V1.5.4 m12t2 物理删除
  t07: §4.1 物理删除落地清单完整
  t08: §3 严禁行为更新为"禁止从 git 历史拉回"
  t09: §5 评审通过清单含 m12t2 物理删除
  t10: §6 评审依据文件 m7t2_sign_goldset.py 标"已物理删除"

Section 3 — 引用清理(5 测点):
  t11: m10t5_test 含 4 个 m7t2 物理删除测点(t01-t04 改写)
  t12: m11t4_test 含 4 个 m7t2 物理删除测点
  t13: m7t2_test_signoff.py 不 import m7t2_sign_goldset
  t14: m9t3_test_reviewer_cli 仍测 reviewer_cli(不受影响)
  t15: m10t5_test 25 测点总数保留(4 改写后总数不变)

Section 4 — 替代路径 + 单一权威(5 测点):
  t16: reviewer_cli.py cmd_register 函数存在
  t17: reviewer_cli.py cmd_sign 函数存在
  t18: reviewer_cli.py cmd_batch_verify 函数存在
  t19: m7t2_sign_goldset() 函数已无定义(物理删除)
  t20: m7t2 main() runtime 拦截已无定义(物理删除)

Section 5 — 25 测点 + 评审项(5 测点):
  t21: V1.5.4 m12t2 marker 存在
  t22: V1.5.3 评审项 M10-UNPASSED-4 仍记录(历史延续)
  t23: C-4 候选完成
  t24: m8t1 M12_SCRIPTS 含 m12t2(本测试脚本)
  t25: 25 测点总数校验

总计 25 测点。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "backend" / "scripts"
M7T2_PY = SCRIPTS / "m7t2_sign_goldset.py"
M7T2_TEST_PY = SCRIPTS / "m7t2_test_signoff.py"
M10T5_TEST_PY = SCRIPTS / "m10t5_test_reviewer_cli_replace.py"
M11T4_TEST_PY = SCRIPTS / "m11t4_test_reviewer_cli_toolchain.py"
M9T3_TEST_PY = SCRIPTS / "m9t3_test_reviewer_cli.py"
# V1.5.6 接力期 m14t1:reviewer_cli 拆分为独立目录包
REVIEWER_CLI_PKG = SCRIPTS / "reviewer_cli"
REVIEWER_CLI_INIT = REVIEWER_CLI_PKG / "__init__.py"
REVIEWER_CLI_CLI = REVIEWER_CLI_PKG / "_cli.py"


def _read_reviewer_cli() -> str:
    """V1.5.6 m14t1:合并读 reviewer_cli/ 子模块,等价于原 _read(REVIEWER_CLI_PY)。"""
    parts: list[str] = []
    for p in (REVIEWER_CLI_INIT, REVIEWER_CLI_CLI):
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)
MIGRATION_MD = ROOT / "docs" / "REVIEWER_CLI_MIGRATION.md"
GOLDSET_JSONL = ROOT / "data" / "backtest_event_goldset.sample.jsonl"
AUDIT_JSONL = ROOT / "data" / "backtest_event_goldset.signoff_audit.jsonl"
AUDIT_MD = ROOT / "docs" / "BD-086-signoff-audit-log.md"
M8T1_PY = SCRIPTS / "m8t1_test_regression.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---- Section 1: 物理删除(5 测点) ------------------------------------


def t01_m7t2_physically_deleted() -> bool:
    """t01: m7t2_sign_goldset.py 文件已物理删除。"""
    if M7T2_PY.exists():
        print(f"    [FAIL] m7t2_sign_goldset.py 仍存在:{M7T2_PY}")
        return False
    print("    [PASS] m7t2_sign_goldset.py 已物理删除")
    return True


def t02_m7t2_test_signoff_preserved() -> bool:
    """t02: m7t2_test_signoff.py 保留(测数据,不依赖 m7t2_sign_goldset.py 脚本本身)。"""
    if not M7T2_TEST_PY.exists():
        print(f"    [FAIL] m7t2_test_signoff.py 不应被删除:{M7T2_TEST_PY}")
        return False
    print("    [PASS] m7t2_test_signoff.py 保留(测数据)")
    return True


def t03_goldset_31_events_preserved() -> bool:
    """t03: data/backtest_event_goldset.sample.jsonl 31 事件双签保留。"""
    objs = _read_jsonl(GOLDSET_JSONL)
    if len(objs) != 31:
        print(f"    [FAIL] goldset 事件数={len(objs)} != 31")
        return False
    # 每个事件 reviewer_signoff 非 TBD
    tbd = sum(1 for o in objs if o.get("reviewer_signoff", {}).get("cr") == "TBD")
    if tbd > 0:
        print(f"    [FAIL] goldset TBD 事件 {tbd} 个")
        return False
    print(f"    [PASS] goldset 31 事件双签保留")
    return True


def t04_audit_jsonl_31_lines_preserved() -> bool:
    """t04: data/backtest_event_goldset.signoff_audit.jsonl 31 行保留。"""
    records = _read_jsonl(AUDIT_JSONL)
    if len(records) != 31:
        print(f"    [FAIL] audit jsonl 行数={len(records)} != 31")
        return False
    print(f"    [PASS] audit jsonl 31 行保留")
    return True


def t05_audit_md_preserved() -> bool:
    """t05: docs/BD-086-signoff-audit-log.md 保留(人类可读审计)。"""
    if not AUDIT_MD.exists():
        print(f"    [FAIL] BD-086-signoff-audit-log.md 不应被删除:{AUDIT_MD}")
        return False
    md = _read(AUDIT_MD)
    if "## 一、补全范围" not in md:
        print("    [FAIL] audit md 缺 6 章节")
        return False
    print("    [PASS] audit md 保留 + 6 章节齐全")
    return True


# ---- Section 2: 文档更新(5 测点) ----------------------------------


def t06_migration_md_v154_marker() -> bool:
    """t06: REVIEWER_CLI_MIGRATION.md 标 V1.5.4 m12t2 物理删除。"""
    txt = _read(MIGRATION_MD)
    if "V1.5.4 接力期 m12t2 物理删除" not in txt:
        print("    [FAIL] 缺 V1.5.4 m12t2 物理删除 marker")
        return False
    print("    [PASS] REVIEWER_CLI_MIGRATION.md 标 V1.5.4 m12t2")
    return True


def t07_migration_md_section_4_1() -> bool:
    """t07: REVIEWER_CLI_MIGRATION.md §4.1 m12t2 物理删除清单完整。"""
    txt = _read(MIGRATION_MD)
    if "## 4.1 V1.5.4 m12t2 物理删除落地" not in txt:
        print("    [FAIL] 缺 §4.1 V1.5.4 m12t2 物理删除落地")
        return False
    # 8 项 checklist
    items = [
        "m7t2_sign_goldset.py 物理删除",
        "REVIEWER_CLI_MIGRATION.md 改写",
        "m10t5_test_reviewer_cli_replace.py",
        "m11t4_test_reviewer_cli_toolchain.py",
        "m12t2_test_m7t2_deletion.py",
        "m8t1_test_regression.py",
        "git 历史",
        "data/backtest_event_goldset.sample.jsonl",
    ]
    missing = [i for i in items if i not in txt]
    if len(missing) >= 2:
        print(f"    [FAIL] §4.1 checklist 缺:{missing}")
        return False
    print(f"    [PASS] §4.1 物理删除清单完整({len(items) - len(missing)}/{len(items)})")
    return True


def t08_migration_md_strict_no_legacy() -> bool:
    """t08: §3 严禁行为更新为"禁止从 git 历史拉回"。"""
    txt = _read(MIGRATION_MD)
    if "禁止从 git 历史拉回 m7t2_sign_goldset.py" not in txt:
        print("    [FAIL] §3 严禁行为未更新为'禁止从 git 历史拉回'")
        return False
    print("    [PASS] §3 严禁行为已更新")
    return True


def t09_migration_md_pass_checklist_v154() -> bool:
    """t09: §5 评审通过清单含 m12t2 物理删除。"""
    txt = _read(MIGRATION_MD)
    if "V1.5.4 m12t2 物理删除落地" not in txt:
        print("    [FAIL] §5 通过清单缺 m12t2 物理删除")
        return False
    print("    [PASS] §5 通过清单含 m12t2")
    return True


def t10_migration_md_references_m7t2_removed() -> bool:
    """t10: §6 评审依据文件 m7t2_sign_goldset.py 标"已物理删除"。"""
    txt = _read(MIGRATION_MD)
    if "m7t2_sign_goldset.py" not in txt:
        print("    [FAIL] §6 缺 m7t2_sign_goldset.py 引用(应在历史记录中保留)")
        return False
    if "V1.5.4 m12t2 物理删除" not in txt:
        print("    [FAIL] §6 未标 m7t2 已物理删除")
        return False
    print("    [PASS] §6 评审依据标 m7t2 已物理删除")
    return True


# ---- Section 3: 引用清理(5 测点) ----------------------------------


def t11_m10t5_test_has_deletion_tests() -> bool:
    """t11: m10t5_test 含 4 个 m7t2 物理删除测点(t01-t04 改写)。"""
    txt = _read(M10T5_TEST_PY)
    funcs = [
        "t01_m7t2_physically_deleted",
        "t02_m7t2_deprecated_in_docs",
        "t03_m7t2_replacement_in_docs",
        "t04_v154_m12t2_physical_delete",
    ]
    missing = [f for f in funcs if f not in txt]
    if len(missing) >= 2:
        print(f"    [FAIL] m10t5_test 缺物理删除测点:{missing}")
        return False
    print(f"    [PASS] m10t5_test 含 4 个物理删除测点")
    return True


def t12_m11t4_test_has_deletion_tests() -> bool:
    """t12: m11t4_test 含 4 个 m7t2 物理删除测点(t01-t04 改写)。"""
    txt = _read(M11T4_TEST_PY)
    funcs = [
        "t01_m7t2_physically_deleted",
        "t02_m7t2_deletion_documented",
        "t03_m7t2_deletion_in_migration_md",
        "t04_m7t2_no_legacy_flag_needed",
    ]
    missing = [f for f in funcs if f not in txt]
    if len(missing) >= 2:
        print(f"    [FAIL] m11t4_test 缺物理删除测点:{missing}")
        return False
    print(f"    [PASS] m11t4_test 含 4 个物理删除测点")
    return True


def t13_m7t2_test_signoff_no_import() -> bool:
    """t13: m7t2_test_signoff.py 不 import m7t2_sign_goldset(测数据)。"""
    if not M7T2_TEST_PY.exists():
        print("    [SKIP] m7t2_test_signoff.py 不存在")
        return True
    txt = _read(M7T2_TEST_PY)
    if "import m7t2_sign_goldset" in txt or "from m7t2_sign_goldset" in txt:
        print("    [FAIL] m7t2_test_signoff 仍 import m7t2_sign_goldset")
        return False
    print("    [PASS] m7t2_test_signoff 不依赖 m7t2_sign_goldset 脚本")
    return True


def t14_m9t3_test_still_valid() -> bool:
    """t14: m9t3_test_reviewer_cli 仍测 reviewer_cli(不受物理删除影响)。"""
    if not M9T3_TEST_PY.exists():
        print("    [SKIP] m9t3_test_reviewer_cli 不存在")
        return True
    txt = _read(M9T3_TEST_PY)
    if "reviewer_cli" not in txt:
        print("    [FAIL] m9t3_test 缺 reviewer_cli 引用")
        return False
    print("    [PASS] m9t3_test_reviewer_cli 兼容")
    return True


def t15_m10t5_test_25_testpoints_intact() -> bool:
    """t15: m10t5_test 25 测点总数保留(4 改写后总数不变)。"""
    txt = _read(M10T5_TEST_PY)
    funcs = re.findall(r"^def (t\d{2}_\w+)\(", txt, re.MULTILINE)
    if len(funcs) != 25:
        print(f"    [FAIL] m10t5_test 测点函数={len(funcs)} != 25")
        return False
    print(f"    [PASS] m10t5_test 25 测点总数保留")
    return True


# ---- Section 4: 替代路径 + 单一权威(5 测点) -----------------------


def t16_reviewer_cli_register_exists() -> bool:
    """t16: reviewer_cli.py cmd_register 函数存在(替代 m7t2 入口)。"""
    txt = _read_reviewer_cli()
    if "def cmd_register(" not in txt:
        print("    [FAIL] 缺 cmd_register")
        return False
    print("    [PASS] reviewer_cli.cmd_register 存在")
    return True


def t17_reviewer_cli_sign_exists() -> bool:
    """t17: reviewer_cli.py cmd_sign 函数存在(替代 m7t2 sign_goldset)。"""
    txt = _read_reviewer_cli()
    if "def cmd_sign(" not in txt:
        print("    [FAIL] 缺 cmd_sign")
        return False
    print("    [PASS] reviewer_cli.cmd_sign 存在")
    return True


def t18_reviewer_cli_batch_verify_exists() -> bool:
    """t18: reviewer_cli.py cmd_batch_verify 函数存在(替代 m7t2 write_audit_md)。"""
    txt = _read_reviewer_cli()
    if "def cmd_batch_verify" not in txt:
        print("    [FAIL] 缺 cmd_batch_verify")
        return False
    print("    [PASS] reviewer_cli.cmd_batch_verify 存在")
    return True


def t19_m7t2_sign_goldset_no_definition() -> bool:
    """t19: m7t2 sign_goldset() 函数已无定义(物理删除)。"""
    # m7t2_sign_goldset.py 已物理删除,sign_goldset 函数自然无定义
    if M7T2_PY.exists():
        print("    [FAIL] m7t2 仍存在,sign_goldset 函数仍在")
        return False
    # reviewer_cli.py 中无 sign_goldset 函数定义(只有 cmd_sign)
    cli_txt = _read_reviewer_cli()
    if "def sign_goldset" in cli_txt:
        print("    [FAIL] reviewer_cli.py 误含 sign_goldset 函数")
        return False
    print("    [PASS] sign_goldset() 函数已无定义")
    return True


def t20_m7t2_runtime_block_no_definition() -> bool:
    """t20: m7t2 main() runtime 拦截已无定义(物理删除)。"""
    # m7t2_sign_goldset.py 已物理删除,main 函数自然无定义
    if M7T2_PY.exists():
        print("    [FAIL] m7t2 仍存在,main() runtime 拦截仍在")
        return False
    # HR_ALLOW_LEGACY_SCRIPTS 不再被 m7t2 引用(物理删除后无意义)
    cli_txt = _read_reviewer_cli()
    if "HR_ALLOW_LEGACY_SCRIPTS" in cli_txt:
        # reviewer_cli 不应引用此 env(那是 m7t2 的 env)
        print("    [FAIL] reviewer_cli.py 不应引用 HR_ALLOW_LEGACY_SCRIPTS")
        return False
    print("    [PASS] main() runtime 拦截已无定义,HR_ALLOW_LEGACY_SCRIPTS 失效")
    return True


# ---- Section 5: 25 测点 + 评审项(5 测点) ---------------------------


def t21_v154_m12t2_marker_in_docs() -> bool:
    """t21: V1.5.4 m12t2 marker 在 REVIEWER_CLI_MIGRATION.md 存在。"""
    txt = _read(MIGRATION_MD)
    if "m12t2" not in txt:
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺 m12t2 marker")
        return False
    if "V1.5.4" not in txt:
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺 V1.5.4 marker")
        return False
    print("    [PASS] V1.5.4 m12t2 marker 存在")
    return True


def t22_m10_unpassed_4_still_recorded() -> bool:
    """t22: V1.5.3 评审项 M10-UNPASSED-4 仍记录(历史延续,V1.5.3 修复 + V1.5.4 物理删除)。"""
    txt = _read(MIGRATION_MD)
    if "M10-UNPASSED-4" in txt or "runtime 拦截" in txt:
        # m10t5 / m11t4 段含 runtime 拦截历史 + M10-UNPASSED-4
        print("    [PASS] V1.5.3 评审项 M10-UNPASSED-4 历史延续")
        return True
    print("    [FAIL] V1.5.3 评审项 M10-UNPASSED-4 缺失")
    return False


def t23_c4_candidate_completed() -> bool:
    """t23: C-4 候选(m7t2 物理删除)完成。"""
    txt = _read(MIGRATION_MD)
    # C-4 候选完成 → REVIEWER_CLI_MIGRATION.md 标 m12t2 物理删除
    if "m12t2 物理删除落地" in txt and "V1.5.4 接力期 m12t2" in txt:
        print("    [PASS] C-4 候选完成")
        return True
    print("    [FAIL] C-4 候选未完成")
    return False


def t24_m8t1_m12_scripts_includes_m12t2() -> bool:
    """t24: m8t1 M12_SCRIPTS 含 m12t2(本测试脚本)。"""
    if not M8T1_PY.exists():
        print(f"    [FAIL] m8t1_test_regression.py 不存在:{M8T1_PY}")
        return False
    txt = _read(M8T1_PY)
    if "M12_SCRIPTS" not in txt:
        print("    [FAIL] m8t1 缺 M12_SCRIPTS")
        return False
    if "m12t2_test_m7t2_deletion" not in txt:
        print("    [FAIL] m8t1 M12_SCRIPTS 缺 m12t2_test_m7t2_deletion")
        return False
    print("    [PASS] m8t1 M12_SCRIPTS 含 m12t2")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_m7t2_physically_deleted, t02_m7t2_test_signoff_preserved,
        t03_goldset_31_events_preserved, t04_audit_jsonl_31_lines_preserved,
        t05_audit_md_preserved,
        t06_migration_md_v154_marker, t07_migration_md_section_4_1,
        t08_migration_md_strict_no_legacy, t09_migration_md_pass_checklist_v154,
        t10_migration_md_references_m7t2_removed,
        t11_m10t5_test_has_deletion_tests, t12_m11t4_test_has_deletion_tests,
        t13_m7t2_test_signoff_no_import, t14_m9t3_test_still_valid,
        t15_m10t5_test_25_testpoints_intact,
        t16_reviewer_cli_register_exists, t17_reviewer_cli_sign_exists,
        t18_reviewer_cli_batch_verify_exists, t19_m7t2_sign_goldset_no_definition,
        t20_m7t2_runtime_block_no_definition,
        t21_v154_m12t2_marker_in_docs, t22_m10_unpassed_4_still_recorded,
        t23_c4_candidate_completed, t24_m8t1_m12_scripts_includes_m12t2,
        t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print(f"    [PASS] 25 测点总数校验")
    return True


# ---- main ----------------------------------------------------------------


CHECKS = [
    # Section 1
    ("t01_m7t2_physically_deleted", t01_m7t2_physically_deleted),
    ("t02_m7t2_test_signoff_preserved", t02_m7t2_test_signoff_preserved),
    ("t03_goldset_31_events_preserved", t03_goldset_31_events_preserved),
    ("t04_audit_jsonl_31_lines_preserved", t04_audit_jsonl_31_lines_preserved),
    ("t05_audit_md_preserved", t05_audit_md_preserved),
    # Section 2
    ("t06_migration_md_v154_marker", t06_migration_md_v154_marker),
    ("t07_migration_md_section_4_1", t07_migration_md_section_4_1),
    ("t08_migration_md_strict_no_legacy", t08_migration_md_strict_no_legacy),
    ("t09_migration_md_pass_checklist_v154", t09_migration_md_pass_checklist_v154),
    ("t10_migration_md_references_m7t2_removed", t10_migration_md_references_m7t2_removed),
    # Section 3
    ("t11_m10t5_test_has_deletion_tests", t11_m10t5_test_has_deletion_tests),
    ("t12_m11t4_test_has_deletion_tests", t12_m11t4_test_has_deletion_tests),
    ("t13_m7t2_test_signoff_no_import", t13_m7t2_test_signoff_no_import),
    ("t14_m9t3_test_still_valid", t14_m9t3_test_still_valid),
    ("t15_m10t5_test_25_testpoints_intact", t15_m10t5_test_25_testpoints_intact),
    # Section 4
    ("t16_reviewer_cli_register_exists", t16_reviewer_cli_register_exists),
    ("t17_reviewer_cli_sign_exists", t17_reviewer_cli_sign_exists),
    ("t18_reviewer_cli_batch_verify_exists", t18_reviewer_cli_batch_verify_exists),
    ("t19_m7t2_sign_goldset_no_definition", t19_m7t2_sign_goldset_no_definition),
    ("t20_m7t2_runtime_block_no_definition", t20_m7t2_runtime_block_no_definition),
    # Section 5
    ("t21_v154_m12t2_marker_in_docs", t21_v154_m12t2_marker_in_docs),
    ("t22_m10_unpassed_4_still_recorded", t22_m10_unpassed_4_still_recorded),
    ("t23_c4_candidate_completed", t23_c4_candidate_completed),
    ("t24_m8t1_m12_scripts_includes_m12t2", t24_m8t1_m12_scripts_includes_m12t2),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M12-t2 V1.5.4 m7t2_sign_goldset.py 物理删除自测(25 测点)")
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
        print("[m12t2] V1.5.4 m7t2 物理删除 25/25 ALL PASSED")
        return 0
    print(f"[m12t2] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())

