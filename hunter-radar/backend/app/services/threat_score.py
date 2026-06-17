"""Hunter Radar V1.4 — Threat Score 与 EMA 平滑核心服务。

OQ-02 决策落地:
- 「持续」严格定义为连续 2 个交易日(T 日与 T-1 日)
- 各模块子评分与 Threat Score 引入 EMA(指数移动平均),半衰期默认 2 交易日
- 防毛刺:严禁仅基于单日 EMA 前原始分触发终极警报
- 单元测试覆盖「单日尖峰」「连续上升」「连续下降」三种曲线
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from math import log, log1p


def ema_smooth(history: Sequence[float], halflife_days: int = 2) -> list[float]:
    """指数移动平均(EMA),半衰期 = halflife_days 个交易日。

    算法:
        alpha = 1 - exp(-ln(2) / halflife)
        ema_t = alpha * x_t + (1 - alpha) * ema_{t-1}
    当 history 为空 → 返回 []
    当 history 只有一个值 → 返回 [history[0]](无平滑余地)
    """
    if halflife_days <= 0:
        raise ValueError("halflife_days must be > 0")
    if not history:
        return []
    if len(history) == 1:
        return [float(history[0])]

    alpha = 1.0 - 2.0 ** (-1.0 / halflife_days)  # 2^(−1/halflife) = exp(−ln2/halflife)
    out: list[float] = [float(history[0])]
    prev = float(history[0])
    for x in history[1:]:
        prev = alpha * float(x) + (1.0 - alpha) * prev
        out.append(prev)
    return out


def consecutive_business_days_above(
    history: Sequence[float],
    threshold: float,
) -> int:
    """计算 history 末尾连续 ≥ threshold 的交易日长度(从右往左数)。

    用于 OQ-02 的「持续 N 日」判定,严格按交易日(传入序列本身已按交易日排序)。
    当 history 为空 → 0
    """
    count = 0
    for x in reversed(history):
        if x >= threshold:
            count += 1
        else:
            break
    return count


def z_score_to_score(z: float | None, *, cap: float = 3.0) -> float:
    """Z-Score → 0–100 子评分(单调递增,S 形)。

    映射:
        z = -∞  → 0
        z =  0  → 50
        z = +∞  → 100
        |z| >= cap 时截断(避免极端值撑爆)
    """
    if z is None:
        return 50.0  # 缺失值置中
    z = max(-cap, min(cap, z))
    # 50 * (1 + tanh(z / cap)) 给出 [0, 100] 平滑映射
    import math
    return 50.0 * (1.0 + math.tanh(z / cap))


def percentile_to_score(p: float | None) -> float:
    """分位数(0–1)→ 0–100 子评分(线性)。

    p=0.0 → 0
    p=1.0 → 100
    p=None → 50(中性)
    """
    if p is None:
        return 50.0
    return max(0.0, min(100.0, float(p) * 100.0))


def compute_threat_score(
    *,
    module_options: float,
    module_short: float,
    module_divergence: float,
    module_insider: float,
    weights: dict[str, float],
    ema_halflife_days: int = 2,
    history: Sequence[dict] | None = None,
) -> dict:
    """计算单标的当日的 Threat Score(原始 + EMA 平滑)。

    参数:
        module_* : 各模块子评分(0–100)
        weights   : 个股/ETF 权重,例 {"options":0.30,"short":0.35,"divergence":0.20,"insider":0.15}
        ema_halflife_days: OQ-02 决策
        history   : 历史上 N 日的 `{date, module_options, module_short, ...}` 列表(按日期升序),
                    用于 EMA 计算;若不传则 EMA = 当日原始分(无平滑)

    返回:
        {
            "raw": <float>,       # 当日原始加权
            "ema": <float>,       # EMA 平滑后
            "lifecycle": <str>,   # 'init'|'red'|'yellow'|'gray'|'green'
        }
    """
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {sum(weights.values())}")

    raw_today = (
        weights.get("options", 0) * module_options
        + weights.get("short", 0) * module_short
        + weights.get("divergence", 0) * module_divergence
        + weights.get("insider", 0) * module_insider
    )

    if history:
        scores_history = [
            (
                weights.get("options", 0) * h.get("module_options", 0)
                + weights.get("short", 0) * h.get("module_short", 0)
                + weights.get("divergence", 0) * h.get("module_divergence", 0)
                + weights.get("insider", 0) * h.get("module_insider", 0)
            )
            for h in history
        ]
        scores_history.append(raw_today)
    else:
        scores_history = [raw_today]

    ema_series = ema_smooth(scores_history, halflife_days=ema_halflife_days)
    ema_today = ema_series[-1]

    return {
        "raw": round(raw_today, 2),
        "ema": round(ema_today, 2),
        "ema_series": [round(x, 2) for x in ema_series],
    }


def decide_lifecycle(
    ema_score: float,
    red_threshold: float,
    yellow_threshold: float = 50.0,
    green_threshold: float = 30.0,
) -> str:
    """根据 EMA 后总分(严禁用原始分)决定信号灯。

    | 区间          | 颜色 |
    | ------------- | ---- |
    | ema >= red    | red  |
    | red > ema >= yellow | yellow |
    | yellow > ema >= green | gray |
    | ema < green   | green |
    """
    if ema_score >= red_threshold:
        return "red"
    if ema_score >= yellow_threshold:
        return "yellow"
    if ema_score >= green_threshold:
        return "gray"
    return "green"
