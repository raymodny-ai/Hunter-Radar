"""补齐剩余 6 个 trade_date 的 short_volume + options_chain。

Owner 报告 (2026-07-26 凌晨 3 点):
- 已有: 6 dates options + 6 dates short_volume + 12 dates threat_score
- 缺: 2024-05-31 / 06-28 / 07-31 / 08-30 / 09-30 / 10-31 / 11-29 / 12-31 的 short/options

改进:
- 每 ticker 拉完立即写(避免一次性 50k contracts 慢)
- 实时进度 logging (per ticker per day)
- 失败 ticker 跳过继续(不让单个拖死整个 ETL)
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
from etl.load_short_volume import load_short_volume as load_sv
from etl.load_options_chain import load_options_chain as load_oc
from etl.load_threat_score import compute_threat_scores
from etl.refresh_data_status import mark_ready
from etl.finra_short import run as finra_run
from etl.yfinance_pull import fetch_options_chain

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "BABA",
    "GME", "AMC", "SPY", "QQQ", "IWM", "VTI", "DIA",
]

# 剩余 8 个目标日期
TARGET_DATES = [
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
    log.info(f"=== Resume backfill: {len(TARGET_DATES)} dates × (short+options+threat) ===")

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
                    inserted = getattr(res, 'inserted', '?')
                    log.info(f"  short_volume: {len(sv)} fetched, inserted={inserted}")
            else:
                log.info(f"  short_volume: empty (可能节假日)")
        except Exception as e:
            log.warning(f"  short_volume fail: {e}")

        # 2) options_chain (per ticker, 串行立即写)
        oc_total = 0
        for ticker in TICKERS:
            t_tk = time.time()
            try:
                contracts = await fetch_options_chain(ticker)
                if contracts:
                    async with AsyncSessionLocal() as session:
                        res = await load_oc(contracts, trade_date=target, source="yfinance", session=session)
                        await session.commit()
                        inserted = getattr(res, 'inserted', len(contracts))
                    oc_total += inserted
                    log.info(f"  {ticker:6s} options: {len(contracts)} fetched, inserted={inserted}, {time.time()-t_tk:.1f}s")
                else:
                    log.info(f"  {ticker:6s} options: empty, {time.time()-t_tk:.1f}s")
            except Exception as e:
                log.warning(f"  {ticker:6s} options FAIL: {e}")
        log.info(f"  options_chain TOTAL: {oc_total} contracts")

        # 3) threat_score
        try:
            async with AsyncSessionLocal() as session:
                ts_res = await compute_threat_scores(target, session=session)
                await session.commit()
                log.info(f"  threat_score: {ts_res.attempted} attempted, {ts_res.inserted} inserted, red={ts_res.red_count}, yellow={ts_res.yellow_count}")
                try:
                    await mark_ready(target, session=session)
                except Exception as e:
                    log.warning(f"  mark_ready fail: {e}")
        except Exception as e:
            log.warning(f"  threat_score fail: {e}")

        log.info(f"  ----- {target} 总耗时: {time.time()-t_m:.1f}s -----")

    log.info(f"\n=== Resume 完成, 总耗时: {(time.time()-t_total)/60:.1f}min ===")


if __name__ == "__main__":
    asyncio.run(main())