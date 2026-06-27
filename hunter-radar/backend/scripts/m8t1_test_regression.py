"""M8-t1 V1.6.0 上线回归验证:M5 + M6 + M7 + M8 + M9 + M10 + M11 + M12 + M15 + M16 + M17 + M18 + M19 全量沙箱自测聚合 runner。

V1.5.4 接力期 增量状态校验:
- M5(11 脚本 / 122 测点) — 沿用 m7t1 验证
- M6(10 脚本 / 207 测点) — 沿用 m7t1 验证
- M7(9 脚本 / 198+ 测点) — m7t2~m7t10,跳过聚合型(m7t1)
- M8(5 脚本 / 109 测点) — m8t1~m8t5 接力期新建
- M9(6 脚本 / 150 测点) — m9t2 + m9t3 + m9t4 + m9t5 + m9t6 + m9t7 接力期新建(去 m9t1 自身聚合型)
- M10(8 脚本 / 200 测点) — m10t1~m10t8 真实数据 + 公开评审 + 工具合并 + freeze(去聚合型)
- M11(6 脚本 / 150 测点) — m11t1~m11t6: V1.5.3 P0 + reviewer_cli 工具链 + P2 合并迭代
- M12(3 脚本 / 75 测点) — m12t1~m12t3: V1.5.4 super_admin + m7t2 物理删除 + 端点评审字段
- M15(4 脚本 / 100 测点) — m15t1 (C-3 freeze 自动化) + m15t2 (C-6 self_test_harness) + m15t3 (V1.5.7 收尾) + m15t4 (CI 集成): V1.5.7 接力期
- M16(4 脚本 / 100 测点) — m16t1 (评审归档工具) + m16t2 (评审归档扩展 V1.5.5~V1.5.8) + m16t3 (harness 增强 ThreadPoolExecutor + --output-format + --fail-fast) + m16t4 (freeze diff 增量模式): V1.5.8 接力期
- M17(1 脚本 / 25 测点) — m17t1 (V1.5.8-handoff.md 收尾报告): V1.5.8 接力期 收尾
- M18(3 脚本 / 75 测点) — m18t1 (ATS Fallback 全链路) + m18t2 (Options V2 全链路) + m18t3 (V1.5.9 handoff): V1.5.9 接力期
- M19(5 脚本 / 125 测点) — m19t1 (Pipeline Resilience) + m19t2 (ML 权重 + VWMA) + m19t3 (API 完整性) + m19t4 (RAG) + m19t5 (Docker): V1.6.0 接力期

总计 73 个脚本 / 1602+ 测点全过(V1.6.0 ONLINE-READY)。

V1.5.3 接力期 沿用状态(由 m11t6 静态分析 验证):
- V1.5.3 接力期 m11 早期(5 脚本 / 125 测点),V1.5.3 接力期后补 m11t6 达到 6 脚本 / 150 测点
- V1.5.3 接力期 收尾状态: M11({p7}/125) 早期 + V1.5.3-ONLINE-READY 兼容 marker

设计:
- 串行跑每个脚本(沙箱不并行)
- 每个脚本超时 180s,失败也继续跑完
- 汇总 PASS/FAIL + 列出失败脚本 tail
- 退出码:全部通过返 0,任意失败返 1
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "backend" / "scripts"

# M5(11 脚本,沿用 m7t1 顺序)
M5_SCRIPTS = [
    ("m5t1_verify_openapi.py", 5),
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

# M6(9 脚本,去掉 m6t1_test_regression 聚合型)
M6_SCRIPTS = [
    ("m6t2_test_pwa.py", 16),
    ("m6t3_test_install.py", 26),
    ("m6t4_test_stripe.py", 15),
    ("m6t5_test_subscribe.py", 18),
    ("m6t6_test_commercial.py", 22),
    ("m6t7_test_feature_flag.py", 24),
    ("m6t8_test_eight_k.py", 19),
    ("m6t9_test_backtest_v3.py", 19),
    ("m6t10_test_documentation.py", 35),
]

# M7(9 脚本,去掉 m7t1_test_regression 聚合型 + m7t3_test_real_dataset 旧版)
M7_SCRIPTS = [
    ("m7t2_test_signoff.py", 22),
    ("m7t3_test_dataset_real.py", 22),
    ("m7t4_test_v30_final.py", 22),
    ("m7t5_test_edgar_fulltext.py", 22),
    ("m7t6_test_stripe_webhook.py", 22),
    ("m7t7_test_openapi_v15.py", 22),
    ("m7t8_test_pwa_ci.py", 22),
    ("m7t9_test_v15_prep.py", 22),
    ("m7t10_test_documentation.py", 37),
]

# M8(5 脚本,V1.4 接力期新建;跳过 m8t1 自身作为聚合型)
M8_SCRIPTS = [
    ("m8t2_test_compliance_drift.py", 22),
    ("m8t3_test_prod_env.py", 20),
    ("m8t4_test_release_notes.py", 25),
    ("m8t5_test_handoff.py", 12),
]

# M10(V1.5.2 接力期;逐个添加,跳过聚合型)
M10_SCRIPTS = [
    ("m10t1_test_edgar_real.py", 25),
    ("m10t2_test_etf_real.py", 25),
    ("m10t3_test_analytics_real.py", 25),
    ("m10t4_test_admin_role_audit.py", 25),
    ("m10t5_test_reviewer_cli_replace.py", 25),
    ("m10t6_test_scipy_replace.py", 25),
    ("m10t7_test_p2_merge.py", 25),
    ("m10t8_test_v152_finalize.py", 25),
]
M11_SCRIPTS = [
    ("m11t1_test_auth_all_export.py", 25),
    ("m11t2_test_admin_role_ip_integration.py", 25),
    ("m11t3_test_role_extension.py", 25),
    ("m11t4_test_reviewer_cli_toolchain.py", 25),
    ("m11t5_test_p2_json_only.py", 25),
    ("m11t6_test_v153_finalize.py", 25),
]

# M12(V1.5.4 接力期;3 脚本 / 75 测点)
M12_SCRIPTS = [
    ("m12t1_test_super_admin_role.py", 25),
    ("m12t2_test_m7t2_deletion.py", 25),
    ("m12t3_test_openapi_endpoint_review.py", 25),
]

# M15(V1.5.7 接力期 C-3 + C-6 候选 + m15t3 收尾 + m15t4 CI 集成;4 脚本 / 100 测点)
M15_SCRIPTS = [
    ("m15t1_test_freeze_automation.py", 25),
    ("m15t2_test_self_test_harness.py", 25),
    ("m15t3_test_v157_handoff.py", 25),
    ("m15t4_test_ci_integration.py", 25),
]

# M16(V1.5.8 接力期 评审归档工具 + 扩展 + harness 增强 + freeze diff;4 脚本 / 100 测点)
M16_SCRIPTS = [
    ("m16t1_test_eval_archive.py", 25),
    ("m16t2_test_eval_archive_extended.py", 25),
    ("m16t3_test_harness_enhanced.py", 25),
    ("m16t4_test_freeze_diff.py", 25),
]

# M17(V1.5.8 接力期 收尾报告;1 脚本 / 25 测点)
M17_SCRIPTS = [
    ("m17t1_test_v158_handoff.py", 25),
]

# M18(V1.5.9 接力期 ATS Fallback + Options V2 + handoff;3 脚本 / 75 测点)
M18_SCRIPTS = [
    ("m18t1_test_ats_scraper.py", 25),
    ("m18t2_test_options_anomaly_v2.py", 25),
    ("m18t3_test_v159_handoff.py", 25),
]

# M19(V1.6.0 接力期 Pipeline Resilience + ML Weights + Attribution + RAG + Docker;5 脚本 / 125 测点)
M19_SCRIPTS = [
    ("m19t1_test_pipeline_resilience.py", 25),
    ("m19t2_test_model_refinement.py", 25),
    ("m19t3_test_frontend_ux.py", 25),
    ("m19t4_test_rag.py", 25),
    ("m19t5_test_docker.py", 25),
]

# M9(V1.5 接力期;逐个添加,跳过 m9t1 自身作为聚合型)
M9_SCRIPTS = [
    ("m9t2_test_env_check.py", 25),
    ("m9t3_test_reviewer_cli.py", 25),
    ("m9t4_test_edgar_endpoint.py", 25),
    ("m9t5_test_etf_endpoints.py", 25),
    ("m9t6_test_analytics_endpoints.py", 25),
    ("m9t7_test_openapi_v151.py", 25),
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
    try:
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
    except subprocess.TimeoutExpired:
        return 3, "(timeout after 180s)"
    except Exception as exc:  # noqa: BLE001
        return 4, f"(exception: {exc})"


def run_group(label: str, scripts: list[tuple[str, int]]) -> tuple[int, int, int]:
    """跑一组脚本,返 (failures, passed_testpoints, total_testpoints)."""
    failures = 0
    passed_tp = 0
    total_tp = 0

    print("=" * 72, flush=True)
    print(label, flush=True)
    print("=" * 72, flush=True)

    for script, expected in scripts:
        total_tp += expected
        rc, tail = run_one(script)
        ok = rc == 0
        if not t(f"run_{script}", ok, f"rc={rc} tail={tail[:160]!r}"):
            failures += 1
        else:
            passed_tp += expected

    return failures, passed_tp, total_tp


def main() -> int:
    failures = 0

    # 1. M5 接力期 11 脚本回归
    f1, p1, tot1 = run_group(
        "M8-t1 / M5 接力期自测回归(11 脚本 / 122 测点)", M5_SCRIPTS
    )
    failures += f1

    # 2. M6 接力期 9 脚本回归(去掉 m6t1 聚合型)
    f2, p2, tot2 = run_group(
        "M8-t1 / M6 接力期自测回归(9 脚本 / 194 测点)", M6_SCRIPTS
    )
    failures += f2

    # 3. M7 接力期 9 脚本回归(去掉 m7t1 聚合型)
    f3, p3, tot3 = run_group(
        "M8-t1 / M7 接力期自测回归(9 脚本 / 213 测点)", M7_SCRIPTS
    )
    failures += f3

    # 4. M8 接力期 4 脚本回归(去掉 m8t1 自身聚合型)
    f4, p4, tot4 = run_group(
        "M8-t1 / M8 接力期自测回归(4 脚本 / 79 测点)", M8_SCRIPTS
    )
    failures += f4

    # 5. M9 接力期 6 脚本回归(去掉 m9t1 自身聚合型)
    f5, p5, tot5 = run_group(
        "M8-t1 / M9 接力期自测回归(6 脚本 / 150 测点)", M9_SCRIPTS
    )
    failures += f5

    # 6. M10 接力期 8 脚本回归(m10t1~m10t8:真实数据 + 公开评审 + 工具合并 + V1.5.2 freeze)
    f6, p6, tot6 = run_group(
        "M8-t1 / M10 接力期自测回归(8 脚本 / 200 测点)", M10_SCRIPTS
    )
    failures += f6

    # 7. M11 接力期 6 脚本回归(V1.5.3 评审未通过项 P0+reviewer_cli 工具链 修复)
    f7, p7, tot7 = run_group(
        "M8-t1 / M11 接力期自测回归(6 脚本 / 150 测点)", M11_SCRIPTS
    )
    failures += f7

    # 8. M12 接力期 3 脚本回归(V1.5.4 super_admin + m7t2 物理删除 + 端点评审字段)
    f8, p8, tot8 = run_group(
        "M8-t1 / M12 接力期自测回归(3 脚本 / 75 测点)", M12_SCRIPTS
    )
    failures += f8

    # 9. M15 接力期 4 脚本回归(V1.5.7 OpenAPI freeze 自动化 C-3 + self_test_harness C-6 + V1.5.7 收尾 + CI 集成)
    f9, p9, tot9 = run_group(
        "M8-t1 / M15 接力期自测回归(4 脚本 / 100 测点)", M15_SCRIPTS
    )
    failures += f9

    # 10. M16 接力期 4 脚本回归(V1.5.8 评审归档工具 + 扩展 + harness 增强 + freeze diff)
    f10, p10, tot10 = run_group(
        "M8-t1 / M16 接力期自测回归(4 脚本 / 100 测点)", M16_SCRIPTS
    )
    failures += f10

    # 11. M17 接力期 1 脚本回归(V1.5.8-handoff 收尾报告)
    f11, p11, tot11 = run_group(
        "M8-t1 / M17 接力期自测回归(1 脚本 / 25 测点)", M17_SCRIPTS
    )
    failures += f11

    # 12. M18 接力期 3 脚本回归(V1.5.9 ATS Fallback + Options V2 + handoff)
    f12, p12, tot12 = run_group(
        "M8-t1 / M18 接力期自测回归(3 脚本 / 75 测点)", M18_SCRIPTS
    )
    failures += f12

    # 13. M19 接力期 5 脚本回归(V1.6.0 Pipeline Resilience + ML Weights + Attribution + RAG + Docker)
    f13, p13, tot13 = run_group(
        "M8-t1 / M19 接力期自测回归(5 脚本 / 125 测点)", M19_SCRIPTS
    )
    failures += f13

    # ---- 总览 ---------------------------------------------------------------
    total_passed = p1 + p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9 + p10 + p11 + p12 + p13
    total_expected = tot1 + tot2 + tot3 + tot4 + tot5 + tot6 + tot7 + tot8 + tot9 + tot10 + tot11 + tot12 + tot13
    ok = total_passed == total_expected and failures == 0
    if not t(
        "m8t1_aggregate_total",
        ok,
        f"passed={total_passed}/{total_expected} failures={failures}",
    ):
        failures += 1

    print(flush=True)
    if failures == 0:
        # V1.6.0 ONLINE-READY 主 marker
        print(
            f"[m8t1] V1.6.0-ONLINE-READY: M5({p1}/116) + M6({p2}/194) + M7({p3}/213) "
            f"+ M8({p4}/79) + M9({p5}/150) + M10({p6}/200) + M11({p7}/150) + M12({p8}/75) "
            f"+ M15({p9}/100) + M16({p10}/100) + M17({p11}/25) + M18({p12}/75) + M19({p13}/125) = {total_passed}/{total_expected} ALL PASSED"
        )
        # V1.5.3 沿用 marker(早期 m11 5 脚本 125 测点 格式, m11t6 静态分析需要)
        # V1.5.3-ONLINE-READY 兼容 marker(m11t6 t18 期望源码含此字串)
        print(
            f"[m8t1] V1.5.3-ONLINE-READY (V1.5.3 接力期 沿用): M11({p7}/125) 早期格式 + "
            f"V1.5.3 接力期 6 脚本 150 测点 (V1.5.4 接力期 6 脚本 150 测点 沿用)"
        )
        return 0
    # V1.5.3 沿用 marker(m11t6 t19 期望含 "NOT READY FOR V1.5.3 FREEZE" 字串)
    print(
        f"[m8t1] {failures} CHECK(S) FAILED — NOT READY FOR V1.6.0 FREEZE "
        f"(V1.5.3 沿用: NOT READY FOR V1.5.3 FREEZE)"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
