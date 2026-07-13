"""后台日志 SSE 端点。将 structlog 日志通过 Server-Sent Events 实时推送到前端。"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

# ---- server.log 位置 ----
# 与 control.sh 中 start_backend() 写出的位置一致:
#   nohup ... -m app.static_serve > "$ROOT/server.log" 2>&1
# 其中 ROOT = Hunter-Radar/ 目录(workspace/Hunter-Radar/server.log)
_DEFAULT_LOG_PATHS = [
    Path(os.environ.get("HUNTER_RADAR_LOG", "")) if os.environ.get("HUNTER_RADAR_LOG") else None,
    Path("/vol1/@apphome/trim.openclaw/data/workspace/Hunter-Radar/server.log"),
    Path(__file__).resolve().parents[4] / "server.log",  # backend/app/api → 4 级上溯到 Hunter-Radar/
]
_SERVER_LOG: Path | None = next(
    (p for p in _DEFAULT_LOG_PATHS if p and p.is_file()),
    None,
)

# ANSI 控制字符剔除(structlog 彩色输出) + 正常化空白
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# uvicorn access: "INFO:     127.0.0.1:12345 - \"GET /foo HTTP/1.1\" 200 OK"
_UVICORN_ACCESS_RE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?\s*'
    r'(?:\[(?P<ctx>[^\]]+)\]\s*)?'
    r'(?P<level>INFO|WARNING|WARN|ERROR|DEBUG|CRITICAL)[:\s]\s*'
    r'(?P<msg>.*)$',
    re.IGNORECASE,
)
# structlog ISO 行: "2026-06-30T18:39:59.040266Z [info    ] app.startup    env=development version=1.4.0"
_STRUCTLOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s*"
    r"\[\s*(?P<level>info|debug|warning|error|critical)\s*\]\s*"
    r"(?P<msg>\S+)(?:\s+(?P<kv>\S.*))?$",
    re.IGNORECASE,
)

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
async def stream_logs(request: Request):
    """SSE 日志流。前端用 EventSource 消费。

    V1.4 原实现: 用 async generator + return type annotation,
    但 ORJSONResponse 默认 Response 会把 generator 试着用 orjson 序列化,
    报 "Type is not JSON serializable: async_generator"。
    修复: 显式用 StreamingResponse(text/event-stream) 包装。
    """
    client_id = id(request)
    _log_event(f"SSE client connected: {client_id}")

    async def _gen() -> AsyncGenerator[bytes, None]:
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

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 不要缓冲
            "Connection": "keep-alive",
        },
    )


@router.get("/logs/history")
async def get_log_history(limit: int = 100) -> list[dict]:
    """返回近期日志历史（调试用）。"""
    snapshot = list(_LOG_BUFFER._queue)[-limit:]
    return snapshot


# ---- server.log 文件读取端点 ----
@router.get("/logs/file")
async def read_log_file(
    tail: int = Query(200, ge=1, le=5000, description="返回最后 N 行"),
    level: str | None = Query(None, description="按级别过滤,逗号分隔: INFO,WARNING,ERROR"),
    q: str | None = Query(None, description="关键字过滤(不区分大小写)"),
    source: str | None = Query(None, description="app|uvicorn|all,默认 all"),
) -> dict:
    """读取 server.log 文件,返回结构化日志条目。

    与 /logs/history 不同:该端点从磁盘文件读取,进程重启后历史不丢失,
    适合做"持久化的后台日志查看页面"。
    """
    if _SERVER_LOG is None or not _SERVER_LOG.is_file():
        raise HTTPException(status_code=503, detail=f"server.log not found in any of: {[str(p) for p in _DEFAULT_LOG_PATHS if p]}")

    wanted_levels: set[str] | None = None
    if level:
        wanted_levels = {x.strip().upper() for x in level.split(",") if x.strip()}
    keyword = q.strip().lower() if q else None
    src_filter = (source or "all").lower()

    try:
        # tail 用反向块读取,O(N) 但 N = 文件总行数 ≈ 几百~几千,完全够用
        # 真要处理 100MB+ 日志再换 mmap
        with _SERVER_LOG.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"read failed: {e!s}") from e

    parsed: list[dict] = []
    for raw in lines:
        entry = _parse_line(raw, src_filter)
        if entry is None:
            continue
        if wanted_levels and entry["level"] not in wanted_levels:
            continue
        if keyword and keyword not in entry["msg"].lower() and keyword not in entry["raw"].lower():
            continue
        parsed.append(entry)

    # 倒序,只取最后 tail 条
    parsed = parsed[-tail:]
    parsed.reverse()

    return {
        "source": str(_SERVER_LOG),
        "size_bytes": _SERVER_LOG.stat().st_size,
        "returned": len(parsed),
        "entries": parsed,
    }


def _parse_line(raw: str, src_filter: str) -> dict | None:
    """把一行原始日志解析成 {ts, level, msg, source, raw}。

    支持 3 种格式:
    1. uvicorn access:  INFO:     1.2.3.4:80 - "GET /x HTTP/1.1" 200 OK
    2. structlog:       2026-06-30T18:39:59Z [info] app.startup env=...
    3. 纯文本/警告(无 ts)  兜底 INFO
    """
    line = _ANSI_RE.sub("", raw).rstrip("\n")
    if not line.strip():
        return None

    # 1) structlog
    m = _STRUCTLOG_RE.match(line)
    if m:
        return {
            "ts": m.group("ts") if m.group("ts").endswith("Z") else m.group("ts") + "Z",
            "level": m.group("level").upper(),
            "msg": m.group("msg"),
            "extra": _parse_kv(m.group("kv") or ""),
            "source": "app",
            "raw": line,
        }

    # 2) uvicorn access / 通用 "LEVEL: msg"
    m = _UVICORN_ACCESS_RE.match(line)
    if m:
        lvl = m.group("level").upper()
        if lvl == "WARN":
            lvl = "WARNING"
        return {
            "ts": m.group("ts") or "",
            "level": lvl,
            "msg": m.group("msg").strip(),
            "extra": {},
            "source": "uvicorn",
            "raw": line,
        }

    # 3) 兜底(无 LEVEL 前缀的行,比如 DeprecationWarning 堆栈的中间行)
    if src_filter == "uvicorn":
        return None
    return {
        "ts": "",
        "level": "INFO",
        "msg": line[:500],
        "extra": {},
        "source": "app",
        "raw": line,
    }


def _parse_kv(blob: str) -> dict[str, str]:
    """解析 'env=development version=1.4.0' 这种 structlog key=value 串。"""
    out: dict[str, str] = {}
    if not blob:
        return out
    # 简易 tokenizer: 支持带空格的值用引号包裹
    i = 0
    while i < len(blob):
        # 跳空白
        while i < len(blob) and blob[i].isspace():
            i += 1
        if i >= len(blob):
            break
        # 找 key
        eq = blob.find("=", i)
        if eq < 0:
            break
        key = blob[i:eq]
        i = eq + 1
        # 读 value
        if i < len(blob) and blob[i] in ("'", '"'):
            quote = blob[i]
            i += 1
            end = blob.find(quote, i)
            if end < 0:
                out[key] = blob[i:]
                break
            out[key] = blob[i:end]
            i = end + 1
        else:
            end = i
            while end < len(blob) and not blob[end].isspace():
                end += 1
            out[key] = blob[i:end]
            i = end
    return out


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
