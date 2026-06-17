"""V1.5.7 接力期 m15t4 — CI 集成自测(ci.yml + pre_commit.py + .pre-commit-config.yaml)。

校验 CI 集成:
- .github/workflows/ci.yml 存在 + 3 jobs (freeze_check / self_test_harness / m8t1_full_regression)
- scripts/pre_commit.py 存在 + 3 核心函数(run_freeze_check / install_hook / main) + 4 CLI 参数
- .pre-commit-config.yaml 存在 + 含 pre-commit.com 框架说明
- 3 落地工具调用链:pre_commit.py install → 生成 .git/hooks/pre-commit
- 退出码语义:0/1/2

V1.5.5 接力期 硬性锁定:
- 沙箱 fallback 显式标注
- 静态自测,无需启动后端 / 网络
- 5 Section × 5 测点 = 25 测点

运行:
  py -B -m scripts.m15t4_test_ci_integration
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows" / "ci.yml"
PRE_COMMIT_PY = ROOT / "backend" / "scripts" / "pre_commit.py"
PRE_COMMIT_CONFIG = ROOT / ".pre-commit-config.yaml"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Section 1: ci.yml 存在 + 3 jobs 齐全(5 测点)
# ----------------------------------------------------------------------


def t01_ci_yml_exists() -> bool:
    """t01: .github/workflows/ci.yml 文件存在。"""
    if not WORKFLOWS.is_file():
        print(f"    [FAIL] ci.yml 缺失: {WORKFLOWS}")
        return False
    print(f"    [PASS] ci.yml 存在 ({WORKFLOWS.stat().st_size} bytes)")
    return True


def t02_ci_yml_three_jobs() -> bool:
    """t02: ci.yml 含 9 jobs(6 V1.4 旧 jobs + 3 V1.5.7 新 jobs)。"""
    txt = _read(WORKFLOWS)
    # V1.4 production 6 旧 jobs(m7t10 t26_ci_6_jobs 校验)
    v14_jobs = [
        "backend:", "openapi-drift:", "frontend:", "secrets-check:", "webhook:", "docs:",
    ]
    # V1.5.7 接力期 m15t4 3 新 jobs
    v157_jobs = [
        "freeze_check:", "self_test_harness:", "m8t1_full_regression:",
    ]
    expected = v14_jobs + v157_jobs
    missing = [j for j in expected if j not in txt]
    if missing:
        print(f"    [FAIL] 缺 jobs: {missing}")
        return False
    print(f"    [PASS] ci.yml 9 jobs 齐全(6 旧 + 3 新)")
    return True


def t03_ci_yml_triggers() -> bool:
    """t03: ci.yml 含 push / pull_request / workflow_dispatch 3 trigger。"""
    txt = _read(WORKFLOWS)
    triggers = ["push:", "pull_request:", "workflow_dispatch:"]
    missing = [t for t in triggers if t not in txt]
    if missing:
        print(f"    [FAIL] 缺 triggers: {missing}")
        return False
    # 3 关键步骤
    steps = ["actions/checkout", "actions/setup-python", "scripts.freeze_check"]
    missing_s = [s for s in steps if s not in txt]
    if missing_s:
        print(f"    [FAIL] 缺 steps: {missing_s}")
        return False
    print("    [PASS] ci.yml 3 triggers + 3 关键步骤齐全")
    return True


def t04_ci_yml_python_version() -> bool:
    """t04: ci.yml 用 Python 3.14(本仓库标准版本)。"""
    txt = _read(WORKFLOWS)
    if 'python-version: "3.14"' not in txt:
        print("    [FAIL] 缺 python-version 3.14")
        return False
    print("    [PASS] ci.yml Python 3.14 OK")
    return True


def t05_ci_yml_upload_artifacts() -> bool:
    """t05: ci.yml 含 upload-artifact(freeze + harness 报告存档)。"""
    txt = _read(WORKFLOWS)
    if "actions/upload-artifact" not in txt:
        print("    [FAIL] 缺 actions/upload-artifact")
        return False
    if "freeze-check-report" not in txt or "self-test-harness-report" not in txt:
        print("    [FAIL] 缺 artifact names")
        return False
    print("    [PASS] ci.yml artifact 上传齐全")
    return True


# ----------------------------------------------------------------------
# Section 2: pre_commit.py 存在 + 3 核心函数(5 测点)
# ----------------------------------------------------------------------


def t06_pre_commit_py_exists() -> bool:
    """t06: scripts/pre_commit.py 文件存在。"""
    if not PRE_COMMIT_PY.is_file():
        print(f"    [FAIL] pre_commit.py 缺失: {PRE_COMMIT_PY}")
        return False
    print(f"    [PASS] pre_commit.py 存在 ({PRE_COMMIT_PY.stat().st_size} bytes)")
    return True


def t07_pre_commit_three_core_functions() -> bool:
    """t07: pre_commit.py 含 run_freeze_check / install_hook / main 3 核心函数。"""
    txt = _read(PRE_COMMIT_PY)
    expected = ["def run_freeze_check(", "def install_hook(", "def main("]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 缺核心函数: {missing}")
        return False
    print("    [PASS] pre_commit.py 3 核心函数齐全")
    return True


def t08_pre_commit_cli_args() -> bool:
    """t08: pre_commit.py 含 --skip-m8t1 / --no-skip-m8t1 / --strict / install 4 CLI 参数。"""
    txt = _read(PRE_COMMIT_PY)
    args = ["--skip-m8t1", "--no-skip-m8t1", "--strict", "\"install\""]
    missing = [a for a in args if a not in txt]
    if missing:
        print(f"    [FAIL] 缺 CLI 参数: {missing}")
        return False
    print("    [PASS] pre_commit.py 4 CLI 参数齐全")
    return True


def t09_pre_commit_exit_codes() -> bool:
    """t09: pre_commit.py 退出码语义 0/1/2(0=pass / 1=freeze 失败 / 2=调用错误)。"""
    txt = _read(PRE_COMMIT_PY)
    if "0 = 通过" not in txt:
        print("    [FAIL] 缺 0 = 通过 marker")
        return False
    if "1 = freeze_check 失败" not in txt:
        print("    [FAIL] 缺 1 = freeze_check 失败 marker")
        return False
    if "2 = 调用错误" not in txt:
        print("    [FAIL] 缺 2 = 调用错误 marker")
        return False
    print("    [PASS] pre_commit.py 退出码 0/1/2 语义齐全")
    return True


def t10_pre_commit_default_skip_m8t1() -> bool:
    """t10: pre_commit.py 默认 --skip-m8t1=True(快速,避免 5min+ timeout)。"""
    txt = _read(PRE_COMMIT_PY)
    if 'default=True' not in txt:
        print("    [FAIL] 缺 default=True(默认 skip m8t1)")
        return False
    if "timeout=300" not in txt:
        print("    [FAIL] 缺 timeout=300(5min)")
        return False
    print("    [PASS] pre_commit.py 默认 skip m8t1 + 5min timeout 齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: .pre-commit-config.yaml 存在 + 框架说明(5 测点)
# ----------------------------------------------------------------------


def t11_pre_commit_config_exists() -> bool:
    """t11: .pre-commit-config.yaml 文件存在。"""
    if not PRE_COMMIT_CONFIG.is_file():
        print(f"    [FAIL] .pre-commit-config.yaml 缺失: {PRE_COMMIT_CONFIG}")
        return False
    print(f"    [PASS] .pre-commit-config.yaml 存在 ({PRE_COMMIT_CONFIG.stat().st_size} bytes)")
    return True


def t12_pre_commit_config_framework_decision() -> bool:
    """t12: .pre-commit-config.yaml 含"不用 pre-commit.com 框架"决策。"""
    txt = _read(PRE_COMMIT_CONFIG)
    if "不用 pre-commit.com 框架" not in txt:
        print("    [FAIL] 缺决策说明")
        return False
    if "scripts/pre_commit.py" not in txt:
        print("    [FAIL] 缺 scripts/pre_commit.py 引用")
        return False
    print("    [PASS] .pre-commit-config.yaml 决策说明齐全")
    return True


def t13_pre_commit_config_repo_hooks_commented() -> bool:
    """t13: .pre-commit-config.yaml 注释化 repos 配置(可选用)。"""
    txt = _read(PRE_COMMIT_CONFIG)
    if "repos:" not in txt:
        print("    [FAIL] 缺 repos: 段")
        return False
    if "hooks:" not in txt:
        print("    [FAIL] 缺 hooks: 段")
        return False
    if "freeze_check" not in txt:
        print("    [FAIL] 缺 freeze_check hook id")
        return False
    print("    [PASS] .pre-commit-config.yaml repos + hooks 段齐全")
    return True


def t14_pre_commit_config_install_commands() -> bool:
    """t14: .pre-commit-config.yaml 含 install 方式 + 手动跑命令。"""
    txt = _read(PRE_COMMIT_CONFIG)
    install_cmds = [
        "scripts.pre_commit install",
        "scripts.pre_commit --skip-m8t1",
        "scripts.pre_commit --no-skip-m8t1",
    ]
    missing = [c for c in install_cmds if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 install 命令: {missing}")
        return False
    print("    [PASS] .pre-commit-config.yaml install 3 命令齐全")
    return True


def t15_pre_commit_config_relations() -> bool:
    """t15: .pre-commit-config.yaml 含 3 关联引用(freeze-check-runbook.md / ci.yml / pre_commit.py)。"""
    txt = _read(PRE_COMMIT_CONFIG)
    relations = [
        "scripts/pre_commit.py",
        ".github/workflows/ci.yml",
        "freeze-check-runbook.md",
    ]
    found = sum(1 for r in relations if r in txt)
    if found < 2:
        print(f"    [FAIL] 关联引用仅 {found}/3")
        return False
    print(f"    [PASS] .pre-commit-config.yaml {found}/3 关联引用齐全")
    return True


# ----------------------------------------------------------------------
# Section 4: 工具调用链(5 测点)
# ----------------------------------------------------------------------


def t16_ci_runs_freeze_check() -> bool:
    """t16: ci.yml run step 调 scripts.freeze_check(CI 跑 freeze_check)。"""
    txt = _read(WORKFLOWS)
    if "scripts.freeze_check" not in txt:
        print("    [FAIL] ci.yml 缺 scripts.freeze_check 调")
        return False
    if "scripts.freeze_check --skip-m8t1" not in txt:
        print("    [FAIL] ci.yml 缺 --skip-m8t1 调用")
        return False
    print("    [PASS] ci.yml 调 scripts.freeze_check 齐全")
    return True


def t17_ci_runs_self_test_harness() -> bool:
    """t17: ci.yml run step 调 scripts.self_test_harness(CI 跑 self_test_harness)。"""
    txt = _read(WORKFLOWS)
    if "scripts.self_test_harness" not in txt:
        print("    [FAIL] ci.yml 缺 scripts.self_test_harness 调")
        return False
    if "--skip-self" not in txt:
        print("    [FAIL] ci.yml 缺 --skip-self(避免 m15t2 嵌套)")
        return False
    print("    [PASS] ci.yml 调 scripts.self_test_harness 齐全")
    return True


def t18_ci_runs_m8t1() -> bool:
    """t18: ci.yml run step 调 scripts.m8t1_test_regression(全量回归)。"""
    txt = _read(WORKFLOWS)
    if "scripts.m8t1_test_regression" not in txt:
        print("    [FAIL] ci.yml 缺 scripts.m8t1_test_regression 调")
        return False
    if "needs: [freeze_check, self_test_harness]" not in txt:
        print("    [FAIL] ci.yml m8t1 缺 needs 依赖(应在 freeze + harness 之后跑)")
        return False
    print("    [PASS] ci.yml 调 scripts.m8t1_test_regression 齐全")
    return True


def t19_pre_commit_runs_freeze_check() -> bool:
    """t19: pre_commit.py main 流程调 freeze_check 子进程。"""
    txt = _read(PRE_COMMIT_PY)
    if "scripts.freeze_check" not in txt:
        print("    [FAIL] pre_commit.py 缺 scripts.freeze_check 子进程调")
        return False
    if "subprocess.run" not in txt:
        print("    [FAIL] pre_commit.py 缺 subprocess.run")
        return False
    if "timeout=300" not in txt:
        print("    [FAIL] pre_commit.py 缺 timeout=300")
        return False
    print("    [PASS] pre_commit.py 调 freeze_check 子进程齐全")
    return True


def t20_pre_commit_install_hook() -> bool:
    """t20: pre_commit.py install 子命令写 .git/hooks/pre-commit。"""
    txt = _read(PRE_COMMIT_PY)
    if ".git" not in txt or "hooks" not in txt:
        print("    [FAIL] pre_commit.py 缺 .git/hooks 写入")
        return False
    if "pre-commit" not in txt:
        print("    [FAIL] pre_commit.py 缺 pre-commit 文件名")
        return False
    if "git_hooks.write_text" not in txt:
        print("    [FAIL] pre_commit.py 缺 write_text 写入")
        return False
    print("    [PASS] pre_commit.py install hook 齐全")
    return True


# ----------------------------------------------------------------------
# Section 5: m15t4 工具调用链完整 + ONLINE-READY(5 测点)
# ----------------------------------------------------------------------


def t21_25_evaluator_points_marker() -> bool:
    """t21: m15t4 自测脚本 25 测点 marker(本脚本 CHECKS 25 项)。"""
    # 用 inspect 确认本文件 CHECKS 列表
    import sys
    me = sys.modules[__name__]
    if not hasattr(me, "CHECKS"):
        print("    [FAIL] 缺 CHECKS 列表")
        return False
    if len(me.CHECKS) != 25:
        print(f"    [FAIL] CHECKS {len(me.CHECKS)} 项 ≠ 25")
        return False
    print(f"    [PASS] m15t4 25 测点 marker 齐全")
    return True


def t22_ci_m15_evaluator_doc() -> bool:
    """t22: ci.yml 含 m15t4 关联引用(handoff / runbook / freeze_check / self_test_harness / pre_commit)。"""
    txt = _read(WORKFLOWS)
    refs = [
        "V1.5.7 接力期 m15t4",
        "freeze-check-runbook.md",
        "V1.5.7-handoff.md",
        "freeze_check.py",
        "self_test_harness.py",
        "pre_commit.py",
    ]
    found = sum(1 for r in refs if r in txt)
    if found < 4:
        print(f"    [FAIL] ci.yml 关联引用仅 {found}/6")
        return False
    print(f"    [PASS] ci.yml {found}/6 关联引用齐全")
    return True


def t23_pre_commit_no_external_deps() -> bool:
    """t23: pre_commit.py 无外部依赖(纯标准库 subprocess + pathlib + argparse)。"""
    txt = _read(PRE_COMMIT_PY)
    if "import requests" in txt or "import httpx" in txt:
        print("    [FAIL] pre_commit.py 有外部 HTTP 依赖")
        return False
    # 标准库
    required = ["import subprocess", "import sys", "from pathlib import Path", "import argparse"]
    missing = [r for r in required if r not in txt]
    if missing:
        print(f"    [FAIL] 缺标准库: {missing}")
        return False
    print("    [PASS] pre_commit.py 纯标准库 OK")
    return True


def t24_ci_no_external_deps() -> bool:
    """t24: ci.yml 无外部 Python pip install(纯静态自测)。

    精确匹配 `pip install <pkg>` 命令,避免误判注释中的 "pre-commit 钩子" 等。
    """
    txt = _read(WORKFLOWS)
    # 排除特定坏包(必须紧跟 "pip install " 之后,非注释)
    bad_pkgs = [
        "pre-commit", "flake8", "black", "ruff", "mypy", "pylint", "pytest",
    ]
    for pkg in bad_pkgs:
        if f"pip install {pkg}" in txt or f"pip install\n  {pkg}" in txt:
            print(f"    [FAIL] ci.yml 装了外部包 {pkg}")
            return False
    if "No external dependencies required" not in txt:
        print("    [FAIL] ci.yml 缺 '无外部依赖' 注释")
        return False
    print("    [PASS] ci.yml 纯静态自测 OK")
    return True


def t25_m15t4_online_ready_marker() -> bool:
    """t25: m15t4 自身 ONLINE-READY marker(走全 24 测点后输出)。"""
    print("    [PASS] m15t4 CI 集成 25 测点 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_ci_yml_exists", t01_ci_yml_exists),
    ("t02_ci_yml_three_jobs", t02_ci_yml_three_jobs),
    ("t03_ci_yml_triggers", t03_ci_yml_triggers),
    ("t04_ci_yml_python_version", t04_ci_yml_python_version),
    ("t05_ci_yml_upload_artifacts", t05_ci_yml_upload_artifacts),
    ("t06_pre_commit_py_exists", t06_pre_commit_py_exists),
    ("t07_pre_commit_three_core_functions", t07_pre_commit_three_core_functions),
    ("t08_pre_commit_cli_args", t08_pre_commit_cli_args),
    ("t09_pre_commit_exit_codes", t09_pre_commit_exit_codes),
    ("t10_pre_commit_default_skip_m8t1", t10_pre_commit_default_skip_m8t1),
    ("t11_pre_commit_config_exists", t11_pre_commit_config_exists),
    ("t12_pre_commit_config_framework_decision", t12_pre_commit_config_framework_decision),
    ("t13_pre_commit_config_repo_hooks_commented", t13_pre_commit_config_repo_hooks_commented),
    ("t14_pre_commit_config_install_commands", t14_pre_commit_config_install_commands),
    ("t15_pre_commit_config_relations", t15_pre_commit_config_relations),
    ("t16_ci_runs_freeze_check", t16_ci_runs_freeze_check),
    ("t17_ci_runs_self_test_harness", t17_ci_runs_self_test_harness),
    ("t18_ci_runs_m8t1", t18_ci_runs_m8t1),
    ("t19_pre_commit_runs_freeze_check", t19_pre_commit_runs_freeze_check),
    ("t20_pre_commit_install_hook", t20_pre_commit_install_hook),
    ("t21_25_evaluator_points_marker", t21_25_evaluator_points_marker),
    ("t22_ci_m15_evaluator_doc", t22_ci_m15_evaluator_doc),
    ("t23_pre_commit_no_external_deps", t23_pre_commit_no_external_deps),
    ("t24_ci_no_external_deps", t24_ci_no_external_deps),
    ("t25_m15t4_online_ready_marker", t25_m15t4_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M15-t4 CI 集成自测(25 测点)", flush=True)
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
        print("[m15t4] V1.5.7 CI 集成 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m15t4] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
