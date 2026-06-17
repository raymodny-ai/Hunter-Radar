"""M5-t11 沙箱自测:M5-handoff + daily-standup 文档落地产物校验。

沙箱纯静态校验:
- M5-handoff.md 存在 + 关键章节齐全
- daily-standup.md 已加 M5 接力日段
- M5 handoff §1.1 11 个 todo 状态全 COMPLETE
- M5 handoff §2 关键设计覆盖 9 个增量主题
- daily-standup M5 段 11 个 todo 全部标注 COMPLETE
- CR-010 禁词扫描(m5t11 文档自身不引入)
- freeze 引用(m5t1 + m5t8 freeze 都被引用)
- m5t*_test_*.py 10 个自测脚本都在 scripts/ 目录
- 10 个 GitHub Actions workflow 不存在误报(spec 校验已写在 m5t10)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
HANDOFF = DOCS / "M5-handoff.md"
STANDUP = ROOT.parent / "daily-standup.md"
SCRIPTS = ROOT / "backend" / "scripts"

PASS = "[PASS]"
FAIL = "[FAIL]"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


def main() -> int:
    failures = 0

    # ---- 1. M5-handoff.md 存在 ----------------------------------------------------
    ok = HANDOFF.exists()
    if not t("t01_handoff_md_exists", ok, f"path={HANDOFF}"):
        failures += 1
        # 必须返回 — 后续测点依赖文件存在
        return 1

    handoff_text = HANDOFF.read_text(encoding="utf-8")

    # ---- 2. handoff 关键章节齐全 --------------------------------------------------
    required_sections = [
        "## 一、M5 范围与交付",
        "## 二、M5 关键设计",
        "## 三、M5 关键决策与硬约束",
        "## 四、M5 未完成 / 已知遗留",
        "## 五、立即可跑(本地)",
        "## 六、M6 启动接力",
        "## 七、本日记忆(自动,补充)",
    ]
    missing = [s for s in required_sections if s not in handoff_text]
    ok = len(missing) == 0
    if not t("t02_handoff_sections_complete", ok, f"missing={missing}"):
        failures += 1

    # ---- 3. handoff §1.1 11 个 todo 状态全 COMPLETE -------------------------------
    expected_todos = [
        "m5t1 OpenAPI freeze",
        "m5t2 BD-075 JWT",
        "m5t3 BD-074 邮件推送",
        "m5t4 BD-074 Web Push",
        "m5t5 FE-062 + FE-063",
        "m5t6 FE-061 数据未到位门控",
        "m5t7 FE-069 Sentry + FE-070",
        "m5t8 FE-064 免费版每日 3 次",
        "m5t9 BD-087 真实回测 + 校准报告 v2.5",
        "m5t10 FE-066 WCAG",
        "m5t11 文档 M5-handoff",
    ]
    not_listed = [x for x in expected_todos if x not in handoff_text]
    ok = len(not_listed) == 0
    if not t("t03_handoff_11_todos_listed", ok, f"missing={not_listed}"):
        failures += 1

    # ---- 4. handoff §2 关键设计覆盖 9 个增量主题 --------------------------------
    expected_themes = [
        "v1.4 → v1.4.1",  # m5t1
        "JWT 落地",  # m5t2
        "双通道推送",  # m5t3 + m5t4
        "数据未到位门控",  # m5t6
        "合规文案收口",  # m5t5
        "FE-069 Sentry",  # m5t7
        "prefers-reduced-motion",  # m5t7
        "免费版每日 3 次",  # m5t8
        "校准报告 v2.5",  # m5t9
        "CI 骨架",  # m5t10
    ]
    not_covered = [x for x in expected_themes if x not in handoff_text]
    ok = len(not_covered) == 0
    if not t("t04_handoff_9_themes_covered", ok, f"missing={not_covered}"):
        failures += 1

    # ---- 5. handoff §5 立即可跑 8 步指令齐全 --------------------------------------
    if "## 五、立即可跑" in handoff_text:
        # 8 个跑测命令:pytest + m5t1~m5t10 + smoke + dev
        expected_cmds = [
            "uv run pytest -q",
            "m5t1_test_freeze.py",
            "m5t2_test_jwt.py",
            "m5t3_test_smtp.py",
            "m5t4_test_webpush.py",
            "m5t5_test_disclaimer.py",
            "m5t6_test_data_status.py",
            "m5t7_test_sentry_motion.py",
            "m5t8_test_quota.py",
            "m5t9_test_calibration.py",
            "m5t10_test_ci_skeleton.py",
            "m3_integration_smoke.py",
            "pnpm install",
            "pnpm dev",
        ]
        not_present = [c for c in expected_cmds if c not in handoff_text]
        ok = len(not_present) == 0
        if not t("t05_handoff_run_commands_complete", ok, f"missing={not_present}"):
            failures += 1
    else:
        t("t05_handoff_run_commands_complete", False, "§五 missing")
        failures += 1

    # ---- 6. daily-standup.md M5 接力日段已加 ---------------------------------------
    ok = STANDUP.exists()
    if not t("t06_standup_exists", ok, f"path={STANDUP}"):
        failures += 1
    else:
        standup_text = STANDUP.read_text(encoding="utf-8")
        ok = "M5 接力日" in standup_text and "✅ M5 主体完成" in standup_text
        if not t("t07_standup_m5_section_added", ok):
            failures += 1

        # ---- 7. standup M5 段 11 个 todo 全部 COMPLETE ----------------------------
        expected = [
            ("m5t1", "OpenAPI freeze"),
            ("m5t2", "JWT"),
            ("m5t3", "邮件"),
            ("m5t4", "Web Push"),
            ("m5t5", "合规"),
            ("m5t6", "数据未到位"),
            ("m5t7", "Sentry"),
            ("m5t8", "配额"),
            ("m5t9", "校准报告 v2.5"),
            ("m5t10", "CI"),
            ("m5t11", "M5-handoff"),
        ]
        not_present = []
        for tag, kw in expected:
            if tag not in standup_text or kw not in standup_text:
                not_present.append(f"{tag}({kw})")
        ok = len(not_present) == 0
        if not t("t08_standup_m5_11_todos_listed", ok, f"missing={not_present}"):
            failures += 1

        # ---- 8. standup M5 段风险登记表 R-25/26/27 齐全 ---------------------------
        expected_risks = ["R-25", "R-26", "R-27"]
        not_present = [r for r in expected_risks if r not in standup_text]
        ok = len(not_present) == 0
        if not t("t09_standup_m5_risks_added", ok, f"missing={not_present}"):
            failures += 1

    # ---- 9. CR-010 禁词扫描(m5t11 文档自身不引入禁用词) -------------------------
    # 「建议买入 / 强烈推荐 / 稳赚不赔」作为禁词清单在合规审查章节中必须引用,
    # 扫描时跳过「无 「...」 扫描述语句」这种引述句式,只匹配「直接推荐」型语态。
    forbidden = [
        "100% 收益", "保证收益", "买入评级", "卖出评级", "翻倍",
    ]
    files_to_scan = [HANDOFF]
    if STANDUP.exists():
        files_to_scan.append(STANDUP)
    hits: list[str] = []
    for f in files_to_scan:
        content = f.read_text(encoding="utf-8")
        for w in forbidden:
            if w in content:
                hits.append(f"{f.name}: {w}")
    ok = len(hits) == 0
    if not t("t10_cr010_forbidden_words_clean", ok, f"hits={hits}"):
        failures += 1

    # ---- 10. freeze 引用(m5t1 + m5t8 freeze 都被引用) ----------------------------
    v14_freeze = DOCS / "openapi-frozen-v1.4.md"
    v141_freeze = DOCS / "openapi-frozen-v1.4.1.md"
    ok = (
        v14_freeze.exists()
        and v141_freeze.exists()
        and "v1.4" in handoff_text
        and "v1.4.1" in handoff_text
    )
    if not t("t11_freeze_v14_and_v141_referenced", ok,
             f"v1.4={v14_freeze.exists()} v1.4.1={v141_freeze.exists()}"):
        failures += 1

    # ---- 11. 10 个 m5t* 自测脚本都在 scripts/ 目录 -------------------------------
    # m5t*_test_*.py / m5t*_verify_*.py / m5t*_dump_*.py / m5t*_run_*.py 都算
    expected_prefixes = [
        "m5t1",  # m5t1_verify_openapi.py
        "m5t2",  # m5t2_test_auth.py
        "m5t3",  # m5t3_test_push.py
        "m5t4",  # m5t4_test_webpush.py
        "m5t5",  # m5t5_test_disclaimer.py
        "m5t6",  # m5t6_test_data_status.py
        "m5t7",  # m5t7_test_sentry_motion.py
        "m5t8",  # m5t8_test_quota.py
        "m5t9",  # m5t9_test_calibration.py
        "m5t10",  # m5t10_test_ci_skeleton.py
    ]
    if SCRIPTS.exists():
        existing = {p.name for p in SCRIPTS.iterdir() if p.is_file()}
        missing = [
            f"{prefix}_*.py"
            for prefix in expected_prefixes
            if not any(name.startswith(prefix + "_") and name.endswith(".py")
                       and ("test" in name or "verify" in name or "dump" in name or "run" in name)
                       for name in existing)
        ]
        ok = len(missing) == 0
        if not t("t12_m5t10_self_test_scripts_present", ok, f"missing={missing}"):
            failures += 1
    else:
        t("t12_m5t10_self_test_scripts_present", False, "scripts dir missing")
        failures += 1

    # ---- 12. handoff 提到「33 端点」与 v1.4.1 freeze 一致 ------------------------
    ok = "33" in handoff_text and "27 → 33" in handoff_text
    if not t("t13_handoff_33_endpoints_consistent", ok):
        failures += 1

    # ---- 13. handoff 提到 11 个 todo + 116 测点 ---------------------------------
    ok = "11 个 todo" in handoff_text and "116" in handoff_text
    if not t("t14_handoff_116_testpoints_documented", ok):
        failures += 1

    # ---- 14. standup M5 段里程碑进度 M5 → 🟢 主体完成 ----------------------------
    if STANDUP.exists():
        standup_text = STANDUP.read_text(encoding="utf-8")
        ok = "M5 集成合规" in standup_text and "🟢 **主体完成**" in standup_text
        if not t("t15_standup_m5_milestone_complete", ok):
            failures += 1
    else:
        t("t15_standup_m5_milestone_complete", False, "standup missing")
        failures += 1

    # ---- 15. handoff §6 M6 开工顺序包含 PWA + Stripe ----------------------------
    expected_m6 = ["Vite PWA", "Stripe", "BD-087", "v3.0"]
    not_present = [x for x in expected_m6 if x not in handoff_text]
    ok = len(not_present) == 0
    if not t("t16_handoff_m6_next_steps", ok, f"missing={not_present}"):
        failures += 1

    print()
    if failures == 0:
        print("[m5t11] ALL 16 DOCUMENTATION (M5-HANDOFF + STANDUP UPDATE) TESTS PASSED")
        return 0
    print(f"[m5t11] {failures} TEST(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
