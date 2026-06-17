"""M10-t2 BD-088 ETF 申赎代理 — V1.5.2 真实代理数据源(yfinance)。

数据源链路(生产 vs 沙箱):
- 生产:yfinance → ETF 实时市价 + 30 天历史 → 计算 premium/discount 代理指标
  沙箱:yfinance 不可用 → fallback `app/services/etf_proxy.py:build_etf_basket()` + compute_premium_discount()(沿用 m9t5)
- 成分股详情:仍 mock(需 Bloomberg/Refinitiv 付费数据,R-38 部分解除)

代理指标(沿用 BD-088 方案):
1. Premium/Discount to NAV(折溢价率):基于实时市价 vs NAV
2. INAV 偏离度:iNAV vs NAV 偏离(%)
3. 二级市场异常放量:近 5 日均量 vs 近 30 日均量(>2x 触发)
4. 套利窗口:综合 |premium_pct| > 0.5% + 偏离度 > 0.3% → arb_opportunity

环境变量:
- ETF_PROVIDER:可选,默认 "yfinance"(支持 "yfinance" / "sandbox")
- ETF_PROXY_TIMEOUT_SEC:可选,默认 10.0
"""
from __future__ import annotations

import asyncio
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# 探测 yfinance 是否可用(沙箱 fallback 用)
try:
    import yfinance as yf  # type: ignore[import-untyped]
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

# 沿用 m9t5 sandbox 模块
from app.services.etf_proxy import (  # noqa: E402
    SANDBOX_REVIEW_MODE,
    EtfBasket,
    build_etf_basket,
    compute_premium_discount,
)

# 真实模式常量
PRODUCTION_REVIEW_MODE = "production_real"
SANDBOX_FALLBACK_REVIEW_MODE = "sandbox_stub_v15_prep"
PROVIDER_YFINANCE = "yfinance"
PROVIDER_SANDBOX = "sandbox"

# 配置
ETF_PROVIDER_DEFAULT = PROVIDER_YFINANCE
ETF_PROXY_TIMEOUT_DEFAULT = 10.0

# 套利窗口阈值
ARB_PREMIUM_PCT_THRESHOLD = 0.5  # |premium_pct| > 0.5%
ARB_INAV_DEVIATION_THRESHOLD = 0.3  # |inav_deviation| > 0.3%
VOLUME_SPIKE_RATIO_THRESHOLD = 2.0  # 5d 均量 / 30d 均量 > 2x


@dataclass
class EtfProxyIndicators:
    """ETF 代理指标(premium/discount/inav_deviation/volume_spike)。"""

    etf_ticker: str
    market_price: float
    nav: float
    inav: float
    premium: float
    premium_pct: float
    inav_deviation: float  # (inav - nav) / nav * 100
    volume_5d_avg: int
    volume_30d_avg: int
    volume_spike_ratio: float
    arb_opportunity: bool
    fetched_at: str
    fetch_source: str  # "yfinance" | "sandbox"
    review_mode: str
    sandbox: bool
    http_latency_ms: int | None = None
    warning: str | None = None
    query_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def _calc_inav_deviation(nav: float, inav: float) -> float:
    """iNAV 偏离度 = (iNAV - NAV) / NAV * 100。"""
    if nav <= 0:
        return 0.0
    return round((inav - nav) / nav * 100, 4)


def _calc_volume_spike(volumes_5d: list[int], volumes_30d: list[int]) -> tuple[float, int, int]:
    """5 日均量 / 30 日均量,返 (ratio, 5d_avg, 30d_avg)。"""
    avg_5d = int(statistics.mean(volumes_5d)) if volumes_5d else 0
    avg_30d = int(statistics.mean(volumes_30d)) if volumes_30d else 0
    if avg_30d <= 0:
        return 0.0, avg_5d, avg_30d
    ratio = round(avg_5d / avg_30d, 4)
    return ratio, avg_5d, avg_30d


