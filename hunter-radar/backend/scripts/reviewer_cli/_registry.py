"""V1.5.6 接力期 m14t1 — reviewer_cli registry / tokens / 审计读写。

本模块(_registry)负责:
- _load_registry / _save_registry(.reviewer-registry.json)
- _load_tokens / _save_tokens(.reviewer-tokens.json)
- _append_action(.signoff-actions.jsonl 追加,每行一条)
"""
from __future__ import annotations

import json

from ._paths import _a, _r, _t


def _load_registry() -> list[dict]:
    if not _r().exists():
        return []
    return json.loads(_r().read_text(encoding="utf-8"))


def _save_registry(registry: list[dict]) -> None:
    _r().parent.mkdir(parents=True, exist_ok=True)
    _r().write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_tokens() -> dict:
    if not _t().exists():
        return {}
    return json.loads(_t().read_text(encoding="utf-8"))


def _save_tokens(tokens: dict) -> None:
    _t().parent.mkdir(parents=True, exist_ok=True)
    _t().write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _append_action(record: dict) -> None:
    _a().parent.mkdir(parents=True, exist_ok=True)
    with _a().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
