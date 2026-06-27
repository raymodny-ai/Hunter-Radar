"""V1.6.0 Threat Score ML 动态权重优化器。

基于过去 90 天各模块子评分对实际后续波动率的预测贡献度,
通过简单 LinearRegression 自动调整权重系数。

设计原则:
- 冷启动兼容: 历史 < 90 天 → 返回默认固定权重
- 权重 clamp: 每模块 [0.10, 0.50],总和 = 1.0
- 与 V1.5.9 动态重分配叠加: ML 权重作为 base_weights 传入 reallocate_weights()

依赖:
- numpy(最小二乘法,无需 scikit-learn 完整依赖)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

log = logging.getLogger(__name__)

# 默认权重(stock / etf)
_DEFAULT_WEIGHTS_STOCK: dict[str, float] = {
    "options": 0.30,
    "short": 0.35,
    "divergence": 0.20,
    "insider": 0.15,
}
_DEFAULT_WEIGHTS_ETF: dict[str, float] = {
    "options": 0.35,
    "short": 0.45,
    "divergence": 0.20,
}

# 权重约束
_MIN_WEIGHT: float = 0.10
_MAX_WEIGHT: float = 0.50
_MIN_HISTORY_DAYS: int = 90


@dataclass(slots=True)
class MLOptimizationResult:
    """ML 权重优化结果。"""

    weights: dict[str, float]
    r_squared: dict[str, float]  # 各模块的解释度(R²)
    sample_size: int  # 训练样本数
    is_valid: bool  # 是否有效(样本充足 + 拟合成功)
    fallback_reason: str | None = None  # 降级原因


def _compute_realized_volatility(
    price_history: list[float],
    window: int = 20,
) -> list[float]:
    """计算实现波动率(年化)。

    Args:
        price_history: 收盘价序列(按日期升序)
        window: 滚动窗口(交易日,默认 20)

    Returns:
        与 price_history 等长的年化波动率序列(前 window-1 个为 0)
    """
    if len(price_history) < 2:
        return [0.0] * len(price_history)

    # 日收益率
    returns = [0.0]
    for i in range(1, len(price_history)):
        if price_history[i - 1] > 0:
            returns.append(math.log(price_history[i] / price_history[i - 1]))
        else:
            returns.append(0.0)

    # 滚动标准差 × sqrt(252)
    out = [0.0] * len(returns)
    for i in range(window, len(returns)):
        w = returns[i - window : i]
        mean = sum(w) / len(w)
        var = sum((r - mean) ** 2 for r in w) / (len(w) - 1)
        out[i] = math.sqrt(var) * math.sqrt(252)

    return out


def _normalize_weights(
    raw_weights: dict[str, float],
    *,
    min_w: float = _MIN_WEIGHT,
    max_w: float = _MAX_WEIGHT,
) -> dict[str, float]:
    """归一化权重: clamp + 总和 = 1.0。

    步骤:
    1. 每个权重 clamp 到 [min_w, max_w]
    2. 归一化使总和 = 1.0
    """
    if not raw_weights:
        return {}

    # Clamp
    clamped = {k: max(min_w, min(max_w, v)) for k, v in raw_weights.items()}

    # 归一化
    total = sum(clamped.values())
    if total <= 0:
        # 全零 → 等权
        n = len(clamped)
        return {k: 1.0 / n for k in clamped}

    normalized = {k: v / total for k, v in clamped.items()}
    return normalized


def compute_prediction_contribution(
    module_scores_history: dict[str, list[float]],
    realized_vol: list[float],
) -> dict[str, float]:
    """计算各模块对后续波动率的预测贡献度。

    使用简单线性回归: realized_vol[i] = β0 + β1*options[i] + β2*short[i] + ...
    各模块的 R²(解释度)作为权重依据。

    Args:
        module_scores_history: {module_name: [score_1, score_2, ...]} 各模块子评分历史
        realized_vol: 对应的实现波动率序列(长度与各模块历史相同)

    Returns:
        {module_name: r_squared} 各模块的解释度
    """
    modules = list(module_scores_history.keys())
    n = len(realized_vol)

    if n < _MIN_HISTORY_DAYS:
        log.warning("ml_weights.insufficient_history", n=n, min=_MIN_HISTORY_DAYS)
        return {m: 0.0 for m in modules}

    # 简单线性回归(每个模块单独)
    r_squared: dict[str, float] = {}

    for module in modules:
        scores = module_scores_history[module]
        if len(scores) != n:
            r_squared[module] = 0.0
            continue

        # 计算相关系数 r
        mean_x = sum(scores) / n
        mean_y = sum(realized_vol) / n

        ss_xx = sum((x - mean_x) ** 2 for x in scores)
        ss_yy = sum((y - mean_y) ** 2 for y in realized_vol)
        ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(scores, realized_vol))

        if ss_xx <= 0 or ss_yy <= 0:
            r_squared[module] = 0.0
            continue

        r = ss_xy / math.sqrt(ss_xx * ss_yy)
        r_squared[module] = max(0.0, r ** 2)  # R² ∈ [0, 1]

    return r_squared


def optimize_weights(
    module_scores_history: dict[str, list[float]],
    realized_vol: list[float],
    *,
    symbol_type: str = "stock",
) -> MLOptimizationResult:
    """基于预测贡献度优化权重。

    步骤:
    1. 计算各模块 R²
    2. R² 归一化为权重
    3. Clamp 到 [0.10, 0.50]
    4. 总和 = 1.0

    Args:
        module_scores_history: {module_name: [score_1, ...]} 各模块子评分历史
        realized_vol: 实现波动率序列
        symbol_type: "stock" | "etf"

    Returns:
        MLOptimizationResult
    """
    default_weights = (
        _DEFAULT_WEIGHTS_ETF.copy()
        if symbol_type == "etf"
        else _DEFAULT_WEIGHTS_STOCK.copy()
    )

    n = len(realized_vol)
    if n < _MIN_HISTORY_DAYS:
        return MLOptimizationResult(
            weights=default_weights,
            r_squared={m: 0.0 for m in default_weights},
            sample_size=n,
            is_valid=False,
            fallback_reason=f"insufficient_history({n}<{_MIN_HISTORY_DAYS})",
        )

    # 计算 R²
    r_sq = compute_prediction_contribution(module_scores_history, realized_vol)

    # R² → 权重
    total_r2 = sum(r_sq.values())
    if total_r2 <= 0:
        return MLOptimizationResult(
            weights=default_weights,
            r_squared=r_sq,
            sample_size=n,
            is_valid=False,
            fallback_reason="zero_r_squared",
        )

    raw_weights = {m: r_sq[m] / total_r2 for m in default_weights}
    optimized = _normalize_weights(raw_weights)

    log.info(
        "ml_weights.optimized",
        symbol_type=symbol_type,
        weights=optimized,
        r_squared=r_sq,
        sample_size=n,
    )

    return MLOptimizationResult(
        weights=optimized,
        r_squared=r_sq,
        sample_size=n,
        is_valid=True,
        fallback_reason=None,
    )


def get_ml_weights(
    module_scores_history: dict[str, list[float]],
    price_history: list[float],
    *,
    symbol_type: str = "stock",
    vol_window: int = 20,
) -> MLOptimizationResult:
    """ML 权重优化入口。

    Args:
        module_scores_history: {module_name: [score_1, ...]} 各模块子评分历史
        price_history: 收盘价历史(用于计算实现波动率)
        symbol_type: "stock" | "etf"
        vol_window: 实现波动率滚动窗口(默认 20 交易日)

    Returns:
        MLOptimizationResult
    """
    # 计算实现波动率
    realized_vol = _compute_realized_volatility(price_history, window=vol_window)

    # 对齐长度(取交集)
    min_len = min(len(realized_vol), min(len(v) for v in module_scores_history.values()))
    if min_len < _MIN_HISTORY_DAYS:
        default_weights = (
            _DEFAULT_WEIGHTS_ETF.copy()
            if symbol_type == "etf"
            else _DEFAULT_WEIGHTS_STOCK.copy()
        )
        return MLOptimizationResult(
            weights=default_weights,
            r_squared={m: 0.0 for m in default_weights},
            sample_size=min_len,
            is_valid=False,
            fallback_reason=f"insufficient_aligned_history({min_len}<{_MIN_HISTORY_DAYS})",
        )

    # 截取最近 min_len 个数据点
    aligned_scores = {m: v[-min_len:] for m, v in module_scores_history.items()}
    aligned_vol = realized_vol[-min_len:]

    return optimize_weights(aligned_scores, aligned_vol, symbol_type=symbol_type)
