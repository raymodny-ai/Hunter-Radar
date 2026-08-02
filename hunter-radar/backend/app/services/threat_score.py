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
from math import log, log1p, tanh

# CA-11 (优化方案 2.1): 单模块独占权重保护。
# 至少 2 个模块有真实数据才出分, 否则返回 confidence="insufficient_data"。
# 防止 3/4 模块缺失时剩余 1 个模块独占 100% 权重放大噪声。
MIN_ACTIVE_MODULES = 2


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
    return 50.0 * (1.0 + tanh(z / cap))


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
    module_options: float | None = None,
    module_short: float | None = None,
    module_divergence: float | None = None,
    module_insider: float | None = None,
    weights: dict[str, float],
    ema_halflife_days: int = 2,
    history: Sequence[dict] | None = None,
) -> dict:
    """计算单标的当日的 Threat Score(原始 + EMA 平滑)。

    V1.6.1: NULL ≠ 0 —— 模块返回 None 时从加权平均中排除并重新归一化权重。

    参数:
        module_* : 各模块子评分(0–100),None 表示数据缺失(排除)
        weights   : 个股/ETF 权重,例 {"options":0.30,"short":0.35,"divergence":0.20,"insider":0.15}
        ema_halflife_days: OQ-02 决策
        history   : 历史上 N 日的 `{date, module_options, module_short, ...}` 列表(按日期升序),
                    用于 EMA 计算;若不传则 EMA = 当日原始分(无平滑)

    返回:
        {
            "raw": <float>,       # 当日原始加权
            "ema": <float>,       # EMA 平滑后
            "lifecycle": <str>,   # 'init'|'red'|'yellow'|'gray'|'green'
            "modules_active": <list[str]>,  # 参与计算的有效模块
            "data_quality": <str>,  # 'complete'|'degraded'
        }
    """
    # V1.6.1: 收集有效模块(排除 None)
    modules: dict[str, float | None] = {
        "options": module_options,
        "short": module_short,
        "divergence": module_divergence,
        "insider": module_insider,
    }
    active = {k: v for k, v in modules.items() if v is not None and k in weights}

    if not active:
        # 所有模块缺失——无法计算
        return {
            "raw": 0.0,
            "ema": 0.0,
            "ema_series": [0.0],
            "modules_active": [],
            "data_quality": "stale",
            "confidence": "insufficient_data",
            "active_modules": 0,
        }

    if len(active) < MIN_ACTIVE_MODULES:
        # CA-11: 仅 1 个模块有数据 → 不出分(避免单模块独占 100% 权重)
        return {
            "raw": None,
            "ema": None,
            "ema_series": [],
            "modules_active": sorted(active.keys()),
            "data_quality": "insufficient",
            "confidence": "insufficient_data",
            "active_modules": len(active),
            "note": f"仅 {len(active)}/{len(modules)} 模块有数据,不出分(CA-11)",
        }

    # 重新归一化权重(排除 None 模块后总和可能 < 1.0)
    total_weight = sum(weights[k] for k in active)
    if total_weight < 1e-9:
        total_weight = 1.0

    raw_today = sum(active[k] * weights[k] / total_weight for k in active)

    # 数据质量标记
    all_modules = {k for k in weights if weights[k] > 0}
    data_quality = "complete" if set(active.keys()) >= all_modules else "degraded"

    if history:
        scores_history = []
        for h in history:
            h_active = {
                k: h.get(f"module_{k}")
                for k in weights
                if h.get(f"module_{k}") is not None
            }
            if h_active:
                h_total_w = sum(weights[k] for k in h_active)
                scores_history.append(
                    sum(h_active[k] * weights[k] / h_total_w for k in h_active)
                )
            else:
                scores_history.append(0.0)
        scores_history.append(raw_today)
    else:
        scores_history = [raw_today]

    ema_series = ema_smooth(scores_history, halflife_days=ema_halflife_days)
    ema_today = ema_series[-1]

    return {
        "raw": round(raw_today, 2),
        "ema": round(min(ema_today, 100.0), 2),  # Min(Score, 100) 硬截断
        "ema_series": [round(min(x, 100.0), 2) for x in ema_series],
        "modules_active": sorted(active.keys()),
        "data_quality": data_quality,
        "confidence": "high" if len(active) == len(modules) else "medium",
        "active_modules": len(active),
    }


# ---- V1.5.9 动态权重重分配 ----

# 默认权重(stock / etf)
_DEFAULT_WEIGHTS_STOCK: dict[str, float] = {
    "options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15
}
_DEFAULT_WEIGHTS_ETF: dict[str, float] = {
    "options": 0.35, "short": 0.45, "divergence": 0.20
}

# 当某模块 signal=HIGH 时,该模块权重提升至 0.40,压缩其他 Normal 模块
_HIGH_BOOST: float = 0.40


def reallocate_weights(
    signals: dict[str, str],
    *,
    base_weights: dict[str, float] | None = None,
    symbol_type: str = "stock",
) -> dict[str, float]:
    """动态权重重分配:总和恒=1.0。

    当某模块 signal_strength=HIGH 时,其权重提升至 _HIGH_BOOST,
    剩余权重按 Normal 模块原比例重分配。

    Args:
        signals: {module_name: "HIGH" | "NORMAL"}
        base_weights: 基准权重;None 时用默认(stock/etf)
        symbol_type: "stock" | "etf"

    Returns:
        重新分配后的权重 dict(总和 = 1.0)
    """
    if base_weights is None:
        base_weights = (
            _DEFAULT_WEIGHTS_ETF.copy()
            if symbol_type == "etf"
            else _DEFAULT_WEIGHTS_STOCK.copy()
        )

    high_modules = [m for m, s in signals.items() if s == "HIGH" and m in base_weights]
    if not high_modules:
        return base_weights.copy()

    # HIGH 模块均分 _HIGH_BOOST
    per_high = _HIGH_BOOST / len(high_modules)
    remaining = 1.0 - _HIGH_BOOST

    normal_modules = [m for m in base_weights if m not in high_modules]
    if normal_modules:
        # 按原比例分配剩余
        normal_sum = sum(base_weights[m] for m in normal_modules)
        if normal_sum > 1e-9:
            normal_weights = {
                m: remaining * (base_weights[m] / normal_sum) for m in normal_modules
            }
        else:
            normal_weights = {m: remaining / len(normal_modules) for m in normal_modules}
    else:
        normal_weights = {}

    weights = {m: per_high for m in high_modules}
    weights.update(normal_weights)
    return weights


def decide_lifecycle(
    ema_score: float,
    red_threshold: float,
    yellow_threshold: float = 50.0,
    green_threshold: float = 30.0,
    *,
    raw_score: float | None = None,
    panic_threshold: float = 80.0,
) -> str:
    """根据 EMA 后总分决定信号灯。

    V1.6.1 EMA 尖峰覆盖: raw_score ≥ panic_threshold 时直接判定 "red",
    避免 2 日 EMA 半衰期延迟急性威胁检测。

    | 区间          | 颜色 |
    | ------------- | ---- |
    | raw >= panic  | red  (尖峰覆盖)
    | ema >= red    | red  |
    | red > ema >= yellow | yellow |
    | yellow > ema >= green | gray |
    | ema < green   | green |
    """
    # V1.6.1: 尖峰覆盖——原始分超过 panic 阈值时立即红灯
    if raw_score is not None and raw_score >= panic_threshold:
        return "red"
    if ema_score >= red_threshold:
        return "red"
    if ema_score >= yellow_threshold:
        return "yellow"
    if ema_score >= green_threshold:
        return "gray"
    return "green"
