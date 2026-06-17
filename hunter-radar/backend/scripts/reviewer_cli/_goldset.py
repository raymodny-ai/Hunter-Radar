"""V1.5.6 接力期 m14t1 — reviewer_cli goldset JSONL 读写。

本模块(_goldset)负责:
- _read_goldset(.backtest_event_goldset.sample.jsonl 读)
- _write_goldset(写回,带 UTF-8 + ensure_ascii=False)
"""
from __future__ import annotations

import json

from ._paths import _g


def _read_goldset() -> list[dict]:
    if not _g().exists():
        raise SystemExit(f"goldset not found: {_g()}")
    return [
        json.loads(line)
        for line in _g().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_goldset(objs: list[dict]) -> None:
    _g().write_text(
        "\n".join(json.dumps(o, ensure_ascii=False) for o in objs) + "\n",
        encoding="utf-8",
    )
