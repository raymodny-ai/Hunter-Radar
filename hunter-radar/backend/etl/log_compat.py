"""stdlib ↔ structlog kwargs 兼容垫片(单一来源)。

背景:etl/*.py 大量使用 structlog 风格 `log.info("foo.bar", key=value, ...)`。
stdlib logging.Logger.info() 不接受任意 kwargs, 会抛 TypeError(例如:

    TypeError: Logger._log() got an unexpected keyword argument 'sym'

这个补丁让 stdlib logger 的 info/warning/error/debug 接受 **kwargs,
把非 stdlib 标准字段合并进 extra={} 并拼到 msg 尾部。

过去这段逻辑只在 app/main.py 里, 依赖 pipeline 入口 `import app.main` 才触发。
单独 import etl/load_options_chain 并调用 compute_option_anomaly() 时垫片不生效,
导致 log.warning("x", sym=...) 直接 TypeError 崩溃(期权异常计算因此无法独立运行)。

现在抽成独立模块, 任何 etl 模块顶部 `import etl.log_compat  # noqa: F401`
即可保证垫片已安装, 不依赖 FastAPI app 启动链路。

注意: 适配层本身要抗型义——万一 fn() 内部再抛(例如 extra 含 Reserved Attr), fallback 到 stderr。
"""
from __future__ import annotations

import logging as _logging


def _patch_logger_log() -> None:
    _orig_info = _logging.Logger.info
    _orig_warn = _logging.Logger.warning
    _orig_error = _logging.Logger.error
    _orig_debug = _logging.Logger.debug

    def _adapt(name: str, fn):
        def _wrapped(self, msg, *args, **kwargs):
            # 提取非 stdlib 标准 kwargs → 拼到 msg 后面
            stdlib_keys = {"exc_info", "stack_info", "stacklevel", "extra"}
            extra_parts = {k: v for k, v in kwargs.items() if k not in stdlib_keys}
            if extra_parts:
                try:
                    suffix = " " + " ".join(f"{k}={v!r}" for k, v in extra_parts.items())
                except Exception:
                    suffix = " <unrepr>"
                msg = f"{msg}{suffix}"
                # 把额外字段塞进 extra(便于 SSE/下游抓取)
                extra = dict(kwargs.get("extra") or {})
                # 避免 LogRecord reserved 字段名冲突
                reserved = {
                    "name", "msg", "args", "levelname", "levelno", "pathname",
                    "filename", "module", "exc_info", "exc_text", "stack_info",
                    "lineno", "funcName", "created", "msecs", "relativeCreated",
                    "thread", "threadName", "processName", "process", "message",
                    "asctime",
                }
                safe_extra = {k: v for k, v in extra_parts.items() if k not in reserved}
                extra.update(safe_extra)
                kwargs["extra"] = extra
                for k in list(extra_parts.keys()):
                    kwargs.pop(k, None)
            try:
                return fn(self, msg, *args, **kwargs)
            except Exception as fallback_err:  # noqa: BLE001
                try:
                    import sys
                    sys.stderr.write(f"[log-fallback:{name}] {msg!r} ({fallback_err!s})\n")
                    sys.stderr.flush()
                except Exception:
                    pass

        _wrapped.__name__ = fn.__name__
        return _wrapped

    _logging.Logger.info = _adapt("info", _orig_info)
    _logging.Logger.warning = _adapt("warning", _orig_warn)
    _logging.Logger.error = _adapt("error", _orig_error)
    _logging.Logger.debug = _adapt("debug", _orig_debug)


_patch_logger_log()
