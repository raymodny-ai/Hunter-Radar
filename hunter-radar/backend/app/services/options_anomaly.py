"""§3.1 模块一:期权异常分布 — 末日 Put / 末日异动过滤(BD-020 / BD-021)。

PRD §3.1 过滤条件:
  - DTE ≤ 3 交易日
  - OTM > 10%(ETF 容忍 5%)
  - Volume > 5 × Open Interest
  - 当日 OI 增幅 > 50%
  - 末日异动 Top10 名义金额
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class OptionCandidate:
    """单条期权合约(从 options_chain 表读出)。"""

    contract: str
    underlying: str
    underlying_type: str  # 'stock' | 'etf'
    trade_date: date
    expiry: date
    dte: int
    right: str  # 'P' | 'C'
    strike: float
    last_price: float
    spot: float
    volume: int
    open_interest: int
    open_interest_prev: int


@dataclass(slots=True, frozen=True)
class AnomalyThresholds:
    """可调阈值,集中在一处方便回测(BD-087)。"""

    dte_max: int = 3
    otm_min_stock: float = 0.10
    otm_min_etf: float = 0.05
    vol_vs_oi_min: float = 5.0
    oi_growth_min: float = 0.50
    top_n_notional: int = 10


def is_otm(contract: OptionCandidate) -> bool:
    """虚值判定(对 Put)。仅做单边测试用,产品层调 is_anomaly_otm_put。"""
    pct = abs(contract.strike - contract.spot) / contract.spot
    threshold = (
        AnomalyThresholds().otm_min_etf
        if contract.underlying_type == "etf"
        else AnomalyThresholds().otm_min_stock
    )
    return pct >= threshold


def is_anomaly_otm_put(c: OptionCandidate, thr: AnomalyThresholds | None = None) -> bool:
    """末日 OTM Put 异常判定(BD-020 主规则)。

    全部满足才返回 True:
      1. DTE ≤ 3
      2. Put 合约
      3. OTM 超过阈值(stock 10% / etf 5%)
      4. Volume ≥ 5 × OI(末日突增交易)
      5. OI 日增幅 ≥ 50%(建仓痕迹)
    """
    thr = thr or AnomalyThresholds()
    if c.right != "P":
        return False
    if c.dte > thr.dte_max:
        return False
    # OTM
    otm_pct = abs(c.strike - c.spot) / max(c.spot, 1e-9)
    min_otm = thr.otm_min_etf if c.underlying_type == "etf" else thr.otm_min_stock
    if otm_pct < min_otm:
        return False
    # Vol / OI
    if c.open_interest <= 0 or c.volume < thr.vol_vs_oi_min * c.open_interest:
        return False
    # OI 增幅
    if c.open_interest_prev <= 0:
        return False
    growth = (c.open_interest - c.open_interest_prev) / c.open_interest_prev
    return growth >= thr.oi_growth_min


def notional(c: OptionCandidate) -> float:
    """名义金额(美元)= volume × last_price × 100(乘数)。"""
    return c.volume * c.last_price * 100.0


def filter_top_anomaly_puts(
    candidates: list[OptionCandidate],
    thr: AnomalyThresholds | None = None,
) -> list[OptionCandidate]:
    """返回同时满足条件 + 名义金额 Top N 的末日 Put 列表(BD-021)。"""
    thr = thr or AnomalyThresholds()
    hits = [c for c in candidates if is_anomaly_otm_put(c, thr)]
    hits.sort(key=notional, reverse=True)
    return hits[: thr.top_n_notional]


def summarize_anomaly_count(
    candidates: list[OptionCandidate], thr: AnomalyThresholds | None = None
) -> int:
    """数量统计(BD-022)— 给前端 KPI 卡片用。"""
    thr = thr or AnomalyThresholds()
    return sum(1 for c in candidates if is_anomaly_otm_put(c, thr))
