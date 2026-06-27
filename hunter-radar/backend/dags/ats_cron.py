"""ATS Fallback Cron:美东 18:00 + 次日 04:00(V1.5.9)。

FINRA ATS 周报数据通常在工作日 18:00 ET 后发布。
本 Cron 在两个时间点尝试拉取:
  - 美东 18:00(UTC 22:00):盘后首次尝试
  - 美东 04:00(UTC 08:00):次日凌晨重试(覆盖延迟发布场景)

当主源返回空时,触发 Playwright fallback 爬虫。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone, timedelta

log = logging.getLogger(__name__)

_ET_OFFSET = timedelta(hours=-5)


async def run_ats_cron() -> dict:
    """ATS Cron 入口:尝试主源 → 空则触发 fallback。"""
    from etl.finra_short import run as finra_run
    from etl.load_ats_short import load_ats_short, pull_finra_ats
    from etl.ats_scraper import fetch_ats_data_fallback, load_ats_fallback, check_fallback_streak
    from etl.refresh_data_status import mark_ready, mark_pending
    from app.services.ats_fallback import warm_ats_cache
    from etl.symbol_seed import DEFAULT_SEEDS

    now_utc = datetime.now(timezone.utc)
    now_et = now_utc + _ET_OFFSET
    trade_date = now_et.date()

    # 周末跳过
    if now_et.weekday() >= 5:
        log.info("[ATS_Cron] 周末,跳过")
        return {"skipped": "weekend"}

    result = {"trade_date": str(trade_date)}

    # 1) 尝试主源(FINRA 周报)
    rows = await pull_finra_ats(week_ending=trade_date)
    if rows:
        res = await load_ats_short(rows, source="finra_ats")
        await mark_ready(
            trade_date, "finra_ats",
            detail={"attempted": res.attempted, "inserted": res.inserted},
        )
        result["source"] = "finra_ats"
        result["inserted"] = res.inserted
    else:
        # 2) 主源空 → 触发 fallback
        log.info("[ATS_Cron] 主源返回空,触发 fallback")
        scraper = await fetch_ats_data_fallback(trade_date=trade_date)
        if scraper.rows:
            res = await load_ats_fallback(scraper.rows)
            await mark_ready(
                trade_date, "ats_fallback",
                detail={"attempted": res.attempted, "inserted": res.inserted},
            )
            result["source"] = "ats_fallback"
            result["inserted"] = res.inserted
            # 连续降级检测
            streak = await check_fallback_streak(trade_date)
            result["fallback_streak"] = streak
        else:
            await mark_pending(trade_date, "ats_fallback", reason="主源和 fallback 均无数据")
            result["source"] = "none"

    # 3) 缓存预热
    tickers = [s["ticker"] for s in DEFAULT_SEEDS if s["is_universe"]]
    warmed = await warm_ats_cache(tickers, trade_date)
    result["cache_warmed"] = warmed

    log.info("[ATS_Cron] 完成: %s", result)
    return result


async def main() -> None:
    """CLI: `python -m dags.ats_cron`"""
    result = await run_ats_cron()
    print(f"[ATS_Cron] result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
