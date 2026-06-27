"""后台日志 SSE 端点。将 structlog 日志通过 Server-Sent Events 实时推送到前端。"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter()

# 全局日志队列（环形缓冲区）
_LOG_BUFFER: asyncio.Queue = asyncio.Queue(maxsize=500)


# ---- 日志摄取接口（后端其他模块调用） ----
def push_log(level: str, msg: str, **extra) -> None:
    """推一条日志到 SSE 队列。线程安全。"""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat() + "Z",
        "level": level.upper(),
        "msg": msg,
        "extra": extra,
    }
    try:
        _LOG_BUFFER.put_nowait(entry)
    except asyncio.QueueFull:
        # 队列满时丢弃最旧日志
        try:
            _LOG_BUFFER.get_nowait()
            _LOG_BUFFER.put_nowait(entry)
        except (asyncio.QueueEmpty, asyncio.QueueFull):
            pass


# ---- 钩子: 拦截 structlog 输出 ----
class SseLogProcessor:
    """structlog 处理器,将每条日志复制到 SSE 队列。"""

    def __call__(self, logger, method_name, event_dict):
        if isinstance(event_dict, dict):
            level = event_dict.get("level", method_name.upper())
            msg = event_dict.get("event", str(event_dict))
            extra = {k: v for k, v in event_dict.items() if k not in ("event", "level", "timestamp")}
            push_log(level, msg, **extra)
        return event_dict


# ---- SSE 端点 ----
@router.get("/logs/stream")
async def stream_logs(request: Request) -> AsyncGenerator[bytes, None]:
    """SSE 日志流。前端用 EventSource 消费。"""
    client_id = id(request)
    _log_event(f"SSE client connected: {client_id}")
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                entry = await asyncio.wait_for(_LOG_BUFFER.get(), timeout=10)
                data = json.dumps(entry, ensure_ascii=False)
                yield f"data: {data}\n\n".encode("utf-8")
            except asyncio.TimeoutError:
                # 心跳: 保持连接
                yield ": heartbeat\n\n".encode("utf-8")
    except Exception:
        pass
    finally:
        _log_event(f"SSE client disconnected: {client_id}")


@router.get("/logs/history")
async def get_log_history(limit: int = 100) -> list[dict]:
    """返回近期日志历史（调试用）。"""
    snapshot = list(_LOG_BUFFER._queue)[-limit:]
    return snapshot


def _log_event(msg: str) -> None:
    push_log("INFO", msg, source="sse")


def install_sse_logger() -> None:
    """安装 structlog 处理器（在 app 启动时调用）。在 ConsoleRenderer 之前插入。"""
    import structlog

    processors = structlog.get_config().get("processors", [])
    # 找到 ConsoleRenderer,在其之前插入 SseLogProcessor
    insert_idx = len(processors)
    for i, p in enumerate(processors):
        name = getattr(p, "__class__", type(p)).__name__
        if "ConsoleRenderer" in name:
            insert_idx = i
            break
    processors.insert(insert_idx, SseLogProcessor())
    structlog.configure(processors=processors)
