"""Yahoo Finance 日 K / 期权链拉取(BD-008 / BD-009)。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

log = logging.getLogger(__name__)

# 3.3 (AQ-03): yfinance 外部调用重试 — 网络抖动/限流重试 2 次, 指数退避 5-30s
_YF_ATTEMPTS = 2


async def _yf_call(fn):
    """重试包裹: 把同步 yfinance 调用放进线程池, 失败重试 (3.3 AQ-03)。"""
    return await _yf_with_retry(fn)


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(_YF_ATTEMPTS),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    reraise=True,
)
async def _yf_with_retry(fn):
    """async 重试体: 每次 attempt 新建 to_thread 协程并 await (异常可触发重试)。"""
    import asyncio

    return await asyncio.to_thread(fn)


@dataclass(slots=True)
class DailyBar:
    trade_date: date
    symbol: str
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


@dataclass(slots=True)
class OptionContract:
    contract: str
    underlying: str
    expiry: date
    strike: float
    right: Literal["C", "P"]
    last_price: float | None
    bid: float | None
    ask: float | None
    volume: int
    open_interest: int
    implied_vol: float | None
    in_the_money: bool


class _RateLimiter:
    """简单令牌桶,QPS 控制(yfinance 限制 1 QPS)。"""

    def __init__(self, rate_per_sec: float) -> None:
        self._interval = 1.0 / max(0.1, rate_per_sec)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._last + self._interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = asyncio.get_event_loop().time()


_limiter = _RateLimiter(settings.yfinance_rate_limit_per_sec)


async def fetch_daily_bars(symbol: str, start: date, end: date) -> list[DailyBar]:
    """通过 yfinance SDK 拉取个股/ETF 日 K。

    本实现使用 yfinance 包,生产可替换为自有行情商(数据契约不变)。
    """
    import yfinance as yf

    await _limiter.acquire()
    ticker = yf.Ticker(symbol)
    # yfinance 同步 API 放进线程池执行 (失败自动重试 3.3)
    df = await _yf_call(
        lambda: ticker.history(
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
        )
    )
    out: list[DailyBar] = []
    for ts, row in df.iterrows():
        d = ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10])
        out.append(
            DailyBar(
                trade_date=d,
                symbol=symbol,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                adj_close=float(row.get("Adj Close", row["Close"])),
                volume=int(row.get("Volume", 0)),
            )
        )
    return out


async def fetch_options_chain(symbol: str, max_dte: int | None = None) -> list[OptionContract]:
    """拉取未到期合约的 Volume / OI / 行权价 / 到期日。

    方案 3.2 (AQ-02): `max_dte` 前置过滤 — 仅拉取 DTE ≤ max_dte 的到期日,
    减少远月无用 API 调用(正常盘后采集限 7 天内可省 ~70% 配额)。
    max_dte=None 时拉全部到期日(历史回填等需要全链场景)。

    yfinance 返回的 options 数据较慢;生产建议用更专业的行情商。
    """
    import yfinance as yf

    await _limiter.acquire()
    ticker = yf.Ticker(symbol)
    # yfinance 1.x: Ticker.options 是 property(tuple), 不是 method (失败重试 3.3)
    expirations: list[str] = list(await _yf_call(lambda: ticker.options))
    today = date.today()
    # 前置过滤: 仅保留 DTE ≤ max_dte 的到期日 (None → 全部)
    if max_dte is not None:
        expirations = [
            e for e in expirations
            if (date.fromisoformat(e) - today).days <= max_dte
        ]
        if not expirations:
            log.info("options.no_valid_expiry", symbol=symbol, max_dte=max_dte)
            return []
    out: list[OptionContract] = []
    for exp in expirations:
        await _limiter.acquire()
        chain = await _yf_call(lambda e=exp: ticker.option_chain(e))
        for df, right in [(chain.calls, "C"), (chain.puts, "P")]:
            for _, row in df.iterrows():
                out.append(
                    OptionContract(
                        contract=row.get("contractSymbol", ""),
                        underlying=symbol,
                        expiry=date.fromisoformat(exp),
                        strike=float(row["strike"]),
                        right=right,
                        last_price=_safe_float(row.get("lastPrice")),
                        bid=_safe_float(row.get("bid")),
                        ask=_safe_float(row.get("ask")),
                        volume=_safe_int(row.get("volume", 0)),
                        open_interest=_safe_int(row.get("openInterest", 0)),
                        implied_vol=_safe_float(row.get("impliedVolatility")),
                        in_the_money=bool(row.get("inTheMoney", False)),
                    )
                )
    return out


def _safe_float(v) -> float | None:
    try:
        if v is None or (isinstance(v, float) and v != v):  # NaN
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int:
    """NaN-safe int cast (yfinance 1.x 常返 float NaN for volume/OI)."""
    try:
        if v is None or (isinstance(v, float) and v != v):
            return 0
        return int(float(v))
    except (TypeError, ValueError):
        return 0
        return None
