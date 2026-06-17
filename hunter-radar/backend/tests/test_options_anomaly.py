"""BD-020 / BD-021 / BD-022 期权异常服务测试。"""

from __future__ import annotations

from datetime import date, timedelta

from app.services.options_anomaly import (
    AnomalyThresholds,
    OptionCandidate,
    filter_top_anomaly_puts,
    is_anomaly_otm_put,
    is_otm,
    notional,
    summarize_anomaly_count,
)


def _mk(
    symbol: str = "AAPL",
    underlying_type: str = "stock",
    strike: float = 180.0,
    spot: float = 200.0,
    dte: int = 2,
    right: str = "P",
    volume: int = 50_000,
    oi: int = 8_000,
    oi_prev: int = 4_000,
) -> OptionCandidate:
    return OptionCandidate(
        contract=f"{symbol}240216P{strike:.0f}",
        underlying=symbol,
        underlying_type=underlying_type,
        trade_date=date(2024, 2, 13),
        expiry=date(2024, 2, 13) + timedelta(days=dte + 1),
        dte=dte,
        right=right,
        strike=strike,
        last_price=1.5,
        spot=spot,
        volume=volume,
        open_interest=oi,
        open_interest_prev=oi_prev,
    )


class TestOTM:
    def test_stock_otm_threshold(self):
        """个股 10% OTM 阈值。"""
        c = _mk(strike=170, spot=200)  # |strike-spot|/spot = 15% > 10%
        assert is_otm(c) is True

    def test_stock_close_to_atm(self):
        c = _mk(strike=195, spot=200)  # 2.5% < 10%
        assert is_otm(c) is False

    def test_etf_relaxed_threshold(self):
        c = _mk(symbol="SPY", underlying_type="etf", strike=195, spot=200)  # 2.5% < 5%
        assert is_otm(c) is False
        c2 = _mk(symbol="SPY", underlying_type="etf", strike=190, spot=200)  # 5%
        assert is_otm(c2) is True


class TestAnomaly:
    def test_full_match(self):
        """全部条件满足 → True"""
        c = _mk(dte=2, strike=170, spot=200, volume=50_000, oi=8_000, oi_prev=4_000)
        assert is_anomaly_otm_put(c) is True

    def test_reject_dte_too_long(self):
        c = _mk(dte=5)
        assert is_anomaly_otm_put(c) is False

    def test_reject_call(self):
        c = _mk(right="C")
        assert is_anomaly_otm_put(c) is False

    def test_reject_low_volume(self):
        c = _mk(volume=1_000, oi=8_000)  # Vol/OI = 0.125 < 5
        assert is_anomaly_otm_put(c) is False

    def test_reject_oi_not_growing(self):
        c = _mk(oi=8_000, oi_prev=8_000)  # 增长 0%
        assert is_anomaly_otm_put(c) is False

    def test_reject_too_close_to_atm(self):
        c = _mk(strike=195, spot=200)  # 2.5% OTM
        assert is_anomaly_otm_put(c) is False

    def test_etf_relaxed_otm(self):
        c = _mk(symbol="SPY", underlying_type="etf", strike=190, spot=200)  # 5% OTM OK
        assert is_anomaly_otm_put(c) is True

    def test_zero_oi_prev(self):
        c = _mk(oi=8_000, oi_prev=0)
        assert is_anomaly_otm_put(c) is False  # 无法计算增幅


class TestTopN:
    def test_top_n_sort(self):
        candidates = [
            _mk(contract="A1", volume=100_000),  # 名义 = 100k * 1.5 * 100 = 15M
            _mk(contract="A2", volume=50_000),   # 7.5M
            _mk(contract="A3", volume=20_000),   # 3M
        ]
        thr = AnomalyThresholds(top_n_notional=2)
        top = filter_top_anomaly_puts(candidates, thr)
        assert len(top) == 2
        assert top[0].contract == "A1"
        assert top[1].contract == "A2"

    def test_filter_non_matching(self):
        candidates = [
            _mk(contract="GOOD", volume=50_000, oi=8_000, oi_prev=4_000),
            _mk(contract="BAD", dte=10, volume=50_000, oi=8_000, oi_prev=4_000),
        ]
        top = filter_top_anomaly_puts(candidates)
        assert len(top) == 1
        assert top[0].contract == "GOOD"


class TestNotional:
    def test_calc(self):
        c = _mk(volume=10_000, last_price=2.0)
        c.last_price = 2.0
        assert notional(c) == 2_000_000.0


class TestCount:
    def test_count(self):
        c1 = _mk(contract="A1")
        c2 = _mk(contract="A2", dte=10)  # 不满足
        assert summarize_anomaly_count([c1, c2]) == 1
