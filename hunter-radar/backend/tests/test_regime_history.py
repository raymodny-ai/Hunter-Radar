"""BD-063 / BD-066 市场门控 + 90 日轨迹测试。"""

from __future__ import annotations

from datetime import date, timedelta

from app.services.regime_history import (
    MarketSnapshot,
    RegimeConfig,
    decide_regime,
    filter_history_window,
    moving_average_ema,
)


def _snap(vix: float | None, spx: float | None, ma20: float | None) -> MarketSnapshot:
    return MarketSnapshot(
        trade_date=date(2024, 2, 1),
        vix=vix,
        spx_close=spx,
        spx_ma20=ma20,
    )


class TestRegime:
    def test_normal_low_vix(self):
        regime, thr = decide_regime(_snap(vix=15.0, spx=5000, ma20=4800))
        assert regime == "normal"
        assert thr == 70

    def test_panic_high_vix(self):
        regime, thr = decide_regime(_snap(vix=35.0, spx=5000, ma20=4800))
        assert regime == "panic"
        assert thr == 80

    def test_panic_below_ma20(self):
        regime, thr = decide_regime(_snap(vix=20.0, spx=4800, ma20=5000))
        assert regime == "panic"
        assert thr == 80

    def test_normal_above_ma20(self):
        regime, thr = decide_regime(_snap(vix=20.0, spx=5100, ma20=5000))
        assert regime == "normal"
        assert thr == 70

    def test_panic_either_trigger(self):
        """VIX 高 OR 跌破 MA20,任一触发即 panic"""
        # 仅 VIX
        r1, _ = decide_regime(_snap(vix=35.0, spx=5100, ma20=5000))
        # 仅 SPX
        r2, _ = decide_regime(_snap(vix=15.0, spx=4800, ma20=5000))
        assert r1 == r2 == "panic"

    def test_none_data(self):
        """冷启动期,全 None → normal 默认"""
        regime, thr = decide_regime(_snap(vix=None, spx=None, ma20=None))
        assert regime == "normal"
        assert thr == 70

    def test_custom_config(self):
        cfg = RegimeConfig(vix_panic_threshold=25.0, threshold_red_panic=85)
        regime, thr = decide_regime(_snap(vix=27.0, spx=5000, ma20=4800), cfg)
        assert regime == "panic"
        assert thr == 85


class TestHistoryWindow:
    def test_basic(self):
        asof = date(2024, 2, 1)
        rows = [
            (asof - timedelta(days=i), 50.0 + i)
            for i in range(100)
        ]
        out = filter_history_window(rows, asof, window_days=90)
        assert len(out) == 90  # 1.6 倍自然日够覆盖 90 个交易日
        assert out[-1][0] == asof

    def test_empty(self):
        assert filter_history_window([], date(2024, 2, 1)) == []

    def test_filter_old(self):
        asof = date(2024, 2, 1)
        rows = [
            (date(2023, 1, 1), 50.0),  # 一年前
            (asof - timedelta(days=10), 60.0),  # 10 天前
            (asof, 70.0),
        ]
        out = filter_history_window(rows, asof, window_days=90)
        assert len(out) == 2
        assert out[0][0] == asof - timedelta(days=10)
        assert out[1][0] == asof

    def test_sorted(self):
        asof = date(2024, 2, 1)
        rows = [
            (asof - timedelta(days=5), 60.0),
            (asof, 70.0),
            (asof - timedelta(days=10), 50.0),
        ]
        out = filter_history_window(rows, asof, window_days=90)
        assert [d for d, _ in out] == sorted([d for d, _ in out])


class TestMovingAverageEma:
    def test_empty(self):
        assert moving_average_ema([]) == []

    def test_constant(self):
        hist = [(date(2024, 2, i), 50.0) for i in range(1, 6)]
        out = moving_average_ema(hist, halflife_days=2)
        # 全部常数 → EMA 仍是常数
        for _, v in out:
            assert abs(v - 50.0) < 1e-9

    def test_smooths_spike(self):
        """50, 50, 50, 50, 100 → 最后一个 EMA 应该 < 100"""
        hist = [(date(2024, 2, i), v) for i, v in enumerate([50.0, 50.0, 50.0, 50.0, 100.0])]
        out = moving_average_ema(hist, halflife_days=2)
        last = out[-1][1]
        assert 50.0 < last < 100.0  # 平滑过
