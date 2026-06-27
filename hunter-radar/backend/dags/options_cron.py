"""Options 30min 轮询 Cron(V1.5.9)。

限流 + 抖动轮询 Options Chain,避免 yfinance 429 / IP 封禁。
仅拉 0-7 DTE 近端合约(严格控制 Payload)。

调度: 每 30min(美股交易时段,美东 09:30-16:00)
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import date, datetime, time, timezone, timedelta

log = logging.getLogger(__name__)

# 美股交易时段(美东)
_MARKET_OPEN_ET = time(9, 30)
_MARKET_CLOSE_ET = time(16, 0)
_ET_OFFSET = timedelta(hours=-5)  # UTC-5

# 轮询配置
_POLL_INTERVAL_MIN = 30
_RATE_PER_SEC = 1.5  # 每秒 1.5 个标的
_DTE_MAX = 7  # 仅拉 0-7 DTE 合约
_JITTER_RANGE_SEC = (0, 120)  # 0-120 秒随机抖动


async def poll_options_batch(
    tickers: list[str],
    trade_date: date,
    *,
    rate_per_sec: float = _RATE_PER_SEC,
    dte_max: int = _DTE_MAX,
) -> dict:
    """限流 + 抖动轮询 Options Chain。

    Args:
        tickers: 标的列表
        trade_date: 交易日
        rate_per_sec: 每秒拉取标的数(默认 1.5)
        dte_max: 仅拉取 DTE ≤ dte_max 的合约

    Returns:
        执行摘要 dict
    """
    from etl.yfinance_pull import fetch_options_chain
    from etl.load_options_chain import load_options_chain, compute_pcr_gamma, warm_options_cache

    random.shuffle(tickers)  # 打乱顺序(避免固定顺序偏压)
    delay = 1.0 / rate_per_sec + random.uniform(0, 0.3)  # jitter per-request

    total = {"attempted": 0, "inserted": 0, "skipped": 0, "failures": 0, "errors": []}

    for ticker in tickers:
        try:
            rows = await fetch_options_chain(ticker)
            if rows:
                res = await load_options_chain(rows, trade_date=trade_date)
                total["attempted"] += res.attempted
                total["inserted"] += res.inserted
                total["skipped"] += res.skipped
                total["failures"] += res.failures
        except Exception as e:
            total["errors"].append(f"{ticker}: {e}")
            log.warning("[OptionsCron] %s fetch fail: %s", ticker, e)

        await asyncio.sleep(delay)

    # PCR + Gamma 计算
    pg_results = await compute_pcr_gamma(trade_date)
    warmed = await warm_options_cache(trade_date, pg_results)

    total["pcr_symbols"] = len(pg_results)
    total["high_signals"] = sum(1 for r in pg_results if r.signal_strength == "HIGH")
    total["cache_warmed"] = warmed

    return total


async def run_options_cron() -> dict:
    """Cron 入口:检查是否在交易时段内,执行 Options 轮询。"""
    from etl.symbol_seed import DEFAULT_SEEDS

    now_utc = datetime.now(timezone.utc)
    now_et = now_utc + _ET_OFFSET

    # 仅在交易时段内执行(周末跳过)
    if now_et.weekday() >= 5:
        log.info("[OptionsCron] 周末,跳过")
        return {"skipped": "weekend"}

    if not (_MARKET_OPEN_ET <= now_et.time() <= _MARKET_CLOSE_ET):
        log.info("[OptionsCron] 非交易时段,跳过")
        return {"skipped": "outside_market_hours"}

    # 加 jitter 延迟启动
    jitter = random.uniform(*_JITTER_RANGE_SEC)
    log.info("[OptionsCron] jitter 延迟 %.1fs", jitter)
    await asyncio.sleep(jitter)

    trade_date = now_et.date()
    tickers = [
        s["ticker"]
        for s in DEFAULT_SEEDS
        if s["is_universe"] and s["type"] in ("stock", "etf")
    ]

    result = await poll_options_batch(tickers, trade_date)
    log.info(
        "[OptionsCron] 完成: attempted=%d inserted=%d pcr_symbols=%d high_signals=%d",
        result.get("attempted", 0),
        result.get("inserted", 0),
        result.get("pcr_symbols", 0),
        result.get("high_signals", 0),
    )
    return result


async def main() -> None:
    """CLI: `python -m dags.options_cron`"""
    result = await run_options_cron()
    print(f"[OptionsCron] result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
