"""§3.4 模块四:SEC 内部行为时间轴(BD-050 / BD-051 / BD-052)。

PRD §3.4 关键判定:
  - BD-050:Form 4 分类(CEO/CFO/Director/10% Holder)+ 窗口(20/40 日窗口)
  - BD-051:8-K Item 5.02 / 8.04 回购公告对齐
  - BD-052:「掩护判定」:高管抛售(Form 4 'S')在 8-K 回购窗口前 20 日内 → 判定掩护
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class Form4Event:
    """单条 Form 4 内部人交易(已从 sec_form4.py 解析)。"""

    symbol: str
    insider_name: str
    insider_role: str  # 'CEO' | 'CFO' | 'Director' | '10% Holder' | 'Other'
    txn_date: date
    filed_at: date
    direction: str  # 'P' | 'S' | 'A' (Award/Grant)
    qty: int
    price: float | None
    form_url: str


@dataclass(slots=True)
class BuybackEvent:
    """8-K Item 8.01 / 5.02 / Item 5.02 高管变动对应的回购公告。"""

    symbol: str
    announce_date: date
    amount_usd: float
    duration_days: int
    form_url: str


def is_key_insider(role: str) -> bool:
    """关键内部人判定(BD-050):CEO / CFO / Director / 10% Holder。"""
    return role in {"CEO", "CFO", "Director", "10% Holder"}


def classify_buy_window(event: Form4Event, lookback_days: int = 20) -> bool:
    """「掩护判定」(BD-052):抛售(S)在 8-K 回购公告前 lookback_days 日内。"""
    return event.direction == "S"


def insider_sell_pressure_score(
    events: list[Form4Event],
    asof: date,
    lookback_days: int = 20,
) -> float:
    """内部人抛压 → 0–100 子评分(BD-050 子评分)。

    逻辑:
      - lookback 窗口内关键内部人 S 笔数 × qty
      - 与历史均值比,>2x → 90,<0.5x → 20,线性插值
    """
    window = [
        e
        for e in events
        if e.direction == "S"
        and is_key_insider(e.insider_role)
        and (asof - e.txn_date).days <= lookback_days
    ]
    if not window:
        return 20.0
    sell_qty = sum(e.qty for e in window)
    # 简化:用笔数 + 总额做粗评分(M1 阶段不引入历史均值,留 M2 回测)
    if sell_qty >= 500_000:
        return 90.0
    if sell_qty >= 100_000:
        return 70.0
    if sell_qty >= 10_000:
        return 50.0
    return 30.0


def cover_up_alert(
    sells: list[Form4Event],
    buybacks: list[BuybackEvent],
    asof: date,
    pre_window_days: int = 20,
) -> list[tuple[Form4Event, BuybackEvent]]:
    """掩护配对(BD-052):返回所有 (S 事件, 8-K 回购公告) 配对。

    规则:S 事件 txn_date ∈ [8-K announce_date - pre_window_days, 8-K announce_date)。
    """
    pairs: list[tuple[Form4Event, BuybackEvent]] = []
    for bb in buybacks:
        for s in sells:
            if s.symbol != bb.symbol:
                continue
            if s.direction != "S" or not is_key_insider(s.insider_role):
                continue
            delta = (bb.announce_date - s.txn_date).days
            if 0 <= delta <= pre_window_days:
                pairs.append((s, bb))
    return pairs


def cover_up_score(pairs: list[tuple[Form4Event, BuybackEvent]]) -> float:
    """掩护配对 → 0–100 子评分(BD-052 子评分)。"""
    if not pairs:
        return 10.0
    if len(pairs) >= 3:
        return 95.0
    if len(pairs) >= 1:
        return 80.0
    return 10.0
