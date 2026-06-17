"""§6.2 数据状态端点(FE-061 全局 DataStatusBanner 数据源)。

返回:
{
  "status": "ready" | "warming" | "stale" | "error",
  "reason": "<人类可读理由>",
  "data_warmup": bool,         # 冷启动期(默认 60 个交易日)
  "last_data_date": str | null,  # ISO date
  "is_stale": bool,              # 距 last_data_date > 1 个交易日
  "db_ok": bool,
  "redis_ok": bool
}

沙箱/无 PG:status=warming + reason="sandbox: no PG,设 HR_PG_OK=1 后重试",
不返回 last_data_date。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import engine

router = APIRouter()


_STALE_DAYS_THRESHOLD = 1  # 距 last_data_date > 1 个交易日视为 stale


async def _db_ok() -> bool:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


async def _last_data_date() -> date | None:
    """threat_score_daily 表最新 trade_date;无 PG/无表:None。"""
    try:
        async with engine.begin() as conn:
            rs = await conn.execute(
                text("SELECT MAX(trade_date) FROM threat_score_daily")
            )
            row = rs.first()
            if row is None or row[0] is None:
                return None
            v = row[0]
            if isinstance(v, date):
                return v
            return datetime.fromisoformat(str(v)).date()
    except Exception:  # noqa: BLE001
        return None


@router.get("/data-status", summary="全局数据状态(FE-061)")
async def get_data_status() -> dict[str, Any]:
    """全局数据状态聚合:db / redis / data_warmup / is_stale。"""
    db_ok = await _db_ok()
    redis_ok = True  # redis_client 是可选依赖,沙箱常见 None
    try:
        from app.core.redis_client import redis_client

        redis_ok = await redis_client.ping()
    except Exception:  # noqa: BLE001
        redis_ok = False

    if not db_ok:
        return {
            "status": "warming",
            "reason": "sandbox: no PG reachable,设 HR_PG_OK=1 后重试",
            "data_warmup": True,
            "last_data_date": None,
            "is_stale": False,
            "db_ok": False,
            "redis_ok": redis_ok,
        }

    last = await _last_data_date()
    today = date.today()
    is_stale = (
        last is None
        or (today - last) > timedelta(days=_STALE_DAYS_THRESHOLD + 1)
    )
    data_warmup = last is None or (today - last) > timedelta(days=60)

    if is_stale:
        return {
            "status": "stale",
            "reason": (
                f"数据最后更新 {last.isoformat() if last else '未知'},"
                f"距今 > {_STALE_DAYS_THRESHOLD} 个交易日,可能存在缺失"
            ),
            "data_warmup": data_warmup,
            "last_data_date": last.isoformat() if last else None,
            "is_stale": True,
            "db_ok": True,
            "redis_ok": redis_ok,
        }
    if data_warmup:
        return {
            "status": "warming",
            "reason": "数据积累中(冷启动约 60 个交易日),Z-Score 暂不可用",
            "data_warmup": True,
            "last_data_date": last.isoformat() if last else None,
            "is_stale": False,
            "db_ok": True,
            "redis_ok": redis_ok,
        }
    return {
        "status": "ready",
        "reason": "ok",
        "data_warmup": False,
        "last_data_date": last.isoformat() if last else None,
        "is_stale": False,
        "db_ok": True,
        "redis_ok": redis_ok,
    }
