"""全年 ETL — 直接 yfinance.download 绕过 DataProviderManager。

Owner 报告 2026-07-26 凌晨 DataProviderManager fallback 在新浪财经墙重试卡死。
本次 ETL 改用裸 yf.download (Yahoo Finance 单一源),跑 2024 全年 12 个月。

Usage:
    .venv/bin/python -u scripts/etl_year_2024.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from datetime import date, timedelta

# 调 etl 模块需要数据库
sys.path.insert(0, ".")

# 重要:触发 app.main 启动 → 注册 _patch_logger_log 让 stdlib logger 接受 structlog kwargs
try:
    import app.main  # noqa: F401
except Exception:
    pass

import yfinance as yf

from app.core.database import AsyncSessionLocal
from etl.load_daily_price import load_daily_price as load_dp
from etl.load_short_volume import load_short_volume as load_sv
from etl.load_options_chain import load_options_chain as load_oc
from etl.load_threat_score import compute_threat_scores
from etl.refresh_data_status import mark_ready
from sqlalchemy import text

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "BABA",
    "GME", "AMC", "SPY", "QQQ", "IWM", "VTI", "DIA",
]

# 2024 全年 12 个月最后交易日 (Friday or last bizday of month)
# 简化:每月最后一个交易日(美东)
TARGET_DATES = [
    date(2024, 1, 31),   # ✓ done
    date(2024, 2, 29),   # ✓ done
    date(2024, 3, 29),   # ✓ done
    date(2024, 4, 30),   # ✓ done
    date(2024, 5, 31),
    date(2024, 6, 28),
    date(2024, 7, 31),
    date(2024, 8, 30),
    date(2024, 9, 30),
    date(2024, 10, 31),
    date(2024, 11, 29),
    date(2024, 12, 31),
]


def _pull_daily_prices_sync(ticker: str, start: date, end: date) -> list[dict]:
    """裸 yf.download, 一次拿一个月日 K."""
    t0 = time.time()
    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),  # yfinance end exclusive
        progress=False,
        auto_adjust=False,
        threads=False,
    )
    if df is None or df.empty:
        return []
    # yfinance 1.x 返回 multi-index 即使单 ticker (列 = (Field, Ticker))
    # 扁平化 columns
    if hasattr(df.columns, 'get_level_values'):
        # MultiIndex — 取 ticker 字段
        if 'Ticker' in df.columns.names or len(df.columns.names) > 1:
            df.columns = [c[0] for c in df.columns]
        else:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    elif isinstance(df.columns, tuple):
        df = df.droplevel(1, axis=1) if len(df.columns.names) > 1 else df

    def _val(row, key):
        v = row[key]
        if hasattr(v, 'iloc'):
            return v.iloc[0]
        return v

    out = []
    for ts, row in df.iterrows():
        d = ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10])
        out.append({
            "trade_date": d,
            "symbol": ticker,
            "open": float(_val(row, "Open")),
            "high": float(_val(row, "High")),
            "low": float(_val(row, "Low")),
            "close": float(_val(row, "Close")),
            "adj_close": float(_val(row, "Adj Close")),
            "volume": int(_val(row, "Volume") or 0),
        })
    log.info(f"  {ticker} {start}~{end}: {len(out)} bars in {time.time()-t0:.1f}s")
    return out


async def main():
    t_total = time.time()
    new_dates = TARGET_DATES[4:]  # 前 4 个已 done
    log.info(f"=== ETL year 2024 (剩余 {len(new_dates)} 个月): {new_dates[0]} ~ {new_dates[-1]} ===")

    # 当前 PG 已 done 的日期
    async with AsyncSessionLocal() as session:
        rs = await session.execute(text("SELECT DISTINCT trade_date FROM daily_price ORDER BY trade_date"))
        existing = sorted([r[0] for r in rs.all()])
        log.info(f"现有 daily_price 跨度: {existing[0] if existing else None} ~ {existing[-1] if existing else None} ({len(existing)} dates)")

    # 处理每个月
    for target in new_dates:
        log.info(f"\n===== {target} =====")
        t_m = time.time()

        # 拉取当月 daily_price (15 ticker)
        all_bars: list[dict] = []
        for ticker in TICKERS:
            try:
                bars = _pull_daily_prices_sync(ticker, target - timedelta(days=20), target)
                all_bars.extend(bars)
            except Exception as e:
                log.warning(f"  {ticker} FAIL: {e}")
                continue

        # 落库 daily_price (批量)
        if all_bars:
            async with AsyncSessionLocal() as session:
                try:
                    # load_daily_price 签名: list[DailyBar] 期待 DailyBar 对象
                    from etl.yfinance_pull import DailyBar
                    bars_obj = [
                        DailyBar(
                            trade_date=b["trade_date"],
                            symbol=b["symbol"],
                            open=b["open"], high=b["high"], low=b["low"], close=b["close"],
                            adj_close=b["adj_close"], volume=b["volume"],
                        )
                        for b in all_bars
                    ]
                    res = await load_dp(bars_obj, source="yfinance", session=session)
                    log.info(f"  daily_price: {res}")
                    await session.commit()
                except Exception as e:
                    log.warning(f"  daily_price load fail: {e}")
                    await session.rollback()

        # FINRA short_volume (单文件 1 天)
        try:
            from etl.finra_short import run as finra_run
            sv = await finra_run(target)
            if sv:
                async with AsyncSessionLocal() as session:
                    res = await load_sv(sv, source="finra", session=session)
                    log.info(f"  short_volume: {len(sv)} fetched, load result: {res}")
                    await session.commit()
        except Exception as e:
            log.warning(f"  short_volume fail: {e}")

        # options_chain (per ticker)
        oc_count = 0
        for ticker in TICKERS:
            try:
                from etl.yfinance_pull import fetch_options_chain
                contracts = await fetch_options_chain(ticker)
                if contracts:
                    async with AsyncSessionLocal() as session:
                        await load_oc(contracts, symbol=ticker, trade_date=target, source="yfinance", session=session)
                        await session.commit()
                        oc_count += len(contracts)
                else:
                    log.info(f"  {ticker} options: empty")
            except Exception as e:
                log.warning(f"  {ticker} options fail: {e}")
                continue
        log.info(f"  options_chain: {oc_count} contracts")

        # compute threat_score for that day
        try:
            async with AsyncSessionLocal() as session:
                ts_res = await compute_threat_scores(target, session=session)
                log.info(f"  threat_score: {ts_res.attempted} attempted, {ts_res.inserted} inserted")
                await session.commit()
                await mark_ready(target, session=session)
        except Exception as e:
            log.warning(f"  threat_score fail: {e}")

        log.info(f"  ----- {target} 总耗时: {time.time()-t_m:.1f}s -----")

    log.info(f"\n=== 全年 ETL 完成, 总耗时: {(time.time()-t_total)/60:.1f}min ===")


if __name__ == "__main__":
    asyncio.run(main())