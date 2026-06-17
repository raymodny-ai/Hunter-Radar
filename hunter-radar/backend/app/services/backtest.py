"""§3.1.9 离线回测框架(BD-089)。

职责:
1. 从 `backtest_dataset` 读历史 EOD 三源快照
2. 用历史 daily_price + short_volume + form4_events 重算 Threat Score
3. 与 `backtest_event_goldset` 中的金标准事件对齐,算命中/误报率
4. 支持 A/B 权重对比(同时跑两组 weights,输出指标差异)
5. 输出 CSV 明细 + 指标报告

CLI:
    uv run python -m app.services.backtest run --tickers AAPL,TSLA --start 2023-01-01 --end 2024-01-01
    uv run python -m app.services.backtest compare --tickers AAPL --weights-a stock --weights-b etf
"""
from __future__ import annotations

import argparse
import csv
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Symbol
from app.services.divergence import (
    DivergenceVerdict,
    divergence_to_score,
    linear_regression_slope,
    percentile_rank,
)
from app.services.insider import (
    BuybackEvent,
    Form4Event,
    cover_up_alert,
    cover_up_score,
    insider_sell_pressure_score,
)
from app.services.short_metrics import z_score_rolling
from app.services.threat_score import compute_threat_score, decide_lifecycle

log = logging.getLogger(__name__)


@dataclass(slots=True)
class BacktestConfig:
    """回测配置。"""

    tickers: list[str]
    start_date: date
    end_date: date
    weights_name: str = "default"  # 'default' | 'stock' | 'etf' | 'custom'
    custom_weights: dict[str, float] | None = None
    ema_halflife_days: int = 2
    consecutive_days: int = 2
    lookback_div: int = 10
    history_lookback_div: int = 120
    zscore_lookback: int = 60
    output_dir: str = "backtest_output"

    def resolve_weights(self, symbol_type: str) -> dict[str, float]:
        if self.custom_weights is not None:
            return self.custom_weights
        if self.weights_name == "etf":
            return settings.threat_weights_default["etf"]
        # 默认 / stock
        return settings.threat_weights_default["stock"]


@dataclass(slots=True)
class BacktestMetrics:
    """回测指标。"""

    n_event_days: int = 0
    n_hit_event_days: int = 0
    hit_rate: float = 0.0
    n_non_event_days: int = 0
    n_false_alarm_days: int = 0
    false_alarm_rate: float = 0.0
    avg_score_event: float = 0.0
    avg_score_non_event: float = 0.0
    score_lift: float = 0.0  # event 分 - non-event 分


@dataclass(slots=True)
class BacktestResult:
    """回测结果(供 CLI 输出 CSV / 报告)。"""

    config: BacktestConfig
    rows: list[dict] = field(default_factory=list)  # 每个 (ticker, trade_date, total_raw, total_ema, lifecycle, hit)
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)
    csv_path: str | None = None
    summary: str = ""


# ---- 1) 数据读取辅助 ----


async def _read_backtest_payload(
    session: AsyncSession, ticker: str, start: date, end: date
) -> list[dict]:
    """读 backtest_dataset 的 payload JSON,按 trade_date 升序。"""
    tbl = Symbol.__table__.metadata.tables["backtest_dataset"]
    sql = (
        select(tbl.c.trade_date, tbl.c.payload)
        .where(tbl.c.ticker == ticker)
        .where(tbl.c.trade_date >= start)
        .where(tbl.c.trade_date <= end)
        .order_by(tbl.c.trade_date.asc())
    )
    rs = await session.execute(sql)
    out: list[dict] = []
    for row in rs.all():
        d = row._mapping
        p = d["payload"]
        if isinstance(p, str):
            import json

            p = json.loads(p)
        out.append({"trade_date": d["trade_date"], "payload": p})
    return out


