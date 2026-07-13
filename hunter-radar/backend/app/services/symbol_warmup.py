"""单标的 warmup ETL 服务(V1.7.0 新增)。

设计目标:
- 标的首次入库(POST /api/v1/symbols)后,后台立即拉真实 yfinance/FINRA 数据
- 替换原有 _seed_ticker 的随机假数据逻辑
- 进度写入 Redis(`warmup:<TICKER>`),前端 /warmup 端点可读
- 用 Redis 锁防同一 ticker 并发重复拉数
- 单 ticker 失败不影响其他 ticker 调度

执行顺序(单标的):
    1. 拉 yfinance 日 K 90 天(供 daily_price + EMA 历史)
    2. 拉 FINRA short volume(最近 5 个交易日)
    3. 算 threat_score_daily(会读 4 模组历史 → 因新标的天数不足,首日 raw=0 是预期)
    4. 写 symbol_master.warmup_completed_at(待 schema 兼容 → 写入 metadata_json)
    5. 清 cache:cache:get_threat_score:<T> / cache:get_threat_history:<T>:90

异常处理:
- yfinance 失败 → 不写 warmup_completed_at,留给重试
- 单阶段失败 → log + 继续下一阶段(尽量给前端一个能 partial 看的看板)
- 整体超时(默认 60s)→ log + 退出 task
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.core.database import AsyncSessionLocal
from app.core.redis_client import redis_client
from app.models import Symbol

log = logging.getLogger(__name__)


# ---- 进度报告(写 Redis) ----
WARMUP_KEY_TPL = "warmup:{ticker}"           # hash: status / progress / last_run / message
WARMUP_LOCK_TPL = "warmup:lock:{ticker}"     # string: 1(防并发)
WARMUP_RESULT_TTL = 60 * 60 * 24 * 2        # 2 天后自动清(给前端看进度用)
WARMUP_LOCK_TTL = 120                        # 单次 warmup 锁


@dataclass(slots=True)
class WarmupResult:
    """单标的 warmup 结果。"""

    ticker: str
    status: str = "pending"          # pending / running / done / failed
    daily_bars: int = 0
    short_rows: int = 0
    threat_rows: int = 0
    options_rows: int = 0
    days_covered: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "status": self.status,
            "daily_bars": self.daily_bars,
            "short_rows": self.short_rows,
            "threat_rows": self.threat_rows,
            "options_rows": self.options_rows,
            "days_covered": self.days_covered,
            "errors": self.errors,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


async def _set_warmup_status(ticker: str, payload: dict[str, Any]) -> None:
    """写 hash 到 Redis。前端读 /warmup 端点拿到。"""
    import json

    key = WARMUP_KEY_TPL.format(ticker=ticker)
    mapping: dict[str, str] = {}
    for k, v in payload.items():
        if isinstance(v, (list, dict)):
            mapping[k] = json.dumps(v, default=str)
        else:
            mapping[k] = "" if v is None else str(v)
    try:
        await redis_client._c.hset(key, mapping=mapping)
        await redis_client._c.expire(key, WARMUP_RESULT_TTL)
    except Exception as e:  # noqa: BLE001
        log.warning("warmup.status.write.fail", extra={"ticker": ticker, "error": str(e)})


async def get_warmup_status(ticker: str) -> dict[str, Any] | None:
    """读 hash;无则返回 None(从未拉数过)。"""
    import json

    key = WARMUP_KEY_TPL.format(ticker=ticker)
    try:
        raw = await redis_client._c.hgetall(key)
        if not raw:
            return None
        out: dict[str, Any] = {}
        for k, v in raw.items():
            if k in ("errors",):
                try:
                    out[k] = json.loads(v)
                except Exception:  # noqa: BLE001
                    out[k] = []
            elif k in ("daily_bars", "short_rows", "threat_rows", "days_covered"):
                try:
                    out[k] = int(v)
                except Exception:  # noqa: BLE001
                    out[k] = 0
            else:
                out[k] = v
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("warmup.status.read.fail", extra={"ticker": ticker, "error": str(e)})
        return None


async def _acquire_lock(ticker: str) -> bool:
    """非阻塞锁,返回 True 表示拿到。"""
    key = WARMUP_LOCK_TPL.format(ticker=ticker)
    try:
        ok = await redis_client._c.set(key, "1", ex=WARMUP_LOCK_TTL, nx=True)
        return bool(ok)
    except Exception:  # noqa: BLE001
        return True   # Redis 挂了就放行,避免阻塞新增标的


async def _release_lock(ticker: str) -> None:
    key = WARMUP_LOCK_TPL.format(ticker=ticker)
    try:
        await redis_client._c.delete(key)
    except Exception:  # noqa: BLE001
        pass


async def _warmup_one_symbol(ticker: str) -> WarmupResult:
    """主流程:1 个 ticker 的 ETL。返回结果,异常不抛(由调用方记状态)。"""
    import time

    t = ticker.strip().upper()
    res = WarmupResult(ticker=t, status="running")
    res.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # ---- 1) daily_price:拉 90 天 ----
    days_back = 90
    start = date.today() - timedelta(days=days_back)
    end = date.today()
    try:
        from etl.yfinance_pull import fetch_daily_bars
        from etl.load_daily_price import load_daily_price

        bars = await fetch_daily_bars(t, start, end)
        if bars:
            load_res = await load_daily_price(bars)
            res.daily_bars = load_res.inserted + load_res.skipped
            res.days_covered = len({b.trade_date for b in bars})
        else:
            res.errors.append("daily_price: yfinance returned empty")
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"daily_price: {e!s}")
        log.warning("warmup.daily_price.fail", extra={"ticker": t, "error": str(e)})

    # ---- 2) FINRA short volume:过去 90 天 (V1.7.2 deep backfill) ----
    # finra_short.run() 签名只接受单日 trade_date, 需循环。
    # 总是拉过去 90 个自然日 (~63 个交易日), 让 Z-Score / EMA 有足够 history
    # 避免冷启动 z=None → 中性 50 的死循环
    # 优化: 如果 DB 已有 50+ 行 short_volume 跨 30+ 天, 说明首次 deep backfill 已跑过, 跳过 FINRA loop
    # 避免每次重跑都重拉 90 个 TXT(每个 11k 行 parse, 耗 4-5 min)
    try:
        from etl.finra_short import run as finra_run
        from etl.load_short_volume import load_short_volume
        from sqlalchemy import select, func, distinct
        from app.models import ShortVolume

        # 检 DB 是否已有足够 short_volume 记录
        async with AsyncSessionLocal() as _sess:
            cnt_q = select(func.count()).select_from(ShortVolume).where(ShortVolume.symbol == t)
            existing_count = (await _sess.execute(cnt_q)).scalar() or 0
            distinct_days_q = select(func.count(distinct(ShortVolume.trade_date))).where(
                ShortVolume.symbol == t
            )
            distinct_days = (await _sess.execute(distinct_days_q)).scalar() or 0
        already_backfilled = existing_count >= 30 and distinct_days >= 20

        finra_lookback_days = 90
        sv_rows: list = []
        if already_backfilled:
            log.info(
                "warmup.finra.skip",
                extra={
                    "ticker": t,
                    "reason": f"already have {existing_count} sv rows across {distinct_days} days",
                },
            )
            # 从 DB 读已有 sv_rows 走后续 derived / threat_score 循环(免重拉 FINRA)
            from etl.finra_short import ShortVolumeRow
            async with AsyncSessionLocal() as _sess2:
                rs = await _sess2.execute(
                    select(ShortVolume).where(ShortVolume.symbol == t).order_by(ShortVolume.trade_date)
                )
                for row in rs.scalars().all():
                    sv_rows.append(
                        ShortVolumeRow(
                            trade_date=row.trade_date,
                            symbol=row.symbol,
                            short_volume=row.short_volume,
                            non_short_volume=row.non_short_volume,
                        )
                    )
        else:
            cur = end
            attempted_days = 0
            while attempted_days < finra_lookback_days:
                cur = cur - timedelta(days=1)
                attempted_days += 1
                try:
                    day_rows = await finra_run(trade_date=cur)
                except Exception:  # noqa: BLE001
                    continue
                sv_rows.extend([r for r in day_rows if r.symbol == t])

        if sv_rows:
            load_res = await load_short_volume(sv_rows)
            res.short_rows = load_res.inserted + load_res.skipped
        else:
            res.errors.append(f"short_volume: FINRA returned no rows for ticker in past {finra_lookback_days} days")
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"short_volume: {e!s}")
        log.warning("warmup.short_volume.fail", extra={"ticker": t, "error": str(e)})

    # ---- 2.5) 派生计算:short_ratio_daily + divergence_window(V1.7.2 循环 90 天) ----
    # 原因:这两个表默认仅取 universe(True),用户后加的 AMD/TSM 不在 universe 里,不走通用 pipeline 也不会算。
    # warmup 显式 symbols=[t] 让 AMD 也能拿到自己的短仓比 + 量价背离。
    # 为让 Z-Score / EMA 有足够 history, 对 sv_dates 升序循环算每个 trade_date
    # divergence 也循环(后期 60 天 daily_price 都齐了后会真有量价背离)
    try:
        from etl.load_short_ratio import compute_short_ratio
        from etl.load_divergence import compute_divergence

        if sv_rows:
            sv_dates = sorted({r.trade_date for r in sv_rows})
            latest_sv_date = sv_dates[-1]
            sr_inserted = 0
            z_scored = 0
            z_warmup = 0
            # warmup 用短 lookback=5,让前 6 个数据点就能产生 Z
            warmup_lookback = 5
            for d in sv_dates:
                sr = await compute_short_ratio(d, symbols=[t], lookback=warmup_lookback)
                sr_inserted += sr.inserted
                z_scored += sr.z_scored
                z_warmup += sr.z_warmup
            # divergence 循环所有 sv_dates(后期 daily_price 有 60 天会真的出现量价背离)
            # warmup 期 daily_price 只 60-90 天, 临时收紧到 lookback=5, history_lookback=20(25 天足够)
            dv_inserted = 0
            for d in sv_dates:
                dv = await compute_divergence(
                    d, symbols=[t], lookback=5, history_lookback=20
                )
                dv_inserted += dv.inserted
            log.info(
                "warmup.derived.compute",
                extra={
                    "ticker": t,
                    "asof": str(latest_sv_date),
                    "short_ratio": sr_inserted,
                    "divergence": dv_inserted,
                    "z_scored": z_scored,
                    "z_warmup": z_warmup,
                    "sv_dates_count": len(sv_dates),
                },
            )
        else:
            latest_sv_date = end
            log.info("warmup.derived.skip", extra={"ticker": t, "reason": "no FINRA short data"})
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"derived(short_ratio/divergence): {e!s}")
        log.warning("warmup.derived.fail", extra={"ticker": t, "error": str(e)})

    # ---- 3) threat_score:循环 90 天每个 sv_date 都算(V1.7.2 deep backfill) ----
    # 目的: 填齐 60+ 天 history → EMA halflife=2 稳定 → ultimate_alert 连续 2 日模块≥60 判断能成立
    # 这样不需要 30 个交易日 ETL 累计, 一次 deep backfill 就足够
    try:
        from etl.load_threat_score import compute_threat_scores

        ts_inserted = 0
        if sv_rows:
            sv_dates = sorted({r.trade_date for r in sv_rows})
            for d in sv_dates:
                ts_res = await compute_threat_scores(d, symbols=[t])
                ts_inserted += ts_res.inserted + ts_res.skipped
        else:
            ts_res = await compute_threat_scores(end, symbols=[t])
            ts_inserted = ts_res.inserted + ts_res.skipped
        res.threat_rows = ts_inserted
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"threat_score: {e!s}")
        log.warning("warmup.threat_score.fail", extra={"ticker": t, "error": str(e)})

    # ---- 3.5) evaluate_ultimate_alerts(V1.7.2): 检测 + 触发终极警报 ----
    # evaluate_ultimate_alerts 默认仅取 universe=True, 用户后加的 AMD/TSM 需传 symbols=[t]
    # 判断逻辑: score ≥ red_threshold(70) + 某模块连续 ≥2 日 ≥60 + 24h 防抖
    try:
        from app.services.ultimate_alert import evaluate_ultimate_alerts

        ua_result = await evaluate_ultimate_alerts(end, symbols=[t])
        log.info(
            "warmup.ultimate_alert.evaluate",
            extra={
                "ticker": t,
                "attempted": ua_result.attempted,
                "rows": len(ua_result.rows),
            },
        )
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"ultimate_alert: {e!s}")
        log.warning("warmup.ultimate_alert.fail", extra={"ticker": t, "error": str(e)})

    # ---- 3.6) options_chain + compute_pcr_gamma + 推 Redis(V1.7.3 options V2 填充) ----
    # 拉近 3 个 expiration, DTE ≤ 60, 上限 ~1500 合约避免 OOM
    # 落库 options_chain + compute_pcr_gamma → Redis cache(opt:{t}:{date})
    try:
        from etl.market_data_provider import fetch_options_recent
        from etl.load_options_chain import load_options_chain, compute_pcr_gamma, warm_options_cache

        contracts = await fetch_options_recent(t, max_expirations=3, max_dte_days=60)
        if contracts:
            # 拿当日 spot
            async with AsyncSessionLocal() as _spot_sess:
                spot_rs = await _spot_sess.execute(
                    select(Symbol.__table__.metadata.tables["daily_price"].c.close)
                    .where(Symbol.__table__.metadata.tables["daily_price"].c.symbol == t)
                    .order_by(Symbol.__table__.metadata.tables["daily_price"].c.trade_date.desc())
                    .limit(1)
                )
                spot_row = spot_rs.first()
            spot_map = {t: float(spot_row[0]) if spot_row and spot_row[0] else 0.0}

            load_res = await load_options_chain(contracts, trade_date=end, spot_by_symbol=spot_map)
            res.options_rows = load_res.inserted + load_res.skipped

            pcrg = await compute_pcr_gamma(end, symbols=[t])
            warmed = await warm_options_cache(end, pcrg)
            log.info(
                "warmup.options.done",
                extra={
                    "ticker": t,
                    "contracts": len(contracts),
                    "options_rows": res.options_rows,
                    "pcr_gamma_rows": len(pcrg),
                    "redis_warmed": warmed,
                },
            )
        else:
            log.info("warmup.options.empty", extra={"ticker": t, "reason": "yfinance 返回 0 合约(可能 ETF 或无期权)"})
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"options: {e!s}")
        log.warning("warmup.options.fail", extra={"ticker": t, "error": str(e)})

    # ---- 4) 写 symbol_master.warmup metadata + 清缓存 ----
    try:
        async with AsyncSessionLocal() as session:
            rs = await session.execute(
                Symbol.__table__.select().where(Symbol.ticker == t)
            )
            row = rs.first()
            if row is not None:
                meta = dict(row.metadata or {})
                meta["warmup_attempts"] = meta.get("warmup_attempts", 0) + 1
                meta["warmup_last_run"] = res.started_at
                meta["warmup_last_status"] = "ok" if not res.errors else "partial"
                meta["warmup_daily_bars"] = res.daily_bars
                from sqlalchemy import update as _update
                await session.execute(
                    _update(Symbol)
                    .where(Symbol.ticker == t)
                    .values(metadata=meta)
                )
                await session.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("warmup.metadata.write.fail", extra={"ticker": t, "error": str(e)})

    # ---- 5) 清缓存,下次 /threat 拉最新 ----
    try:
        keys = [
            f"cache:get_threat_score:{t}",
            f"cache:get_threat_history:{t}:90",
            f"cache:get_threat_history:{t}:30",
        ]
        for k in keys:
            try:
                await redis_client._c.delete(k)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass

    res.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    res.status = "done" if not res.errors else "partial"
    return res


async def schedule_warmup(ticker: str) -> dict[str, Any]:
    """供 API 调用的入口: 加锁 → 后台 task → 立即返回状态。

    返回给调用方的 payload 总是包含:
      - status: scheduled / already_running / done / failed
      - message: 描述
      - warmup_key: Redis hash key(供前端 poll)
    """
    t = ticker.strip().upper()

    # 1) 检查是否正在跑
    if not await _acquire_lock(t):
        existing = await get_warmup_status(t)
        return {
            "status": "already_running",
            "message": f"warmup for {t} is already in progress",
            "warmup": existing,
        }

    # 2) 初始化状态
    await _set_warmup_status(t, {
        "status": "scheduled",
        "started_at": "",
        "finished_at": "",
        "daily_bars": 0,
        "short_rows": 0,
        "threat_rows": 0,
        "days_covered": 0,
        "errors": [],
        "message": "queued, will start within 5s",
    })

    # 3) 后台 task(不要 await,fire-and-forget)
    async def _runner() -> None:
        try:
            await _set_warmup_status(t, {"status": "running", "message": "fetching yfinance daily bars..."})
            result = await _warmup_one_symbol(t)
            await _set_warmup_status(t, result.to_dict())
            log.info(
                "warmup.done",
                extra={
                    "ticker": t,
                    "status": result.status,
                    "daily_bars": result.daily_bars,
                    "threat_rows": result.threat_rows,
                    "errors": len(result.errors),
                },
            )
        except Exception as e:  # noqa: BLE001
            log.error("warmup.runner.fail", extra={"ticker": t, "error": str(e)})
            await _set_warmup_status(t, {
                "status": "failed",
                "message": f"runner exception: {e!s}",
                "errors": [f"runner: {e!s}"],
            })
        finally:
            await _release_lock(t)

    task = asyncio.create_task(_runner(), name=f"warmup:{t}")
    # 防 task 被 GC(fire-and-forget 模式下 Python 不强引用会丢)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)

    return {
        "status": "scheduled",
        "message": f"warmup for {t} scheduled, poll /symbols/{t}/warmup for progress",
        "ticker": t,
    }


# 持有后台 task 引用,避免 GC
_TASKS: set[asyncio.Task] = set()
