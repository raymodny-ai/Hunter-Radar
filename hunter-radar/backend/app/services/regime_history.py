"""§3.5 市场状态门控 + 90 日 Threat Score 轨迹(BD-063 / BD-066)。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(slots=True, frozen=True)
class RegimeConfig:
    """可配置阈值(BD-087 回测时调整)。"""

    vix_panic_threshold: float = 30.0
    spx_ma20_window: int = 20
    threshold_red_normal: int = 70
    threshold_red_panic: int = 80


@dataclass(slots=True)
class MarketSnapshot:
    """每日 EOD 市场快照。"""

    trade_date: date
    vix: float | None
    spx_close: float | None
    spx_ma20: float | None


def decide_regime(
    snap: MarketSnapshot, cfg: RegimeConfig | None = None
) -> tuple[str, int]:
    """市场状态门控(BD-063)。

    Returns:
        (regime, threshold_red)
        regime ∈ {'normal', 'panic'}
    """
    cfg = cfg or RegimeConfig()
    is_panic = False
    if snap.vix is not None and snap.vix > cfg.vix_panic_threshold:
        is_panic = True
    if (
        snap.spx_close is not None
        and snap.spx_ma20 is not None
        and snap.spx_close < snap.spx_ma20
    ):
        is_panic = True
    return ("panic" if is_panic else "normal"), (
        cfg.threshold_red_panic if is_panic else cfg.threshold_red_normal
    )


def filter_history_window(
    rows: Iterable[tuple[date, float]],
    asof: date,
    window_days: int = 90,
) -> list[tuple[date, float]]:
    """§3.5/§4.1 90 日 Threat Score 轨迹(BD-066)。

    Args:
        rows: (trade_date, threat_score) 元组迭代
        asof: 当前交易日
        window_days: 窗口大小(交易日,非自然日)

    Returns:
        [(trade_date, score), ...] 按时间升序,最多 window_days 条
    """
    out: list[tuple[date, float]] = []
    cutoff = asof - timedelta(days=int(window_days * 1.6))  # 1.6 系数预留周末/节假日
    for d, s in rows:
        if cutoff <= d <= asof:
            out.append((d, s))
    out.sort(key=lambda x: x[0])
    return out[-window_days:]


def moving_average_ema(
    history: list[tuple[date, float]], halflife_days: int = 2
) -> list[tuple[date, float]]:
    """对历史轨迹做二次 EMA 平滑(用于轨迹展示而非告警)。"""
    if not history:
        return []
    alpha = 1.0 - 2.0 ** (-1.0 / halflife_days)
    ema = history[0][1]
    out: list[tuple[date, float]] = []
    for d, s in history:
        ema = alpha * s + (1.0 - alpha) * ema
        out.append((d, ema))
    return out
