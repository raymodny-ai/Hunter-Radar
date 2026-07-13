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
    # V1.7.6: BLPOP 等阻塞命令需要 socket_timeout, 否则默认 None
    # 在 idle 30s+ 后会被中间网络/socket keepalive 关闭, 报
    # 'Timeout reading from 127.0.0.1:6379'。30s 足够覆盖 dispatcher 的 5s BLPOP
    socket_timeout=30.0,
    socket_connect_timeout=10.0,
    # V1.7.6: health_check_interval 让连接空闲一段时间后自动 PING 探活,
    # 避免 BLPOP 拿到 stale connection 后一执行就 timeout
    health_check_interval=15,
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

    # ---- List / Key (V1.7.6 warmup dispatcher 队列需要) ----
    async def rpush(self, key: str, value: str) -> int:
        """List 右推 (RPUSH),返新 list 长度。"""
        return int(await self._c.rpush(key, value))

    async def lpush(self, key: str, value: str) -> int:
        """List 左推 (LPUSH),返新 list 长度。"""
        return int(await self._c.lpush(key, value))

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        """List 范围 (LRANGE start end),end=-1 取到末尾。"""
        res = await self._c.lrange(key, start, end)
        return list(res or [])

    async def blpop(
        self, key: str, timeout: int = 0
    ) -> tuple[str, str] | None:
        """阻塞左弹 (BLPOP)。timeout 秒后返 None。

        redis-py async 返 Awaitable[tuple[bytes, bytes] | None],
        包装为 str 元组保持上层一致。
        """
        res = await self._c.blpop(key, timeout=timeout)
        if res is None:
            return None
        k, v = res
        # decode_responses=True 已开,直接 str
        return (str(k), str(v))

    async def exists(self, key: str) -> bool:
        """key 是否存在 (EXISTS)。"""
        return bool(await self._c.exists(key))

    async def delete(self, *keys: str) -> int:
        """删 1+ key,返删除数量。"""
        return int(await self._c.delete(*keys))

    async def llen(self, key: str) -> int:
        """List 长度 (LLEN)。"""
        return int(await self._c.llen(key))

    async def close(self) -> None:
        await self._c.aclose()

    # ---- 高级 ----
    async def get_json(self, key: str) -> Any:
        raw = await self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        # pydantic v2 BaseModel: 用 model_dump(mode='json') 避免 str() 序列化
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        elif hasattr(value, "__pydantic_serializer__"):
            value = value.__pydantic_serializer__.to_python(value)
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
