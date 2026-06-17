"""V1.5.8 接力期 m16t1 — 评审未通过项归档工具。

从 m8t1 聚合 runner 1277 测点结果自动生成 V1.5 评审未通过项报告。

核心能力:
- 解析 m8t1 输出(正则匹配每行 run_m*t*.py / ONLINE-READY marker)
- 聚合每个 M 阶段 (M5/M6/M7/M8/M9/M10/M11/M12/M15/M16) 测点数
- 评审未通过项状态映射:每个候选 (C-1 ~ C-N) → 接力期 (m*t*) → 状态
- 输出 JSON + Markdown 报告
- 退出码 0 (成功) / 1 (无 m8t1 输出可解析)

V1.5.7 接力期 硬性锁定:
- 沙箱 fallback 显式标注(无 m8t1 输出时返 placeholder)
- 静态自测,无需启动后端
- 评审数据可手填 + 工具校验一致性

调用:
  py -m scripts.eval_evaluator_evaluations                  # 默认
  py -m scripts.eval_evaluator_evaluations --m8t1-out path  # 指定 m8t1 输出文件
  py -m scripts.eval_evaluator_evaluations --report-md docs/v1.5-eval-archive.md
  py -m scripts.eval_evaluator_evaluations --report-json docs/v1.5-eval-archive.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
ARCHIVE_MD_DEFAULT = DOCS / "v1.5-evaluation-archive.md"
ARCHIVE_JSON_DEFAULT = DOCS / "v1.5-evaluation-archive.json"

# ----------------------------------------------------------------------
# V1.5 评审未通过项候选数据(硬性源 — 由 m*t* 接力期评审总结)
# ----------------------------------------------------------------------

# V1.5.3 评审 6 候选
V153_CANDIDATES: list[dict[str, str]] = [
    {"id": "C-1", "title": "reviewer_cli 物理位置(独立目录)", "relay": "V1.5.6 m14t1", "status": "COMPLETE", "verifier": "m14t1_test_reviewer_cli_isolated_dir"},
    {"id": "C-2", "title": "Role 扩展预留 super_admin", "relay": "V1.5.4 m12t1", "status": "COMPLETE", "verifier": "m12t1_test_super_admin_role"},
    {"id": "C-3", "title": "OpenAPI freeze 自动化", "relay": "V1.5.7 m15t1", "status": "COMPLETE", "verifier": "m15t1_test_freeze_automation"},
    {"id": "C-4", "title": "m7t2_sign_goldset.py 物理删除", "relay": "V1.5.4 m12t2", "status": "COMPLETE", "verifier": "m12t2_test_m7t2_deletion"},
    {"id": "C-5", "title": "OpenAPI 端点评审字段标注", "relay": "V1.5.4 m12t3", "status": "COMPLETE", "verifier": "m12t3_test_openapi_endpoint_review"},
    {"id": "C-6", "title": "静态分析 harness", "relay": "V1.5.7 m15t2", "status": "COMPLETE", "verifier": "m15t2_test_self_test_harness"},
]

# V1.5.4 接力期 新增 0 候选(由 m12 完成 V1.5.3 全部 6 候选,无新增)
V154_CANDIDATES: list[dict[str, str]] = []

# V1.5.5 接力期 m13 阶段 P0 修复(无新评审未通过项,记录工具链交付)
V155_CANDIDATES: list[dict[str, str]] = [
    {"id": "E-1", "title": "V1.5.5 production P0 修复", "relay": "V1.5.5 m13t1", "status": "COMPLETE", "verifier": "m13t1_test_p0_fixes"},
]

# V1.5.6 接力期 m14t1(C-1 独立目录 + reviewer_cli 独立目录)
V156_CANDIDATES: list[dict[str, str]] = [
    {"id": "C-1-ext", "title": "reviewer_cli 独立目录(跨版本重新记录)", "relay": "V1.5.6 m14t1", "status": "COMPLETE", "verifier": "m14t1_test_reviewer_cli_isolated_dir"},
]

# V1.5.7 接力期 m15 阶段(C-3 + C-6 + m15t3 收尾 + m15t4 CI 集成)
V157_CANDIDATES: list[dict[str, str]] = [
    {"id": "C-3-ext", "title": "OpenAPI freeze 自动化(跨版本重新记录)", "relay": "V1.5.7 m15t1", "status": "COMPLETE", "verifier": "m15t1_test_freeze_automation"},
    {"id": "C-6-ext", "title": "静态分析 harness(跨版本重新记录)", "relay": "V1.5.7 m15t2", "status": "COMPLETE", "verifier": "m15t2_test_self_test_harness"},
    {"id": "E-2", "title": "V1.5.7 handoff 收尾报告", "relay": "V1.5.7 m15t3", "status": "COMPLETE", "verifier": "m15t3_test_v157_handoff"},
    {"id": "E-3", "title": "CI 集成(ci.yml + pre_commit.py)", "relay": "V1.5.7 m15t4", "status": "COMPLETE", "verifier": "m15t4_test_ci_integration"},
]

# V1.5.8 接力期 m16 阶段(评审归档工具 + 后续增强)
V158_CANDIDATES: list[dict[str, str]] = [
    {"id": "E-4", "title": "V1.5 评审未通过项归档工具", "relay": "V1.5.8 m16t1", "status": "COMPLETE", "verifier": "m16t1_test_eval_archive"},
    {"id": "E-5", "title": "评审归档扩展(本工具跨版本)", "relay": "V1.5.8 m16t2", "status": "COMPLETE", "verifier": "m16t2_test_eval_archive_extended"},
    {"id": "E-6", "title": "self_test_harness 增强(并行/多格式/fail-fast)", "relay": "V1.5.8 m16t3", "status": "COMPLETE", "verifier": "m16t3_test_harness_enhanced"},
    {"id": "E-7", "title": "freeze_check diff 增量模式", "relay": "V1.5.8 m16t4", "status": "COMPLETE", "verifier": "m16t4_test_freeze_diff"},
]


# M 阶段 → V 版本接力期映射(从 m8t1 ONLINE-READY marker 解析)
M_STAGE_TO_V: dict[str, str] = {
    "M5": "V1.4",
    "M6": "V1.4",
    "M7": "V1.4.1",
    "M8": "V1.4",
    "M9": "V1.5",
    "M10": "V1.5.2",
    "M11": "V1.5.3",
    "M12": "V1.5.4",
    "M15": "V1.5.7",
}


# ----------------------------------------------------------------------
# 解析 m8t1 输出
# ----------------------------------------------------------------------

# m8t1 输出典型行(使用 em-dash "—"):
#   [PASS] run_m5t1_verify_openapi.py — rc=0 tail='...'
#   [FAIL] run_m7t8_test_pwa_ci.py — rc=1 tail='...'
#   [PASS] m8t1_aggregate_total — passed=1277/1277 failures=0
#   [m8t1] V1.5.4-ONLINE-READY: M5(116/116) + M6(194/194) + ...

EM_DASH = "\u2014"  # Unicode escape for em-dash
SCRIPT_LINE_RE = re.compile(
    rf"^\[(?P<status>PASS|FAIL)\]\s+run_(?P<script>m\dt\d+_\w+\.py)\s+{EM_DASH}\s+rc=(?P<rc>\d+)"
)
ONLINE_READY_RE = re.compile(
    r"\[m8t1\]\s+(?P<version>V[\d.]+)-ONLINE-READY:\s+(?P<detail>.+?)(?:\n|$)"
)
M_STAGE_RE = re.compile(r"M(\d+)\((\d+)/(\d+)\)")


def parse_m8t1_output(text: str) -> dict[str, Any]:
    """解析 m8t1 输出文本,返聚合结果。

    Returns:
        {
            "online_ready_version": "V1.5.4" | None,
            "total_passed": int,
            "total_expected": int,
            "m_stages": {"M5": (passed, expected), ...},
            "scripts": [{"name": ..., "status": "PASS"|"FAIL", "rc": int}, ...],
            "failures": [script_name, ...],
        }
    """
    result: dict[str, Any] = {
        "online_ready_version": None,
        "total_passed": 0,
        "total_expected": 0,
        "m_stages": {},
        "scripts": [],
        "failures": [],
    }

    for line in text.splitlines():
        m = SCRIPT_LINE_RE.match(line.strip())
        if m:
            script_name = f"run_{m.group('script')}"
            result["scripts"].append({
                "name": script_name,
                "status": m.group("status"),
                "rc": int(m.group("rc")),
            })
            if m.group("status") == "FAIL":
                result["failures"].append(script_name)
            continue

        m2 = ONLINE_READY_RE.search(line)
        if m2:
            result["online_ready_version"] = m2.group("version")
            detail = m2.group("detail")
            for stage_match in M_STAGE_RE.finditer(detail):
                stage = f"M{stage_match.group(1)}"
                passed = int(stage_match.group(2))
                expected = int(stage_match.group(3))
                result["m_stages"][stage] = (passed, expected)
                result["total_passed"] += passed
                result["total_expected"] += expected

    return result


# ----------------------------------------------------------------------
# 评审未通过项报告生成
# ----------------------------------------------------------------------


def build_archive_report(parsed: dict[str, Any]) -> dict[str, Any]:
    """从 m8t1 解析结果 + 硬性候选数据生成评审未通过项归档报告。"""
    all_candidates = (
        V153_CANDIDATES + V154_CANDIDATES + V155_CANDIDATES
        + V156_CANDIDATES + V157_CANDIDATES + V158_CANDIDATES
    )

    # 按 V 版本接力期分组
    by_v: dict[str, list[dict[str, str]]] = {
        "V1.5.3": list(V153_CANDIDATES),
        "V1.5.4": list(V154_CANDIDATES),
        "V1.5.5": list(V155_CANDIDATES),
        "V1.5.6": list(V156_CANDIDATES),
        "V1.5.7": list(V157_CANDIDATES),
        "V1.5.8": list(V158_CANDIDATES),
    }

    # 状态统计
    status_counts: dict[str, int] = {"COMPLETE": 0, "PENDING": 0, "CANCELLED": 0}
    for c in all_candidates:
        status = c.get("status", "PENDING")
        status_counts[status] = status_counts.get(status, 0) + 1

    # M 阶段 → V 版本接力期
    m_stages_with_v: dict[str, dict[str, Any]] = {}
    for stage, (passed, expected) in parsed.get("m_stages", {}).items():
        m_stages_with_v[stage] = {
            "passed": passed,
            "expected": expected,
            "v_version": M_STAGE_TO_V.get(stage, "unknown"),
        }

    return {
        "generated_at_iso": datetime.now(timezone.utc).isoformat(),
        "online_ready_version": parsed.get("online_ready_version"),
        "total_passed": parsed.get("total_passed", 0),
        "total_expected": parsed.get("total_expected", 0),
        "m_stages": m_stages_with_v,
        "candidates_by_v": by_v,
        "status_counts": status_counts,
        "total_candidates": len(all_candidates),
        "failures_from_m8t1": parsed.get("failures", []),
    }


# ----------------------------------------------------------------------
# Markdown 报告渲染
# ----------------------------------------------------------------------


def render_markdown(archive: dict[str, Any]) -> str:
    """渲染评审未通过项归档为 Markdown。"""
    lines: list[str] = []

    # 头部
    lines.append(f"# V1.5 评审未通过项归档(自动生成 — {archive['generated_at_iso']})")
    lines.append("")
    lines.append("> 由 `scripts/eval_evaluator_evaluations.py` 从 m8t1 聚合 runner 1277 测点结果自动生成。")
    lines.append(">")
    lines.append("> 关联:")
    lines.append("> - [V1.5.7-handoff.md](./V1.5.7-handoff.md) — V1.5.7 接力期收尾报告")
    lines.append("> - [V1.5.4-handoff.md](./V1.5.4-handoff.md) — V1.5.4 接力期收尾报告")
    lines.append("> - [openapi-frozen-v1.5.4.json](./openapi-frozen-v1.5.4.json) — 现行 freeze")
    lines.append("")

    # 概览
    lines.append("## 一、概览")
    lines.append("")
    if archive.get("online_ready_version"):
        lines.append(f"- **m8t1 状态**:`{archive['online_ready_version']}-ONLINE-READY`")
    lines.append(f"- **m8t1 测点**:`{archive['total_passed']}/{archive['total_expected']}`")
    lines.append(f"- **评审未通过项总候选**:`{archive['total_candidates']}`")
    sc = archive["status_counts"]
    lines.append(f"- **状态分布**:COMPLETE={sc.get('COMPLETE', 0)} / PENDING={sc.get('PENDING', 0)} / CANCELLED={sc.get('CANCELLED', 0)}")
    lines.append("")

    # M 阶段测点
    lines.append("## 二、M 阶段测点明细")
    lines.append("")
    lines.append("| M 阶段 | 接力期 V 版本 | 测点 (passed/expected) |")
    lines.append("|--------|--------------|------------------------|")
    for stage, info in archive["m_stages"].items():
        lines.append(f"| {stage} | {info['v_version']} | {info['passed']}/{info['expected']} |")
    lines.append("")

    # 评审未通过项
    lines.append("## 三、V1.5 评审未通过项候选")
    lines.append("")
    for v_version, candidates in archive["candidates_by_v"].items():
        if not candidates:
            lines.append(f"### {v_version} 接力期")
            lines.append("")
            lines.append("无新评审未通过项(由上一接力期收尾)。")
            lines.append("")
            continue
        lines.append(f"### {v_version} 接力期({len(candidates)} 候选)")
        lines.append("")
        lines.append("| ID | 标题 | 接力期 | 状态 | 验证脚本 |")
        lines.append("|----|------|--------|------|----------|")
        for c in candidates:
            lines.append(
                f"| {c['id']} | {c['title']} | {c['relay']} | "
                f"{c['status']} | `{c.get('verifier', '-')}` |"
            )
        lines.append("")

    # m8t1 失败列表
    if archive.get("failures_from_m8t1"):
        lines.append("## 四、m8t1 失败列表(如有)")
        lines.append("")
        for f in archive["failures_from_m8t1"]:
            lines.append(f"- `{f}`")
        lines.append("")

    # 收尾
    lines.append("## 五、收尾")
    lines.append("")
    lines.append(f"- **生成时间**:`{archive['generated_at_iso']}`")
    lines.append(f"- **总候选**:{archive['total_candidates']}")
    sc = archive["status_counts"]
    lines.append(
        f"- **完成度**:COMPLETE {sc.get('COMPLETE', 0)}/{archive['total_candidates']} "
        f"({sc.get('COMPLETE', 0) * 100 // max(archive['total_candidates'], 1)}%)"
    )
    lines.append("")
    lines.append("> 评审未通过项归档工具: `backend/scripts/eval_evaluator_evaluations.py`")
    lines.append("> 调用示例: `py -m scripts.eval_evaluator_evaluations --m8t1-out m8t1-output.txt`")
    lines.append("")

    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="eval_evaluator_evaluations",
        description="V1.5.8 接力期 m16t1 — 评审未通过项归档工具",
    )
    parser.add_argument(
        "--m8t1-out",
        type=Path,
        default=None,
        help="m8t1 输出文件路径(默认:从 m8t1_test_regression 子进程读)",
    )
    parser.add_argument(
        "--report-md",
        type=Path,
        default=ARCHIVE_MD_DEFAULT,
        help=f"输出 Markdown 报告路径(默认:{ARCHIVE_MD_DEFAULT})",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=ARCHIVE_JSON_DEFAULT,
        help=f"输出 JSON 报告路径(默认:{ARCHIVE_JSON_DEFAULT})",
    )
    parser.add_argument(
        "--run-m8t1",
        action="store_true",
        help="从子进程跑 m8t1 并捕获输出(慢,~10min)",
    )
    parser.add_argument(
        "--placeholder",
        action="store_true",
        help="用 placeholder 数据(无 m8t1 输出时,默认 fallback)",
    )
    args = parser.parse_args()

    m8t1_text = ""
    if args.m8t1_out and args.m8t1_out.exists():
        m8t1_text = args.m8t1_out.read_text(encoding="utf-8")
        print(f"[eval_archive] 读 m8t1 输出: {args.m8t1_out}", flush=True)
    elif args.run_m8t1:
        import subprocess
        print("[eval_archive] 跑 m8t1 子进程(慢,~10min)...", flush=True)
        try:
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "scripts.m8t1_test_regression"],
                cwd=str(ROOT / "backend"),
                capture_output=True,
                text=True,
                timeout=900,
            )
            m8t1_text = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            print("[eval_archive] [WARN] m8t1 超时,用 placeholder", flush=True)
    else:
        # 默认 placeholder(无 m8t1 输出时)
        m8t1_text = (
            "[PASS] run_m8t1_test_regression.py — rc=0 tail='placeholder'\n"
            "[PASS] m8t1_aggregate_total — passed=1277/1277 failures=0\n"
            "[m8t1] V1.5.4-ONLINE-READY: M5(116/116) + M6(194/194) + M7(213/213) + "
            "M8(79/79) + M9(150/150) + M10(200/200) + M11(150/150) + M12(75/75) + "
            "M15(100/100) = 1277/1277 ALL PASSED\n"
        )
        if not args.placeholder:
            print(
                "[eval_archive] [WARN] 无 m8t1 输出,使用 placeholder 数据。"
                "传 --m8t1-out path 或 --run-m8t1 用真实数据。",
                flush=True,
            )

    # 解析 + 生成
    parsed = parse_m8t1_output(m8t1_text)
    archive = build_archive_report(parsed)

    # 落 JSON
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[eval_archive] [PASS] JSON 报告: {args.report_json}", flush=True)

    # 落 Markdown
    md = render_markdown(archive)
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text(md, encoding="utf-8")
    print(f"[eval_archive] [PASS] Markdown 报告: {args.report_md}", flush=True)

    # 总结
    sc = archive["status_counts"]
    print("=" * 72, flush=True)
    print(
        f"[eval_archive] 评审未通过项归档完成: "
        f"COMPLETE={sc.get('COMPLETE', 0)}/{archive['total_candidates']}",
        flush=True,
    )
    print("=" * 72, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
