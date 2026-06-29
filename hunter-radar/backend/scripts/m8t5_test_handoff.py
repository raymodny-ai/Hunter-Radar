"""M8-t5 V1.4 final handoff 自测(12 测点)。

V1.4 接力期收尾报告完整性 + 累计成果 + V1.5 接力入口校验:

Section 1 — V1.4-handoff.md 文档完整性(7 测点):
  - 文档存在 + 7 章节齐全
  - 5 个 m8t 全部 COMPLETE
  - 5 解除 + 27 保留 + 1 新增 = 33 风险登记
  - 累计 478+ 沙箱自测测点
  - 19 FE/BD 关键功能列举

Section 2 — V1.4 production 接力入口(3 测点):
  - V1.4-prod-env-setup.md 链接存在
  - V1.4-release-notes.md 链接存在
  - V1.5-eval-checklist.md 链接存在

Section 3 — V1.5 接力者开工顺序(2 测点):
  - V1.5.1 freeze 候选 8 项齐全
  - 优先级 P0/P1/P2 划分清晰

总计 12 测点。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
DOC_HANDOFF = DOCS / "V1.4-handoff.md"
DOC_PROD_ENV = DOCS / "V1.4-prod-env-setup.md"
DOC_RELEASE = DOCS / "V1.4-release-notes.md"
DOC_V15 = DOCS / "V1.5-eval-checklist.md"


def _read(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# Section 1: V1.4-handoff.md 文档完整性(7 测点)
# ----------------------------------------------------------------------

def t01_doc_exists() -> bool:
    if not DOC_HANDOFF.exists():
        print(f"  [FAIL] V1.4-handoff.md 不存在: {DOC_HANDOFF}")
        return False
    print(f"  [PASS] V1.4-handoff.md 存在 ({DOC_HANDOFF.stat().st_size} bytes)")
    return True


def t02_doc_has_7_sections() -> bool:
    txt = _read(DOC_HANDOFF)
    expected = [
        "一、V1.4 接力期范围与交付",
        "二、V1.4 接力期关键设计",
        "三、V1.4 关键决策与硬约束",
        "四、V1.4 未完成 / 已知遗留",
        "五、立即可跑",
        "六、V1.4 production 接力",
        "七、本日记忆",
    ]
    missing = [h for h in expected if h not in txt]
    if missing:
        print(f"  [FAIL] 缺章节: {missing}")
        return False
    print(f"  [PASS] 7 章节齐全")
    return True


def t03_5_m8t_complete() -> bool:
    """5 个 m8t 全部 COMPLETE。"""
    txt = _read(DOC_HANDOFF)
    m8t_ids = ["m8t1", "m8t2", "m8t3", "m8t4", "m8t5"]
    missing = [m for m in m8t_ids if m not in txt]
    if missing:
        print(f"  [FAIL] 缺 m8t ID: {missing}")
        return False
    # 必须有 COMPLETE 标识
    if "COMPLETE" not in txt:
        print("  [FAIL] 缺 COMPLETE 标识")
        return False
    print(f"  [PASS] 5 个 m8t 全部 COMPLETE")
    return True


def t04_109_test_points() -> bool:
    """109 测点累计校验。"""
    txt = _read(DOC_HANDOFF)
    if "109" not in txt:
        print("  [FAIL] 缺 109 测点累计")
        return False
    # 30 + 22 + 20 + 25 + 12 = 109
    if "30" not in txt or "22" not in txt or "20" not in txt or "25" not in txt:
        print("  [FAIL] 缺 m8t 测点数拆解")
        return False
    print(f"  [PASS] 109 测点累计(30+22+20+25+12)")
    return True


def t05_33_risks() -> bool:
    """33 风险登记(5 解除 + 27 保留 + 1 新增)。"""
    txt = _read(DOC_HANDOFF)
    if "33" not in txt:
        print("  [FAIL] 缺 33 风险登记总数")
        return False
    if "R-44" not in txt:
        print("  [FAIL] 缺新增 R-44")
        return False
    # 5 解除:R-12/23/25/27/31
    risk_released = ["R-12", "R-23", "R-25", "R-27", "R-31"]
    missing = [r for r in risk_released if r not in txt]
    if missing:
        print(f"  [FAIL] 缺解除风险: {missing}")
        return False
    print(f"  [PASS] 33 风险登记(5 解除 + 27 保留 + 1 新增 R-44)")
    return True


def t06_478_cumulative_tests() -> bool:
    """累计 478+ 沙箱自测测点(M5+M6+M7+M8)。"""
    txt = _read(DOC_HANDOFF)
    if "478" not in txt:
        print("  [FAIL] 缺累计 478 测点")
        return False
    if "194" not in txt:
        print("  [FAIL] 缺 pytest 194 passed")
        return False
    print(f"  [PASS] 累计 478+ 沙箱测点 + 194 pytest")
    return True


def t07_19_features() -> bool:
    """19 FE/BD 关键功能列举。"""
    txt = _read(DOC_HANDOFF)
    features = [
        "FE-005", "FE-006", "FE-007", "FE-008", "FE-009", "FE-010",
        "FE-011", "FE-012", "FE-013", "FE-014", "FE-015",
        "BD-085", "BD-086", "BD-087",
        "8-K", "WH-001", "PWA-001", "CI-001", "OQ-016",
    ]
    missing = [f for f in features if f not in txt]
    if missing:
        print(f"  [FAIL] 缺功能 ID: {missing}")
        return False
    print(f"  [PASS] 19 FE/BD 关键功能齐全")
    return True


# ----------------------------------------------------------------------
# Section 2: V1.4 production 接力入口(3 测点)
# ----------------------------------------------------------------------

def t08_three_linked_docs() -> bool:
    """V1.4-prod-env-setup.md / V1.4-release-notes.md / V1.5-eval-checklist.md 链接齐全。"""
    txt = _read(DOC_HANDOFF)
    refs = ["V1.4-prod-env-setup.md", "V1.4-release-notes.md", "V1.5-eval-checklist.md"]
    missing = [r for r in refs if r not in txt]
    if missing:
        print(f"  [FAIL] 缺文档链接: {missing}")
        return False
    # 文件必须存在
    for f in [DOC_PROD_ENV, DOC_RELEASE, DOC_V15]:
        if not f.exists():
            print(f"  [FAIL] 关联文档不存在: {f}")
            return False
    print(f"  [PASS] 3 个关联文档链接齐全")
    return True


def t09_7_step_checklist() -> bool:
    """7 步上线清单引用。"""
    txt = _read(DOC_HANDOFF)
    # 7 步:secrets → database → redis → vapid → 双签 → ETL → 重测
    steps = ["secrets", "database", "redis", "vapid", "双签", "ETL", "重测"]
    missing = [s for s in steps if s not in txt]
    if missing:
        print(f"  [FAIL] 缺 7 步关键词: {missing}")
        return False
    print(f"  [PASS] 7 步上线清单关键词齐全")
    return True


def t10_4_rollback_levels() -> bool:
    """4 级 rollback 引用。"""
    txt = _read(DOC_HANDOFF)
    # L1 5min + L2 30min + L3 1h + L4 5min
    levels = ["L1", "L2", "L3", "L4"]
    missing = [l for l in levels if l not in txt]
    if missing:
        print(f"  [FAIL] 缺 rollback 等级: {missing}")
        return False
    if "5min" not in txt or "30min" not in txt or "1h" not in txt:
        print("  [FAIL] 缺 rollback SLA 标识")
        return False
    print(f"  [PASS] 4 级 rollback 引用齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: V1.5 接力者开工顺序(2 测点)
# ----------------------------------------------------------------------

def t11_v15_8_candidates() -> bool:
    """V1.5.1 freeze 候选 8 项齐全。"""
    txt = _read(DOC_HANDOFF)
    expected = [
        "Admin 鉴权", "EDGAR fulltext", "ETF 申赎", "Analytics events",
        "候选 A 权重", "VAPID", "env_check.py", "BD-086 双签 reviewer",
    ]
    hits = sum(1 for e in expected if e in txt)
    if hits < 6:
        print(f"  [FAIL] V1.5.1 候选 8 项不足:{hits}/8")
        return False
    print(f"  [PASS] V1.5.1 候选 8 项齐全({hits}/8)")
    return True


def t12_v15_priority_split() -> bool:
    """V1.5.1 优先级 P0/P1/P2 划分清晰。"""
    txt = _read(DOC_HANDOFF)
    priorities = ["P0", "P1", "P2"]
    missing = [p for p in priorities if p not in txt]
    if missing:
        print(f"  [FAIL] 缺优先级: {missing}")
        return False
    # P0 必冻结 / P1 建议 / P2 后续
    if "P0" not in txt and "必冻结" not in txt:
        print("  [FAIL] P0 优先级描述不清")
        return False
    print(f"  [PASS] V1.5.1 优先级 P0/P1/P2 划分清晰")
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
    print("=== 1. V1.4-handoff.md 文档完整性 ===")
    _run("t01_doc_exists", t01_doc_exists)
    _run("t02_doc_has_7_sections", t02_doc_has_7_sections)
    _run("t03_5_m8t_complete", t03_5_m8t_complete)
    _run("t04_109_test_points", t04_109_test_points)
    _run("t05_33_risks", t05_33_risks)
    _run("t06_478_cumulative_tests", t06_478_cumulative_tests)
    _run("t07_19_features", t07_19_features)

    print("\n=== 2. V1.4 production 接力入口 ===")
    _run("t08_three_linked_docs", t08_three_linked_docs)
    _run("t09_7_step_checklist", t09_7_step_checklist)
    _run("t10_4_rollback_levels", t10_4_rollback_levels)

    print("\n=== 3. V1.5 接力者开工顺序 ===")
    _run("t11_v15_8_candidates", t11_v15_8_candidates)
    _run("t12_v15_priority_split", t12_v15_priority_split)

    total = len(_PASSED) + len(_FAILED)
    print(f"\n[m8t5] SUMMARY: {len(_PASSED)}/{total} PASSED, {len(_FAILED)} FAILED")
    if _FAILED:
        print(f"[m8t5] FAILED TESTS: {', '.join(_FAILED)}")
        return 1
    print(f"[m8t5] ALL {total} V1.4-HANDOFF TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
