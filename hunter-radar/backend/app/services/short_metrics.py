"""§3.2 模块二:全监管做空筹码追踪(BD-030 / BD-031 / BD-032)。

PRD §3.2 关键派生指标:
  - BD-030:Short Ratio 60 日滚动 Z-Score
  - BD-031:ATS 暗池占做空总量的比例(暗池渗透率)
  - BD-032:ETF 一级做空代理:Premium/Discount to NAV + INAV 偏离(BD-088 预备)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class DailyShortRecord:
    """单日做空数据(从 short_volume + ats_short 合并)。"""

    trade_date: date
    symbol: str
    short_volume: int
    total_volume: int
    ats_short_volume: int = 0  # 来自 ats_short 表


def short_ratio(r: DailyShortRecord) -> float:
    """当日做空比例(short_volume / total_volume)。"""
    if r.total_volume <= 0:
        return 0.0
    return r.short_volume / r.total_volume


def ats_penetration(r: DailyShortRecord) -> float:
    """暗池渗透率(BD-031)= ATS 成交量 / 做空总量。"""
    if r.short_volume <= 0:
        return 0.0
    return min(1.0, r.ats_short_volume / r.short_volume)


def z_score_rolling(history: Sequence[float], lookback: int = 60) -> list[float | None]:
    """60 日滚动 Z-Score(BD-030)。

    对于 t 时刻,使用 [t-lookback, t) 共 lookback 个历史点的均值/标准差,
    排除当天自身(避免数据泄露)。
    返回长度与 history 相同,前 lookback 天为 None(冷启动)。
    """
    out: list[float | None] = [None] * len(history)
    if lookback < 2:
        raise ValueError("lookback 必须 ≥ 2")
    for i in range(lookback, len(history)):
        window = history[i - lookback : i]
        mean = sum(window) / lookback
        var = sum((x - mean) ** 2 for x in window) / (lookback - 1)
        sd = math.sqrt(var) if var > 1e-12 else 0.0
        out[i] = (history[i] - mean) / sd if sd > 0 else 0.0
    return out


def z_to_anomaly_score(z: float | None, cap: float = 3.0) -> float:
    """Z-Score → 0–100 分(BD-030 子评分)。"""
    if z is None or math.isnan(z):
        return 50.0  # 冷启动期给中性
    # z=0 → 50, z=+2 → ~83, z=+3 → 100, z=-2 → ~17
    s = 50.0 + (z / cap) * 50.0
    return max(0.0, min(100.0, s))


def ats_penetration_to_score(p: float) -> float:
    """暗池渗透率 → 0–100 分(BD-031 子评分)。

    假设:
      - 0% → 30(健康)
      - 30% → 60(警惕)
      - 60% → 100(高危)
    分段线性。
    """
    if p <= 0:
        return 30.0
    if p >= 0.60:
        return 100.0
    if p <= 0.30:
        return 30.0 + (p / 0.30) * 30.0  # 30→60
    return 60.0 + ((p - 0.30) / 0.30) * 40.0  # 60→100


# ---- BD-032 ETF 一级市场代理(BD-088 预备) ----


@dataclass(slots=True)
class ETFProxyTick:
    """ETF 代理指标(单日)— Premium/Discount to NAV + 二级放量。"""

    trade_date: date
    symbol: str
    nav: float
    iopv: float  # Indicative Optimized Portfolio Value(盘中)
    close: float
    volume: int
    volume_20d_avg: int


def premium_to_iopv(t: ETFProxyTick) -> float:
    """二级收盘价相对 IOPV 的偏离率。

    +1% 表示二级溢价 1%(可能触发 AP 赎回份额);
    -1% 表示二级折价(可能触发 AP 申购份额)。
    """
    if t.iopv <= 0:
        return 0.0
    return (t.close - t.iopv) / t.iopv


def relative_volume(t: ETFProxyTick) -> float:
    """相对 20 日均量的倍数。"""
    if t.volume_20d_avg <= 0:
        return 1.0
    return t.volume / t.volume_20d_avg


def etf_proxy_anomaly_score(
    t: ETFProxyTick, abs_premium_threshold: float = 0.01
) -> float:
    """ETF 代理异常分(BD-032 / BD-088)。

    条件:
      - |折溢价| ≥ 1% + 量比 ≥ 1.5x → 80 分
      - |折溢价| ≥ 0.5% + 量比 ≥ 1.2x → 60 分
      - 其他 → 30 分
    """
    ap = abs(premium_to_iopv(t))
    rv = relative_volume(t)
    if ap >= abs_premium_threshold and rv >= 1.5:
        return 80.0
    if ap >= 0.005 and rv >= 1.2:
        return 60.0
    return 30.0
