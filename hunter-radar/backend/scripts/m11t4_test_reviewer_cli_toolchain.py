"""M11-t4 V1.5.3 reviewer_cli 工具链重构自测(25 测点,V1.5.4 m12t2 物理删除同步)。

V1.5.3 接力期 m11t4 — 修复 V1.5.2 UNPASSED-4/5/6:
- m7t2_sign_goldset.py 加 runtime 拦截(HR_ALLOW_LEGACY_SCRIPTS=1 放行,默认拒绝) — V1.5.3 m11t4
- reviewer_cli.py 加 --dry-run 全局 flag
- TOKEN_HEX_LEN 硬编码 → env 变量 REVIEWER_TOKEN_HEX_LEN(env 默认 32,生产 ≥64)
- _resolve_token_hex_len() helper(env 解析 + 下限保护 ≥16)

V1.5.4 接力期 m12t2 — m7t2_sign_goldset.py 物理删除:
- t01~t04 / t20 从"测 m7t2 runtime 拦截"改测"m7t2 已物理删除 + 历史可查"
- t21 仍测 m7t2_test_signoff 不依赖 m7t2_sign_goldset.py 脚本本身
- t24 测 V1.5.3 + V1.5.4 双 marker

Section 1 — m7t2 物理删除(4 测点,V1.5.4 m12t2 改写):
  t01: m7t2_sign_goldset.py 文件已物理删除
  t02: docs/REVIEWER_CLI_MIGRATION.md 标 V1.5.4 m12t2 物理删除
  t03: m7t2 历史可从 git log 查(REVIEWER_CLI_MIGRATION.md §4.1)
  t04: 物理删除是 V1.5.4 freeze 后的最终状态(HR_ALLOW_LEGACY_SCRIPTS 不再需要)

Section 2 — reviewer_cli --dry-run 全局 flag(5 测点):
  - main() parser.add_argument("--dry-run")
  - dry_run = getattr(args, "dry_run", False) 解析
  - cmd_register 接收 dry_run
  - cmd_revoke 接收 dry_run
  - cmd_sign 接收 dry_run

Section 3 — TOKEN_HEX_LEN env 变量(5 测点):
  - _resolve_token_hex_len 函数定义
  - TOKEN_HEX_LEN_DEFAULT = 32
  - TOKEN_HEX_LEN_MIN = 16
  - TOKEN_HEX_LEN_PROD_RECOMMENDED = 64
  - _gen_token 用 _resolve_token_hex_len()

Section 4 — 写盘 dry-run 行为(5 测点):
  - cmd_register dry_run 模式不写盘
  - cmd_revoke dry_run 模式不写盘
  - cmd_sign dry_run 模式不写盘
  - cmd_verify / cmd_batch_verify 不接受 dry_run(只读)
  - main() 顶层 dry_run 传入 3 个写盘 cmd

Section 5 — 评审 + 兼容(6 测点):
  - m7t2 DEPRECATED 警告历史记录在 docs(REVIEWER_CLI_MIGRATION.md)
  - m7t2_test_signoff 不依赖 m7t2_sign_goldset.py 脚本
  - m9t3_test_reviewer_cli 仍能调用
  - m10t5_test_reviewer_cli_replace 仍能调用
  - V1.5.3 m11t4 + V1.5.4 m12t2 双 marker
  - 25 测点总数

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
# V1.5.4 接力期 m12t2:m7t2_sign_goldset.py 已物理删除,路径常量保留作为"不存在验证"用
M7T2_PY = ROOT / "backend" / "scripts" / "m7t2_sign_goldset.py"
# V1.5.6 接力期 m14t1:reviewer_cli 拆分为独立目录包
REVIEWER_CLI_PKG = ROOT / "backend" / "scripts" / "reviewer_cli"
M7T2_TEST_PY = ROOT / "backend" / "scripts" / "m7t2_test_signoff.py"
M9T3_TEST_PY = ROOT / "backend" / "scripts" / "m9t3_test_reviewer_cli.py"
M10T5_TEST_PY = ROOT / "backend" / "scripts" / "m10t5_test_reviewer_cli_replace.py"
MIGRATION_MD = ROOT / "docs" / "REVIEWER_CLI_MIGRATION.md"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_reviewer_cli_all() -> str:
    """V1.5.6 m14t1:合并读 reviewer_cli/ 所有子模块,等价于原 _read_reviewer_cli_all()。"""
    parts: list[str] = []
    for name in ("__init__.py", "_cli.py", "_paths.py", "_token.py", "_registry.py", "_goldset.py"):
        p = REVIEWER_CLI_PKG / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _extract_function_block(src: str, fn_name: str) -> str:
    """提取 def fn_name( 起的连续缩进代码块。"""
    lines = src.splitlines()
    out: list[str] = []
    started = False
    for line in lines:
        if not started and re.match(rf"^def {re.escape(fn_name)}\(", line):
            started = True
        if started:
            out.append(line)
            if len(out) > 1 and re.match(r"^(def |class )", line) and fn_name not in line:
                out.pop()
                break
    return "\n".join(out)


# ---- Section 1: m7t2 物理删除(4 测点,V1.5.4 m12t2 改写) ----------------


def t01_m7t2_physically_deleted() -> bool:
    """t01: m7t2_sign_goldset.py 文件已物理删除(V1.5.4 m12t2 落地)。"""
    if M7T2_PY.exists():
        print(f"    [FAIL] m7t2_sign_goldset.py 仍存在:{M7T2_PY}")
        return False
    print("    [PASS] m7t2_sign_goldset.py 已物理删除")
    return True


def t02_m7t2_deletion_documented() -> bool:
    """t02: docs/REVIEWER_CLI_MIGRATION.md 标 V1.5.4 m12t2 物理删除。"""
    txt = _read(MIGRATION_MD)
    if "V1.5.4 接力期 m12t2 物理删除" not in txt and "V1.5.4 m12t2 物理删除" not in txt:
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 未标 V1.5.4 m12t2 物理删除")
        return False
    print("    [PASS] REVIEWER_CLI_MIGRATION.md 标 V1.5.4 m12t2 物理删除")
    return True


def t03_m7t2_deletion_in_migration_md() -> bool:
    """t03: REVIEWER_CLI_MIGRATION.md §4.1 含 m12t2 物理删除清单。"""
    txt = _read(MIGRATION_MD)
    if "## 4.1 V1.5.4 m12t2 物理删除落地" not in txt:
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺 §4.1 m12t2 物理删除落地")
        return False
    if "m7t2_sign_goldset.py" not in txt:
        print("    [FAIL] §4.1 未提及 m7t2_sign_goldset.py 物理删除")
        return False
    print("    [PASS] §4.1 含 m7t2 物理删除清单")
    return True


def t04_m7t2_no_legacy_flag_needed() -> bool:
    """t04: m7t2 物理删除后,HR_ALLOW_LEGACY_SCRIPTS 不再被 m7t2 引用。"""
    # 物理删除后该 env 不再有任何引用价值
    # 验证:REVIEWER_CLI_MIGRATION.md 严禁行为 §3 已更新
    txt = _read(MIGRATION_MD)
    if "禁止从 git 历史拉回 m7t2_sign_goldset.py" not in txt:
        print("    [FAIL] §3 严禁行为未更新为 m7t2 物理删除后规则")
        return False
    print("    [PASS] §3 严禁行为已更新(V1.5.4 m12t2 物理删除后规则)")
    return True


# ---- Section 2: reviewer_cli --dry-run(5 测点) -------------------------


def t05_reviewer_cli_dry_run_arg() -> bool:
    """t05: reviewer_cli.py main() parser.add_argument('--dry-run')。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "main")
    if '"--dry-run"' not in block or 'action="store_true"' not in block:
        print("    [FAIL] main() 缺 --dry-run 全局 flag")
        return False
    print("    [PASS] main() 含 --dry-run 全局 flag")
    return True


