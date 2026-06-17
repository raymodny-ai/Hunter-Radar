"""M5-t9 沙箱自测:BD-087 校准报告 v2.5 + 回测 runner 落地产物校验。

不动 main.py / runtime,只静态校验:
- v2.5 校准报告字段齐全(M5 增量)
- 回测 run JSON 存在 + 31 事件已读
- runner 脚本存在
- 候选 A 权重正确
- v1.0 锁定沿用声明
- OQ-01/02 守护描述
- OpenAPI v1.4.1 校准时间表引用
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BACKEND = ROOT / "backend"
DATA = ROOT / "data"
REPORT = DOCS / "BD-087-calibration-report-v2.5.md"
RUN_JSON = DOCS / "BD-087-calibration-run-m5t9.json"
RUNNER = BACKEND / "scripts" / "m5t9_run_backtest.py"
GOLDSET = DATA / "backtest_event_goldset.sample.jsonl"
FREEZE = DOCS / "openapi-frozen-v1.4.1.md"

PASS = "[PASS]"
FAIL = "[FAIL]"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


def main() -> int:
    failures = 0

    # ---- 1. 报告存在 + 标题正确 ------------------------------------------------
    if not REPORT.exists():
        t("t01_report_exists", False, f"{REPORT} missing")
        return 1
    text = REPORT.read_text(encoding="utf-8")
    ok = "# BD-087《Threat Score 校准报告 v2.5》" in text and "M5 接力期" in text
    if not t("t01_report_title_v25", ok):
        failures += 1

    # ---- 2. v1.0 锁定声明 ------------------------------------------------------
    ok = "v1.0 默认" in text and "v2.5 沿用" in text
    if not t("t02_v10_weights_locked", ok):
        failures += 1

    # ---- 3. 候选 A 权重正确(25/40/20/15) ---------------------------------------
    # md 中存在 JSON 块带引号空格版 + 表格列 | 25 | 40 | 20 | 15 | 版
    cands = (
        '"options": 25' in text,
        "options:25" in text,
        '"short": 40' in text,
        "short:40" in text,
        "| 25 | 40 | 20 | 15 |" in text,
    )
    ok = any(cands[:2]) and any(cands[2:4]) and cands[4]
    if not t("t03_candidate_A_weights_25_40_20_15", ok, f"cands={cands}"):
        failures += 1
    # ---- 4. 31 金标准事件数 -----------------------------------------------------
    ok = "31" in text and "short_squeeze" in text and "earnings_crash" in text
    if not t("t04_31_goldset_events", ok):
        failures += 1

    # ---- 5. 沙箱回测结论 + 沿用 v1.0 推荐 --------------------------------------
    ok = (
        "沙箱空跑" in text
        and "沿用 v1.0 默认权重" in text
        and "M6 切真实 EOD" in text
    )
    if not t("t05_sandbox_recommendation", ok):
        failures += 1

    # ---- 6. OQ-01/02/16 守护描述 ------------------------------------------------
    ok = "OQ-01" in text and "OQ-02" in text and "OQ-16" in text and "CR-010" in text
    if not t("t06_oq_guards_described", ok):
        failures += 1

    # ---- 7. M5 增量阈值集中化(quota / push / sentry / reduced-motion) ------------
    missing = [n for n in ("FREE_DAILY_LIMIT", "SMTP_HOST", "VAPID", "Sentry", "reduced-motion") if n not in text]
    ok = len(missing) == 0
    if not t("t07_m5_thresholds_centralized", ok, f"missing={missing}"):
        failures += 1

    # ---- 8. v3.0 校准计划存在 --------------------------------------------------
    ok = "v3.0" in text and "M6 切真实 EOD" in text and "灰度发布" in text
    if not t("t08_v30_calibration_plan", ok):
        failures += 1

    # ---- 9. 回测 runner + json + freeze 关联 -----------------------------------
    ok = (
        RUNNER.exists()
        and RUN_JSON.exists()
        and FREEZE.exists()
    )
    if not t("t09_runner_json_freeze_exist", ok, f"runner={RUNNER.exists()} json={RUN_JSON.exists()}"):
        failures += 1

    # ---- 10. 回测 JSON 内容校验 + goldset 一致 --------------------------------
    try:
        run = json.loads(RUN_JSON.read_text(encoding="utf-8"))
        ok_metrics = (
            run["is_sandbox"] is True
            and run["weights_v10"]["options"] == 30
            and run["weights_v10"]["short"] == 35
            and run["weights_candidate_A"]["short"] == 40
            and run["metrics_v10"]["n_events_total"] == 31
            and run["metrics_v10"]["reason"].startswith("sandbox")
        )
        # goldset 实际事件数校验
        n_goldset = 0
        with GOLDSET.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    n_goldset += 1
        ok = ok_metrics and n_goldset == 31
        if not t("t10_run_json_metrics_consistent", ok, f"run n={run['metrics_v10']['n_events_total']} goldset={n_goldset}"):
            failures += 1
    except Exception as e:  # noqa: BLE001
        t("t10_run_json_metrics_consistent", False, str(e))
        failures += 1

    print()
    if failures == 0:
        print("[m5t9] ALL 10 CALIBRATION v2.5 TESTS PASSED")
        return 0
    print(f"[m5t9] {failures} TEST(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
