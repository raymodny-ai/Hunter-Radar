"""etl logger monkeypatch.

2026-07-23 patch: etl/*.py 用 `logging.getLogger(__name__)`(标准库 logger),
但调用方式是 `log.info("msg", symbol=sym)` 等带额外 kwarg — 这会触发
`Logger._log() got an unexpected keyword argument` 异常。

最小侵入修复: 在 etl 模块加载前,把 logger._log / info / warning / error
的额外 kwargs 拼到消息末尾。完全不改 etl 源码。

放在 /app/scripts/etl_logger_patch.py, etl_runner.py 顶部 import 即生效。
"""

from __future__ import annotations

import logging
from typing import Any

_PATCHED = False


def _format_kwargs(kwargs: dict[str, Any]) -> str:
    """把 kwargs 拼成 `k1=v1 k2=v2` 形式。"""
    if not kwargs:
        return ""
    parts = []
    for k, v in kwargs.items():
        s = str(v)
        if len(s) > 200:
            s = s[:200] + "..."
        parts.append(f"{k}={s}")
    return " ".join(parts)


def _wrap_method(method_name: str) -> None:
    """给 Logger.<method_name> 包一层:把 kwargs 拼进 message。"""
    original = getattr(logging.Logger, method_name)

    def wrapped(self, msg, *args, **kwargs):
        if kwargs:
            suffix = _format_kwargs(kwargs)
            if suffix:
                msg = f"{msg} {suffix}" if isinstance(msg, str) else f"{msg} {suffix}"
        return original(self, msg, *args)

    setattr(logging.Logger, method_name, wrapped)


def apply() -> None:
    """Idempotent: 重复调用安全。"""
    global _PATCHED
    if _PATCHED:
        return
    for name in ("debug", "info", "warning", "error", "critical", "exception"):
        _wrap_method(name)
    _PATCHED = True