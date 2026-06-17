"""V1.5.6 接力期 m14t1 — reviewer_cli 独立目录包入口。

V1.5.6 接力期 C-1:从 scripts/reviewer_cli.py 单文件(504 行)拆为独立目录包。
本 __init__.py 作为薄包装,re-export 公共 API(cmd_*, 路径 helper, 角色常量,
token 常量),保持向后兼容。

向后兼容矩阵:
- `from scripts.reviewer_cli import cmd_register` → 仍可用(指向 _cli.cmd_register)
- `python scripts/reviewer_cli.py` 命令行调用 → 不再支持(物理删除原 .py)
  改用 `python -m scripts.reviewer_cli._cli` 或 `python -m reviewer_cli`(需 PYTHONPATH)

模块结构:
  scripts/reviewer_cli/
    __init__.py     本文件(薄包装 + re-export)
    _paths.py       路径 helper + 时间 + 角色常量
    _token.py       token 常量 + 生成/校验
    _registry.py    registry / tokens / 审计读写
    _goldset.py     goldset JSONL 读写
    _cli.py         6 个 cmd_* 子命令 + main 入口
"""
from __future__ import annotations

# 公共 API re-export(向后兼容)
from ._cli import (
    cmd_batch_verify,
    cmd_list,
    cmd_register,
    cmd_revoke,
    cmd_sign,
    cmd_verify,
    main,
)
from ._paths import (
    ROOT,
    ROLE_CR,
    ROLE_PRODUCT,
    VALID_ROLES,
    _a,
    _data_dir,
    _g,
    _now_iso,
    _r,
    _t,
)
from ._token import (
    TOKEN_HEX_LEN_DEFAULT,
    TOKEN_HEX_LEN_MIN,
    TOKEN_HEX_LEN_PROD_RECOMMENDED,
    _gen_token,
    _hash_token,
    _resolve_token_hex_len,
    _secret_key,
)

__all__ = [
    # cmd_*
    "cmd_batch_verify",
    "cmd_list",
    "cmd_register",
    "cmd_revoke",
    "cmd_sign",
    "cmd_verify",
    "main",
    # 路径 / 时间
    "ROOT",
    "_a",
    "_data_dir",
    "_g",
    "_now_iso",
    "_r",
    "_t",
    # 角色
    "ROLE_CR",
    "ROLE_PRODUCT",
    "VALID_ROLES",
    # token
    "TOKEN_HEX_LEN_DEFAULT",
    "TOKEN_HEX_LEN_MIN",
    "TOKEN_HEX_LEN_PROD_RECOMMENDED",
    "_gen_token",
    "_hash_token",
    "_resolve_token_hex_len",
    "_secret_key",
]
