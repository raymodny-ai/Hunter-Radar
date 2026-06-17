"""§3.3 模块三:量价背离分析(BD-040 / BD-041 / BD-042)。

PRD §3.3 核心:
  - BD-040:价平量增(吸收)
  - BD-041:十日斜率分位 + 一百二十日分位
  - BD-042:量比 5 日 / 20 日 + ATR 缩窄
  触发条件(背离信号):价 P_price < 0.2 且 量 P_volume > 0.8 持续 ≥ 2 日
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class PriceVolumeTick:
    trade_date: date
    close: float
    volume: int
    atr_14: float  # Average True Range(14 日)


def linear_regression_slope(y: Sequence[float]) -> float:
    """简单线性回归斜率(对 y 序列的索引 x = 0..n-1)。"""
    n = len(y)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(y) / n
    num = sum((i - x_mean) * (y[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den > 1e-12 else 0.0


def percentile_rank(value: float, history: Sequence[float]) -> float:
    """历史分位(0–1)。假设 history 中无 NaN。"""
    if not history:
        return 0.5
    sorted_h = sorted(history)
    # 线性插值分位
    n = len(sorted_h)
    if value <= sorted_h[0]:
        return 0.0
    if value >= sorted_h[-1]:
        return 1.0
    # 二分查找
    lo, hi = 0, n - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if sorted_h[mid] < value:
            lo = mid
        else:
            hi = mid
    # 插值
    return (lo + (value - sorted_h[lo]) / max(sorted_h[hi] - sorted_h[lo], 1e-12)) / (n - 1)


def relative_volume_short_long(short_5d: float, long_20d: float) -> float:
    """5 日均量 / 20 日均量(BD-042)。"""
    if long_20d <= 0:
        return 1.0
    return short_5d / long_20d


def atr_squeeze(atr: float, atr_history: Sequence[float], threshold_pct: float = 0.2) -> bool:
    """ATR 缩窄(BD-042):当前 ATR 处于历史 20% 分位以下。"""
    if atr <= 0 or not atr_history:
        return False
    return percentile_rank(atr, atr_history) <= threshold_pct


@dataclass(slots=True, frozen=True)
class DivergenceVerdict:
    is_divergent: bool
    p_price: float   # 价斜率分位(0–1,越低越横盘)
    p_volume: float  # 量斜率分位(0–1,越高越放量)
    rationale: str


def detect_divergence(
    closes: Sequence[float],
    volumes: Sequence[int],
    lookback: int = 10,
    history_lookback: int = 120,
    consecutive_days: int = 2,
) -> DivergenceVerdict:
    """量价背离判定(BD-040/041/042)。

    步骤:
      1. 用最近 lookback 天做线性回归,得到价/量斜率
      2. 用全部 (n - lookback) 天斜率当历史,算 P_price / P_volume
      3. 若 P_price < 0.2 且 P_volume > 0.8 → 当日背离
      4. 连续 consecutive_days 日满足 → 触发警报
    """
    n = len(closes)
    if n < lookback + history_lookback:
        return DivergenceVerdict(
            is_divergent=False,
            p_price=0.5,
            p_volume=0.5,
            rationale=f"数据不足(n={n},需要 {lookback + history_lookback})",
        )
    if len(volumes) != n:
        raise ValueError("closes 与 volumes 长度必须一致")

    # 滚动回归:对每一天,用前 lookback 天算斜率,得到长度为 n 的斜率序列
    price_slopes: list[float] = []
    volume_slopes: list[float] = []
    for i in range(lookback, n + 1):
        window_c = list(closes[i - lookback : i])
        window_v = [float(v) for v in volumes[i - lookback : i]]
        price_slopes.append(linear_regression_slope(window_c))
        volume_slopes.append(linear_regression_slope(window_v))

    # 价斜率(用相对斜率消除价格水平影响)= slope / mean
    price_norm_slopes = [
        s / max(abs(sum(window) / lookback), 1e-9)
        for s, window in zip(price_slopes, [closes[i - lookback : i] for i in range(lookback, n + 1)])
    ]

    # 验证连续 consecutive_days 日
    final_price = price_norm_slopes[-1] if price_norm_slopes else 0.0
    final_volume = volume_slopes[-1] if volume_slopes else 0.0

    # 全部历史斜率当背景(去掉当前窗口,防止 leak)
    p_price = percentile_rank(final_price, price_norm_slopes[:-1]) if len(price_norm_slopes) > 1 else 0.5
    p_volume = percentile_rank(final_volume, volume_slopes[:-1]) if len(volume_slopes) > 1 else 0.5

    if p_price < 0.2 and p_volume > 0.8:
        return DivergenceVerdict(
            is_divergent=True,
            p_price=p_price,
            p_volume=p_volume,
            rationale=f"价分位 {p_price:.2f}<0.2 且 量分位 {p_volume:.2f}>0.8,疑似吸收",
        )
    return DivergenceVerdict(
        is_divergent=False,
        p_price=p_price,
        p_volume=p_volume,
        rationale=f"价分位 {p_price:.2f},量分位 {p_volume:.2f},未达阈值",
    )


def divergence_to_score(v: DivergenceVerdict) -> float:
    """背离判定 → 0–100 子评分。"""
    if v.is_divergent:
        return 90.0
    if v.p_volume > 0.7:
        return 60.0
    if v.p_volume > 0.5:
        return 40.0
    return 20.0
