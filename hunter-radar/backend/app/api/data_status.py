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


async def _module_quality_status(trade_date: date) -> tuple[str | None, str]:
    """4.2 (断裂点 5): 读最新日 threat_score_daily.module_quality,推导评分完整性。

    返回 (status, reason):
      - ("partial", ...) : 存在模块 quality=missing(数据不完整,评分仅供参考)
      - ("degraded", ...): 存在模块 quality=degraded(部分数据源降级,评分可能偏低)
      - (None, "ok")     : 全 complete(或列未落库,回退 ready)

    module_quality 形如 {options: complete|degraded|missing, short: ...}。
    历史行/旧部署无此列时返回 (None, "ok") 不误报。
    """
    try:
        async with engine.begin() as conn:
            rs = await conn.execute(
                text(
                    """SELECT module_quality FROM threat_score_daily
                       WHERE trade_date = :d AND module_quality IS NOT NULL
                       LIMIT 200"""
                ),
                {"d": trade_date},
            )
            rows = rs.all()
    except Exception:  # noqa: BLE001
        return None, "ok"

    if not rows:
        return None, "ok"

    missing_syms: list[str] = []
    degraded_syms: list[str] = []
    for (mq,) in rows:
        if not mq:
            continue
        quals = set(mq.values())
        if "missing" in quals:
            missing_syms.append("x")
        elif "degraded" in quals:
            degraded_syms.append("x")

    if missing_syms:
        return (
            "partial",
            f"{len(missing_syms)} 个标的模块数据不完整(missing),评分仅供参考",
        )
    if degraded_syms:
        return (
            "degraded",
            f"{len(degraded_syms)} 个标的部分数据源降级,评分可能偏低",
        )
    return None, "ok"


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

    # 4.2 (断裂点 5): 非 stale/非 warmup 时,检查最新日模块质量 → degraded/partial
    health_status, health_reason = await _module_quality_status(last)
    return {
        "status": health_status or "ready",
        "reason": health_reason if health_status else "ok",
        "data_warmup": False,
        "last_data_date": last.isoformat() if last else None,
        "is_stale": False,
        "db_ok": True,
        "redis_ok": redis_ok,
    }
