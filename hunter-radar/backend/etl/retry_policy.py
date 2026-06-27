"""V1.6.0 ETL 统一重试策略。

基于 tenacity 的指数退避重试装饰器,供 pipeline 各阶段统一使用。

重试参数:
- attempts: 3 次(默认)
- wait: 指数退避,min=5s, max=60s, multiplier=2
- retry: httpx.HTTPError / httpx.TimeoutException / ConnectionError / OSError

使用方式:
    @etl_retry
    async def my_etl_function():
        ...

    # 或在 pipeline 中:
    await etl_retry_async(stage_func, *args, **kwargs)
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

# ---- 重试策略常量 ----

ETL_RETRY_ATTEMPTS: int = 3
ETL_RETRY_MIN_WAIT: int = 5  # 秒
ETL_RETRY_MAX_WAIT: int = 60  # 秒
ETL_RETRY_MULTIPLIER: int = 2

# 可重试的异常类型
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    OSError,
    TimeoutError,
)

# 尝试导入 httpx(网络请求常见异常)
try:
    import httpx

    RETRYABLE_EXCEPTIONS = RETRYABLE_EXCEPTIONS + (
        httpx.HTTPError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )
except ImportError:
    pass


# ---- 装饰器 ----

etl_retry = retry(
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    stop=stop_after_attempt(ETL_RETRY_ATTEMPTS),
    wait=wait_exponential(
        multiplier=ETL_RETRY_MULTIPLIER,
        min=ETL_RETRY_MIN_WAIT,
        max=ETL_RETRY_MAX_WAIT,
    ),
    reraise=True,
    before_sleep=_log_retry_attempt if False else None,  # noqa: F821 placeholder
)


def _log_before_sleep(retry_state) -> None:
    """重试前日志记录。"""
    log.warning(
        "etl.retry.sleeping",
        attempt=retry_state.attempt_number,
        wait=retry_state.upcoming_sleep,
        fn=getattr(retry_state.fn, "__name__", "?"),
    )


# 重新定义带日志的装饰器
etl_retry = retry(
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    stop=stop_after_attempt(ETL_RETRY_ATTEMPTS),
    wait=wait_exponential(
        multiplier=ETL_RETRY_MULTIPLIER,
        min=ETL_RETRY_MIN_WAIT,
        max=ETL_RETRY_MAX_WAIT,
    ),
    before_sleep=_log_before_sleep,
    reraise=True,
)


# ---- 函数式调用 ----

T = TypeVar("T")


async def etl_retry_async(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    stage_name: str = "",
    **kwargs: Any,
) -> T:
    """异步函数重试包装。

    Args:
        func: 要执行的异步函数
        *args: 函数参数
        stage_name: 阶段名称(用于日志)
        **kwargs: 函数关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次重试失败后抛出原始异常
    """
    last_error: Exception | None = None

    for attempt in range(1, ETL_RETRY_ATTEMPTS + 1):
        try:
            return await func(*args, **kwargs)
        except RETRYABLE_EXCEPTIONS as e:
            last_error = e
            if attempt < ETL_RETRY_ATTEMPTS:
                wait_time = min(
                    ETL_RETRY_MIN_WAIT * (ETL_RETRY_MULTIPLIER ** (attempt - 1)),
                    ETL_RETRY_MAX_WAIT,
                )
                log.warning(
                    "etl.retry.attempt_failed",
                    stage=stage_name or func.__name__,
                    attempt=attempt,
                    max_attempts=ETL_RETRY_ATTEMPTS,
                    wait_seconds=wait_time,
                    error=str(e),
                )
                import asyncio

                await asyncio.sleep(wait_time)
            else:
                log.error(
                    "etl.retry.all_failed",
                    stage=stage_name or func.__name__,
                    attempts=ETL_RETRY_ATTEMPTS,
                    error=str(e),
                )

    # 不应该到这里,但保险起见
    if last_error:
        raise last_error
    raise RuntimeError(f"etl_retry_async: unexpected state for {stage_name}")


# ---- Pipeline Stage 包装 ----


async def run_stage_with_retry(
    stage_name: str,
    func: Callable[..., Awaitable[T]],
    *args: Any,
    report=None,
    mark_failed_fn=None,
    trade_date=None,
    source_name: str = "",
    **kwargs: Any,
) -> T | None:
    """Pipeline 阶段重试包装(集成 PipelineReport + mark_failed)。

    Args:
        stage_name: 阶段名(如 "load_daily_price")
        func: 异步函数
        report: PipelineReport 实例(可选,失败时 add_error)
        mark_failed_fn: mark_failed 异步函数(可选)
        trade_date: 交易日期(供 mark_failed 使用)
        source_name: 数据源名(供 mark_failed 使用)

    Returns:
        函数返回值,全部失败时返回 None
    """
    try:
        return await etl_retry_async(func, *args, stage_name=stage_name, **kwargs)
    except Exception as e:  # noqa: BLE001
        log.error("pipeline.stage.failed", stage=stage_name, error=str(e))
        if report:
            report.add_error(stage_name, str(e))
        if mark_failed_fn and trade_date:
            try:
                await mark_failed_fn(
                    trade_date,
                    source_name or stage_name,
                    error=str(e),
                )
            except Exception:  # noqa: BLE001
                pass
        return None
