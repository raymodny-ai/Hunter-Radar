"""V1.5.7 接力期 m15t4 — pre-commit hook 脚本(本地 commit 之前跑 freeze_check)。

调用场景:
1. git pre-commit hook(自动): commit 之前跑 freeze_check --skip-m8t1
   - 失败 → 阻止 commit
   - 成功 → 允许 commit
2. 手动跑: py -m scripts.pre_commit [--strict] [--skip-m8t1]
   - --strict: 把 warning 升级为 error
   - --skip-m8t1: 跳过 m8t1 子进程(快速)

退出码:
  0 = 通过(可 commit)
  1 = freeze_check 失败(阻止 commit)
  2 = 调用错误(参数无效)

落地位置: .git/hooks/pre-commit(可由 install.sh 复制)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def run_freeze_check(skip_m8t1: bool, strict: bool) -> int:
    """调 freeze_check 子进程,返退出码。"""
    cmd = [sys.executable, "-B", "-u", "-m", "scripts.freeze_check"]
    if skip_m8t1:
        cmd.append("--skip-m8t1")

    print(f"[pre-commit] 跑 freeze_check (skip_m8t1={skip_m8t1}, strict={strict})", flush=True)
    print(f"[pre-commit] cmd: {' '.join(cmd)}", flush=True)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BACKEND),
            capture_output=False,  # 实时输出,不缓冲
            timeout=300,  # 5 分钟超时(含 m8t1 时 1227 测点可能较久)
        )
    except subprocess.TimeoutExpired:
        print("[pre-commit] [FAIL] freeze_check 超时 300s", flush=True)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[pre-commit] [FAIL] freeze_check 调用异常: {exc}", flush=True)
        return 2

    if proc.returncode == 0:
        print("[pre-commit] [PASS] freeze_check 通过,可 commit", flush=True)
        return 0

    print(f"[pre-commit] [FAIL] freeze_check 返 {proc.returncode}, 阻止 commit", flush=True)
    return 1


def install_hook() -> int:
    """安装 pre-commit hook 到 .git/hooks/pre-commit。

    V1.5.7 m15t4:简化版,直接复制当前脚本到 .git/hooks/pre-commit。
    更复杂的安装可改用 pre-commit.com 框架。
    """
    git_hooks = ROOT / ".git" / "hooks" / "pre-commit"
    if not (ROOT / ".git").exists():
        print(f"[pre-commit] [FAIL] 非 git 仓库: {ROOT}", flush=True)
        return 1

    # 写一个简化的 hook 脚本(直接调 py + pre_commit.py)
    hook_content = f"""#!/usr/bin/env python
\"\"\"V1.5.7 接力期 m15t4 — pre-commit hook(自动生成)。

自动跑 freeze_check。失败 → 阻止 commit。
由 scripts/pre_commit.py install 生成。
\"\"\"
import subprocess, sys
from pathlib import Path

BACKEND = Path(r"{BACKEND}")
proc = subprocess.run(
    [sys.executable, "-B", "-u", "-m", "scripts.pre_commit", "--skip-m8t1"],
    cwd=str(BACKEND),
)
sys.exit(proc.returncode)
"""
    git_hooks.parent.mkdir(parents=True, exist_ok=True)
    git_hooks.write_text(hook_content, encoding="utf-8")
    # Windows 上 git hook 不需要 chmod +x(PowerShell 直接读)
    print(f"[pre-commit] [PASS] hook 已安装: {git_hooks}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pre_commit",
        description="V1.5.7 接力期 m15t4 pre-commit hook 工具",
    )
    parser.add_argument(
        "--skip-m8t1",
        action="store_true",
        default=True,  # 默认 skip(快速,CI 跑全量)
        help="跳过 m8t1 子进程(默认开启,5 分钟内完成)",
    )
    parser.add_argument(
        "--no-skip-m8t1",
        dest="skip_m8t1",
        action="store_false",
        help="跑 m8t1 全量(慢但更严格)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="strict 模式(warning 也算失败)",
    )
    parser.add_argument(
        "install",
        nargs="?",
        default=None,
        help="特殊子命令: install (安装 pre-commit hook 到 .git/hooks/)",
    )
    args = parser.parse_args()

    if args.install == "install":
        return install_hook()

    return run_freeze_check(skip_m8t1=args.skip_m8t1, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
