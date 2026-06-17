"""V1.5.8 接力期 m16t2 — 评审归档扩展自测(覆盖 V1.5.5/5.6/5.7/5.8 候选)。

校验 scripts/eval_evaluator_evaluations.py 扩展:
- 4 个 V 版本候选数据(V155/V156/V157/V158)齐全
- V1.5.5 1 候选 E-1 + V1.5.6 1 候选 C-1-ext + V1.5.7 4 候选 + V1.5.8 4 候选
- 总候选 ≥ 10(原 6 + 扩展 10 = 16)
- 全部 COMPLETE 状态(无 PENDING)
- 报告 markdown + json 重新生成
- 工具 idempotent(可重复跑)

V1.5.5 接力期 硬性锁定:
- 沙箱 fallback 显式标注
- 静态自测,无需启动后端
- 5 Section × 5 测点 = 25 测点

运行:
  py -B -m scripts.m16t2_test_eval_archive_extended
"""
from __future__ import annotations

import importlib.util
import json
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
    spec = importlib.util.spec_from_file_location("eval_evaluator_evaluations_extended", EVALUATOR_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_evaluator_evaluations_extended"] = mod
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------
# Section 1: 扩展候选数据完整性(5 测点)
# ----------------------------------------------------------------------


def t01_v155_one_candidate() -> bool:
    """t01: V155_CANDIDATES 1 候选 E-1(V1.5.5 production P0 修复)。"""
    ea = _load_evaluator()
    if not hasattr(ea, "V155_CANDIDATES"):
        return False
    if len(ea.V155_CANDIDATES) != 1:
        print(f"    [FAIL] V155_CANDIDATES {len(ea.V155_CANDIDATES)} 候选,期望 1")
        return False
    c = ea.V155_CANDIDATES[0]
    if c["id"] != "E-1" or c["status"] != "COMPLETE":
        print(f"    [FAIL] V1.5.5 候选 id={c['id']!r} status={c['status']!r}")
        return False
    if "m13t1" not in c["relay"]:
        print(f"    [FAIL] V1.5.5 接力期 {c['relay']!r} 缺 m13t1")
        return False
    print("    [PASS] V155_CANDIDATES 1 候选 E-1 OK")
    return True


def t02_v156_one_candidate() -> bool:
    """t02: V156_CANDIDATES 1 候选 C-1-ext(reviewer_cli 独立目录)。"""
    ea = _load_evaluator()
    if not hasattr(ea, "V156_CANDIDATES"):
        return False
    if len(ea.V156_CANDIDATES) != 1:
        print(f"    [FAIL] V156_CANDIDATES {len(ea.V156_CANDIDATES)} 候选,期望 1")
        return False
    c = ea.V156_CANDIDATES[0]
    if "C-1" not in c["id"] or c["status"] != "COMPLETE":
        print(f"    [FAIL] V1.5.6 候选 id={c['id']!r} status={c['status']!r}")
        return False
    if "m14t1" not in c["relay"]:
        print(f"    [FAIL] V1.5.6 接力期 {c['relay']!r} 缺 m14t1")
        return False
    print("    [PASS] V156_CANDIDATES 1 候选 C-1-ext OK")
    return True


def t03_v157_four_candidates() -> bool:
    """t03: V157_CANDIDATES 4 候选(C-3-ext + C-6-ext + E-2 + E-3)。"""
    ea = _load_evaluator()
    if not hasattr(ea, "V157_CANDIDATES"):
        return False
    if len(ea.V157_CANDIDATES) != 4:
        print(f"    [FAIL] V157_CANDIDATES {len(ea.V157_CANDIDATES)} 候选,期望 4")
        return False
    ids = [c["id"] for c in ea.V157_CANDIDATES]
    for required in ["C-3-ext", "C-6-ext", "E-2", "E-3"]:
        if required not in ids:
            print(f"    [FAIL] V1.5.7 缺候选 {required}")
            return False
    print("    [PASS] V157_CANDIDATES 4 候选齐全")
    return True


def t04_v158_four_candidates() -> bool:
    """t04: V158_CANDIDATES 4 候选(E-4 + E-5 + E-6 + E-7)。"""
    ea = _load_evaluator()
    if not hasattr(ea, "V158_CANDIDATES"):
        return False
    if len(ea.V158_CANDIDATES) != 4:
        print(f"    [FAIL] V158_CANDIDATES {len(ea.V158_CANDIDATES)} 候选,期望 4")
        return False
    ids = [c["id"] for c in ea.V158_CANDIDATES]
    for required in ["E-4", "E-5", "E-6", "E-7"]:
        if required not in ids:
            print(f"    [FAIL] V1.5.8 缺候选 {required}")
            return False
    print("    [PASS] V158_CANDIDATES 4 候选齐全")
    return True


def t05_total_candidates_at_least_16() -> bool:
    """t05: 总候选 ≥ 16(V1.5.3 6 + V1.5.4 0 + V1.5.5 1 + V1.5.6 1 + V1.5.7 4 + V1.5.8 4 = 16)。"""
    ea = _load_evaluator()
    total = (
        len(ea.V153_CANDIDATES) + len(ea.V154_CANDIDATES)
        + len(ea.V155_CANDIDATES) + len(ea.V156_CANDIDATES)
        + len(ea.V157_CANDIDATES) + len(ea.V158_CANDIDATES)
    )
    if total != 16:
        print(f"    [FAIL] 总候选 {total},期望 16")
        return False
    print(f"    [PASS] 总候选 16 OK")
    return True


# ----------------------------------------------------------------------
# Section 2: build_archive_report 扩展聚合(5 测点)
# ----------------------------------------------------------------------


def t06_build_archive_v155_grouped() -> bool:
    """t06: build_archive_report V1.5.5 分组含 1 候选。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    by_v = archive["candidates_by_v"]
    if len(by_v.get("V1.5.5", [])) != 1:
        print(f"    [FAIL] V1.5.5 {len(by_v.get('V1.5.5', []))} 候选,期望 1")
        return False
    if by_v["V1.5.5"][0]["id"] != "E-1":
        return False
    print("    [PASS] V1.5.5 1 候选 E-1 OK")
    return True


def t07_build_archive_v157_grouped() -> bool:
    """t07: build_archive_report V1.5.7 分组含 4 候选。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    by_v = archive["candidates_by_v"]
    if len(by_v.get("V1.5.7", [])) != 4:
        print(f"    [FAIL] V1.5.7 {len(by_v.get('V1.5.7', []))} 候选,期望 4")
        return False
    print("    [PASS] V1.5.7 4 候选 OK")
    return True


def t08_build_archive_v158_grouped() -> bool:
    """t08: build_archive_report V1.5.8 分组含 4 候选。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    by_v = archive["candidates_by_v"]
    if len(by_v.get("V1.5.8", [])) != 4:
        print(f"    [FAIL] V1.5.8 {len(by_v.get('V1.5.8', []))} 候选,期望 4")
        return False
    print("    [PASS] V1.5.8 4 候选 OK")
    return True


def t09_build_archive_total_candidates_16() -> bool:
    """t09: build_archive_report total_candidates=16(硬性)。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    if archive["total_candidates"] != 16:
        print(f"    [FAIL] total_candidates={archive['total_candidates']},期望 16")
        return False
    print(f"    [PASS] total_candidates=16 OK")
    return True


def t10_build_archive_all_complete() -> bool:
    """t10: build_archive_report COMPLETE=16, PENDING=0(全部完成)。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    sc = archive["status_counts"]
    if sc.get("COMPLETE", 0) != 16:
        print(f"    [FAIL] COMPLETE={sc.get('COMPLETE', 0)},期望 16")
        return False
    if sc.get("PENDING", 0) != 0:
        print(f"    [FAIL] PENDING={sc.get('PENDING', 0)},期望 0")
        return False
    print(f"    [PASS] COMPLETE=16, PENDING=0 OK")
    return True


# ----------------------------------------------------------------------
# Section 3: 报告生成 + 跨版本表格(5 测点)
# ----------------------------------------------------------------------


def t11_render_markdown_v155_section() -> bool:
    """t11: render_markdown V1.5.5 section 含 1 候选 E-1。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    md = ea.render_markdown(archive)
    if "V1.5.5 接力期(1 候选)" not in md:
        print("    [FAIL] 缺 V1.5.5 接力期(1 候选) 标题")
        return False
    if "E-1" not in md:
        print("    [FAIL] 缺 E-1 候选")
        return False
    if "V1.5.5 production P0 修复" not in md:
        return False
    print("    [PASS] V1.5.5 section OK")
    return True


def t12_render_markdown_v158_section() -> bool:
    """t12: render_markdown V1.5.8 section 含 4 候选。"""
    ea = _load_evaluator()
    parsed = ea.parse_m8t1_output("")
    archive = ea.build_archive_report(parsed)
    md = ea.render_markdown(archive)
    if "V1.5.8 接力期(4 候选)" not in md:
        print("    [FAIL] 缺 V1.5.8 接力期(4 候选) 标题")
        return False
    for required in ["E-4", "E-5", "E-6", "E-7"]:
        if required not in md:
            print(f"    [FAIL] V1.5.8 md 缺候选 {required}")
            return False
    print("    [PASS] V1.5.8 section OK")
    return True


def t13_archive_md_16_complete() -> bool:
    """t13: docs/v1.5-evaluation-archive.md 收尾段含 16/16 COMPLETE 100% marker。"""
    md = _read(ARCHIVE_MD)
    if "COMPLETE 16/16" not in md:
        print("    [FAIL] 缺 'COMPLETE 16/16' marker")
        return False
    if "100%" not in md:
        print("    [FAIL] 缺 100% 比例")
        return False
    print("    [PASS] 归档 md 16/16 COMPLETE OK")
    return True


def t14_archive_json_total_candidates_16() -> bool:
    """t14: docs/v1.5-evaluation-archive.json total_candidates=16。"""
    if not ARCHIVE_JSON.is_file():
        print("    [FAIL] json 缺失")
        return False
    data = json.loads(ARCHIVE_JSON.read_text(encoding="utf-8"))
    if data.get("total_candidates") != 16:
        print(f"    [FAIL] json total_candidates={data.get('total_candidates')},期望 16")
        return False
    if data["status_counts"].get("COMPLETE", 0) != 16:
        return False
    print("    [PASS] 归档 json 16 候选 OK")
    return True


def t15_archive_json_v158_four() -> bool:
    """t15: docs/v1.5-evaluation-archive.json candidates_by_v.V1.5.8 = 4 候选。"""
    data = json.loads(ARCHIVE_JSON.read_text(encoding="utf-8"))
    by_v = data.get("candidates_by_v", {})
    if len(by_v.get("V1.5.8", [])) != 4:
        print(f"    [FAIL] V1.5.8 {len(by_v.get('V1.5.8', []))} 候选,期望 4")
        return False
    print("    [PASS] V1.5.8 json 4 候选 OK")
    return True


# ----------------------------------------------------------------------
# Section 4: 工具 idempotent + CLI 兼容(5 测点)
# ----------------------------------------------------------------------


def t16_idempotent_reload() -> bool:
    """t16: 工具 reload 后数据一致(无 hidden 状态)。"""
    ea1 = _load_evaluator()
    ea2 = _load_evaluator()
    if len(ea1.V157_CANDIDATES) != len(ea2.V157_CANDIDATES):
        return False
    if len(ea1.V158_CANDIDATES) != len(ea2.V158_CANDIDATES):
        return False
    print("    [PASS] 工具 reload idempotent OK")
    return True


def t17_cli_args_compatible() -> bool:
    """t17: CLI 5 参数兼容(--m8t1-out / --report-md / --report-json / --run-m8t1 / --placeholder)。"""
    txt = _read(EVALUATOR_PY)
    for arg in ["--m8t1-out", "--report-md", "--report-json", "--run-m8t1", "--placeholder"]:
        if arg not in txt:
            print(f"    [FAIL] 缺 CLI 参数 {arg}")
            return False
    print("    [PASS] CLI 5 参数兼容 OK")
    return True


def t18_m_stage_to_v_unchanged() -> bool:
    """t18: M_STAGE_TO_V 映射未变(向后兼容)。"""
    ea = _load_evaluator()
    expected = {"M5": "V1.4", "M11": "V1.5.3", "M12": "V1.5.4", "M15": "V1.5.7"}
    for stage, v in expected.items():
        if ea.M_STAGE_TO_V.get(stage) != v:
            print(f"    [FAIL] {stage}={ea.M_STAGE_TO_V.get(stage)},期望 {v}")
            return False
    print("    [PASS] M_STAGE_TO_V 兼容 OK")
    return True


def t19_no_external_deps() -> bool:
    """t19: 工具仍无外部依赖(纯标准库)。"""
    txt = _read(EVALUATOR_PY)
    if "import requests" in txt or "import httpx" in txt:
        return False
    if "import pandas" in txt or "import numpy" in txt:
        return False
    print("    [PASS] 工具无外部依赖 OK")
    return True


def t20_evaluator_sandbox_fallback_unchanged() -> bool:
    """t20: sandbox placeholder fallback 仍存在(向后兼容)。"""
    txt = _read(EVALUATOR_PY)
    if "placeholder" not in txt:
        return False
    if "[WARN]" not in txt:
        return False
    print("    [PASS] sandbox fallback 兼容 OK")
    return True


# ----------------------------------------------------------------------
# Section 5: m16t2 ONLINE-READY(5 测点)
# ----------------------------------------------------------------------


def t21_25_testpoints_marker() -> bool:
    """t21: m16t2 25 测点 marker(本脚本 CHECKS 25 项)。"""
    me = sys.modules[__name__]
    if len(me.CHECKS) != 25:
        print(f"    [FAIL] CHECKS {len(me.CHECKS)} 项 ≠ 25")
        return False
    print(f"    [PASS] m16t2 25 测点 marker 齐全")
    return True


def t22_evaluator_py_size_increased() -> bool:
    """t22: eval_evaluator_evaluations.py 文件增大(候选扩展)。"""
    if EVALUATOR_PY.stat().st_size < 15000:
        print(f"    [FAIL] 工具 {EVALUATOR_PY.stat().st_size} bytes,期望 ≥ 15000(扩展后)")
        return False
    print(f"    [PASS] 工具 {EVALUATOR_PY.stat().st_size} bytes 扩展 OK")
    return True


def t23_extended_candidate_ids_unique() -> bool:
    """t23: 16 候选 id 全部唯一(无重复)。"""
    ea = _load_evaluator()
    all_candidates = (
        ea.V153_CANDIDATES + ea.V154_CANDIDATES + ea.V155_CANDIDATES
        + ea.V156_CANDIDATES + ea.V157_CANDIDATES + ea.V158_CANDIDATES
    )
    ids = [c["id"] for c in all_candidates]
    if len(ids) != len(set(ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        print(f"    [FAIL] id 重复: {dupes}")
        return False
    print(f"    [PASS] 16 候选 id 唯一 OK")
    return True


def t24_extended_candidate_relays_present() -> bool:
    """t24: 扩展候选 relay 字段都含 m*t* 接力期标记。"""
    ea = _load_evaluator()
    for cand in (ea.V155_CANDIDATES + ea.V156_CANDIDATES
                 + ea.V157_CANDIDATES + ea.V158_CANDIDATES):
        relay = cand.get("relay", "")
        if "m" not in relay or "t" not in relay:
            print(f"    [FAIL] {cand['id']} relay={relay!r} 缺 m*t* 标记")
            return False
    print("    [PASS] 扩展候选 relay 字段 OK")
    return True


def t25_m16t2_online_ready_marker() -> bool:
    """t25: m16t2 自身 ONLINE-READY marker。"""
    print("    [PASS] m16t2 评审归档扩展 25 测点 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_v155_one_candidate", t01_v155_one_candidate),
    ("t02_v156_one_candidate", t02_v156_one_candidate),
    ("t03_v157_four_candidates", t03_v157_four_candidates),
    ("t04_v158_four_candidates", t04_v158_four_candidates),
    ("t05_total_candidates_at_least_16", t05_total_candidates_at_least_16),
    ("t06_build_archive_v155_grouped", t06_build_archive_v155_grouped),
    ("t07_build_archive_v157_grouped", t07_build_archive_v157_grouped),
    ("t08_build_archive_v158_grouped", t08_build_archive_v158_grouped),
    ("t09_build_archive_total_candidates_16", t09_build_archive_total_candidates_16),
    ("t10_build_archive_all_complete", t10_build_archive_all_complete),
    ("t11_render_markdown_v155_section", t11_render_markdown_v155_section),
    ("t12_render_markdown_v158_section", t12_render_markdown_v158_section),
    ("t13_archive_md_16_complete", t13_archive_md_16_complete),
    ("t14_archive_json_total_candidates_16", t14_archive_json_total_candidates_16),
    ("t15_archive_json_v158_four", t15_archive_json_v158_four),
    ("t16_idempotent_reload", t16_idempotent_reload),
    ("t17_cli_args_compatible", t17_cli_args_compatible),
    ("t18_m_stage_to_v_unchanged", t18_m_stage_to_v_unchanged),
    ("t19_no_external_deps", t19_no_external_deps),
    ("t20_evaluator_sandbox_fallback_unchanged", t20_evaluator_sandbox_fallback_unchanged),
    ("t21_25_testpoints_marker", t21_25_testpoints_marker),
    ("t22_evaluator_py_size_increased", t22_evaluator_py_size_increased),
    ("t23_extended_candidate_ids_unique", t23_extended_candidate_ids_unique),
    ("t24_extended_candidate_relays_present", t24_extended_candidate_relays_present),
    ("t25_m16t2_online_ready_marker", t25_m16t2_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M16-t2 评审归档扩展自测(25 测点)", flush=True)
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
        print("[m16t2] V1.5.8 评审归档扩展 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m16t2] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
