"""BD-050 / BD-051 / BD-052 SEC 内部行为服务测试。"""

from __future__ import annotations

from datetime import date, timedelta

from app.services.insider import (
    BuybackEvent,
    Form4Event,
    classify_buy_window,
    cover_up_alert,
    cover_up_score,
    insider_sell_pressure_score,
    is_key_insider,
)


def _mk_sell(
    symbol: str = "AAPL",
    role: str = "CEO",
    txn: date = date(2024, 2, 1),
    qty: int = 10_000,
) -> Form4Event:
    return Form4Event(
        symbol=symbol,
        insider_name="John Doe",
        insider_role=role,
        txn_date=txn,
        filed_at=txn + timedelta(days=2),
        direction="S",
        qty=qty,
        price=180.0,
        form_url="https://www.sec.gov/...",
    )


def _mk_buyback(announce: date, amount: float = 1e9) -> BuybackEvent:
    return BuybackEvent(
        symbol="AAPL",
        announce_date=announce,
        amount_usd=amount,
        duration_days=180,
        form_url="https://www.sec.gov/...",
    )


class TestKeyInsider:
    def test_yes(self):
        assert is_key_insider("CEO") is True
        assert is_key_insider("CFO") is True
        assert is_key_insider("Director") is True
        assert is_key_insider("10% Holder") is True

    def test_no(self):
        assert is_key_insider("Other") is False
        assert is_key_insider("VP") is False


class TestBuyWindow:
    def test_sell_in_window(self):
        e = _mk_sell()
        assert classify_buy_window(e) is True

    def test_buy_not_in_window(self):
        e = _mk_sell()
        e.direction = "P"
        assert classify_buy_window(e) is False


class TestSellScore:
    def test_no_sells(self):
        score = insider_sell_pressure_score([], date(2024, 2, 15))
        assert score == 20.0

    def test_key_sell_high(self):
        sells = [_mk_sell(qty=1_000_000)]
        score = insider_sell_pressure_score(sells, date(2024, 2, 15))
        assert score == 90.0

    def test_key_sell_mid(self):
        sells = [_mk_sell(qty=200_000)]
        score = insider_sell_pressure_score(sells, date(2024, 2, 15))
        assert score == 70.0

    def test_key_sell_low(self):
        sells = [_mk_sell(qty=20_000)]
        score = insider_sell_pressure_score(sells, date(2024, 2, 15))
        assert score == 50.0

    def test_non_key_ignored(self):
        sells = [_mk_sell(role="VP", qty=1_000_000)]
        score = insider_sell_pressure_score(sells, date(2024, 2, 15))
        assert score == 20.0  # 不在 is_key_insider 列表

    def test_old_sell_ignored(self):
        sells = [_mk_sell(txn=date(2023, 1, 1))]
        score = insider_sell_pressure_score(sells, date(2024, 2, 15))
        assert score == 20.0  # 超过 20 日


class TestCoverUp:
    def test_pair_match(self):
        """CEO 在 2/1 卖 → 2/15 公司宣布回购 → 掩护配对"""
        sells = [_mk_sell(txn=date(2024, 2, 1))]
        bbs = [_mk_buyback(announce=date(2024, 2, 15))]
        pairs = cover_up_alert(sells, bbs, date(2024, 3, 1))
        assert len(pairs) == 1
        assert pairs[0][0].insider_name == "John Doe"
        assert pairs[0][1].amount_usd == 1e9

    def test_no_pair_sell_too_early(self):
        """CEO 在 1/1 卖 → 2/15 公告 → 间隔 45 天超过 20 日窗口 → 不配对"""
        sells = [_mk_sell(txn=date(2024, 1, 1))]
        bbs = [_mk_buyback(announce=date(2024, 2, 15))]
        pairs = cover_up_alert(sells, bbs, date(2024, 3, 1))
        assert len(pairs) == 0

    def test_no_pair_sell_after_buyback(self):
        """卖在公告之后 → 不构成掩护"""
        sells = [_mk_sell(txn=date(2024, 2, 20))]
        bbs = [_mk_buyback(announce=date(2024, 2, 15))]
        pairs = cover_up_alert(sells, bbs, date(2024, 3, 1))
        assert len(pairs) == 0

    def test_no_pair_different_symbol(self):
        sells = [_mk_sell(symbol="TSLA", txn=date(2024, 2, 1))]
        bbs = [_mk_buyback(announce=date(2024, 2, 15))]  # AAPL
        pairs = cover_up_alert(sells, bbs, date(2024, 3, 1))
        assert len(pairs) == 0

    def test_no_pair_buy_direction(self):
        """Form 4 'P' 不计入"""
        e = _mk_sell(txn=date(2024, 2, 1))
        e.direction = "P"
        sells = [e]
        bbs = [_mk_buyback(announce=date(2024, 2, 15))]
        pairs = cover_up_alert(sells, bbs, date(2024, 3, 1))
        assert len(pairs) == 0


class TestCoverUpScore:
    def test_no_pair(self):
        assert cover_up_score([]) == 10.0

    def test_one_pair(self):
        e = _mk_sell()
        b = _mk_buyback(announce=date(2024, 2, 15))
        assert cover_up_score([(e, b)]) == 80.0

    def test_multi_pair(self):
        e1 = _mk_sell()
        e2 = _mk_sell()
        b = _mk_buyback(announce=date(2024, 2, 15))
        assert cover_up_score([(e1, b), (e2, b)]) == 95.0
