"""V1.5 接力期 m9t5 — ETF 申赎代理 3 端点(BD-088)。

复用 backend/app/services/etf_proxy.py 的沙箱实现:
- build_etf_basket() — 构造申赎篮子
- submit_etf_order() — 提交申赎订单(sandbox_stub)
- compute_premium_discount() — 溢价折价计算

端点(V1.5.1 freeze):
  GET  /api/v1/etf/basket?etf=SPY
    返 EtfBasket(etf_ticker / nav / inav / shares_per_unit / cash_component / components)
  POST /api/v1/etf/orders
    body: { etf, order_type, settlement_mode, units, ap? }
    返 EtfOrder(order_id / etf_ticker / order_type / status / submitted_at)
  GET  /api/v1/etf/premium-discount?etf=SPY&price=450.0
    返 { market_price / nav / premium / premium_pct / arb_opportunity }

沙箱 fallback 显式标注:
  - review_mode="sandbox_stub_v15_prep"(沿用 etf_proxy.SANDBOX_REVIEW_MODE)
  - 严禁 mock 200 伪装成功(M5 锁定)
  - 订单 submit 仅构造对象,不发真实 AP 请求

V1.5.1 freeze:
  - /api/v1/etf/{basket,orders,premium-discount} 三路径
  - POST /etf/orders body 含 5 字段(etf/order_type/settlement_mode/units/ap)
  - 错误码 400(参数错) / 422(order_type / settlement_mode 不合法)
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.services.etf_proxy import (
    SANDBOX_REVIEW_MODE,
    EtfBasket,
    EtfOrder,
    EtfOrderStatus,
    EtfOrderType,
    EtfSettlementMode,
    build_etf_basket,
    compute_premium_discount,
    submit_etf_order,
)
from app.services.etf_proxy_real import (
    PRODUCTION_REVIEW_MODE,
    SANDBOX_FALLBACK_REVIEW_MODE,
    fetch_etf_proxy_indicators,
)

router = APIRouter()


# ----------------------------------------------------------------------
# Pydantic schemas
# ----------------------------------------------------------------------

class EtfOrderRequest(BaseModel):
    """POST /etf/orders 请求体。"""

    etf: str = Field(..., min_length=1, max_length=10, description="ETF ticker")
    order_type: str = Field(..., description="creation | redemption")
    settlement_mode: str = Field(..., description="cash | in_kind")
    units: int = Field(..., ge=1, le=10000, description="申购/赎回单位数(1-10000)")
    ap: Optional[str] = Field(default=None, max_length=64, description="Authorized Participant 名")

    @field_validator("order_type")
    @classmethod
    def _check_order_type(cls, v: str) -> str:
        if v not in (EtfOrderType.CREATION.value, EtfOrderType.REDEMPTION.value):
            raise ValueError(f"order_type 必须是 creation|redemption,收到:{v}")
        return v

    @field_validator("settlement_mode")
    @classmethod
    def _check_settlement(cls, v: str) -> str:
        if v not in (EtfSettlementMode.CASH.value, EtfSettlementMode.IN_KIND.value):
            raise ValueError(f"settlement_mode 必须是 cash|in_kind,收到:{v}")
        return v


# ----------------------------------------------------------------------
# GET /basket
# ----------------------------------------------------------------------

@router.get("/basket", summary="ETF 申赎篮子(sandbox_stub)")
async def get_etf_basket(etf: str = Query(..., min_length=1, max_length=10, description="ETF ticker")) -> dict:
    """拉 ETF 申赎篮子(NAV / iNAV / 成分股清单)。"""
    etf_t = etf.strip().upper()
    basket: EtfBasket = build_etf_basket(etf_t)

    # 沙箱 fallback:无真实 ETF 数据源时始终走 sandbox
    # 即使未来接 Bloomberg/ETF.com,也走 sandbox fallback(因 V1.5.1 暂未实装)
    sandbox = True
    if os.environ.get("ETF_BLOOMBERG_KEY"):
        sandbox = True  # 占位,V1.5.2 才实装真实数据源

    return {
        "basket": basket.to_dict(),
        "sandbox": sandbox,
        "review_mode": SANDBOX_REVIEW_MODE,
        "disclaimer": "Sandbox stub:基于 mock 篮子,非真实 NAV/iNAV/成分股数据。V1.5.1 起仅供 dev/sandbox,生产前需替换为 Bloomberg/ETF.com 实时数据。",
    }


# ----------------------------------------------------------------------
# POST /orders
# ----------------------------------------------------------------------

@router.post("/orders", summary="提交 ETF 申赎订单(sandbox_stub)")
async def post_etf_order(req: EtfOrderRequest = Body(...)) -> dict:
    """提交 ETF 申赎订单(沙箱 stub,不发真实 AP 请求)。"""
    etf_t = req.etf.strip().upper()
    order = submit_etf_order(
        etf_ticker=etf_t,
        order_type=EtfOrderType(req.order_type),
        settlement_mode=EtfSettlementMode(req.settlement_mode),
        units=req.units,
        ap=req.ap,
    )
    return {
        "order": order.to_dict(),
        "sandbox": True,
        "review_mode": SANDBOX_REVIEW_MODE,
        "disclaimer": "Sandbox stub:仅构造订单对象,未发真实 AP 请求。V1.5.1 起仅供 dev/sandbox,生产前需接入 BNY Mellon / JPMorgan AP API。",
    }


# ----------------------------------------------------------------------
# GET /premium-discount
# ----------------------------------------------------------------------

@router.get("/premium-discount", summary="ETF 溢价/折价计算(V1.5.2 真实代理数据)")
async def get_premium_discount(
    etf: str = Query(..., min_length=1, max_length=10, description="ETF ticker"),
    price: float | None = Query(default=None, gt=0, le=10000, description="市场实时价(可空;为空时用 yfinance 真实代理价)"),
) -> dict:
    """计算 ETF 市价相对 NAV 的溢价/折价 + 套利窗口(V1.5.2 升级)。

    V1.5.2 双轨:
    - price 参数提供时:用传入价格计算(沿用 V1.5.1 行为)
    - price 为空时:调 fetch_etf_proxy_indicators(yfinance 真实代理数据)
      失败 fallback sandbox_stub_v15_prep,显式标注 fetch_source + warning

    响应新增字段:inav_deviation / volume_5d_avg / volume_30d_avg / volume_spike_ratio / fetch_source
    """
    etf_t = etf.strip().upper()

    if price is not None:
        # V1.5.1 行为:用传入 price 直接计算(沿用)
        basket: EtfBasket = build_etf_basket(etf_t)
        result = compute_premium_discount(basket, market_price=price)
        result["sandbox"] = True
        result["review_mode"] = SANDBOX_REVIEW_MODE
        result["etf"] = etf_t
        result["fetch_source"] = "user_provided_price"
        result["disclaimer"] = "Sandbox stub:price 由用户传入,用 mock NAV/iNAV 计算;V1.5.2 起建议留空 price 走真实代理。"
        return result

    # V1.5.2 升级:price 为空 → 拉真实代理指标
    import asyncio as _asyncio

    indicators = _asyncio.run(fetch_etf_proxy_indicators(etf_t))
    return {
        "etf": etf_t,
        "market_price": indicators.market_price,
        "nav": indicators.nav,
        "inav": indicators.inav,
        "premium": indicators.premium,
        "premium_pct": indicators.premium_pct,
        "inav_deviation": indicators.inav_deviation,
        "volume_5d_avg": indicators.volume_5d_avg,
        "volume_30d_avg": indicators.volume_30d_avg,
        "volume_spike_ratio": indicators.volume_spike_ratio,
        "arb_opportunity": indicators.arb_opportunity,
        "fetched_at": indicators.fetched_at,
        "fetch_source": indicators.fetch_source,
        "sandbox": indicators.sandbox,
        "review_mode": indicators.review_mode,
        "http_latency_ms": indicators.http_latency_ms,
        "warning": indicators.warning,
        "disclaimer": (
            "V1.5.2 双轨:price 为空时用 yfinance 真实代理数据;"
            "失败自动 fallback sandbox_stub_v15_prep,显式 fetch_source + warning 标注,严禁 mock 200 伪装。"
        ),
    }