async def _read_goldset_events(
    session: AsyncSession, ticker: str, start: date, end: date
) -> list[tuple[date, date, str]]:
    """读金标准事件窗口。返回 [(start, end, severity), ...]"""
    tbl = Symbol.__table__.metadata.tables["backtest_event_goldset"]
    sql = (
        select(
            tbl.c.t_window_start,
            tbl.c.t_window_end,
            tbl.c.severity,
        )
        .where(tbl.c.ticker == ticker)
        .where(tbl.c.t_window_end >= start)
        .where(tbl.c.t_window_start <= end)
    )
    rs = await session.execute(sql)
    return [(r[0], r[1], r[2]) for r in rs.all()]


def _in_event_window(td: date, windows: list[tuple[date, date, str]]) -> bool:
    return any(s <= td <= e for s, e, _ in windows)


# ---- 2) 单 ticker 单日 Threat Score 回算 ----


def _short_score_from_payload(history: list[dict], target_idx: int) -> float | None:
    """从 backtest payload 算 short_ratio 历史 + Z-Score,返回当日 Z→ 0-100。"""
    ratios: list[float] = []
    for r in history[: target_idx + 1]:
        sv = (r["payload"].get("short_volume") or {}).get("short_volume")
        tv = (r["payload"].get("daily_price") or {}).get("volume")
        if sv is None or tv is None or tv == 0:
            continue
        ratios.append(sv / tv)
    if len(ratios) < 2:
        return None
    z = z_score_rolling(ratios, lookback=min(60, len(ratios) - 1))
    z_today = z[-1] if z else None
    if z_today is None:
        return None
    # 简化为直接 cap 0..100
    return max(0.0, min(100.0, 50.0 + z_today * 16.6))


def _div_score_from_payload(history: list[dict], target_idx: int) -> float:
    """从 backtest payload 算价/量斜率 + 背离判定。"""
    closes: list[float] = []
    volumes: list[int] = []
    for r in history[: target_idx + 1]:
        c = (r["payload"].get("daily_price") or {}).get("close")
        v = (r["payload"].get("daily_price") or {}).get("volume")
        if c is None or v is None:
            continue
        closes.append(float(c))
        volumes.append(int(v))
    n = len(closes)
    if n < 10 + 120:
        return 20.0  # 数据不足
    price_slope = linear_regression_slope(closes[-10:])
    vol_slope = linear_regression_slope([float(v) for v in volumes[-10:]])
    p_price = percentile_rank(price_slope, [linear_regression_slope(closes[i - 10 : i]) for i in range(10, n)])
    p_vol = percentile_rank(vol_slope, [linear_regression_slope([float(v) for v in volumes[i - 10 : i]]) for i in range(10, n)])
    is_div = p_price < 0.2 and p_vol > 0.8
    v = DivergenceVerdict(
        is_divergent=is_div,
        p_price=p_price,
        p_volume=p_vol,
        rationale="",
    )
    return divergence_to_score(v)


def _insider_score_from_payload(payload: dict, asof: date) -> float:
    """从 form4_events 算内部人抛压 + 掩护配对(简化版)。"""
    f4 = payload.get("form4_events", [])
    sells: list[Form4Event] = []
    buybacks: list[BuybackEvent] = []
    for e in f4:
        d = e.get("txn_date")
        if d is None:
            continue
        # DB 返回可能是 str
        if isinstance(d, str):
            from datetime import date as _d

            d = _d.fromisoformat(d)
        if e.get("direction") == "sell" and (asof - d).days <= 20:
            sells.append(
                Form4Event(
                    symbol="",
                    insider_name=e.get("insider_name", ""),
                    insider_role=e.get("insider_role", "Other"),
                    txn_date=d,
                    filed_at=d,
                    direction="S",
                    qty=int(e.get("qty", 0) or 0),
                    price=float(e["price"]) if e.get("price") is not None else None,
                    form_url="",
                )
            )
    press = insider_sell_pressure_score(sells, asof=asof)
    pairs = cover_up_alert(sells, buybacks, asof=asof)
    cover = cover_up_score(pairs)
    return round(press * 0.6 + cover * 0.4, 2)


def _options_score_from_payload(payload: dict) -> float:
    """回测场景无 options_chain 真实数据,固定 30(中性偏低)。"""
    return 30.0


