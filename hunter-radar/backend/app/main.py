"""Hunter Radar V1.4 FastAPI 应用入口。"""

from __future__ import annotations

import logging

import sentry_sdk
import structlog

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text

from app.api import (
    admin,
    alerts,
    analytics,
    attribution,
    basket,
    data_status,
    edgar,
    eight_k,
    etf,
    feature_flags,
    health,
    push,
    quota,
    regime,
    regime_timeline,
    screener,
    symbols,
    symbol_admin,
    llm,
    log_stream,
)
from app.core.config import settings
from app.core.database import engine
from app.core.redis_client import redis_client

# ---- 日志 ----
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
# 安装 SSE 日志处理器(将所有 structlog 输出推送到前端 SSE 流)
from app.api.log_stream import install_sse_logger
install_sse_logger()

log = structlog.get_logger("hunter_radar")
logging.basicConfig(level=settings.log_level)

# ---- V1.7.0 stdlib ↔ structlog kwargs 兼容垫片 ----
# 背景:etl/*.py 大量使用 structlog 风格 log.info("foo.bar", key=value, ...)。
# stdlib logging.Logger._log() 不接受任意 kwargs,会抛 TypeError。
# 这里打补丁:让 stdlib logger 的 info/warning/error/debug 接受 **kwargs,
# 合并进 extra={}。这样 etl 现存代码无需修改也能跑。
# 重要:适配层本身要抗型义——万一 fn() 内部再抛(例如 extra 含 Reserved Attr),Fallback 到 print
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
                # 避免 LogRecord reserved 字段名冲突(模块默认 LogRecord 字段是双下划线中间名字)
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
                # 剩下的合法 kwargs 走原 fn
                for k in list(extra_parts.keys()):
                    kwargs.pop(k, None)
            try:
                return fn(self, msg, *args, **kwargs)
            except Exception as fallback_err:  # noqa: BLE001
                # 极限 fallback: 调到原 _log 不带 extra
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

# ---- Sentry ----
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        traces_sample_rate=0.1,
        release="hunter-radar@1.4.0",
    )

# ---- App ----
app = FastAPI(
    title=settings.app_name,
    version="1.4.0",
    description="美股盘后另类数据雷达 — 期权异常/全监管做空/量价背离/SEC 内部行为 + Threat Score 共振看板",
    default_response_class=ORJSONResponse,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ---- 路由(M0 阶段先挂骨架,M1 后逐步替换为真实实现) ----
app.include_router(health.router, tags=["health"])
app.include_router(symbols.router, prefix="/api/v1", tags=["symbols"])
app.include_router(symbol_admin.router, prefix="/api/v1", tags=["symbol-admin"])
app.include_router(regime.router, prefix="/api/v1", tags=["regime"])
app.include_router(screener.router, prefix="/api/v1", tags=["screener"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(basket.router, prefix="/api/v1", tags=["basket"])
app.include_router(push.router, prefix="/api/v1", tags=["push"])
app.include_router(data_status.router, prefix="/api/v1", tags=["data-status"])
# m5t8 FE-064 BD-076 配额查询端点
app.include_router(quota.router, prefix="/api/v1", tags=["auth"])

# m6t7 灰度发布 flag 端点
app.include_router(feature_flags.router, prefix="/api/v1", tags=["feature-flags"])
# m6t8 BD-051 8-K Item 8.01 重大事件流
app.include_router(eight_k.router, prefix="/api/v1", tags=["events"])
# m9t4 V1.5.1 EDGAR full-text search 端点(sandbox_stub)
app.include_router(edgar.router, prefix="/api/v1/edgar", tags=["edgar"])
# m9t5 V1.5.1 ETF 申赎代理 3 端点(BD-088 sandbox_stub)
app.include_router(etf.router, prefix="/api/v1/etf", tags=["etf"])
# m9t6 V1.5.1 Analytics events 3 端点(sandbox_stub)
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
# m7t7 V1.5 OpenAPI freeze admin 端点(ETL run / backtest run / result / webhook replay)
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
app.include_router(log_stream.router, prefix="/api/v1", tags=["log-stream"])
app.include_router(llm.router, prefix="/api/v1", tags=["llm"])
app.include_router(attribution.router, prefix="/api/v1", tags=["attribution"])
app.include_router(regime_timeline.router, prefix="/api/v1", tags=["regime-timeline"])





# ---- 自定义 OpenAPI(便于前端 openapi-typescript 自动生成类型) ----
def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=settings.app_name,
        version="1.4.0",
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("info", {})["x-logo"] = {
        "url": "https://hunter-radar.example/logo.png"
    }
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi  # type: ignore[method-assign]


# ---- 启动 / 关闭事件 ----
@app.on_event("startup")
async def on_startup() -> None:
    log.info("app.startup", env=settings.env, version="1.4.0")
    # 探活数据库与 Redis;不通过则记录但不阻断启动(开发期常见)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("db.ready")
    except Exception as e:  # noqa: BLE001
        log.warning("db.unreachable", error=str(e))
    try:
        await redis_client.ping()
        log.info("redis.ready")
    except Exception as e:  # noqa: BLE001
        log.warning("redis.unreachable", error=str(e))

    # V1.7.6: 启动 warmup dispatcher (串行调度, 避免 31 ticker 并发撞墙)
    try:
        from app.services.symbol_warmup import start_dispatcher

        await start_dispatcher()
        log.info("warmup.dispatcher.startup.ok")
    except Exception as e:  # noqa: BLE001
        log.warning("warmup.dispatcher.startup.fail", error=str(e))


@app.on_event("shutdown")
async def on_shutdown() -> None:
    log.info("app.shutdown")
    await engine.dispose()
    await redis_client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
