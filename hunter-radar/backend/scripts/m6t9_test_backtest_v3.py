"""M6-t9 沙箱自测:BD-087 v3.0 真实回测落地产物校验。

沙箱不实跑历史 EOD 数据(无 PG/BD-085),只静态校验:
- backtest service:支持 v1.0 default + 候选 A 权重对比
- v3.0 runner CLI 命令:run / compare / report
- v3.0 校准报告:候选 A vs v1.0 对比表 + 阈值集中化清单 + M6/M7 后续计划
- 候选 A 权重定义(stock {options:25, short:40, divergence:20, insider:15})
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DOCS = ROOT / "docs"
APP = BACKEND / "app"
SERVICE = APP / "services" / "backtest.py"
SCRIPTS = BACKEND / "scripts"
V25_REPORT = DOCS / "BD-087-calibration-report-v2.5.md"
V30_REPORT = DOCS / "BD-087-calibration-report-v3.0.md"
RUNNER = SCRIPTS / "m6t9_run_backtest_v3.py"

PASS = "[PASS]"
FAIL = "[FAIL]"
failures = 0


def t(name: str, ok: bool, detail: str = "") -> bool:
    global failures
    if ok:
        print(f"  {PASS} {name}{('(' + detail + ')') if detail else ''}")
    else:
        print(f"  {FAIL} {name}{('(' + detail + ')') if detail else ''}")
        failures += 1
    return ok


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
section("1. v3.0 校准报告存在")

t("t01_v30_report_exists", V30_REPORT.exists(), f"path={V30_REPORT}")

v30_text = V30_REPORT.read_text(encoding="utf-8") if V30_REPORT.exists() else ""

t("t02_v30_report_baseline_v25",
  "v2.5" in v30_text and "v3.0" in v30_text)

t("t03_v30_report_candidate_a_weights",
  "candidate_a" in v30_text.lower() or "候选 A" in v30_text or "candidate A" in v30_text)

# 候选 A 权重数字组合
required_weights = {
    "options_25": "25",
    "short_40": "40",
    "divergence_20": "20",
    "insider_15": "15",
}
all_present = all(w in v30_text for w in required_weights.values())
t("t04_v30_report_candidate_a_numerics", all_present,
  f"missing={[v for k,v in required_weights.items() if v not in v30_text]}")


# ---------------------------------------------------------------------------
section("2. v3.0 报告章节完整")

required_sections = [
    "一、",  # 概述 / 增量
    "二、",  # 当前权重基线
    "三、",  # 候选 A 对比(新增)
    "四、",  # 阈值集中化清单
    "五、",  # v3.0 vs v2.5 增量
    "六、",  # 沙箱限制与 M7 计划
    "七、",  # 风险与遗留
]
missing_sections = [s for s in required_sections if s not in v30_text]
t("t05_v30_sections_complete", len(missing_sections) == 0, f"missing={missing_sections}")


# ---------------------------------------------------------------------------
section("3. 候选 A vs v1.0 对比表")

t("t06_v30_compare_table",
  "v1.0" in v30_text and ("候选" in v30_text or "candidate" in v30_text.lower()))

# 命中率/误报率列标题
t("t07_v30_metrics_columns",
  ("hit_rate" in v30_text or "命中率" in v30_text) and
  ("false_positive" in v30_text or "误报率" in v30_text))

# 推荐结论
t("t08_v30_recommendation",
  "推荐" in v30_text or "recommend" in v30_text.lower() or "结论" in v30_text or "建议" in v30_text)


# ---------------------------------------------------------------------------
section("4. 沙箱限制声明")

sandbox_caveats = [
    "沙箱",
    "无 PG",
    "无 EOD",
    "BD-085",
]
ok_caveats = sum(1 for c in sandbox_caveats if c in v30_text)
t("t09_v30_sandbox_caveats", ok_caveats >= 2, f"matched={ok_caveats}/4")


# ---------------------------------------------------------------------------
section("5. v2.5 → v3.0 演进继承")

v25_text = V25_REPORT.read_text(encoding="utf-8") if V25_REPORT.exists() else ""
t("t10_v25_baseline_candidate_a_inherited",
  "25" in v25_text and "40" in v25_text and "candidate" in v25_text.lower())

t("t11_v30_references_v25",
  "v2.5" in v30_text and ("继承" in v30_text or "沿用" in v30_text or "incremental" in v30_text.lower()))


# ---------------------------------------------------------------------------
section("6. v3.0 runner CLI stub")

t("t12_runner_module_exists", RUNNER.exists(), f"path={RUNNER}")
runner_text = RUNNER.read_text(encoding="utf-8") if RUNNER.exists() else ""

t("t13_runner_subcommand_run",
  re.search(r'subparser\.add_parser\(["\']run["\']', runner_text) is not None or
  '"run"' in runner_text or "'run'" in runner_text)

t("t14_runner_subcommand_compare",
  re.search(r'subparser\.add_parser\(["\']compare["\']', runner_text) is not None or
  '"compare"' in runner_text or "'compare'" in runner_text)

t("t15_runner_subcommand_report",
  re.search(r'subparser\.add_parser\(["\']report["\']', runner_text) is not None or
  '"report"' in runner_text or "'report'" in runner_text)

t("t16_runner_sandbox_marker",
  "sandbox" in runner_text.lower() and ("fallback" in runner_text.lower() or "无 PG" in runner_text or "无 EOD" in runner_text))


# ---------------------------------------------------------------------------
section("7. backtest service 支持 A/B 权重对比")

t("t17_backtest_service_exists", SERVICE.exists(), f"path={SERVICE}")
service_text = SERVICE.read_text(encoding="utf-8") if SERVICE.exists() else ""

t("t18_backtest_resolve_weights",
  "def resolve_weights" in service_text and "custom_weights" in service_text)

t("t19_backtest_metrics_class",
  "BacktestMetrics" in service_text and "hit_rate" in service_text)


# ---------------------------------------------------------------------------
print()
if failures == 0:
    print("[m6t9] ALL 19 BACKTEST-V3.0 (REPORT + RUNNER + SERVICE) TESTS PASSED")
    sys.exit(0)
else:
    print(f"[m6t9] {failures} TEST(S) FAILED")
    sys.exit(1)