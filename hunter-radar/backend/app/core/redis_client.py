"""Redis 异步客户端 + 装饰器式缓存。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

_client: redis.Redis = redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
    max_connections=50,
)


class RedisClient:
    """对原生客户端的薄包装,便于替换/测试。"""

    def __init__(self, c: redis.Redis) -> None:
        self._c = c

    async def ping(self) -> bool:
        return bool(await self._c.ping())

    async def get(self, key: str) -> str | None:
        return await self._c.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if ttl:
            await self._c.set(key, value, ex=ttl)
        else:
            await self._c.set(key, value)

    async def incr(self, key: str) -> int:
        return await self._c.incr(key)

    async def expire(self, key: str, ttl: int) -> None:
        await self._c.expire(key, ttl)

    async def close(self) -> None:
        await self._c.aclose()

    # ---- 高级 ----
    async def get_json(self, key: str) -> Any:
        raw = await self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self.set(key, json.dumps(value, ensure_ascii=False, default=str), ttl=ttl)


redis_client = RedisClient(_client)


def cached_json(ttl: int) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """装饰器：对异步函数的返回值做 JSON 缓存。

    缓存键由函数名 + 参数 hash 组成；命中失败（Redis 挂了）时降级到原函数。
    """

    def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"cache:{fn.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            try:
                hit = await redis_client.get_json(key)
                if hit is not None:
                    return hit
            except Exception:  # noqa: BLE001
                pass
            value = await fn(*args, **kwargs)
            try:
                await redis_client.set_json(key, value, ttl=ttl)
            except Exception:  # noqa: BLE001
                pass
            return value

        return wrapper

    return deco


async def cache_or_set_json(
    key: str, ttl: int, compute_fn: Callable[[], Awaitable[Any]]
) -> tuple[Any, bool]:
    """手动缓存包装（BD-080）：给 FastAPI 端点用，避免装饰器与 Depends 冲突。

    Args:
        key: 缓存键（业务层拼）
        ttl: 过期秒数
        compute_fn: 未命中时调用的取数函数（业务层传 lambda 闭包）

    Returns:
        (value, hit) — value 为最终返回值，hit 为是否命中缓存
    """
    try:
        hit = await redis_client.get_json(key)
        if hit is not None:
            return hit, True
    except Exception:  # noqa: BLE001
        pass
    value = await compute_fn()
    try:
        await redis_client.set_json(key, value, ttl=ttl)
    except Exception:  # noqa: BLE001
        pass
    return value, False
