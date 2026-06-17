"""§6.2 push_subscription 业务逻辑(BD-074 m5t4)。

设计:
- 不引入 ORM,直接走 SQLAlchemy 异步 text()(与其他服务一致,迁移轻量)
- 沙箱/无 PG:所有函数返 None(API 层回 503 / 200+空)
- 端点(endpoint)唯一:同设备重复订阅 → upsert(更新 p256dh / auth / user_agent)
- is_active:订阅失效(410 Gone)由 API 层软删

表结构见 sql/migrations/2026_06_15_push_subscription.sql
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---- CRUD -------------------------------------------------------------------


async def upsert_subscription(
    session: AsyncSession,
    *,
    user_id: UUID,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None = None,
) -> int | None:
    """新增或更新订阅(以 endpoint 为唯一键)。

    Returns:
        subscription id(新插入或更新后的 id)
        沙箱/失败:None
    """
    try:
        now = datetime.now(tz=timezone.utc)
        # 先查在不在(按 endpoint)
        existing = await session.execute(
            text(
                "SELECT id, user_id FROM push_subscription "
                "WHERE endpoint = :endpoint"
            ),
            {"endpoint": endpoint},
        )
        row = existing.mappings().first()
        if row is not None:
            # 已存在:更新 p256dh / auth / user_agent / updated_at / is_active
            await session.execute(
                text(
                    "UPDATE push_subscription "
                    "SET p256dh = :p256dh, auth = :auth, user_agent = :ua, "
                    "    updated_at = :now, is_active = TRUE "
                    "WHERE id = :id"
                ),
                {
                    "p256dh": p256dh,
                    "auth": auth,
                    "ua": user_agent,
                    "now": now,
                    "id": row["id"],
                },
            )
            await session.commit()
            return int(row["id"])
        # 新插入
        ins = await session.execute(
            text(
                "INSERT INTO push_subscription "
                "(user_id, endpoint, p256dh, auth, user_agent, is_active, created_at, updated_at) "
                "VALUES (:uid, :ep, :p256dh, :auth, :ua, TRUE, :now, :now) "
                "RETURNING id"
            ),
            {
                "uid": str(user_id),
                "ep": endpoint,
                "p256dh": p256dh,
                "auth": auth,
                "ua": user_agent,
                "now": now,
            },
        )
        new_id = ins.scalar_one()
        await session.commit()
        return int(new_id)
    except Exception:  # noqa: BLE001
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


async def list_subscriptions_by_user(
    session: AsyncSession, user_id: UUID
) -> list[dict[str, Any]] | None:
    """列某用户的所有 active 订阅;沙箱返 None。"""
    try:
        rs = await session.execute(
            text(
                "SELECT id, endpoint, p256dh, auth, user_agent, created_at, updated_at "
                "FROM push_subscription "
                "WHERE user_id = :uid AND is_active = TRUE "
                "ORDER BY created_at DESC"
            ),
            {"uid": str(user_id)},
        )
        return [dict(r) for r in rs.mappings().all()]
    except Exception:  # noqa: BLE001
        return None


async def get_subscription(
    session: AsyncSession, sub_id: int, user_id: UUID
) -> dict[str, Any] | None:
    """按 id 查订阅(校验属于该 user);沙箱/无权限:None。"""
    try:
        rs = await session.execute(
            text(
                "SELECT id, endpoint, p256dh, auth, user_agent, is_active, "
                "       created_at, updated_at "
                "FROM push_subscription WHERE id = :id AND user_id = :uid"
            ),
            {"id": sub_id, "uid": str(user_id)},
        )
        row = rs.mappings().first()
        return dict(row) if row else None
    except Exception:  # noqa: BLE001
        return None


async def soft_delete_subscription(
    session: AsyncSession, sub_id: int, user_id: UUID
) -> bool:
    """软删(is_active=False);沙箱/失败/不存在:False。"""
    try:
        rs = await session.execute(
            text(
                "UPDATE push_subscription SET is_active = FALSE, updated_at = :now "
                "WHERE id = :id AND user_id = :uid AND is_active = TRUE"
            ),
            {
                "now": datetime.now(tz=timezone.utc),
                "id": sub_id,
                "uid": str(user_id),
            },
        )
        await session.commit()
        return rs.rowcount > 0
    except Exception:  # noqa: BLE001
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


def to_push_api_dict(row: dict[str, Any]) -> dict[str, Any]:
    """DB row → 前端订阅对象(标准 PushSubscription JSON 风格)。

    注意:不返回 p256dh / auth(避免泄露)。
    """
    return {
        "id": int(row["id"]),
        "endpoint_prefix": (row.get("endpoint") or "")[:80],
        "user_agent": row.get("user_agent"),
        "is_active": bool(row.get("is_active", True)),
        "created_at": (
            row["created_at"].isoformat()
            if hasattr(row.get("created_at"), "isoformat")
            else str(row.get("created_at") or "")
        ),
    }


# ---- 构造 send_webpush 入参(给 dispatch_event 复用) -----------------------


def to_webpush_subscription(row: dict[str, Any]) -> dict[str, Any]:
    """DB row → send_webpush 入参(标准 PushSubscription JSON)。"""
    return {
        "endpoint": row["endpoint"],
        "keys": {
            "p256dh": row["p256dh"],
            "auth": row["auth"],
        },
    }


__all__ = [
    "upsert_subscription",
    "list_subscriptions_by_user",
    "get_subscription",
    "soft_delete_subscription",
    "to_push_api_dict",
    "to_webpush_subscription",
]
