"""V1.5.6 接力期 m14t1 — reviewer_cli 路径与时间 helper。

V1.5.6 接力期 C-1:从 scripts/reviewer_cli.py 单文件(504 行)拆为独立目录包。
本模块(_paths)负责:
- ROOT(项目根)
- _data_dir / _g / _r / _t / _a 5 个路径 helper
- _now_iso UTC ISO 8601 时间
- ROLE_CR / ROLE_PRODUCT / VALID_ROLES 3 个角色常量

数据文件位置(沿用 m9t3 布局):
  .reviewer-registry.json   名册 [{name, role, token_hash, registered_at, status}]
  .reviewer-tokens.json     token 库 {token: {name, role, registered_at, status}}
  .signoff-actions.jsonl    审计(每行一条 action)
  backtest_event_goldset.sample.jsonl  31 事件双签 goldset
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _data_dir() -> Path:
    """运行时 data 目录(沙箱/自测可走 REVIEWER_CLI_DATA_DIR)。

    生产/默认:d:\\Financial Project\\Hunter Radar\\hunter-radar\\data
    自测时:os.environ["REVIEWER_CLI_DATA_DIR"]=tmp_path(子脚本读取)
    """
    env_dir = os.environ.get("REVIEWER_CLI_DATA_DIR")
    return Path(env_dir) if env_dir else (ROOT / "data")


def _g() -> Path:
    """goldset JSONL 路径(_data_dir() 动态计算)。"""
    return _data_dir() / "backtest_event_goldset.sample.jsonl"


def _r() -> Path:
    """reviewer-registry.json 路径。"""
    return _data_dir() / ".reviewer-registry.json"


def _t() -> Path:
    """reviewer-tokens.json 路径。"""
    return _data_dir() / ".reviewer-tokens.json"


def _a() -> Path:
    """signoff-actions.jsonl 路径。"""
    return _data_dir() / ".signoff-actions.jsonl"


def _now_iso() -> str:
    """UTC ISO 8601 字符串。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# BD-086 reviewer 角色
ROLE_CR = "cr"
ROLE_PRODUCT = "product"
VALID_ROLES = (ROLE_CR, ROLE_PRODUCT)
