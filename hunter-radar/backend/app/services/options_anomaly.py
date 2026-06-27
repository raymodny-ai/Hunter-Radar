"""§3.1 模块一:期权异常分布 — 末日 Put / 末日异动过滤 + V1.5.9 增强(BD-020 / BD-021)。

PRD §3.1 过滤条件:
  - DTE ≤ 3 交易日
  - OTM > 10%(ETF 容忍 5%)
  - Volume > 5 × Open Interest
  - 当日 OI 增幅 > 50%
  - 末日异动 Top10 名义金额

V1.5.9 增强:
  - 2.1: PCR + Z-Score 极值检测(全局 Put/Call 比率的 2σ 突变)
  - 2.2: 动态基准(30 日均量 × N,ETF/stock 分级阈值)
  - 2.3: 末日 Gamma 聚集(strike 维度成交量聚合检测)
  - 2.4: signal_strength 分级(HIGH/NORMAL)
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


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


# ================================================================
# V1.5.9 增强
# ================================================================


class SignalStrength(str, Enum):
    """Options 模块信号强度(供 Threat 引擎权重调整)。"""

    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


# ---- 2.2 动态基准 ----


@dataclass(slots=True, frozen=True)
class DynamicBaseline:
    """动态成交量阈值配置(替代静态 vol_min=500)。

    对于 SPY/QQQ 等大流动性标的,500 手 Put 是日常散单;
    对于小盘股,500 手可能是巨大异常暴露。
    动态基准 = max(absolute_floor, avg_30d_volume × multiplier)
    """

    lookback_days: int = 30
    vol_multiplier_etf: float = 3.0
    vol_multiplier_stock: float = 5.0
    absolute_floor_etf: int = 1000
    absolute_floor_stock: int = 200


def compute_dynamic_vol_min(
    ticker_type: str,
    avg_30d_volume: float,
    cfg: DynamicBaseline | None = None,
) -> int:
    """计算动态 vol_min。

    Args:
        ticker_type: 'etf' 或 'stock'
        avg_30d_volume: 过去 30 天平均期权成交量
        cfg: 配置;None 用默认
    """
    cfg = cfg or DynamicBaseline()
    if ticker_type == "etf":
        return max(cfg.absolute_floor_etf, int(avg_30d_volume * cfg.vol_multiplier_etf))
    return max(cfg.absolute_floor_stock, int(avg_30d_volume * cfg.vol_multiplier_stock))


# ---- 2.1 PCR + Z-Score 极值 ----


@dataclass(slots=True)
class PCRResult:
    """Put/Call Ratio 计算结果。"""

    total_put_volume: int
    total_call_volume: int
    pcr: float  # put_vol / call_vol
    pcr_z_score: float | None  # 相对历史的 Z-Score;None = 冷启动
    is_extreme: bool = False  # |z| >= 2σ


def compute_pcr(
    put_volume: int,
    call_volume: int,
    *,
    pcr_history: list[float] | None = None,
    z_threshold: float = 2.0,
) -> PCRResult:
    """计算 PCR + Z-Score 极值检测。

    Args:
        put_volume: 当日 Put 总成交量
        call_volume: 当日 Call 总成交量
        pcr_history: 过去 N 日 PCR 历史(用于 Z-Score);None = 冷启动
        z_threshold: Z-Score 阈值(默认 2σ)
    """
    pcr = put_volume / max(call_volume, 1)  # 防除零

    z_score: float | None = None
    is_extreme = False

    if pcr_history and len(pcr_history) >= 5:
        mean = sum(pcr_history) / len(pcr_history)
        var = sum((x - mean) ** 2 for x in pcr_history) / (len(pcr_history) - 1)
        sd = math.sqrt(var) if var > 1e-12 else 0.0
        if sd > 0:
            z_score = (pcr - mean) / sd
            is_extreme = abs(z_score) >= z_threshold

    return PCRResult(
        total_put_volume=put_volume,
        total_call_volume=call_volume,
        pcr=round(pcr, 4),
        pcr_z_score=round(z_score, 4) if z_score is not None else None,
        is_extreme=is_extreme,
    )


# ---- 2.2 OTM 刺客合约(动态基准) ----


def is_otm_assassin(
    c: OptionCandidate,
    dynamic_vol_min: int,
    *,
    vol_oi_ratio_min: float = 3.0,
) -> bool:
    """OTM 刺客合约判定(动态基准版)。

    条件:
      1. Put 合约
      2. OTM(strike < spot)
      3. DTE ≤ 7
      4. volume > dynamic_vol_min(基于 30 日均量)
      5. volume / open_interest > vol_oi_ratio_min
    """
    if c.right != "P":
        return False
    if c.dte > 7:
        return False
    # OTM: Put 的 strike < spot
    if c.strike >= c.spot:
        return False
    # 动态成交量阈值
    if c.volume < dynamic_vol_min:
        return False
    # Vol/OI 比
    if c.open_interest > 0 and (c.volume / c.open_interest) < vol_oi_ratio_min:
        return False
    return True


# ---- 2.3 Gamma 聚集 ----


@dataclass(slots=True)
class GammaCluster:
    """Gamma 聚集检测结果。"""

    symbol: str
    strike: float
    total_volume: int
    contract_count: int
    is_cluster: bool
    cluster_ratio: float  # 该 strike 成交量占 DTE≤3 总 Put 成交量的比例


def detect_gamma_cluster(
    candidates: list[OptionCandidate],
    *,
    dte_max: int = 3,
    cluster_threshold: float = 0.30,
) -> list[GammaCluster]:
    """检测末日 Gamma 聚集:同一 strike 的 Put 成交量集中度。

    当某 strike 的成交量占 DTE≤3 总 Put 成交量 ≥ cluster_threshold 时,
    视为 Gamma 聚集(做市商需要在此 strike 附近大量 delta-hedge)。

    Args:
        candidates: 全部 Put 合约候选
        dte_max: DTE 上限(默认 3)
        cluster_threshold: 聚集比例阈值(默认 30%)
    """
    # 筛选 DTE ≤ dte_max 的 Put
    near_puts = [c for c in candidates if c.right == "P" and c.dte <= dte_max]
    if not near_puts:
        return []

    total_vol = sum(c.volume for c in near_puts)
    if total_vol <= 0:
        return []

    # 按 strike 聚合
    strike_vol: dict[float, int] = defaultdict(int)
    strike_count: dict[float, int] = defaultdict(int)
    for c in near_puts:
        strike_vol[c.strike] += c.volume
        strike_count[c.strike] += 1

    # 找出聚集点
    clusters: list[GammaCluster] = []
    sym = near_puts[0].underlying if near_puts else ""
    for strike, vol in sorted(strike_vol.items(), key=lambda x: -x[1]):
        ratio = vol / total_vol
        clusters.append(
            GammaCluster(
                symbol=sym,
                strike=strike,
                total_volume=vol,
                contract_count=strike_count[strike],
                is_cluster=(ratio >= cluster_threshold),
                cluster_ratio=round(ratio, 4),
            )
        )
    return clusters


# ---- 2.4 signal_strength 综合分级 ----


@dataclass(slots=True)
class OptionsSignalSummary:
    """Options 模块综合信号摘要。"""

    signal_strength: SignalStrength
    pcr: PCRResult | None
    anomaly_count: int
    otm_assassin_count: int
    gamma_clusters: list[GammaCluster]
    high_signal_modules: list[str] = field(default_factory=list)


def compute_signal_strength(
    pcr: PCRResult | None,
    anomaly_count: int,
    otm_assassins: int,
    gamma_clusters: list[GammaCluster],
    *,
    high_threshold_anomaly: int = 3,
    high_threshold_assassin: int = 2,
) -> OptionsSignalSummary:
    """综合 Options 信号强度判定。

    HIGH 触发条件(任一满足):
      - PCR Z-Score 极值(|z| ≥ 2σ)
      - anomaly_count ≥ high_threshold_anomaly
      - otm_assassin_count ≥ high_threshold_assassin
      - 存在 Gamma 聚集(cluster.is_cluster=True)
    """
    high_modules: list[str] = []

    if pcr and pcr.is_extreme:
        high_modules.append("pcr_extreme")
    if anomaly_count >= high_threshold_anomaly:
        high_modules.append("anomaly_spike")
    if otm_assassins >= high_threshold_assassin:
        high_modules.append("otm_assassin")
    active_clusters = [gc for gc in gamma_clusters if gc.is_cluster]
    if active_clusters:
        high_modules.append("gamma_cluster")

    strength = SignalStrength.HIGH if high_modules else SignalStrength.NORMAL

    return OptionsSignalSummary(
        signal_strength=strength,
        pcr=pcr,
        anomaly_count=anomaly_count,
        otm_assassin_count=otm_assassins,
        gamma_clusters=gamma_clusters,
        high_signal_modules=high_modules,
    )
