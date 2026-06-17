"""BD-030 / BD-031 / BD-032 做空指标服务测试。"""

from __future__ import annotations

import math
from datetime import date

import pytest

from app.services.short_metrics import (
    DailyShortRecord,
    ETFProxyTick,
    ats_penetration,
    ats_penetration_to_score,
    etf_proxy_anomaly_score,
    premium_to_iopv,
    relative_volume,
    short_ratio,
    z_score_rolling,
    z_to_anomaly_score,
)


def _mk(short: int, total: int, ats: int = 0) -> DailyShortRecord:
    return DailyShortRecord(
        trade_date=date(2024, 2, 1),
        symbol="AAPL",
        short_volume=short,
        total_volume=total,
        ats_short_volume=ats,
    )


class TestRatio:
    def test_basic(self):
        assert short_ratio(_mk(30, 100)) == 0.30

    def test_zero_total(self):
        assert short_ratio(_mk(0, 0)) == 0.0


class TestATS:
    def test_basic(self):
        assert ats_penetration(_mk(short=100, total=100, ats=40)) == 0.40

    def test_zero_short(self):
        assert ats_penetration(_mk(0, 100, 0)) == 0.0

    def test_caps_at_100pct(self):
        """ATS 超过 short 是异常(数据 bug),封顶 1.0"""
        assert ats_penetration(_mk(short=100, total=100, ats=200)) == 1.0


class TestATSScore:
    def test_zero(self):
        assert ats_penetration_to_score(0) == 30.0

    def test_low(self):
        assert 30.0 < ats_penetration_to_score(0.10) < 40.0

    def test_mid(self):
        assert 60.0 < ats_penetration_to_score(0.45) < 80.0

    def test_high(self):
        assert ats_penetration_to_score(0.60) == 100.0
        assert ats_penetration_to_score(0.80) == 100.0


class TestZScore:
    def test_short_history_all_none(self):
        """不足 lookback → 全部 None"""
        hist = [0.30, 0.31, 0.29]
        out = z_score_rolling(hist, lookback=60)
        assert out == [None, None, None]

    def test_outlier_z(self):
        """前 60 天稳定 ~0.30,第 61 天飙到 0.90 → z ≈ +18"""
        hist = [0.30] * 60 + [0.90]
        out = z_score_rolling(hist, lookback=60)
        assert out[59] is None  # 60 天不足,无 z
        z61 = out[60]
        assert z61 is not None
        assert z61 > 10.0  # 显著异常

    def test_normal_z(self):
        """前 60 天均 0.30 ± 微小波动,第 61 天 0.31 → z 接近 0"""
        hist = [0.30 + 0.001 * (i % 3) for i in range(60)] + [0.31]
        out = z_score_rolling(hist, lookback=60)
        z = out[60]
        assert z is not None
        assert abs(z) < 1.0

    def test_invalid_lookback(self):
        with pytest.raises(ValueError):
            z_score_rolling([0.1, 0.2], lookback=1)


class TestZToScore:
    def test_zero_z(self):
        assert z_to_anomaly_score(0.0) == 50.0

    def test_positive_z(self):
        assert z_to_anomaly_score(2.0) == pytest.approx(83.33, abs=0.01)
        assert z_to_anomaly_score(3.0) == 100.0
        assert z_to_anomaly_score(5.0) == 100.0  # 截断

    def test_negative_z(self):
        assert z_to_anomaly_score(-2.0) == pytest.approx(16.67, abs=0.01)

    def test_none_cold_start(self):
        assert z_to_anomaly_score(None) == 50.0


# ---- BD-032 ETF 代理指标 ----


def _mk_etf(premium: float = 0.005, vol: int = 100_000, avg: int = 80_000) -> ETFProxyTick:
    iopv = 100.0
    close = iopv * (1 + premium)
    return ETFProxyTick(
        trade_date=date(2024, 2, 1),
        symbol="SPY",
        nav=100.0,
        iopv=iopv,
        close=close,
        volume=vol,
        volume_20d_avg=avg,
    )


class TestETFPremium:
    def test_positive_premium(self):
        t = _mk_etf(premium=0.01)
        assert abs(premium_to_iopv(t) - 0.01) < 1e-9

    def test_zero_iopv(self):
        t = _mk_etf()
        t.iopv = 0
        assert premium_to_iopv(t) == 0.0


class TestRelativeVol:
    def test_double(self):
        t = _mk_etf(vol=160_000, avg=80_000)
        assert relative_volume(t) == 2.0

    def test_zero_avg(self):
        t = _mk_etf(avg=0)
        assert relative_volume(t) == 1.0


class TestETFScore:
    def test_high_premium_high_vol(self):
        t = _mk_etf(premium=0.012, vol=150_000, avg=80_000)  # 1.2% + 1.875x
        assert etf_proxy_anomaly_score(t) == 80.0

    def test_moderate(self):
        t = _mk_etf(premium=0.006, vol=100_000, avg=80_000)  # 0.6% + 1.25x
        assert etf_proxy_anomaly_score(t) == 60.0

    def test_normal(self):
        t = _mk_etf(premium=0.001, vol=80_000, avg=80_000)  # 0.1% + 1.0x
        assert etf_proxy_anomaly_score(t) == 30.0
