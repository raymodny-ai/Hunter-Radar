"""健康检查端点。"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.core.database import engine
from app.core.redis_client import redis_client

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """详细健康状态(供运维与监控)。"""
    db_ok = False
    redis_ok = False
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        pass
    try:
        redis_ok = await redis_client.ping()
    except Exception:  # noqa: BLE001
        pass

    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "version": __version__,
        "db": db_ok,
        "redis": redis_ok,
    }



