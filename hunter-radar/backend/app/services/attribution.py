"""V1.6.0 信号归因分析服务(Attribution)。

计算 Threat Score 中各模块的加权贡献,
帮助用户理解"为什么是红灯"。

输出:
- 各模块的 weight × score 贡献
- 主驱动模块(贡献最大)
- 瀑布图数据(前端可视化用)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class ModuleContribution:
    """单模块的归因贡献。"""

    module: str  # 'options' | 'short' | 'divergence' | 'insider'
    weight: float
    score: float  # 原始子评分(0-100)
    contribution: float  # weight × score
    label: str = ""  # 人类可读标签

    def __post_init__(self) -> None:
        if not self.label:
            labels = {
                "options": "期权异动",
                "short": "做空压力",
                "divergence": "量价背离",
                "insider": "内部人抛压",
            }
            self.label = labels.get(self.module, self.module)


@dataclass(slots=True)
class AttributionBreakdown:
    """归因分析完整结果。"""

    trade_date: date
    symbol: str
    symbol_type: str
    total_score: float  # Threat Score(EMA 后)
    total_raw: float
    modules: list[ModuleContribution]
    primary_driver: str  # 贡献最大的模块名
    primary_driver_label: str  # 主驱动模块标签
    waterfall_data: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为 API 响应格式。"""
        return {
            "trade_date": self.trade_date.isoformat(),
            "symbol": self.symbol,
            "symbol_type": self.symbol_type,
            "total_score": round(self.total_score, 2),
            "total_raw": round(self.total_raw, 2),
            "primary_driver": self.primary_driver,
            "primary_driver_label": self.primary_driver_label,
            "modules": [
                {
                    "module": m.module,
                    "label": m.label,
                    "weight": round(m.weight, 4),
                    "score": round(m.score, 2),
                    "contribution": round(m.contribution, 2),
                }
                for m in self.modules
            ],
            "waterfall_data": self.waterfall_data,
        }


def compute_attribution(
    trade_date: date,
    symbol: str,
    symbol_type: str,
    module_options: float,
    module_short: float,
    module_divergence: float,
    module_insider: float,
    weights: dict[str, float],
    total_score: float,
    total_raw: float,
) -> AttributionBreakdown:
    """计算归因分析。

    Args:
        trade_date: 交易日期
        symbol: 标的代码
        symbol_type: 'stock' | 'etf'
        module_*: 各模块子评分(0-100)
        weights: 权重字典
        total_score: EMA 后总分
        total_raw: 原始总分

    Returns:
        AttributionBreakdown
    """
    modules: list[ModuleContribution] = []

    # Options
    w_opts = weights.get("options", 0.0)
    modules.append(
        ModuleContribution(
            module="options",
            weight=w_opts,
            score=module_options,
            contribution=w_opts * module_options,
        )
    )

    # Short
    w_short = weights.get("short", 0.0)
    modules.append(
        ModuleContribution(
            module="short",
            weight=w_short,
            score=module_short,
            contribution=w_short * module_short,
        )
    )

    # Divergence
    w_div = weights.get("divergence", 0.0)
    modules.append(
        ModuleContribution(
            module="divergence",
            weight=w_div,
            score=module_divergence,
            contribution=w_div * module_divergence,
        )
    )

    # Insider(ETF 无此模块)
    if symbol_type == "stock":
        w_ins = weights.get("insider", 0.0)
        modules.append(
            ModuleContribution(
                module="insider",
                weight=w_ins,
                score=module_insider,
                contribution=w_ins * module_insider,
            )
        )

    # 排序:贡献从大到小
    modules.sort(key=lambda m: m.contribution, reverse=True)
    primary = modules[0] if modules else None

    # 构建瀑布图数据
    waterfall: list[dict] = []
    cumulative = 0.0
    for m in modules:
        waterfall.append(
            {
                "name": m.label,
                "module": m.module,
                "value": round(m.contribution, 2),
                "cumulative": round(cumulative + m.contribution, 2),
                "is_primary": m.module == (primary.module if primary else ""),
            }
        )
        cumulative += m.contribution

    return AttributionBreakdown(
        trade_date=trade_date,
        symbol=symbol,
        symbol_type=symbol_type,
        total_score=total_score,
        total_raw=total_raw,
        modules=modules,
        primary_driver=primary.module if primary else "unknown",
        primary_driver_label=primary.label if primary else "未知",
        waterfall_data=waterfall,
    )