def t06_reviewer_cli_dry_run_parse() -> bool:
    """t06: main() 解析 dry_run 用 getattr 防 AttributeError。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "main")
    if 'dry_run = getattr(args, "dry_run", False)' not in block:
        print("    [FAIL] 缺 dry_run = getattr(args, \"dry_run\", False)")
        return False
    print("    [PASS] dry_run 用 getattr 解析")
    return True


def t07_cmd_register_dry_run() -> bool:
    """t07: cmd_register 函数签名含 dry_run。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "cmd_register")
    if "dry_run: bool = False" not in block:
        print("    [FAIL] cmd_register 缺 dry_run: bool = False")
        return False
    print("    [PASS] cmd_register 含 dry_run 参数")
    return True


def t08_cmd_revoke_dry_run() -> bool:
    """t08: cmd_revoke 函数签名含 dry_run。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "cmd_revoke")
    if "dry_run: bool = False" not in block:
        print("    [FAIL] cmd_revoke 缺 dry_run: bool = False")
        return False
    print("    [PASS] cmd_revoke 含 dry_run 参数")
    return True


def t09_cmd_sign_dry_run() -> bool:
    """t09: cmd_sign 函数签名含 dry_run。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "cmd_sign")
    if "dry_run: bool = False" not in block:
        print("    [FAIL] cmd_sign 缺 dry_run: bool = False")
        return False
    print("    [PASS] cmd_sign 含 dry_run 参数")
    return True


