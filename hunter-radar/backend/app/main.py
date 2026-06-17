"""Hunter Radar V1.4 FastAPI 应用入口。"""

from __future__ import annotations

import logging

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.utils import get_openapi
from sqlalchemy import text

from app.api import (
    admin,
    alerts,
    analytics,
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
    screener,
    subscriptions,
    symbols,
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
log = structlog.get_logger("hunter_radar")
logging.basicConfig(level=settings.log_level)

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
app.include_router(regime.router, prefix="/api/v1", tags=["regime"])
app.include_router(screener.router, prefix="/api/v1", tags=["screener"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(basket.router, prefix="/api/v1", tags=["basket"])
app.include_router(push.router, prefix="/api/v1", tags=["push"])
app.include_router(data_status.router, prefix="/api/v1", tags=["data-status"])
# m5t8 FE-064 BD-076 配额查询端点
app.include_router(quota.router, prefix="/api/v1", tags=["auth"])
# m6t4 BD-105 Stripe 订阅接入(沙箱 fallback)
app.include_router(subscriptions.router, prefix="/api/v1", tags=["subscriptions"])
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


@app.on_event("shutdown")
async def on_shutdown() -> None:
    log.info("app.shutdown")
    await engine.dispose()
    await redis_client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
