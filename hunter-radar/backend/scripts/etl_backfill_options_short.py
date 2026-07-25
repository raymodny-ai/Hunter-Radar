"""补齐 short_volume + options_chain + 重建 threat_score (全年)。

前提:daily_price 已经入库 (2130 行 142 天 × 15 ticker)。
现在缺: short_volume + options_chain 只跑了 4 天,要扩到全年 11+ 天。
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from datetime import date

sys.path.insert(0, ".")

# 触发 logger patch
try:
    import app.main  # noqa: F401
except Exception:
    pass

from app.core.database import AsyncSessionLocal
from etl.load_daily_price import load_daily_price as load_dp
from etl.load_short_volume import load_short_volume as load_sv
from etl.load_options_chain import load_options_chain as load_oc
from etl.load_threat_score import compute_threat_scores
from etl.refresh_data_status import mark_ready
from etl.finra_short import run as finra_run
from etl.yfinance_pull import fetch_options_chain, DailyBar
from sqlalchemy import text

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "BABA",
    "GME", "AMC", "SPY", "QQQ", "IWM", "VTI", "DIA",
]

# 11 个目标日期(美东月末, 已经是交易日)
TARGET_DATES = [
    date(2024, 1, 30),
    date(2024, 2, 29),
    date(2024, 3, 15),    # 实际只有 3-15 (因 3-29 周五 Good Friday 前一天放假)
    date(2024, 4, 29),
    date(2024, 5, 31),
    date(2024, 6, 28),
    date(2024, 7, 31),
    date(2024, 8, 30),
    date(2024, 9, 30),
    date(2024, 10, 31),
    date(2024, 11, 29),
    date(2024, 12, 31),
]


async def main():
    t_total = time.time()
    log.info(f"=== 补齐 short_volume + options_chain + threat_score (全年 {len(TARGET_DATES)} 天) ===")

    for target in TARGET_DATES:
        log.info(f"\n===== {target} =====")
        t_m = time.time()

        # 1) short_volume (FINRA)
        try:
            sv = await finra_run(target)
            if sv:
                async with AsyncSessionLocal() as session:
                    res = await load_sv(sv, source="finra", session=session)
                    await session.commit()
                    log.info(f"  short_volume: {len(sv)} rows, load={res.inserted if hasattr(res, 'inserted') else 'ok'}")
            else:
                log.info(f"  short_volume: empty (可能是节假日)")
        except Exception as e:
            log.warning(f"  short_volume fail: {e}")

        # 2) options_chain (per ticker, 批量收集后一次写)
        contracts_all = []
        for ticker in TICKERS:
            try:
                contracts = await fetch_options_chain(ticker)
                contracts_all.extend(contracts)
            except Exception as e:
                log.warning(f"  {ticker} options fail: {e}")
                continue
        if contracts_all:
            try:
                async with AsyncSessionLocal() as session:
                    res = await load_oc(contracts_all, trade_date=target, source="yfinance", session=session)
                    await session.commit()
                    log.info(f"  options_chain: {len(contracts_all)} fetched, load={res.inserted if hasattr(res, 'inserted') else 'ok'}")
            except Exception as e:
                log.warning(f"  options_chain load fail: {e}")
        else:
            log.info(f"  options_chain: empty")

        # 3) threat_score for that day
        try:
            async with AsyncSessionLocal() as session:
                ts_res = await compute_threat_scores(target, session=session)
                await session.commit()
                log.info(f"  threat_score: {ts_res.attempted} attempted, {ts_res.inserted} inserted, red={ts_res.red_count}, yellow={ts_res.yellow_count}")
                try:
                    await mark_ready(target, session=session)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"  threat_score fail: {e}")

        log.info(f"  ----- {target} 总耗时: {time.time()-t_m:.1f}s -----")

    log.info(f"\n=== 全年补齐完成, 总耗时: {(time.time()-t_total)/60:.1f}min ===")


if __name__ == "__main__":
    asyncio.run(main())