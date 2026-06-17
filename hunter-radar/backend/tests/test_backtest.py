"""Tests for app/services/backtest(BD-089)。"""
from __future__ import annotations

from datetime import date

import pytest


# ---- 1) _in_event_window 纯函数 ----


class TestInEventWindow:
    def test_in_window(self):
        from app.services.backtest import _in_event_window

        windows = [(date(2024, 1, 1), date(2024, 1, 10), "high")]
        assert _in_event_window(date(2024, 1, 5), windows) is True

    def test_outside_window(self):
        from app.services.backtest import _in_event_window

        windows = [(date(2024, 1, 1), date(2024, 1, 10), "high")]
        assert _in_event_window(date(2024, 1, 15), windows) is False

    def test_boundary_inclusive(self):
        from app.services.backtest import _in_event_window

        windows = [(date(2024, 1, 1), date(2024, 1, 10), "high")]
        assert _in_event_window(date(2024, 1, 1), windows) is True
        assert _in_event_window(date(2024, 1, 10), windows) is True

    def test_multiple_windows(self):
        from app.services.backtest import _in_event_window

        windows = [
            (date(2024, 1, 1), date(2024, 1, 10), "high"),
            (date(2024, 2, 1), date(2024, 2, 10), "mid"),
        ]
        assert _in_event_window(date(2024, 2, 5), windows) is True
        assert _in_event_window(date(2024, 1, 20), windows) is False


# ---- 2) _options_score_from_payload 纯函数 ----


class TestOptionsScoreFromPayload:
    def test_constant(self):
        from app.services.backtest import _options_score_from_payload

        # 回测场景无 options_chain → 固定 30
        assert _options_score_from_payload({}) == 30.0
        assert _options_score_from_payload({"options": "anything"}) == 30.0


# ---- 3) _short_score_from_payload 纯函数 ----


class TestShortScoreFromPayload:
    def test_no_volume(self):
        from app.services.backtest import _short_score_from_payload

        # 全部缺 short_volume / total volume → None
        history = [{"payload": {"short_volume": {}, "daily_price": {"volume": 0}}}]
        assert _short_score_from_payload(history, target_idx=0) is None

    def test_two_days_ratio(self):
        from app.services.backtest import _short_score_from_payload

        history = [
            {"payload": {"short_volume": {"short_volume": 1000}, "daily_price": {"volume": 10000}}},
            {"payload": {"short_volume": {"short_volume": 2000}, "daily_price": {"volume": 10000}}},
        ]
        z = _short_score_from_payload(history, target_idx=1)
        # 第二日 ratio 0.20 vs 0.10 → z > 0 → 分数 > 50
        assert z is not None
        assert 50.0 <= z <= 100.0


# ---- 4) _insider_score_from_payload 纯函数 ----


class TestInsiderScoreFromPayload:
    def test_no_events(self):
        from app.services.backtest import _insider_score_from_payload

        s = _insider_score_from_payload({}, date(2024, 2, 1))
        assert s == 0.0

    def test_sell_event_within_window(self):
        from app.services.backtest import _insider_score_from_payload

        payload = {
            "form4_events": [
                {
                    "txn_date": date(2024, 1, 25),
                    "insider_name": "Tim Cook",
                    "insider_role": "CEO",
                    "direction": "sell",
                    "qty": 50000,
                    "price": 180.0,
                }
            ]
        }
        s = _insider_score_from_payload(payload, date(2024, 2, 1))
        # 应得到非零分
        assert s > 0

    def test_sell_outside_20d_window_ignored(self):
        from app.services.backtest import _insider_score_from_payload

        payload = {
            "form4_events": [
                {
                    "txn_date": date(2023, 1, 1),  # 1 年前
                    "insider_name": "Old",
                    "insider_role": "CEO",
                    "direction": "sell",
                    "qty": 50000,
                    "price": 180.0,
                }
            ]
        }
        s = _insider_score_from_payload(payload, date(2024, 2, 1))
        assert s == 0.0


# ---- 5) BacktestConfig.resolve_weights 纯函数 ----


class TestBacktestConfigResolveWeights:
    def test_default_is_stock(self):
        from app.services.backtest import BacktestConfig

        cfg = BacktestConfig(
            tickers=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
            weights_name="default",
        )
        w = cfg.resolve_weights("stock")
        assert "options" in w
        assert "short" in w
        # 必须从 settings 拿 stock 的 → 验证非空 + 总和=1
        assert abs(sum(w.values()) - 1.0) < 0.01

    def test_etf_explicit(self):
        from app.services.backtest import BacktestConfig

        cfg = BacktestConfig(
            tickers=["SPY"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
            weights_name="etf",
        )
        w = cfg.resolve_weights("etf")
        # ETF 权重通常不含 insider
        assert "insider" not in w or w.get("insider", 0) == 0

    def test_custom_overrides(self):
        from app.services.backtest import BacktestConfig

        custom = {"options": 0.5, "short": 0.2, "divergence": 0.2, "insider": 0.1}
        cfg = BacktestConfig(
            tickers=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
            weights_name="custom",
            custom_weights=custom,
        )
        w = cfg.resolve_weights("stock")
        assert w["options"] == 0.5


# ---- 6) BacktestMetrics dataclass 基础 ----


class TestBacktestMetrics:
    def test_zero_state(self):
        from app.services.backtest import BacktestMetrics

        m = BacktestMetrics()
        assert m.n_event_days == 0
        assert m.hit_rate == 0.0
        assert m.false_alarm_rate == 0.0
        assert m.score_lift == 0.0