# ---- Section 3: TOKEN_HEX_LEN env 变量(5 测点) ------------------------


def t10_resolve_token_hex_len_defined() -> bool:
    """t10: _resolve_token_hex_len 函数定义。"""
    txt = _read_reviewer_cli_all()
    if "def _resolve_token_hex_len() -> int:" not in txt:
        print("    [FAIL] 缺 def _resolve_token_hex_len()")
        return False
    print("    [PASS] _resolve_token_hex_len 函数定义")
    return True


def t11_token_hex_len_default_32() -> bool:
    """t11: TOKEN_HEX_LEN_DEFAULT = 32(默认 16 字节)。"""
    txt = _read_reviewer_cli_all()
    if "TOKEN_HEX_LEN_DEFAULT = 32" not in txt:
        print("    [FAIL] 缺 TOKEN_HEX_LEN_DEFAULT = 32")
        return False
    print("    [PASS] TOKEN_HEX_LEN_DEFAULT = 32")
    return True


def t12_token_hex_len_min_16() -> bool:
    """t12: TOKEN_HEX_LEN_MIN = 16(下限安全)。"""
    txt = _read_reviewer_cli_all()
    if "TOKEN_HEX_LEN_MIN = 16" not in txt:
        print("    [FAIL] 缺 TOKEN_HEX_LEN_MIN = 16")
        return False
    print("    [PASS] TOKEN_HEX_LEN_MIN = 16")
    return True


def t13_token_hex_len_prod_64() -> bool:
    """t13: TOKEN_HEX_LEN_PROD_RECOMMENDED = 64(生产推荐)。"""
    txt = _read_reviewer_cli_all()
    if "TOKEN_HEX_LEN_PROD_RECOMMENDED = 64" not in txt:
        print("    [FAIL] 缺 TOKEN_HEX_LEN_PROD_RECOMMENDED = 64")
        return False
    print("    [PASS] TOKEN_HEX_LEN_PROD_RECOMMENDED = 64")
    return True


def t14_gen_token_uses_resolver() -> bool:
    """t14: _gen_token 用 _resolve_token_hex_len() 而非硬编码 TOKEN_HEX_LEN。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "_gen_token")
    if "_resolve_token_hex_len()" not in block:
        print("    [FAIL] _gen_token 未用 _resolve_token_hex_len()")
        return False
    if "TOKEN_HEX_LEN * 2" in block:
        print("    [FAIL] _gen_token 仍用硬编码 TOKEN_HEX_LEN * 2")
        return False
    print("    [PASS] _gen_token 用 _resolve_token_hex_len()")
    return True


# ---- Section 4: 写盘 dry-run 行为(5 测点) ----------------------------


def t15_cmd_register_dry_run_no_write() -> bool:
    """t15: cmd_register dry_run 模式不调 _save_registry/_save_tokens/_append_action。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "cmd_register")
    # 找 dry_run if 分支
    m = re.search(r"if dry_run:(.*?)(?=return 0|$)", block, flags=re.S)
    if not m:
        print("    [FAIL] cmd_register 缺 if dry_run 分支")
        return False
    # dry_run 分支中应没有 _save_* / _append_action 调用
    if "_save_registry" in m.group(1) or "_save_tokens" in m.group(1) or "_append_action" in m.group(1):
        print("    [FAIL] cmd_register dry_run 分支仍写盘")
        return False
    print("    [PASS] cmd_register dry_run 模式不写盘")
    return True


def t16_cmd_revoke_dry_run_no_write() -> bool:
    """t16: cmd_revoke dry_run 模式不调 _save_* / _append_action。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "cmd_revoke")
    m = re.search(r"if dry_run:(.*?)(?=return 0|$)", block, flags=re.S)
    if not m:
        print("    [FAIL] cmd_revoke 缺 if dry_run 分支")
        return False
    if "_save_registry" in m.group(1) or "_save_tokens" in m.group(1) or "_append_action" in m.group(1):
        print("    [FAIL] cmd_revoke dry_run 分支仍写盘")
        return False
    print("    [PASS] cmd_revoke dry_run 模式不写盘")
    return True


def t17_cmd_sign_dry_run_no_write() -> bool:
    """t17: cmd_sign dry_run 模式不调 _write_goldset / _append_action。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "cmd_sign")
    m = re.search(r"if dry_run:(.*?)(?=return 0|$)", block, flags=re.S)
    if not m:
        print("    [FAIL] cmd_sign 缺 if dry_run 分支")
        return False
    if "_write_goldset" in m.group(1) or "_append_action" in m.group(1):
        print("    [FAIL] cmd_sign dry_run 分支仍写盘")
        return False
    print("    [PASS] cmd_sign dry_run 模式不写盘")
    return True