async def fetch_etf_proxy_indicators(
    etf_ticker: str,
    *,
    provider: str | None = None,
    timeout: float | None = None,
) -> EtfProxyIndicators:
    """ETF 代理指标拉取(优先 yfinance,失败 fallback sandbox)。

    Args:
        etf_ticker: ETF ticker(如 "SPY")
        provider: 数据源(默认 "yfinance",可选 "sandbox" 强制沙箱)
        timeout: 超时秒数

    Returns:
        EtfProxyIndicators(含 fetch_source / review_mode / warning)
    """
    etf_t = etf_ticker.strip().upper()
    provider = provider or _get_env("ETF_PROVIDER", ETF_PROVIDER_DEFAULT) or PROVIDER_YFINANCE
    timeout = timeout or float(_get_env("ETF_PROXY_TIMEOUT_SEC", str(ETF_PROXY_TIMEOUT_DEFAULT)))
    fetched_at = _now_iso()

    # 强制 sandbox 或 yfinance 不可用 → fallback
    if provider == PROVIDER_SANDBOX or not YFINANCE_AVAILABLE:
        return _build_indicators_sandbox(
            etf_t,
            fetched_at,
            reason="provider_sandbox" if provider == PROVIDER_SANDBOX else "yfinance_unavailable",
        )

    # yfinance 真实拉取
    started = datetime.now(timezone.utc)
    try:
        ticker_obj = yf.Ticker(etf_t)
        # 30 日历史(用于 5d/30d 均量计算)
        hist = await asyncio.wait_for(
            asyncio.to_thread(lambda: ticker_obj.history(period="1mo")),
            timeout=timeout,
        )
        if hist is None or hist.empty:
            raise ValueError("yfinance 返空数据")
        latest = hist.iloc[-1]
        market_price = float(latest["Close"])
        volumes_30d = hist["Volume"].astype(int).tolist()
        volumes_5d = volumes_30d[-5:] if len(volumes_30d) >= 5 else volumes_30d
        spike_ratio, avg_5d, avg_30d = _calc_volume_spike(volumes_5d, volumes_30d)
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

        # 构造 EtfBasket(沙箱 build_etf_basket 拿 NAV / iNAV)
        basket = build_etf_basket(etf_t)
        nav = basket.nav
        inav = basket.inav
        # 真实模式:用 yfinance 市价重算 premium/discount
        premium = round(market_price - nav, 4)
        premium_pct = round(premium / nav * 100, 4) if nav > 0 else 0.0
        inav_deviation = _calc_inav_deviation(nav, inav)
        arb_op = abs(premium_pct) > ARB_PREMIUM_PCT_THRESHOLD or abs(inav_deviation) > ARB_INAV_DEVIATION_THRESHOLD

        return EtfProxyIndicators(
            etf_ticker=etf_t,
            market_price=round(market_price, 4),
            nav=nav,
            inav=inav,
            premium=premium,
            premium_pct=premium_pct,
            inav_deviation=inav_deviation,
            volume_5d_avg=avg_5d,
            volume_30d_avg=avg_30d,
            volume_spike_ratio=spike_ratio,
            arb_opportunity=arb_op,
            fetched_at=fetched_at,
            fetch_source=PROVIDER_YFINANCE,
            review_mode=PRODUCTION_REVIEW_MODE,
            sandbox=False,
            http_latency_ms=latency_ms,
            warning=None,
            query_meta={"provider": provider, "history_rows": len(hist)},
        )
    except asyncio.TimeoutError:
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return _build_indicators_sandbox(
            etf_t,
            fetched_at,
            reason="yfinance_timeout",
            latency_ms=latency_ms,
            warning=f"yfinance 超时({timeout}s),fallback 到 sandbox",
        )
    except Exception as e:  # noqa: BLE001
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return _build_indicators_sandbox(
            etf_t,
            fetched_at,
            reason="yfinance_error",
            latency_ms=latency_ms,
            warning=f"yfinance 异常({type(e).__name__}: {e}),fallback 到 sandbox",
        )


def _build_indicators_sandbox(
    etf_t: str,
    fetched_at: str,
    *,
    reason: str,
    latency_ms: int | None = None,
    warning: str | None = None,
) -> EtfProxyIndicators:
    """构造 sandbox 代理指标(沿用 m9t5 build_etf_basket + compute_premium_discount)。

    沙箱无市场实时价 → market_price=nav(premium=0,premium_pct=0)。
    """
    basket = build_etf_basket(etf_t)
    # 沙箱模式:用 nav 作为 market_price(premium=0)
    pd_result = compute_premium_discount(basket, market_price=basket.nav)
    return EtfProxyIndicators(
        etf_ticker=etf_t,
        market_price=pd_result["market_price"],
        nav=basket.nav,
        inav=basket.inav,
        premium=pd_result["premium"],
        premium_pct=pd_result["premium_pct"],
        inav_deviation=_calc_inav_deviation(basket.nav, basket.inav),
        volume_5d_avg=0,
        volume_30d_avg=0,
        volume_spike_ratio=0.0,
        arb_opportunity=pd_result["arb_opportunity"],
        fetched_at=fetched_at,
        fetch_source=PROVIDER_SANDBOX,
        review_mode=SANDBOX_FALLBACK_REVIEW_MODE,
        sandbox=True,
        http_latency_ms=latency_ms,
        warning=warning or f"sandbox fallback(reason={reason})",
        query_meta={"reason": reason},
    )


def main() -> int:
    """CLI:拉 ETF 代理指标(单 ticker 调试用)。"""
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(description="ETF 代理指标 real + sandbox fallback (m10t2)")
    parser.add_argument("--ticker", type=str, default="SPY", help="ETF ticker")
    parser.add_argument("--provider", type=str, default=None, help="yfinance | sandbox")
    parser.add_argument("--timeout", type=float, default=ETF_PROXY_TIMEOUT_DEFAULT)
    args = parser.parse_args()

    indicators = asyncio.run(fetch_etf_proxy_indicators(
        args.ticker,
        provider=args.provider,
        timeout=args.timeout,
    ))
    print(_json.dumps({
        "indicators": indicators.to_dict(),
        "yfinance_available": YFINANCE_AVAILABLE,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())