# ---- 3) 跑回测 ----


async def run_backtest(cfg: BacktestConfig) -> BacktestResult:
    """对 cfg.tickers 跑历史回测,产出 BacktestResult。"""
    result = BacktestResult(config=cfg)
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        for sym in cfg.tickers:
            payload_history = await _read_backtest_payload(
                session, sym, cfg.start_date, cfg.end_date
            )
            goldset = await _read_goldset_events(
                session, sym, cfg.start_date, cfg.end_date
            )
            if not payload_history:
                log.warning("backtest.no_data", ticker=sym)
                continue

            sym_type = "etf" if sym in ("SPY", "QQQ", "IWM", "VTI", "DIA") else "stock"
            weights = cfg.resolve_weights(sym_type)

            ema_history: list[dict] = []
            for i, row in enumerate(payload_history):
                td = row["trade_date"]
                p = row["payload"]
                mod_short = _short_score_from_payload(payload_history, i) or 50.0
                mod_div = _div_score_from_payload(payload_history, i)
                mod_insider = _insider_score_from_payload(p, td) if sym_type == "stock" else 0.0
                mod_options = _options_score_from_payload(p)

                score = compute_threat_score(
                    module_options=mod_options,
                    module_short=mod_short,
                    module_divergence=mod_div,
                    module_insider=mod_insider,
                    weights=weights,
                    ema_halflife_days=cfg.ema_halflife_days,
                    history=ema_history,
                )
                ema_history.append(
                    {
                        "module_options": mod_options,
                        "module_short": mod_short,
                        "module_divergence": mod_div,
                        "module_insider": mod_insider,
                    }
                )

                ema = score["ema"]
                lifecycle = decide_lifecycle(ema, red_threshold=float(settings.threat_red_threshold))
                in_event = _in_event_window(td, goldset)
                hit = bool(in_event and ema >= settings.threat_red_threshold)

                result.rows.append(
                    {
                        "ticker": sym,
                        "trade_date": td.isoformat() if hasattr(td, "isoformat") else str(td),
                        "total_raw": score["raw"],
                        "total_ema": ema,
                        "lifecycle": lifecycle,
                        "in_event_window": in_event,
                        "hit": hit,
                    }
                )

    # 算指标
    if result.rows:
        event_rows = [r for r in result.rows if r["in_event_window"]]
        non_event_rows = [r for r in result.rows if not r["in_event_window"]]
        result.metrics.n_event_days = len(event_rows)
        result.metrics.n_non_event_days = len(non_event_rows)
        result.metrics.n_hit_event_days = sum(1 for r in event_rows if r["hit"])
        result.metrics.n_false_alarm_days = sum(
            1 for r in non_event_rows if r["total_ema"] >= settings.threat_red_threshold
        )
        result.metrics.hit_rate = (
            result.metrics.n_hit_event_days / result.metrics.n_event_days
            if result.metrics.n_event_days
            else 0.0
        )
        result.metrics.false_alarm_rate = (
            result.metrics.n_false_alarm_days / result.metrics.n_non_event_days
            if result.metrics.n_non_event_days
            else 0.0
        )
        result.metrics.avg_score_event = (
            sum(r["total_ema"] for r in event_rows) / len(event_rows) if event_rows else 0.0
        )
        result.metrics.avg_score_non_event = (
            sum(r["total_ema"] for r in non_event_rows) / len(non_event_rows)
            if non_event_rows
            else 0.0
        )
        result.metrics.score_lift = (
            result.metrics.avg_score_event - result.metrics.avg_score_non_event
        )

    # 写 CSV
    csv_path = out_dir / f"backtest_{cfg.weights_name}_{date.today().isoformat()}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ticker",
                "trade_date",
                "total_raw",
                "total_ema",
                "lifecycle",
                "in_event_window",
                "hit",
            ],
        )
        writer.writeheader()
        for r in result.rows:
            writer.writerow(r)
    result.csv_path = str(csv_path)

    result.summary = (
        f"Backtest [{cfg.weights_name}] tickers={cfg.tickers} "
        f"{cfg.start_date}~{cfg.end_date}\n"
        f"  event_days={result.metrics.n_event_days} hit={result.metrics.n_hit_event_days} "
        f"hit_rate={result.metrics.hit_rate:.2%}\n"
        f"  non_event_days={result.metrics.n_non_event_days} "
        f"false_alarm={result.metrics.n_false_alarm_days} "
        f"fa_rate={result.metrics.false_alarm_rate:.2%}\n"
        f"  avg_score_event={result.metrics.avg_score_event:.2f} "
        f"avg_score_non_event={result.metrics.avg_score_non_event:.2f} "
        f"lift={result.metrics.score_lift:+.2f}\n"
        f"  csv: {result.csv_path}"
    )
    return result


