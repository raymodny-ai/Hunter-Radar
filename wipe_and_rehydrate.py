#!/usr/bin/env python3
"""V1.7.5: 全量 wipe + 重新 ETL 数据保留 symbol_master + 用户表 (app_user/alert_rule/...).

绕开 asyncpg 默认 ::1 解析问题:用 psql 命令做 truncate + 用 urllib 触发 API 重新 warmup。
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "hunter-radar" / "backend"
sys.path.insert(0, str(BACKEND))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("wipe")

# 17 张表 — TRUNCATE CASCADE (FK 关联 symbol_master 保留,但 cascade 会删行)
TRUNCATE_TABLES = [
    # options 模块
    "options_chain",
    "option_anomaly",
    "option_pcr_daily",
    # daily / market
    "daily_price",
    "daily_screener",
    "etf_proxy_metrics",
    "etf_primary_flow",
    # short 模块
    "short_volume",
    "short_ratio_daily",
    "ats_short",
    "divergence_window",
    # threat
    "threat_score_daily",
    "ultimate_alert",
    "alert_event",
    # insider
    "form4_event",
    "buyback_event",
    # ETL status
    "data_ingestion_status",
]
# 保留: symbol_master / app_user / alert_rule / subscription_event
#        basket* / backtest_* / v_data_ingestion_latest

PSQL = "/usr/bin/psql"
ENV = {
    "PGHOST": "127.0.0.1",
    "PGPORT": "5433",
    "PGUSER": "hunter",
    "PGPASSWORD": "hunter",
    "PGDATABASE": "hunter_radar",
}


def run_psql(sql: str) -> str:
    """跑 PSQL,返 stdout。"""
    res = subprocess.run(
        [PSQL, "-c", sql],
        env={**__import__("os").environ, **ENV},
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        log.error("psql failed: %s", res.stderr)
        raise RuntimeError(f"psql failed: {res.stderr}")
    return res.stdout


def step1_truncate() -> None:
    log.info("STEP 1: TRUNCATE %d tables CASCADE", len(TRUNCATE_TABLES))
    sql = (
        f"TRUNCATE TABLE {', '.join(TRUNCATE_TABLES)} "
        f"RESTART IDENTITY CASCADE"
    )
    out = run_psql(sql)
    log.info(out.strip().splitlines()[-1] if out.strip() else "TRUNCATE ok")

    log.info("STEP 1b: clear symbol_master warmup_started_at + metadata")
    out = run_psql(
        "UPDATE symbol_master "
        "SET warmup_started_at=NULL, metadata='{}'::jsonb, is_universe=FALSE "
        "RETURNING ticker;"
    )
    # 简单计数
    cnt = run_psql("SELECT count(*) FROM symbol_master").strip().splitlines()[-1]
    log.info("symbol_master kept %s", cnt.strip())


def step2_flush_redis() -> None:
    """用 python redis sync client 清 keys (无需 psql)。"""
    log.info("STEP 2: flush redis opt:* / warmup:* keys")
    try:
        import redis

        # 改 path 用 backend 的 venv
        sys.path.insert(
            0, str(BACKEND / ".venv" / "lib" / "python3.12" / "site-packages")
        )
        r = redis.Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
        deleted = 0
        for pattern in ("opt:*", "warmup:*", "warmup-state:*"):
            for k in r.scan_iter(match=pattern, count=200):
                r.delete(k)
                deleted += 1
        log.info("flushed %d redis keys", deleted)
    except Exception as e:  # noqa: BLE001
        log.warning("redis flush failed: %s (continue)", e)


def step3_trigger_rewarmup() -> None:
    """通过 API POST /symbols 触发 22 个 ticker 重 warmup。"""
    log.info("STEP 3: trigger rewarmup via API for every symbol_master ticker")

    out = run_psql("SELECT ticker FROM symbol_master ORDER BY is_universe DESC, ticker")
    tickers = [ln.strip() for ln in out.strip().splitlines() if ln.strip() and not ln.startswith("-") and not ln.startswith("ticker")]
    # 去掉 header (第 1 行)
    if tickers and "ticker" in tickers[0]:
        tickers = tickers[1:]
    log.info("got %d tickers", len(tickers))

    ok = 0
    fail = 0
    for t in tickers:
        url = "http://127.0.0.1:8000/api/v1/symbols"
        data = json.dumps({"ticker": t, "name": t, "type": "stock"}).encode()
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = json.loads(resp.read())
                ok += 1
                log.info(
                    "  %s → created=%s scheduled=%s",
                    t, body.get("created"), body.get("warmup_scheduled"),
                )
        except Exception as e:  # noqa: BLE001
            fail += 1
            log.warning("  %s → %s", t, e)
    log.info("POST /symbols done: %d ok / %d fail", ok, fail)


def main() -> None:
    log.info("=" * 60)
    log.info("V1.7.5 WIPE & REHYDRATE START")
    log.info("=" * 60)
    step1_truncate()
    step2_flush_redis()
    step3_trigger_rewarmup()
    log.info("=" * 60)
    log.info("V1.7.5 WIPE DONE — 后台 warmup 串行排队约 30-50 min")
    log.info("Refresh 首页看实时进度")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
