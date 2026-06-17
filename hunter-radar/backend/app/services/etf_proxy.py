"""BD-088 ETF 申赎代理 — V1.5 准备(M7 接力期)。

V1.5 待落地(V1.4 不暴露 API):
- ETF creation/redemption 代理服务
- Authorized Participant(AP)代理
- Cash + in-kind 两种模式
- NAV/iNAV 校验

沙箱 stub 设计:
- 不发真实下单请求(无券商 API)
- 接口定义完整,业务逻辑留 V1.5+ 实现
- 沙箱模式下返 mock response + sandbox stub 标记
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal


class EtfOrderType(str, Enum):
    """ETF 申赎订单类型。"""

    CREATION = "creation"  # 申购(交付成分股 / 现金 → 获得 ETF 份额)
    REDEMPTION = "redemption"  # 赎回(交付 ETF 份额 → 获得成分股 / 现金)


class EtfSettlementMode(str, Enum):
    """ETF 申赎结算模式。"""

    CASH = "cash"  # 现金结算
    IN_KIND = "in_kind"  # 实物申购赎回(交付成分股)


class EtfOrderStatus(str, Enum):
    """ETF 申赎订单状态。"""

    PENDING = "pending"  # 待提交
    SUBMITTED = "submitted"  # 已提交 AP
    CONFIRMED = "confirmed"  # AP 已确认
    SETTLED = "settled"  # 已结算
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


SANDBOX_REVIEW_MODE = "sandbox_stub_v15_prep"


@dataclass
class EtfBasket:
    """ETF 申赎篮子(成分股清单)。"""

    etf_ticker: str
    nav: float  # 单位净值
    inav: float  # 指示性净值
    shares_per_unit: int  # 每申购单位份数(通常 50000 / 100000)
    cash_component: float  # 现金差额
    components: list[dict] = field(default_factory=list)  # [{ticker, shares, weight}]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EtfOrder:
    """ETF 申赎订单。"""

    order_id: str
    etf_ticker: str
    order_type: EtfOrderType
    settlement_mode: EtfSettlementMode
    units: int  # 申购/赎回单位数
    status: EtfOrderStatus = EtfOrderStatus.PENDING
    submitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    settled_at: str | None = None
    ap: str | None = None  # Authorized Participant 名称
    review_mode: str = SANDBOX_REVIEW_MODE

    def to_dict(self) -> dict:
        return asdict(self)


def build_etf_basket(etf_ticker: str, *, as_of_date: str | None = None) -> EtfBasket:
    """构造 ETF 申赎篮子(V1.5 准备 stub)。

    沙箱 stub:返 mock basket,生产环境应拉 Bloomberg/ETF.com 实时数据。
    """
    return EtfBasket(
        etf_ticker=etf_ticker,
        nav=100.0,  # mock
        inav=100.05,  # mock
        shares_per_unit=50000,
        cash_component=125.30,
        components=[
            {"ticker": "AAPL", "shares": 150, "weight": 0.25},
            {"ticker": "MSFT", "shares": 80, "weight": 0.20},
            {"ticker": "GOOG", "shares": 50, "weight": 0.15},
            {"ticker": "AMZN", "shares": 60, "weight": 0.12},
            {"ticker": "NVDA", "shares": 30, "weight": 0.10},
            {"ticker": "META", "shares": 25, "weight": 0.08},
            {"ticker": "TSLA", "shares": 20, "weight": 0.06},
            {"ticker": "OTHER", "shares": 100, "weight": 0.04},
        ],
    )


def submit_etf_order(
    etf_ticker: str,
    order_type: EtfOrderType,
    settlement_mode: EtfSettlementMode,
    units: int,
    *,
    ap: str | None = None,
) -> EtfOrder:
    """提交 ETF 申赎订单(V1.5 准备 stub)。

    沙箱 stub:仅构造订单,不实际发 AP 请求。
    生产:V1.5+ 接入 AP API(BNY Mellon / JPMorgan 等)。
    """
    return EtfOrder(
        order_id=f"sandbox_etf_{etf_ticker}_{int(datetime.now(timezone.utc).timestamp())}",
        etf_ticker=etf_ticker,
        order_type=order_type,
        settlement_mode=settlement_mode,
        units=units,
        status=EtfOrderStatus.PENDING,
        ap=ap,
    )


def compute_premium_discount(basket: EtfBasket, market_price: float) -> dict:
    """计算 ETF 市价相对 NAV 的溢价/折价。

    Returns:
        {
            "market_price": float,
            "nav": float,
            "premium": float,        # market_price - nav
            "premium_pct": float,    # (market_price - nav) / nav * 100
            "arb_opportunity": bool, # |premium_pct| > 0.5% 时套利窗口存在
        }
    """
    premium = market_price - basket.nav
    premium_pct = premium / basket.nav * 100 if basket.nav > 0 else 0.0
    return {
        "market_price": market_price,
        "nav": basket.nav,
        "premium": round(premium, 4),
        "premium_pct": round(premium_pct, 4),
        "arb_opportunity": abs(premium_pct) > 0.5,
    }