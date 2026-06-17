"""§3.5 自然语言摘要生成器(BD-065)。

职责:
- 调 `etl/load_threat_score` 的子评分 / 生命周期,生成自然语言摘要
- 个股 / ETF 双版本模板
- 严格遵守合规:模板与常量全部走集中常量,CI 拦截禁词(CR-010)

设计原则:
- 模板集中,便于 CR/PO 改稿
- 数值动态填充;无硬编码业务结论
- 不使用 emoji 与营销词(CR-003 / CR-009)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.config import settings


@dataclass(slots=True)
class SummaryContext:
    """摘要上下文(由 caller 准备)。"""

    trade_date: date
    symbol: str
    symbol_type: str  # 'stock' | 'etf'
    module_options: float
    module_short: float
    module_divergence: float
    module_insider: float
    total_ema: float
    signal_lifecycle: str
    regime: str
    consecutive_red_days: int = 0  # M3 接 ultimate_alert 时填充
    data_warmup: bool = False


# ---- 模块文案(集中常量) ----

# BD-065 模板档(CR review 通过后再扩)
MODULE_TEMPLATES_STOCK: dict[str, dict[str, str]] = {
    "options": {
        "high": "末日 Put 异常合约命中数显著(模块评分 {score:.0f})",
        "mid": "末日 Put 合约存在局部异常(模块评分 {score:.0f})",
        "low": "末日 Put 合约未触发异常(模块评分 {score:.0f})",
    },
    "short": {
        "high": "全监管做空量近 60 日滚动 Z-Score 偏高(模块评分 {score:.0f})",
        "mid": "全监管做空量处于中位偏上(模块评分 {score:.0f})",
        "low": "全监管做空量未出现显著异动(模块评分 {score:.0f})",
    },
    "divergence": {
        "high": "量价背离疑似吸筹(模块评分 {score:.0f})",
        "mid": "量价配合存在可疑节律(模块评分 {score:.0f})",
        "low": "量价配合未见明显背离(模块评分 {score:.0f})",
    },
    "insider": {
        "high": "关键内部人抛压显著或与回购公告存在时间接近(模块评分 {score:.0f})",
        "mid": "关键内部人抛压处于中位(模块评分 {score:.0f})",
        "low": "关键内部人近期未出现大额抛售(模块评分 {score:.0f})",
    },
}

MODULE_TEMPLATES_ETF: dict[str, dict[str, str]] = {
    "options": MODULE_TEMPLATES_STOCK["options"],
    "short": MODULE_TEMPLATES_STOCK["short"],
    "divergence": MODULE_TEMPLATES_STOCK["divergence"],
    # ETF 无 insider 模板
}

# 模块分数阈值
_THRESHOLD_HIGH = 70.0
_THRESHOLD_MID = 50.0


def _bucket(score: float) -> str:
    if score >= _THRESHOLD_HIGH:
        return "high"
    if score >= _THRESHOLD_MID:
        return "mid"
    return "low"


def _lifecycle_text(lifecycle: str) -> str:
    """5 态信号灯 → 文本(BD-062)。"""
    return {
        "red": "当前信号处于红灯区间(连续触发中)",
        "yellow": "当前信号处于黄灯区间(持续观察)",
        "gray": "当前信号处于灰灯区间(部分缓解)",
        "green": "当前信号处于绿灯区间(趋于平复)",
        "init": "当前信号处于观察期",
    }.get(lifecycle, "当前信号状态未知")


def _regime_text(regime: str, threshold_red: int) -> str:
    """市场门控文本(BD-063)。"""
    if regime == "panic":
        return f"市场状态为高波动区间,红灯阈值已上调至 {threshold_red}"
    return f"市场状态处于正常区间,红灯阈值 {threshold_red}"


def _warmup_text(data_warmup: bool) -> str:
    if data_warmup:
        return "数据暖启动中,部分指标因历史不足暂未生效"
    return "数据已充分积累"


def _sanitize(s: str) -> str:
    """最后兜底:扫描 CR-010 禁词,触发即抛错(防止无意引入)。"""
    for w in settings.forbidden_recommendation_words:
        if w in s:
            raise ValueError(f"nl_summary 命中禁词: {w!r}")
    return s


def render_summary(ctx: SummaryContext, *, threshold_red: int = 70) -> str:
    """生成自然语言摘要(BD-065)。

    Args:
        ctx: 摘要上下文
        threshold_red: 红灯阈值(由 regime 决定;normal=70, panic=80)

    Returns:
        中性自然语言摘要(不含投资建议)
    """
    templates = (
        MODULE_TEMPLATES_ETF if ctx.symbol_type == "etf" else MODULE_TEMPLATES_STOCK
    )

    parts: list[str] = []
    parts.append(f"标的 {ctx.symbol} 于 {ctx.trade_date} 的统计信号摘要:")
    parts.append(_lifecycle_text(ctx.signal_lifecycle))
    parts.append(_regime_text(ctx.regime, threshold_red))
    parts.append(_warmup_text(ctx.data_warmup))

    for mod_key, mod_score in [
        ("options", ctx.module_options),
        ("short", ctx.module_short),
        ("divergence", ctx.module_divergence),
    ]:
        if mod_key in templates:
            parts.append(templates[mod_key][_bucket(mod_score)].format(score=mod_score))

    if ctx.symbol_type != "etf" and "insider" in templates:
        parts.append(
            templates["insider"][_bucket(ctx.module_insider)].format(score=ctx.module_insider)
        )

    if ctx.consecutive_red_days >= 2:
        parts.append(
            f"已在连续 {ctx.consecutive_red_days} 个交易日的 EMA 后总分处于红灯区间,"
            "本报告仅基于历史数据与统计异常,无投资建议。"
        )

    text = "。".join(parts) + "。"
    return _sanitize(text)


def render_simple_etf_proxy(
    trade_date: date, symbol: str, signal: str, premium_pct: float, volume_ratio: float
) -> str:
    """ETF 折溢价代理信号简化文案(BD-088 / BD-065)。"""
    direction = "溢价" if premium_pct > 0 else "折价"
    strength = "显著" if abs(premium_pct) >= 1.0 else "温和"
    flow = "可能触发申购" if signal == "creation_likely" else "可能触发赎回" if signal == "redemption_likely" else "未触发代理信号"
    text = (
        f"标的 {symbol} 于 {trade_date} 的二级市场出现{strength}{direction},"
        f"幅度 {abs(premium_pct):.2f}%,相对 20 日均量 {volume_ratio:.2f} 倍,{flow}。"
        "本报告仅基于公开数据与统计代理,无投资建议。"
    )
    return _sanitize(text)