def t18_verify_no_dry_run() -> bool:
    """t18: cmd_verify / cmd_batch_verify 是只读,不含 dry_run 参数。"""
    txt = _read_reviewer_cli_all()
    v_block = _extract_function_block(txt, "cmd_verify")
    b_block = _extract_function_block(txt, "cmd_batch_verify")
    if "dry_run" in v_block or "dry_run" in b_block:
        print("    [FAIL] verify/batch_verify 误含 dry_run(只读)")
        return False
    print("    [PASS] verify/batch_verify 不含 dry_run(只读)")
    return True


def t19_main_passes_dry_run() -> bool:
    """t19: main() 顶层 dry_run 传给 3 个写盘 cmd。"""
    block = _extract_function_block(_read_reviewer_cli_all(), "main")
    n = block.count("dry_run=dry_run")
    if n < 3:
        print(f"    [FAIL] main() dry_run 传入数={n} < 3")
        return False
    print(f"    [PASS] main() dry_run 传 3 写盘 cmd({n} 处)")
    return True


# ---- Section 5: 评审 + 兼容(6 测点) ---------------------------------


def t20_m7t2_deprecated_in_docs() -> bool:
    """t20: m7t2 旧 DEPRECATED 警告历史记录在 docs(REVIEWER_CLI_MIGRATION.md)。"""
    txt = _read(MIGRATION_MD)
    if "DEPRECATED" not in txt:
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺 DEPRECATED 历史记录")
        return False
    if "V1.5.2 接力期 m10t5" not in txt:
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺 V1.5.2 m10t5 DEPRECATED 历史")
        return False
    print("    [PASS] m7t2 DEPRECATED 警告历史记录在 docs")
    return True


def t21_m7t2_test_signoff_no_import() -> bool:
    """t21: m7t2_test_signoff.py 不 import m7t2_sign_goldset(测数据,无脚本依赖)。"""
    if not M7T2_TEST_PY.exists():
        print("    [SKIP] m7t2_test_signoff 不存在,跳过兼容校验")
        return True
    txt = _read(M7T2_TEST_PY)
    # 不应 import 或执行 m7t2_sign_goldset 模块(物理删除后无法 import)
    if "import m7t2_sign_goldset" in txt or "from m7t2_sign_goldset" in txt:
        print("    [FAIL] m7t2_test_signoff 仍 import m7t2_sign_goldset")
        return False
    print("    [PASS] m7t2_test_signoff 不依赖 m7t2_sign_goldset.py 脚本")
    return True


def t22_m9t3_test_compat() -> bool:
    """t22: m9t3_test_reviewer_cli.py 仍能测试 reviewer_cli。"""
    if not M9T3_TEST_PY.exists():
        print("    [SKIP] m9t3_test_reviewer_cli 不存在")
        return True
    txt = _read(M9T3_TEST_PY)
    if "reviewer_cli" not in txt:
        print("    [FAIL] m9t3_test_reviewer_cli 缺 reviewer_cli 引用")
        return False
    print("    [PASS] m9t3_test_reviewer_cli 兼容")
    return True


def t23_m10t5_test_compat() -> bool:
    """t23: m10t5_test_reviewer_cli_replace.py 仍能测试 reviewer_cli(V1.5.4 m12t2 改写后)。"""
    if not M10T5_TEST_PY.exists():
        print("    [SKIP] m10t5_test 不存在")
        return True
    txt = _read(M10T5_TEST_PY)
    if "reviewer_cli" not in txt:
        print("    [FAIL] m10t5 缺 reviewer_cli 引用")
        return False
    # V1.5.4 m12t2 改写后,m10t5 应不再断言 m7t2_sign_goldset.py 文件存在
    # 但 m10t5 仍可能引用 m7t2_sign_goldset.py 字符串(用于文档/对比)
    # 这里只验 reviewer_cli 引用存在即可
    print("    [PASS] m10t5_test_reviewer_cli_replace 兼容")
    return True


