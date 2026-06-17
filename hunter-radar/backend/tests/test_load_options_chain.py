"""BD-009 / BD-020 期权链落库 + 末日 Put 异常合约计算测试。

聚焦:
- _build_options_payload(纯函数)
- _anomaly_payload(纯函数,无 DB)
- _classify_signal(纯函数,在 load_etf_proxy)
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.options_anomaly import (
    AnomalyThresholds,
    OptionCandidate,
    filter_top_anomaly_puts,
    notional,
)
from etl.load_etf_proxy import _classify_signal
from etl.load_options_chain import _anomaly_payload, _build_options_payload
from etl.yfinance_pull import OptionContract


def _opt(sym: str, expiry: date, right: str = "P", strike: float = 100.0, vol: int = 100, oi: int = 50, lp: float = 1.5) -> OptionContract:
    return OptionContract(
        contract=f"O:{sym}{expiry.strftime('%y%m%d')}{'C' if right=='C' else 'P'}{int(strike*1000):08d}",
        underlying=sym,
        expiry=expiry,
        strike=strike,
        right=right,
        last_price=lp,
        bid=lp - 0.05,
        ask=lp + 0.05,
        volume=vol,
        open_interest=oi,
        implied_vol=0.30,
        in_the_money=False,
    )


class TestBuildOptionsPayload:
    def test_basic(self):
        opt = _opt("AAPL", date(2024, 6, 21), right="P", strike=180.0, vol=200, oi=100, lp=2.5)
        payload = _build_options_payload([opt], spot_by_symbol={"AAPL": 200.0}, trade_date=date(2024, 6, 18))
        assert len(payload) == 1
        p = payload[0]
        assert p["symbol"] == "AAPL"
        assert p["right"] == "P"
        assert p["strike"] == 180.0
        assert p["volume"] == 200
        assert p["open_interest"] == 100
        assert p["trade_date"] == date(2024, 6, 18)

    def test_empty(self):
        payload = _build_options_payload([], {}, trade_date=date(2024, 6, 18))
        assert payload == []


class TestAnomalyPayload:
    def test_basic(self):
        c = OptionCandidate(
            contract="O:AAPL240621P00180000",
            underlying="AAPL",
            underlying_type="stock",
            trade_date=date(2024, 6, 18),
            expiry=date(2024, 6, 21),
            dte=3,
            right="P",
            strike=180.0,
            last_price=2.5,
            spot=200.0,
            volume=600,  # 12x OI
            open_interest=50,
            open_interest_prev=20,  # +150% > 50%
        )
        oi_5d = {c.contract: [10, 12, 15, 20, 50]}
        payload = _anomaly_payload(date(2024, 6, 18), [c], oi_5d)
        assert len(payload) == 1
        p = payload[0]
        assert p["symbol"] == "AAPL"
        assert p["dte"] == 3
        assert p["oi_increase_pct"] == pytest.approx(1.5, abs=1e-9)
        assert p["volume_oi_ratio"] == pytest.approx(12.0, abs=1e-9)
        assert p["notional"] == pytest.approx(150_000.0, abs=1.0)  # 600 * 2.5 * 100
        assert p["is_top10_notional"] is True
        assert p["oi_5d_series"] == [10, 12, 15, 20, 50]
        assert p["has_known_catalyst"] is False
        assert p["catalyst_note"] is None

    def test_zero_oi_prev_handled(self):
        c = OptionCandidate(
            contract="X",
            underlying="AAPL",
            underlying_type="stock",
            trade_date=date(2024, 6, 18),
            expiry=date(2024, 6, 21),
            dte=3,
            right="P",
            strike=180.0,
            last_price=2.5,
            spot=200.0,
            volume=600,
            open_interest=50,
            open_interest_prev=0,
        )
        p = _anomaly_payload(date(2024, 6, 18), [c], {})[0]
        assert p["oi_increase_pct"] == 0.0  # 不能除以 0,fallback


class TestIntegrationFilterTopAnomaly:
    """确保落库层调用的 services.filter_top_anomaly_puts 仍然按 OQ-01 阈值生效。"""

    def test_filter_works_with_custom_thr(self):
        thr = AnomalyThresholds(otm_min_stock=0.05)  # 放宽
        c = OptionCandidate(
            contract="X",
            underlying="AAPL",
            underlying_type="stock",
            trade_date=date(2024, 6, 18),
            expiry=date(2024, 6, 21),
            dte=2,
            right="P",
            strike=185.0,  # OTM ~7.5%
            last_price=2.0,
            spot=200.0,
            volume=600,
            open_interest=50,
            open_interest_prev=20,
        )
        hits = filter_top_anomaly_puts([c], thr=thr)
        assert len(hits) == 1
        assert hits[0].contract == "X"


class TestClassifySignal:
    def test_creation_likely(self):
        from etl.load_etf_proxy import _classify_signal
        from app.services.short_metrics import ETFProxyTick

        # 收盘价 > IOPV 1% → 溢价 → creation_likely
        t = ETFProxyTick(
            trade_date=date(2024, 2, 1),
            symbol="SPY",
            nav=100.0,
            iopv=100.0,
            close=101.5,  # +1.5%
            volume=100,
            volume_20d_avg=100,
        )
        assert _classify_signal(t) == "creation_likely"

    def test_redemption_likely(self):
        from app.services.short_metrics import ETFProxyTick

        t = ETFProxyTick(
            trade_date=date(2024, 2, 1),
            symbol="SPY",
            nav=100.0,
            iopv=100.0,
            close=98.0,  # -2%
            volume=100,
            volume_20d_avg=100,
        )
        assert _classify_signal(t) == "redemption_likely"

    def test_normal(self):
        from app.services.short_metrics import ETFProxyTick

        t = ETFProxyTick(
            trade_date=date(2024, 2, 1),
            symbol="SPY",
            nav=100.0,
            iopv=100.0,
            close=100.2,  # +0.2% < 0.5%
            volume=100,
            volume_20d_avg=100,
        )
        assert _classify_signal(t) == "normal"
