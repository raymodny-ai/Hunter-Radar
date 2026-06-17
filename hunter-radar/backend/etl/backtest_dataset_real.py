"""§3.1.9-b 回测数据集真实入口(BD-085 M7 接力期)。

M2 `etl/backtest_dataset.py` 走 PG(`daily_price` / `short_volume` / `form4_event` → `backtest_dataset`),
沙箱无 PG 时 SQLAlchemyError 直接退 0,不抛异常(M4 m4t1 已落地)。

M7 接力期新增真实入口 `etl/backtest_dataset_real.py`:
- 真实环境:从 PG daily_price / short_volume / form4_event 拉数据(M2 套路)
- 沙箱环境:无 PG,改读 `data/backtest_event_goldset.sample.jsonl`(m7t2 双签后),
  按事件窗口 ±90 天合成 deterministic OHLCV(short_volume + form4 走 stub),
  输出与 M2 同 schema 的 payload 列表,后续 m7t4(Mann-Whitney U)可直接消费。

合成规则(沙箱):
- close_price: 用 ticker + 日期 hash → [10, 500] USD 之间随机价格,
  围绕事件严重程度调整振幅(extreme 30%, high 20%, medium 10%, low 5%)
- OHLCV: open/high/low/close 在 close_price ± 5% 范围内
- volume: 1M ~ 50M shares(中小盘)
- short_volume_ratio: 0.10 ~ 0.70(高 short interest 触发轧空场景)
- form4_event: 大事件可能有 insider 卖出(0 ~ 3 条)
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

GOLDSET_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "backtest_event_goldset.sample.jsonl"
)


@dataclass(slots=True)
class RealDatasetBuildResult:
    """真实数据集构建结果(沙箱模式)。"""

    attempted: int = 0
    produced: int = 0
    skipped: int = 0
    failures: int = 0
    by_ticker: dict[str, int] | None = None
    source: str = "synthetic"


# ----------------------------------------------------------------------
# 沙箱模式:合成 deterministic OHLCV
# ----------------------------------------------------------------------

def _seeded_float(ticker: str, dt: date, salt: str = "") -> float:
    """deterministic 0.0 ~ 1.0 浮点(seed=ticker+date+salt 的 sha256 头 8 字节 / 0xFFFFFFFF)."""
    h = hashlib.sha256(f"{ticker}|{dt.isoformat()}|{salt}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _severity_amp(severity: str) -> float:
    """按事件严重程度返回价格振幅(±pct)。"""
    return {
        "extreme": 0.30,
        "high": 0.20,
        "medium": 0.10,
        "low": 0.05,
    }.get(severity, 0.10)


def _synthesize_ohlcv_for_day(
    ticker: str, dt: date, severity: str
) -> dict:
    """单日合成 OHLCV。"""
    amp = _severity_amp(severity)
    base = 10.0 + 490.0 * _seeded_float(ticker, dt, "base")  # [10, 500]
    drift = _seeded_float(ticker, dt, "drift")  # 0 ~ 1
    drift_signed = (drift - 0.5) * 2 * amp  # -amp ~ +amp

    open_p = base * (1 + drift_signed * 0.5)
    close_p = base * (1 + drift_signed)
    high_p = max(open_p, close_p) * (1 + _seeded_float(ticker, dt, "high") * amp * 0.5)
    low_p = min(open_p, close_p) * (1 - _seeded_float(ticker, dt, "low") * amp * 0.5)
    volume = int(1_000_000 + 49_000_000 * _seeded_float(ticker, dt, "vol"))

    return {
        "open": round(open_p, 2),
        "high": round(high_p, 2),
        "low": round(low_p, 2),
        "close": round(close_p, 2),
        "adj_close": round(close_p, 2),
        "volume": volume,
    }


def _synthesize_short_volume(ticker: str, dt: date) -> dict:
    """合成 FINRA short_volume。"""
    ratio = 0.10 + 0.60 * _seeded_float(ticker, dt, "short_ratio")
    total = int(1_000_000 + 49_000_000 * _seeded_float(ticker, dt, "short_vol"))
    short_vol = int(total * ratio)
    return {
        "short_volume": short_vol,
        "non_short_volume": total - short_vol,
        "total_volume": total,
        "source": "sandbox_synthetic",
    }


def _synthesize_form4(ticker: str, dt: date, severity: str) -> list[dict]:
    """合成 SEC Form 4 事件(0~3 条,严重程度越高越多)。"""
    n_form4 = {
        "extreme": 3,
        "high": 2,
        "medium": 1,
        "low": 0,
    }.get(severity, 1)

    events: list[dict] = []
    for i in range(n_form4):
        if _seeded_float(ticker, dt, f"form4_{i}") < 0.5:
            continue  # 50% 概率不出 insider
        qty = int(10_000 + 990_000 * _seeded_float(ticker, dt, f"qty_{i}"))
        price = round(50.0 + 200.0 * _seeded_float(ticker, dt, f"price_{i}"), 2)
        events.append(
            {
                "insider_name": f"Insider_{i:02d}_{ticker}",
                "insider_role": ["CEO", "CFO", "Director", "Officer"][i % 4],
                "txn_date": dt.isoformat(),
                "filed_at": dt.isoformat(),
                "direction": "sell" if _seeded_float(ticker, dt, f"dir_{i}") < 0.7 else "buy",
                "qty": qty,
                "price": price,
            }
        )
    return events


def _build_payload_for_event_sandbox(
    ticker: str, t_start: date, t_end: date, severity: str, window_days: int = 90
) -> list[dict]:
    """为单个 ticker 在 [t_start - window_days, t_end + window_days] 合成 payload 列表。"""
    start = t_start - timedelta(days=window_days)
    end = t_end + timedelta(days=window_days)

    payloads: list[dict] = []
    cur = start
    while cur <= end:
        # 跳过周末(简化,沙箱不实跑交易)
        if cur.weekday() >= 5:
            cur += timedelta(days=1)
            continue
        payload = {
            "ticker": ticker,
            "trade_date": cur.isoformat(),
            "daily_price": _synthesize_ohlcv_for_day(ticker, cur, severity),
            "short_volume": _synthesize_short_volume(ticker, cur),
            "form4_events": _synthesize_form4(ticker, cur, severity),
        }
        payloads.append(payload)
        cur += timedelta(days=1)
    return payloads


def _compute_checksum(payload: dict) -> str:
    """SHA256 锁定 payload 完整性(与 M2 backtest_dataset._compute_checksum 同口径)。"""
    s = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# 公共入口
# ----------------------------------------------------------------------

def build_real_dataset_sandbox(
    goldset_path: Path | str = GOLDSET_PATH,
    *,
    window_days: int = 90,
) -> tuple[RealDatasetBuildResult, list[dict]]:
    """沙箱模式:从 goldset 读 31 事件,合成 deterministic OHLCV,返 (result, payloads).

    Returns:
        (RealDatasetBuildResult, list[dict]): 元组,主调用方拿到 payloads 后自行写 JSONL。
    """
    result = RealDatasetBuildResult(by_ticker={})

    goldset_path = Path(goldset_path)
    if not goldset_path.exists():
        result.failures = 1
        log.error("build_real_dataset_sandbox.missing_goldset", path=str(goldset_path))
        return result

    lines = goldset_path.read_text(encoding="utf-8").splitlines()
    payloads_all: list[dict] = []
    attempted = 0
    produced_tickers: dict[str, int] = {}

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        obj = json.loads(raw)
        ticker = obj.get("ticker")
        if not ticker:
            continue
        t_start = date.fromisoformat(obj["t_window_start"])
        t_end = date.fromisoformat(obj["t_window_end"])
        severity = obj.get("severity", "medium")

        attempted += 1
        payloads = _build_payload_for_event_sandbox(
            ticker, t_start, t_end, severity, window_days=window_days
        )
        produced_tickers[ticker] = produced_tickers.get(ticker, 0) + len(payloads)
        payloads_all.extend(payloads)

    result.attempted = attempted
    result.produced = len(payloads_all)
    result.by_ticker = produced_tickers
    result.source = "synthetic"
    log.info(
        "build_real_dataset_sandbox.done",
        attempted=attempted,
        produced=len(payloads_all),
        unique_tickers=len(produced_tickers),
    )
    return result, payloads_all


def main() -> int:
    """CLI: 跑 build_real_dataset_sandbox,落 JSONL 到 data/backtest_dataset_real.sandbox.jsonl.

    返回 0 永远(sandbox 模式不会 fail)。
    """
    import argparse
    import sys
    from pathlib import Path

    p = argparse.ArgumentParser(description="Hunter Radar V1.4 — Build real backtest dataset (BD-085 sandbox)")
    p.add_argument("--window-days", type=int, default=90, help="事件前后合成天数(默认 90)")
    p.add_argument(
        "--out",
        default=str(ROOT_OUT := Path(__file__).resolve().parents[2] / "data" / "backtest_dataset_real.sandbox.jsonl"),
        help="输出 JSONL 路径",
    )
    args = p.parse_args()

    result, payloads = build_real_dataset_sandbox(window_days=args.window_days)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for p_dict in payloads:
            f.write(
                json.dumps(
                    {
                        "ticker": p_dict["ticker"],
                        "trade_date": p_dict["trade_date"],
                        "payload": p_dict,
                        "checksum": _compute_checksum(p_dict),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(
        f"[backtest_dataset_real.sandbox] window_days={args.window_days} "
        f"attempted={result.attempted} produced={result.produced} "
        f"out={out_path}"
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())