# ---- CLI ----


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hunter Radar V1.4 — Backtest CLI (BD-089)")
    sub = p.add_subparsers(dest="cmd")

    pr = sub.add_parser("run", help="单组权重回测")
    pr.add_argument("--tickers", required=True, help="逗号分隔,如 AAPL,TSLA")
    pr.add_argument("--start", required=True, help="YYYY-MM-DD")
    pr.add_argument("--end", required=True, help="YYYY-MM-DD")
    pr.add_argument("--weights", default="default", help="default | stock | etf | custom:opts")
    pr.add_argument("--halflife", type=int, default=2)
    pr.add_argument("--output", default="backtest_output")

    pc = sub.add_parser("compare", help="A/B 权重对比")
    pc.add_argument("--tickers", required=True)
    pc.add_argument("--start", required=True)
    pc.add_argument("--end", required=True)
    pc.add_argument("--weights-a", default="stock")
    pc.add_argument("--weights-b", default="etf")
    pc.add_argument("--halflife", type=int, default=2)
    pc.add_argument("--output", default="backtest_output")
    return p.parse_args()


async def _run_cli() -> None:
    args = _parse_args()
    if args.cmd == "run":
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        custom: dict[str, float] | None = None
        weights_name = args.weights
        if weights_name.startswith("custom:"):
            # 简易解析: "options:0.4,short:0.4,divergence:0.2"
            weights_name = "custom"
            custom = {}
            for kv in args.weights[len("custom:") :].split(","):
                k, v = kv.split(":")
                custom[k.strip()] = float(v)
        cfg = BacktestConfig(
            tickers=tickers,
            start_date=date.fromisoformat(args.start),
            end_date=date.fromisoformat(args.end),
            weights_name=weights_name,
            custom_weights=custom,
            ema_halflife_days=args.halflife,
            output_dir=args.output,
        )
        res = await run_backtest(cfg)
        print(res.summary)
    elif args.cmd == "compare":
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        out_a = await run_backtest(
            BacktestConfig(
                tickers=tickers,
                start_date=date.fromisoformat(args.start),
                end_date=date.fromisoformat(args.end),
                weights_name=args.weights_a,
                ema_halflife_days=args.halflife,
                output_dir=args.output,
            )
        )
        out_b = await run_backtest(
            BacktestConfig(
                tickers=tickers,
                start_date=date.fromisoformat(args.start),
                end_date=date.fromisoformat(args.end),
                weights_name=args.weights_b,
                ema_halflife_days=args.halflife,
                output_dir=args.output,
            )
        )
        print(f"=== A ({args.weights_a}) ===\n{out_a.summary}\n")
        print(f"=== B ({args.weights_b}) ===\n{out_b.summary}\n")
        print(
            f"Δ hit_rate: {out_a.metrics.hit_rate - out_b.metrics.hit_rate:+.2%}\n"
            f"Δ fa_rate:  {out_a.metrics.false_alarm_rate - out_b.metrics.false_alarm_rate:+.2%}\n"
            f"Δ lift:     {out_a.metrics.score_lift - out_b.metrics.score_lift:+.2f}"
        )
    else:
        print("用法: run | compare")


def main() -> None:
    import asyncio

    asyncio.run(_run_cli())


if __name__ == "__main__":
    main()
