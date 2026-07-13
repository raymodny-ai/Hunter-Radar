"""V1.6.0 ETL 多源冗余框架(BD-100+)。

抽象接口 + 多源 Provider + 自动降级管理器。
主源 yfinance → 备份 Alpha Vantage → 最终兜底(最近缓存)。

设计原则:
- 数据契约不变(DailyBar / OptionContract dataclass 复用)
- Provider 实现可热插拔
- DataProviderManager 统一入口,pipeline 不再直接调 yfinance
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Literal

log = logging.getLogger(__name__)


# ---- 数据契约(从 yfinance_pull 复用) ----


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


# ---- 抽象接口 ----


class MarketDataProvider(ABC):
    """行情数据提供者抽象接口。

    所有 Provider 必须实现:
    - fetch_daily_bars(): 日 K 线
    - fetch_options_chain(): 期权链
    """

    name: str = "base"

    @abstractmethod
    async def fetch_daily_bars(
        self, symbol: str, start: date, end: date
    ) -> list[DailyBar]:
        """拉取日 K 线数据。"""

    @abstractmethod
    async def fetch_options_chain(self, symbol: str) -> list[OptionContract]:
        """拉取期权链数据。"""

    async def health_check(self) -> bool:
        """健康检查(默认 True)。"""
        return True


# ---- YFinance Provider ----


class YFinanceProvider(MarketDataProvider):
    """yfinance SDK Provider(主源)。

    包装现有 etl.yfinance_pull 的逻辑,保持数据契约不变。
    """

    name: str = "yfinance"

    def __init__(self) -> None:
        from etl.yfinance_pull import _limiter

        self._limiter = _limiter

    async def fetch_daily_bars(
        self, symbol: str, start: date, end: date
    ) -> list[DailyBar]:
        import yfinance as yf

        await self._limiter.acquire()
        ticker = yf.Ticker(symbol)
        df = await asyncio.to_thread(
            ticker.history,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
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

    async def fetch_options_chain(self, symbol: str) -> list[OptionContract]:
        import yfinance as yf

        await self._limiter.acquire()
        ticker = yf.Ticker(symbol)
        # yfinance Ticker.options 是 property(返回 tuple),不是 method
        expirations: tuple[str, ...] = await asyncio.to_thread(lambda: ticker.options)
        out: list[OptionContract] = []
        for exp in expirations:
            await self._limiter.acquire()
            chain = await asyncio.to_thread(ticker.option_chain, exp)
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
                            volume=_safe_int(row.get("volume")),
                            open_interest=_safe_int(row.get("openInterest")),
                            implied_vol=_safe_float(row.get("impliedVolatility")),
                            in_the_money=bool(row.get("inTheMoney", False)),
                        )
                    )
        return out


# ---- Alpha Vantage Provider(备份源) ----


class AlphaVantageProvider(MarketDataProvider):
    """Alpha Vantage API Provider(备份源)。

    免费层:25 req/day, 5 req/min。
    覆盖核心 ticker 的日 K;期权链暂返回空列表。
    """

    name: str = "alpha_vantage"
    _BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or ""
        self._daily_calls_today = 0
        self._daily_limit = 25

    async def fetch_daily_bars(
        self, symbol: str, start: date, end: date
    ) -> list[DailyBar]:
        """通过 Alpha Vantage TIME_SERIES_DAILY 拉取日 K。"""
        if not self._api_key:
            log.warning("alpha_vantage.no_api_key")
            return []
        if self._daily_calls_today >= self._daily_limit:
            log.warning("alpha_vantage.daily_limit_reached", limit=self._daily_limit)
            return []

        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    self._BASE_URL,
                    params={
                        "function": "TIME_SERIES_DAILY",
                        "symbol": symbol,
                        "apikey": self._api_key,
                        "outputsize": "compact",  # 最近 100 条
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            self._daily_calls_today += 1

            ts_data = data.get("Time Series (Daily)", {})
            if not ts_data:
                log.warning("alpha_vantage.no_data", symbol=symbol)
                return []

            out: list[DailyBar] = []
            for date_str, vals in ts_data.items():
                try:
                    d = date.fromisoformat(date_str)
                except ValueError:
                    continue
                if d < start or d > end:
                    continue
                out.append(
                    DailyBar(
                        trade_date=d,
                        symbol=symbol,
                        open=float(vals.get("1. open", 0)),
                        high=float(vals.get("2. high", 0)),
                        low=float(vals.get("3. low", 0)),
                        close=float(vals.get("4. close", 0)),
                        adj_close=float(vals.get("5. adjusted close", vals.get("4. close", 0))),
                        volume=int(vals.get("6. volume", 0)),
                    )
                )
            out.sort(key=lambda b: b.trade_date)
            log.info(
                "alpha_vantage.fetch_daily_bars.done",
                symbol=symbol,
                bars=len(out),
            )
            return out
        except Exception as e:  # noqa: BLE001
            log.error("alpha_vantage.fetch_daily_bars.fail", symbol=symbol, error=str(e))
            return []

    async def fetch_options_chain(self, symbol: str) -> list[OptionContract]:
        """Alpha Vantage 免费层不支持期权链,返回空列表。"""
        log.info("alpha_vantage.no_options_support", symbol=symbol)
        return []

    async def health_check(self) -> bool:
        return bool(self._api_key) and self._daily_calls_today < self._daily_limit


# ---- DataProviderManager(多源降级管理器) ----


@dataclass(slots=True)
class FetchResult:
    """数据拉取结果(含来源标记)。"""

    data: list[DailyBar] | list[OptionContract]
    source: str  # 'yfinance' | 'alpha_vantage' | 'cache'
    is_fallback: bool = False
    error: str | None = None


class DataProviderManager:
    """多源行情数据管理器。

    降级策略:
    1. 主源(yfinance)成功 → 返回
    2. 主源失败 → 备份源(Alpha Vantage)
    3. 备份源也失败 → 返回空列表 + 标记 error

    pipeline 通过本管理器统一取数,不直接调具体 Provider。
    """

    def __init__(
        self,
        primary: MarketDataProvider | None = None,
        fallbacks: list[MarketDataProvider] | None = None,
    ) -> None:
        self.primary = primary or YFinanceProvider()
        self.fallbacks = fallbacks or []
        # 默认加 Alpha Vantage 作为备份
        if not self.fallbacks:
            from app.core.config import settings

            av_key = getattr(settings, "alpha_vantage_api_key", "")
            if av_key:
                self.fallbacks.append(AlphaVantageProvider(api_key=av_key))

    async def fetch_daily_bars(
        self, symbol: str, start: date, end: date
    ) -> FetchResult:
        """拉取日 K,自动降级。"""
        # 1) 主源
        try:
            bars = await self.primary.fetch_daily_bars(symbol, start, end)
            if bars:
                return FetchResult(
                    data=bars, source=self.primary.name, is_fallback=False
                )
            log.warning(
                "provider.primary_empty",
                provider=self.primary.name,
                symbol=symbol,
            )
        except Exception as e:  # noqa: BLE001
            log.warning(
                "provider.primary_fail",
                provider=self.primary.name,
                symbol=symbol,
                error=str(e),
            )

        # 2) 备份源
        for fb in self.fallbacks:
            try:
                bars = await fb.fetch_daily_bars(symbol, start, end)
                if bars:
                    log.info(
                        "provider.fallback_success",
                        provider=fb.name,
                        symbol=symbol,
                        bars=len(bars),
                    )
                    return FetchResult(
                        data=bars, source=fb.name, is_fallback=True
                    )
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "provider.fallback_fail",
                    provider=fb.name,
                    symbol=symbol,
                    error=str(e),
                )

        # 3) 全部失败
        log.error("provider.all_failed", symbol=symbol)
        return FetchResult(data=[], source="none", is_fallback=True, error="all providers failed")

    async def fetch_options_chain(self, symbol: str) -> FetchResult:
        """拉取期权链,自动降级。"""
        # 1) 主源
        try:
            contracts = await self.primary.fetch_options_chain(symbol)
            if contracts:
                return FetchResult(
                    data=contracts, source=self.primary.name, is_fallback=False
                )
        except Exception as e:  # noqa: BLE001
            log.warning(
                "provider.primary_opt_fail",
                provider=self.primary.name,
                symbol=symbol,
                error=str(e),
            )

        # 2) 备份源(Alpha Vantage 不支持期权,跳过)
        for fb in self.fallbacks:
            try:
                contracts = await fb.fetch_options_chain(symbol)
                if contracts:
                    return FetchResult(
                        data=contracts, source=fb.name, is_fallback=True
                    )
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "provider.fallback_opt_fail",
                    provider=fb.name,
                    symbol=symbol,
                    error=str(e),
                )

        log.error("provider.all_opt_failed", symbol=symbol)
        return FetchResult(data=[], source="none", is_fallback=True, error="all providers failed")


# ---- 辅助 ----


def _safe_float(v) -> float | None:
    try:
        if v is None or (isinstance(v, float) and v != v):  # NaN
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int:
    """yfinance 的 volume/openInterest 是 float(可 NaN),安全转为 int。"""
    try:
        if v is None or (isinstance(v, float) and v != v):  # NaN
            return 0
        return int(v)
    except (TypeError, ValueError):
        return 0


def _yfinance_info(ticker: str) -> dict:
    """轻量查 ticker info 用于 lookup 端点(autocomplete)。

    Returns: dict with longName/shortName/quoteType/exchange, or {} on fail.
    Blocking 调用, 应当用 asyncio.to_thread 包装。
    """
    import yfinance as yf

    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception:
        info = {}
    if not info:
        # yfinance 某些版本 0.2.x 后空 ticker info 返 {} 不再 fast_info
        try:
            fi = t.fast_info or {}
            if fi:
                return {
                    "longName": ticker,
                    "shortName": ticker,
                    "quoteType": "EQUITY",
                    "exchange": (fi.get("exchange") or ""),
                }
        except Exception:
            pass
        return {}
    return {
        "longName": info.get("longName") or info.get("shortName") or ticker,
        "shortName": info.get("shortName") or ticker,
        "quoteType": info.get("quoteType", "EQUITY"),
        "exchange": info.get("exchange", ""),
    }


async def fetch_options_recent(symbol: str, max_expirations: int = 3, max_dte_days: int = 60) -> list:
    """轻量 options 拉数(warmup 用): 只拉最近 N 个 expiration, 限 DTE。

    Returns:
        list[OptionContract]
    """
    import yfinance as yf

    t = yf.Ticker(symbol)
    expirations = await asyncio.to_thread(lambda: t.options) or ()
    # 按 DTE 过滤 + 取前 max_expirations
    today = date.today()
    chosen: list[str] = []
    for exp in expirations:
        try:
            d = date.fromisoformat(exp)
        except Exception:
            continue
        if (d - today).days <= max_dte_days:
            chosen.append(exp)
        if len(chosen) >= max_expirations:
            break

    out: list = []
    for exp in chosen:
        try:
            chain = await asyncio.to_thread(t.option_chain, exp)
        except Exception:
            continue
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
                        volume=_safe_int(row.get("volume")),
                        open_interest=_safe_int(row.get("openInterest")),
                        implied_vol=_safe_float(row.get("impliedVolatility")),
                        in_the_money=bool(row.get("inTheMoney", False)),
                    )
                )
    return out
