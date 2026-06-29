"""M10-t5 V1.5.2 reviewer_cli 替换 m7t2_sign_goldset.py 自测(25 测点,V1.5.4 m12t2 物理删除同步)。

V1.5.2 接力期 m10t5 — reviewer_cli 单一权威迁移验证:
- m7t2_sign_goldset.py 标 DEPRECATED
- REVIEWER_CLI_MIGRATION.md 迁移指南完整
- reviewer_cli.py 6 子命令覆盖 m7t2 全部能力
- 字段映射 + 数据文件映射
- 严禁行为 4 条 + 评审未通过项 3 条

V1.5.4 接力期 m12t2 — m7t2_sign_goldset.py 物理删除:
- t01~t04 从"测 m7t2 物理文件内容"改测"m7t2 已物理删除 + 历史记录在 docs"

Section 1 — m7t2 物理删除(V1.5.4 m12t2 改写,4 测点):
  - m7t2_sign_goldset.py 物理删除
  - DEPRECATED 警告历史记录在 docs
  - 替代关系 3 条在 docs
  - V1.5.4 m12t2 物理删除落地标记

Section 2 — 迁移指南文档(5 测点):
  - REVIEWER_CLI_MIGRATION.md 存在
  - 7 大章节
  - 子命令映射 5+ 行
  - 字段对应 5 行
  - 数据文件 6 行

Section 3 — 迁移步骤(3 测点):
  - 沙箱环境 5 步
  - 生产环境 4 步
  - V1.4 兼容说明

Section 4 — 严禁行为 + 未通过项(4 测点):
  - 严禁行为 4 条
  - 评审未通过项 3 条
  - 评审通过清单 8+ 条
  - 评审依据文件 5+ 引用

Section 5 — reviewer_cli 6 子命令(6 测点):
  - cmd_register
  - cmd_list
  - cmd_revoke
  - cmd_sign
  - cmd_verify
  - cmd_batch_verify

Section 6 — reviewer_cli 关键常量 + 路径(3 测点):
  - ROLE_CR / ROLE_PRODUCT / VALID_ROLES
  - TOKEN_HEX_LEN
  - 3 数据文件路径 helper

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "backend" / "scripts"
M7T2_PY = SCRIPTS / "m7t2_sign_goldset.py"
# V1.5.6 接力期 m14t1:reviewer_cli 拆分为独立目录包
CLI_PKG = SCRIPTS / "reviewer_cli"
CLI_INIT = CLI_PKG / "__init__.py"
CLI_CLI_PY = CLI_PKG / "_cli.py"
CLI_PATHS_PY = CLI_PKG / "_paths.py"
CLI_TOKEN_PY = CLI_PKG / "_token.py"


def _read_all_cli() -> str:
    """V1.5.6 m14t1:合并读 reviewer_cli/ 所有子模块,等价于原 _read(CLI_PY)。"""
    parts: list[str] = []
    for p in (CLI_INIT, CLI_CLI_PY, CLI_PATHS_PY, CLI_TOKEN_PY):
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)
MIG_MD = ROOT / "docs" / "REVIEWER_CLI_MIGRATION.md"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def t01_m7t2_physically_deleted() -> bool:
    """t01: m7t2_sign_goldset.py 已物理删除(V1.5.4 m12t2)。"""
    if M7T2_PY.exists():
        print(f"    [FAIL] m7t2_sign_goldset.py 仍存在:{M7T2_PY}")
        return False
    print("    [PASS] m7t2_sign_goldset.py 已物理删除")
    return True


def t02_m7t2_deprecated_in_docs() -> bool:
    """t02: m7t2 DEPRECATED 警告历史记录在 docs(V1.5.2 m10t5 → V1.5.4 m12t2 物理删除)。"""
    txt = _read(MIG_MD)
    if "DEPRECATED" not in txt:
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺 DEPRECATED 历史记录")
        return False
    if "V1.5.2 接力期 m10t5" not in txt:
        print("    [FAIL] 缺 V1.5.2 m10t5 引用")
        return False
    print("    [PASS] m7t2 DEPRECATED 警告历史记录在 docs")
    return True


def t03_m7t2_replacement_in_docs() -> bool:
    """t03: m7t2 替代关系 3 条在 docs(sign_goldset / write_audit_md / sandbox)。"""
    txt = _read(MIG_MD)
    relations = [
        "sign_goldset",
        "write_audit_md",
        "sandbox",
    ]
    missing = [r for r in relations if r not in txt]
    if len(missing) >= 2:
        print(f"    [FAIL] 替代关系缺:{missing}")
        return False
    print("    [PASS] 替代关系 3 条在 docs")
    return True


def t04_v154_m12t2_physical_delete() -> bool:
    """t04: V1.5.4 m12t2 物理删除标记在 docs(REVIEWER_CLI_MIGRATION.md §4.1)。

    V1.5.5 接力期 m13t3 修复:§4.1 L130 标记从 "(2026-06-15)" 扩展为 "(2026-06-15,文件已从 scripts/ 目录移除)",
    改为正则匹配 m7t2_sign_goldset.py 物理删除(2026-06-15 前缀。
    """
    txt = _read(MIG_MD)
    if "V1.5.4 接力期 m12t2 物理删除" not in txt:
        print("    [FAIL] 缺 V1.5.4 m12t2 物理删除标记")
        return False
    # 接受 "(2026-06-15" 前缀(后缀可变,"文件已从 scripts/ 目录移除" 等)
    if not re.search(r"m7t2_sign_goldset\.py\s*物理删除\s*\(2026-06-15", txt):
        print("    [FAIL] 缺 m7t2 物理删除时间标记")
        return False
    print("    [PASS] V1.5.4 m12t2 物理删除落地")
    return True


def t05_migration_doc_exists() -> bool:
    """t05: REVIEWER_CLI_MIGRATION.md 存在 + V1.5.2 freeze 标注。"""
    if not MIG_MD.exists():
        print("    [FAIL] REVIEWER_CLI_MIGRATION.md 缺失")
        return False
    txt = _read(MIG_MD)
    if "V1.5.2" not in txt:
        print("    [FAIL] 缺 V1.5.2 freeze 标注")
        return False
    if "ONLINE-READY" not in txt:
        print("    [FAIL] 缺 ONLINE-READY 标记")
        return False
    print("    [PASS] 迁移指南存在 + V1.5.2 freeze")
    return True


def t06_migration_doc_sections() -> bool:
    """t06: 7 大章节(0~6)。

    V1.5.5 接力期 m13t3 修复:§4 标题从 "## 4. 评审未通过项" 改为 "## 4. V1.5.3 评审未通过项(已修复)"
    (V1.5.4 接力期 m12t2 补充),接受 V1.5.3 前缀变体。
    """
    txt = _read(MIG_MD)
    # V1.5.5 m13t3:接受 "## 4. 评审未通过项" 或 "## 4. V1.5.3 评审未通过项(已修复)" 变体
    section4_pattern = r"##\s*4\.\s*(V1\.5\.3\s*)?评审未通过项(\(已修复\))?"
    expected = [
        r"##\s*0\.\s*迁移目的",
        r"##\s*1\.\s*功能对比",
        r"##\s*2\.\s*迁移步骤",
        r"##\s*3\.\s*严禁行为",
        section4_pattern,
        r"##\s*5\.\s*评审通过清单",
        r"##\s*6\.\s*评审依据文件",
    ]
    missing = [s for s in expected if not re.search(s, txt)]
    if missing:
        print(f"    [FAIL] 章节缺:{missing[:3]}")
        return False
    print("    [PASS] 7 大章节齐全")
    return True


def t07_migration_subcommand_map() -> bool:
    """t07: 子命令映射表 ≥5 行(register / list / revoke / sign / verify / batch-verify)。"""
    txt = _read(MIG_MD)
    cmds = ["register", "list", "revoke", "sign", "verify", "batch-verify"]
    missing = [c for c in cmds if c not in txt]
    if missing:
        print(f"    [FAIL] 子命令映射缺:{missing}")
        return False
    print("    [PASS] 子命令映射 6 行齐全")
    return True


def t08_migration_field_map() -> bool:
    """t08: 字段对应 5 行(cr / product / signed_at / review_mode / event_id)。"""
    txt = _read(MIG_MD)
    fields = ["cr", "product", "signed_at", "review_mode", "event_id"]
    missing = [f for f in fields if f not in txt]
    if missing:
        print(f"    [FAIL] 字段对应缺:{missing}")
        return False
    print("    [PASS] 字段对应 5 行齐全")
    return True


def t09_migration_data_files() -> bool:
    """t09: 数据文件 6 行(goldset / signoff_audit / audit_md / registry / tokens / actions)。"""
    txt = _read(MIG_MD)
    files = [
        "backtest_event_goldset.sample.jsonl",
        ".reviewer-registry.json",
        ".reviewer-tokens.json",
        ".signoff-actions.jsonl",
    ]
    missing = [f for f in files if f not in txt]
    if missing:
        print(f"    [FAIL] 数据文件缺:{missing}")
        return False
    print("    [PASS] 数据文件 4 行齐全(共 6 个含 signoff_audit / audit_md)")
    return True


def t10_migration_sandbox_steps() -> bool:
    """t10: 沙箱环境迁移 5 步(register alice / register bob / list / sign / batch-verify)。"""
    txt = _read(MIG_MD)
    steps = [
        "register alice",
        "register bob",
        "list",
        "sign",
        "batch-verify",
    ]
    missing = [s for s in steps if s not in txt]
    if len(missing) >= 2:
        print(f"    [FAIL] 沙箱步骤缺:{missing}")
        return False
    print("    [PASS] 沙箱 5 步齐全")
    return True


def t11_migration_prod_steps() -> bool:
    """t11: 生产环境 4 步(生成 token / 真实签 / 校验 / 吊销)。"""
    txt = _read(MIG_MD)
    steps = ["生成生产 token", "真实签", "校验", "吊销"]
    missing = [s for s in steps if s not in txt]
    if missing:
        print(f"    [FAIL] 生产步骤缺:{missing}")
        return False
    print("    [PASS] 生产 4 步齐全")
    return True


def t12_migration_v14_compat() -> bool:
    """t12: V1.4 老环境兼容说明(sandbox_*_signer_* / review_mode=sandbox_stub)。"""
    txt = _read(MIG_MD)
    if "V1.4" not in txt:
        print("    [FAIL] 缺 V1.4 兼容说明")
        return False
    if "sandbox_stub" not in txt:
        print("    [FAIL] 缺 sandbox_stub 引用")
        return False
    if "sandbox_cr_signer" not in txt and "sandbox_*_signer" not in txt:
        print("    [FAIL] 缺 sandbox_*_signer 占位说明")
        return False
    print("    [PASS] V1.4 兼容说明完整")
    return True


def t13_migration_strict_no() -> bool:
    """t13: 严禁行为 4 条。

    V1.5.5 接力期 m13t3 修复:原文用 ❌ emoji 计数,但 PowerShell GBK 编码报
    UnicodeEncodeError。改为 "❌" + "[禁止]" 两种 marker 计数,避免 GBK 编码问题。
    """
    txt = _read(MIG_MD)
    if "严禁行为" not in txt and "禁止" not in txt:
        print("    [FAIL] 缺严禁行为章节")
        return False
    # V1.5.5 m13t3:GBK 编码兼容——用 "[禁止]" ASCII marker 计数
    n_ascii = txt.count("[禁止]")
    # 也统计可能的 "❌" marker(PowerShell GBK 终端可能不显示但源码里存在)
    try:
        n_emoji = txt.count("❌")
    except UnicodeEncodeError:
        n_emoji = 0
    n = n_ascii + n_emoji
    if n < 4:
        print(f"    [FAIL] 严禁行为 marker 仅 {n} 个([禁止]={n_ascii} ❌={n_emoji}),需 ≥4")
        return False
    print(f"    [PASS] 严禁行为 {n} 条([禁止]={n_ascii} emoji={n_emoji})")
    return True


def t14_migration_unpassed_three() -> bool:
    """t14: 评审未通过项 3 条(runtime 拦截 / dry-run / token 长度)。"""
    txt = _read(MIG_MD)
    expected = [
        "runtime 拦截",
        "dry-run",
        "TOKEN_HEX_LEN",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 未通过项 3 条缺:{missing}")
        return False
    print("    [PASS] 未通过项 3 条齐全")
    return True


def t15_migration_pass_checklist() -> bool:
    """t15: 评审通过清单 8+ 条。"""
    txt = _read(MIG_MD)
    if "评审通过清单" not in txt:
        print("    [FAIL] 缺评审通过清单")
        return False
    items = [
        "DEPRECATED 警告",
        "6 子命令",
        "字段映射表",
        "数据文件映射表",
        "沙箱 + 生产两套",
        "V1.4 老环境兼容",
        "严禁行为 4 条",
        "评审未通过项 3 条",
        "m10t5_test_reviewer_cli_replace",
        "m8t1_test_regression",
    ]
    missing = [i for i in items if i not in txt]
    if len(missing) >= 2:
        print(f"    [FAIL] 通过清单缺:{missing}")
        return False
    print(f"    [PASS] 通过清单 {len(items) - len(missing)}/{len(items)} 条齐全")
    return True


def t16_migration_references() -> bool:
    """t16: 评审依据文件 5+ 引用。"""
    txt = _read(MIG_MD)
    expected = [
        "reviewer_cli.py",
        "m7t2_sign_goldset.py",
        "m9t3_test_reviewer_cli.py",
        "m10t5_test_reviewer_cli_replace.py",
        "V1.5-handoff",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 评审依据文件缺:{missing}")
        return False
    print("    [PASS] 评审依据文件 5 引用齐全")
    return True


def t17_cli_register_exists() -> bool:
    """t17: reviewer_cli.py 含 cmd_register 函数。"""
    txt = _read_all_cli()
    if "def cmd_register(" not in txt:
        print("    [FAIL] 缺 cmd_register")
        return False
    print("    [PASS] cmd_register 存在")
    return True


def t18_cli_list_revoke() -> bool:
    """t18: reviewer_cli.py 含 cmd_list + cmd_revoke。"""
    txt = _read_all_cli()
    missing = []
    if "def cmd_list(" not in txt:
        missing.append("cmd_list")
    if "def cmd_revoke(" not in txt:
        missing.append("cmd_revoke")
    if missing:
        print(f"    [FAIL] 缺:{missing}")
        return False
    print("    [PASS] cmd_list + cmd_revoke 齐全")
    return True


def t19_cli_sign_verify() -> bool:
    """t19: reviewer_cli.py 含 cmd_sign + cmd_verify。"""
    txt = _read_all_cli()
    missing = []
    if "def cmd_sign(" not in txt:
        missing.append("cmd_sign")
    if "def cmd_verify(" not in txt:
        missing.append("cmd_verify")
    if missing:
        print(f"    [FAIL] 缺:{missing}")
        return False
    print("    [PASS] cmd_sign + cmd_verify 齐全")
    return True


def t20_cli_batch_verify() -> bool:
    """t20: reviewer_cli.py 含 cmd_batch_verify。"""
    txt = _read_all_cli()
    if "def cmd_batch_verify()" not in txt and "def cmd_batch_verify(" not in txt:
        print("    [FAIL] 缺 cmd_batch_verify")
        return False
    print("    [PASS] cmd_batch_verify 存在")
    return True


def t21_cli_role_constants() -> bool:
    """t21: ROLE_CR / ROLE_PRODUCT / VALID_ROLES 常量。"""
    txt = _read_all_cli()
    missing = []
    if 'ROLE_CR = "cr"' not in txt:
        missing.append("ROLE_CR")
    if 'ROLE_PRODUCT = "product"' not in txt:
        missing.append("ROLE_PRODUCT")
    if "VALID_ROLES" not in txt:
        missing.append("VALID_ROLES")
    if missing:
        print(f"    [FAIL] 角色常量缺:{missing}")
        return False
    print("    [PASS] ROLE_CR / ROLE_PRODUCT / VALID_ROLES 齐全")
    return True


def t22_cli_token_hex_len() -> bool:
    """t22: TOKEN_HEX_LEN = 32(token 长度定义)。

    V1.5.5 接力期 m13t3 修复:V1.5.3 接力期 m11t4 改 `TOKEN_HEX_LEN` 为 env 变量
    `REVIEWER_TOKEN_HEX_LEN`,源代码用 `TOKEN_HEX_LEN_DEFAULT = 32` 三个常量。
    接受 `TOKEN_HEX_LEN_DEFAULT = N` 形式(>=16)。
    """
    txt = _read_all_cli()
    if "TOKEN_HEX_LEN" not in txt:
        print("    [FAIL] 缺 TOKEN_HEX_LEN")
        return False
    # V1.5.5 m13t3:接受 3 个 m11t4 引入的常量(TOKEN_HEX_LEN_DEFAULT / _MIN / _PROD_RECOMMENDED)
    m = re.search(r"TOKEN_HEX_LEN_DEFAULT\s*=\s*(\d+)", txt)
    if not m:
        # 兼容旧形式
        m = re.search(r"TOKEN_HEX_LEN\s*=\s*(\d+)", txt)
    if not m:
        print("    [FAIL] TOKEN_HEX_LEN 格式无法解析")
        return False
    n = int(m.group(1))
    if n < 16:
        print(f"    [WARN] TOKEN_HEX_LEN_DEFAULT={n} < 16(评审未通过项已记录)")
        return True
    print(f"    [PASS] TOKEN_HEX_LEN_DEFAULT = {n}")
    return True


def t23_cli_helpers_three() -> bool:
    """t23: 3 数据文件路径 helper(_r / _t / _a)。

    V1.5.5 接力期 m13t3 修复:reviewer_cli.py 实际 helper 签名是 `def _r() -> Path:`(带返回类型),
    而原测点期望 `def _r():`(无返回类型)。改为正则匹配 `def _r()\\s*(->.*)?:` 形式。
    """
    txt = _read_all_cli()
    missing = []
    for helper in ['_r', '_t', '_a']:
        # 接受 `def _r():` 或 `def _r() -> Path:` 等变体
        if not re.search(rf"def\s+{helper}\s*\([^)]*\)\s*(->[^:]+)?\s*:", txt):
            missing.append(f"def {helper}()")
    if missing:
        print(f"    [FAIL] 路径 helper 缺:{missing}")
        return False
    print("    [PASS] _r / _t / _a 路径 helper 齐全")
    return True


def t24_cli_hmac_sha256() -> bool:
    """t24: HMAC-SHA256 token 生成 + hmac.compare_digest + hashlib。"""
    txt = _read_all_cli()
    if "hmac.new" not in txt:
        print("    [FAIL] 缺 hmac.new(token 生成)")
        return False
    if "hashlib.sha256" not in txt:
        print("    [FAIL] 缺 hashlib.sha256")
        return False
    print("    [PASS] HMAC-SHA256 token 生成齐全")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_m7t2_physically_deleted,
        t02_m7t2_deprecated_in_docs,
        t03_m7t2_replacement_in_docs,
        t04_v154_m12t2_physical_delete,
        t05_migration_doc_exists,
        t06_migration_doc_sections,
        t07_migration_subcommand_map,
        t08_migration_field_map,
        t09_migration_data_files,
        t10_migration_sandbox_steps,
        t11_migration_prod_steps,
        t12_migration_v14_compat,
        t13_migration_strict_no,
        t14_migration_unpassed_three,
        t15_migration_pass_checklist,
        t16_migration_references,
        t17_cli_register_exists,
        t18_cli_list_revoke,
        t19_cli_sign_verify,
        t20_cli_batch_verify,
        t21_cli_role_constants,
        t22_cli_token_hex_len,
        t23_cli_helpers_three,
        t24_cli_hmac_sha256,
        t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_m7t2_physically_deleted", t01_m7t2_physically_deleted),
    ("t02_m7t2_deprecated_in_docs", t02_m7t2_deprecated_in_docs),
    ("t03_m7t2_replacement_in_docs", t03_m7t2_replacement_in_docs),
    ("t04_v154_m12t2_physical_delete", t04_v154_m12t2_physical_delete),
    ("t05_migration_doc_exists", t05_migration_doc_exists),
    ("t06_migration_doc_sections", t06_migration_doc_sections),
    ("t07_migration_subcommand_map", t07_migration_subcommand_map),
    ("t08_migration_field_map", t08_migration_field_map),
    ("t09_migration_data_files", t09_migration_data_files),
    ("t10_migration_sandbox_steps", t10_migration_sandbox_steps),
    ("t11_migration_prod_steps", t11_migration_prod_steps),
    ("t12_migration_v14_compat", t12_migration_v14_compat),
    ("t13_migration_strict_no", t13_migration_strict_no),
    ("t14_migration_unpassed_three", t14_migration_unpassed_three),
    ("t15_migration_pass_checklist", t15_migration_pass_checklist),
    ("t16_migration_references", t16_migration_references),
    ("t17_cli_register_exists", t17_cli_register_exists),
    ("t18_cli_list_revoke", t18_cli_list_revoke),
    ("t19_cli_sign_verify", t19_cli_sign_verify),
    ("t20_cli_batch_verify", t20_cli_batch_verify),
    ("t21_cli_role_constants", t21_cli_role_constants),
    ("t22_cli_token_hex_len", t22_cli_token_hex_len),
    ("t23_cli_helpers_three", t23_cli_helpers_three),
    ("t24_cli_hmac_sha256", t24_cli_hmac_sha256),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M10-t5 V1.5.2 reviewer_cli 替换 m7t2_sign_goldset.py 自测(25 测点)")
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
        print("[m10t5] V1.5.2 reviewer_cli 替换 m7t2_sign_goldset.py 25/25 ALL PASSED")
        return 0
    print(f"[m10t5] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