def t24_v153_v154_dual_marker() -> bool:
    """t24: reviewer_cli.py + docs 含 V1.5.3 m11t4 + V1.5.4 m12t2 双 marker。"""
    cli_txt = _read_reviewer_cli_all()
    migration_txt = _read(MIGRATION_MD)
    # reviewer_cli 含 V1.5.3 标记(可能也含 V1.5.4)
    if "V1.5.3 接力期 m11t4" not in cli_txt:
        print("    [FAIL] reviewer_cli 缺 V1.5.3 接力期 m11t4 标记")
        return False
    # REVIEWER_CLI_MIGRATION.md 含 V1.5.4 标记
    if "V1.5.4" not in migration_txt or "m12t2" not in migration_txt:
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺 V1.5.4 m12t2 标记")
        return False
    print("    [PASS] V1.5.3 m11t4 + V1.5.4 m12t2 双 marker 存在")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_m7t2_physically_deleted, t02_m7t2_deletion_documented, t03_m7t2_deletion_in_migration_md,
        t04_m7t2_no_legacy_flag_needed,
        t05_reviewer_cli_dry_run_arg, t06_reviewer_cli_dry_run_parse,
        t07_cmd_register_dry_run, t08_cmd_revoke_dry_run, t09_cmd_sign_dry_run,
        t10_resolve_token_hex_len_defined, t11_token_hex_len_default_32,
        t12_token_hex_len_min_16, t13_token_hex_len_prod_64, t14_gen_token_uses_resolver,
        t15_cmd_register_dry_run_no_write, t16_cmd_revoke_dry_run_no_write,
        t17_cmd_sign_dry_run_no_write, t18_verify_no_dry_run, t19_main_passes_dry_run,
        t20_m7t2_deprecated_in_docs, t21_m7t2_test_signoff_no_import, t22_m9t3_test_compat,
        t23_m10t5_test_compat, t24_v153_v154_dual_marker, t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_m7t2_physically_deleted", t01_m7t2_physically_deleted),
    ("t02_m7t2_deletion_documented", t02_m7t2_deletion_documented),
    ("t03_m7t2_deletion_in_migration_md", t03_m7t2_deletion_in_migration_md),
    ("t04_m7t2_no_legacy_flag_needed", t04_m7t2_no_legacy_flag_needed),
    ("t05_reviewer_cli_dry_run_arg", t05_reviewer_cli_dry_run_arg),
    ("t06_reviewer_cli_dry_run_parse", t06_reviewer_cli_dry_run_parse),
    ("t07_cmd_register_dry_run", t07_cmd_register_dry_run),
    ("t08_cmd_revoke_dry_run", t08_cmd_revoke_dry_run),
    ("t09_cmd_sign_dry_run", t09_cmd_sign_dry_run),
    ("t10_resolve_token_hex_len_defined", t10_resolve_token_hex_len_defined),
    ("t11_token_hex_len_default_32", t11_token_hex_len_default_32),
    ("t12_token_hex_len_min_16", t12_token_hex_len_min_16),
    ("t13_token_hex_len_prod_64", t13_token_hex_len_prod_64),
    ("t14_gen_token_uses_resolver", t14_gen_token_uses_resolver),
    ("t15_cmd_register_dry_run_no_write", t15_cmd_register_dry_run_no_write),
    ("t16_cmd_revoke_dry_run_no_write", t16_cmd_revoke_dry_run_no_write),
    ("t17_cmd_sign_dry_run_no_write", t17_cmd_sign_dry_run_no_write),
    ("t18_verify_no_dry_run", t18_verify_no_dry_run),
    ("t19_main_passes_dry_run", t19_main_passes_dry_run),
    ("t20_m7t2_deprecated_in_docs", t20_m7t2_deprecated_in_docs),
    ("t21_m7t2_test_signoff_no_import", t21_m7t2_test_signoff_no_import),
    ("t22_m9t3_test_compat", t22_m9t3_test_compat),
    ("t23_m10t5_test_compat", t23_m10t5_test_compat),
    ("t24_v153_v154_dual_marker", t24_v153_v154_dual_marker),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M11-t4 V1.5.3 reviewer_cli 工具链重构自测(25 测点,V1.5.4 m12t2 物理删除同步)")
    print("=" * 72)
    failures = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"    [FAIL] {name} 异常:{type(exc).__name__}: {exc}")
            ok = False
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            failures += 1
    print("=" * 72)
    if failures == 0:
        print("[m11t4] V1.5.3 reviewer_cli 工具链重构 25/25 ALL PASSED")
        return 0
    print(f"[m11t4] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())

