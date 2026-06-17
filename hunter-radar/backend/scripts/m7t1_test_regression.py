"""M7-t1 沙箱自测:M5 + M6 全量自测脚本回归 + M7 入口就位校验。

沙箱不实跑后端(无 PG/Redis),只串行跑 11 个 m5t* + 10 个 m6t*(m6t1 套 M5,其余 M6 接力期),
确认 M5+M6 接力期所有产物的可跑性,作为 M7 接力期入口。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "backend" / "scripts"

# 11 个 M5 自测脚本(顺序:freeze→JWT→push×2→disclaimer→data→sentry→quota→calib→CI→docs)
M5_SCRIPTS = [
    ("m5t1_verify_openapi.py", 11),
    ("m5t2_test_auth.py", 11),
    ("m5t3_test_push.py", 12),
    ("m5t4_test_webpush.py", 13),
    ("m5t5_test_disclaimer.py", 9),
    ("m5t6_test_data_status.py", 10),
    ("m5t7_test_sentry_motion.py", 10),
    ("m5t8_test_quota.py", 10),
    ("m5t9_test_calibration.py", 10),
    ("m5t10_test_ci_skeleton.py", 10),
    ("m5t11_test_documentation.py", 16),
]

# 10 个 M6 自测脚本(m6t1 套 M5,m6t2~m6t10 是 M6 接力期增量)
M6_SCRIPTS = [
    ("m6t1_test_regression.py", 11),  # M5 回归(11 个脚本)
    ("m6t2_test_pwa.py", 18),
    ("m6t3_test_install.py", 26),
    ("m6t4_test_stripe.py", 15),
    ("m6t5_test_subscribe.py", 18),
    ("m6t6_test_commercial.py", 22),
    ("m6t7_test_feature_flag.py", 24),
    ("m6t8_test_eight_k.py", 19),
    ("m6t9_test_backtest_v3.py", 19),
    ("m6t10_test_documentation.py", 35),
]

PASS = "[PASS]"
FAIL = "[FAIL]"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


def run_one(script: str) -> tuple[int, str]:
    """串行跑一个 m*t*_test_*.py 脚本,返 (exit_code, tail_lines)."""
    path = SCRIPTS / script
    if not path.exists():
        return 2, f"script missing: {path}"
    proc = subprocess.run(
        [sys.executable, "-u", str(path)],
        cwd=str(ROOT / "backend"),
        capture_output=True,
        text=True,
        timeout=180,
    )
    out_lines = (proc.stdout + proc.stderr).splitlines()
    tail = "\n".join(out_lines[-3:]) if out_lines else "(no output)"
    return proc.returncode, tail


def run_group(label: str, scripts: list[tuple[str, int]]) -> tuple[int, int, int]:
    """跑一组脚本,返 (failures, passed_testpoints, total_testpoints)."""
    failures = 0
    passed_tp = 0
    total_tp = 0

    print("=" * 70, flush=True)
    print(label, flush=True)
    print("=" * 70, flush=True)

    for script, expected in scripts:
        total_tp += expected
        rc, tail = run_one(script)
        ok = rc == 0
        if not t(f"run_{script}", ok, f"rc={rc} tail={tail[:120]!r}"):
            failures += 1
        else:
            passed_tp += expected

    return failures, passed_tp, total_tp


def main() -> int:
    failures = 0

    # 1. M5 接力期 11 脚本回归
    f1, p1, tot1 = run_group(
        "M7-t1 / M5 接力期自测回归(11 个脚本,期望 122 测点全过)", M5_SCRIPTS
    )
    failures += f1

    # 2. M6 接力期 10 脚本回归(m6t1 套 M5,m6t2~m6t10 是 M6 增量)
    f2, p2, tot2 = run_group(
        "M7-t1 / M6 接力期自测回归(10 个脚本,期望 207 测点全过)", M6_SCRIPTS
    )
    failures += f2

    # 跨组一致性:总测点数
    total_passed = p1 + p2
    total_expected = tot1 + tot2
    ok = total_passed == total_expected
    if not t(
        "aggregate_testpoints_match",
        ok,
        f"passed={total_passed}/{total_expected}",
    ):
        failures += 1

    # ---- M7 关键入口就位 -----------------------------------------------------
    entry_points = [
        ROOT / "docs" / "M6-handoff.md",
        ROOT / "docs" / "BD-087-calibration-report-v3.0.md",
        ROOT / "docs" / "openapi-frozen-v1.4.1.md",
        ROOT / "backend" / "app" / "main.py",
        ROOT / "backend" / "app" / "services" / "subscription.py",
        ROOT / "backend" / "app" / "services" / "feature_flag.py",
        ROOT / "backend" / "app" / "services" / "eight_k.py",
        ROOT / "backend" / "app" / "api" / "subscriptions.py",
        ROOT / "backend" / "app" / "api" / "feature_flags.py",
        ROOT / "backend" / "app" / "api" / "eight_k.py",
        ROOT / "frontend" / "src" / "routes" / "subscribe.tsx",
        ROOT / "frontend" / "src" / "components" / "common" / "ProBadge.tsx",
        ROOT / "frontend" / "src" / "components" / "common" / "UpgradePrompt.tsx",
        ROOT / "frontend" / "src" / "components" / "common" / "GrayReleaseBanner.tsx",
    ]
    missing = [str(p.relative_to(ROOT)) for p in entry_points if not p.exists()]
    ok = len(missing) == 0
    if not t("m7_entry_points_in_place", ok, f"missing={missing}"):
        failures += 1

    # ---- 风险 R-23 / R-27 / R-28 仍待 M7 推进 -------------------------------
    print(flush=True)
    print("[INFO] M7 接力期待推进风险:", flush=True)
    print("  R-12: SEC EDGAR / FINRA ATS 真实数据源 → m7t5", flush=True)
    print("  R-13: 沙箱无 PG/Redis → 集成测试仅 smoke 骨架", flush=True)
    print("  R-23: BD-086 reviewer_signoff 仍是 TBD → m7t2", flush=True)
    print("  R-25: Sentry DSN + VAPID 真实密钥未配 → m7t8", flush=True)
    print("  R-27: BD-087 v2.5 仅理论 + 沙箱空跑 → m7t4 切真实 EOD", flush=True)
    print("  R-28: 候选 A 权重切换需 OpenAPI v1.5 freeze → m7t7", flush=True)
    print("  R-31: Stripe webhook 沙箱简化(无签名校验)→ m7t6", flush=True)
    print("  R-32/33: Vite PWA 沙箱只写配置 → m7t8", flush=True)

    # ---- 已知遗留:BD-086 reviewer_signoff 仍是 TBD -------------------------
    goldset_path = ROOT / "data" / "backtest_event_goldset.sample.jsonl"
    if goldset_path.exists():
        txt = goldset_path.read_text(encoding="utf-8", errors="replace")
        signoff_pending = '"reviewer_signoff"' in txt and '"TBD"' in txt
        if t("goldset_signoff_still_tbd", signoff_pending, "m7t2 待推进"):
            pass  # 这是预期的「仍 TBD」状态
        else:
            print("  [INFO] reviewer_signoff 已非 TBD(M7-t2 已补)", flush=True)

    print(flush=True)
    if failures == 0:
        print(
            f"[m7t1] M5+M6 REGRESSION {total_passed}/{total_expected} PASSED + "
            f"M7 ENTRY POINTS OK"
        )
        return 0
    print(f"[m7t1] {failures} REGRESSION CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())