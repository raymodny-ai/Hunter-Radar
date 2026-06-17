"""Tests for app/services/nl_summary(BD-065)。"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest


def _ctx(symbol_type: str = "stock", **overrides) -> "SummaryContext":
    from app.services.nl_summary import SummaryContext

    base = dict(
        trade_date=date(2024, 2, 1),
        symbol="AAPL",
        symbol_type=symbol_type,
        module_options=80.0,
        module_short=70.0,
        module_divergence=60.0,
        module_insider=50.0,
        total_ema=72.5,
        signal_lifecycle="red",
        regime="normal",
        consecutive_red_days=0,
        data_warmup=False,
    )
    base.update(overrides)
    return SummaryContext(**base)


# ---- 1) _bucket 纯函数 ----


class TestBucket:
    def test_high(self):
        from app.services.nl_summary import _bucket

        assert _bucket(80.0) == "high"

    def test_mid(self):
        from app.services.nl_summary import _bucket

        assert _bucket(60.0) == "mid"

    def test_low(self):
        from app.services.nl_summary import _bucket

        assert _bucket(30.0) == "low"

    def test_boundary(self):
        from app.services.nl_summary import _bucket

        assert _bucket(70.0) == "high"
        assert _bucket(50.0) == "mid"


# ---- 2) _lifecycle_text 纯函数 ----


class TestLifecycleText:
    def test_red(self):
        from app.services.nl_summary import _lifecycle_text

        t = _lifecycle_text("red")
        assert "红灯" in t

    def test_unknown(self):
        from app.services.nl_summary import _lifecycle_text

        assert _lifecycle_text("xx") == "当前信号状态未知"


# ---- 3) _regime_text 纯函数 ----


class TestRegimeText:
    def test_normal(self):
        from app.services.nl_summary import _regime_text

        t = _regime_text("normal", threshold_red=70)
        assert "正常" in t
        assert "70" in t

    def test_panic(self):
        from app.services.nl_summary import _regime_text

        t = _regime_text("panic", threshold_red=80)
        assert "高波动" in t
        assert "80" in t


# ---- 4) _warmup_text 纯函数 ----


class TestWarmupText:
    def test_warmup(self):
        from app.services.nl_summary import _warmup_text

        assert "暖启动" in _warmup_text(True)

    def test_full(self):
        from app.services.nl_summary import _warmup_text

        assert "充分" in _warmup_text(False)


# ---- 5) _sanitize 禁词扫描(CR-010 兜底)----


class TestSanitize:
    def test_normal_passes(self):
        from app.services.nl_summary import _sanitize

        assert "无投资建议" in _sanitize("本报告仅基于历史数据,无投资建议")

    def test_forbidden_word_raises(self):
        from app.services.nl_summary import _sanitize

        # settings.forbidden_recommendation_words 默认至少含"买入"
        with pytest.raises(ValueError, match="禁词"):
            _sanitize("强力买入推荐")


# ---- 6) render_summary 主入口 ----


class TestRenderSummary:
    def test_stock_basic(self):
        from app.services.nl_summary import render_summary

        text = render_summary(_ctx("stock"))
        assert "AAPL" in text
        assert "2024-02-01" in text
        assert "红灯" in text
        assert "末日 Put" in text  # options 模板
        assert "做空量" in text  # short 模板
        assert "内部人" in text  # insider 模板(stock 才有)
        assert text.endswith("。")

    def test_etf_excludes_insider(self):
        from app.services.nl_summary import render_summary

        text = render_summary(_ctx("etf"))
        # ETF 无 insider 段
        assert "关键内部人抛压" not in text
        # options/short/divergence 仍有
        assert "末日 Put" in text
        assert "做空量" in text

    def test_consecutive_red_appends_disclaimer(self):
        from app.services.nl_summary import render_summary

        text = render_summary(_ctx("stock", consecutive_red_days=3))
        assert "连续 3 个交易日" in text
        assert "无投资建议" in text

    def test_warmup_text_inserted(self):
        from app.services.nl_summary import render_summary

        text = render_summary(_ctx("stock", data_warmup=True))
        assert "暖启动" in text

    def test_panic_regime(self):
        from app.services.nl_summary import render_summary

        text = render_summary(_ctx("stock", regime="panic"), threshold_red=80)
        assert "高波动" in text
        assert "80" in text


# ---- 7) render_simple_etf_proxy ----


class TestRenderSimpleEtfProxy:
    def test_premium(self):
        from app.services.nl_summary import render_simple_etf_proxy

        text = render_simple_etf_proxy(
            date(2024, 2, 1), "SPY", "creation_likely", premium_pct=1.5, volume_ratio=1.8
        )
        assert "SPY" in text
        assert "溢价" in text
        assert "1.50%" in text
        assert "1.80" in text
        assert "无投资建议" in text

    def test_discount(self):
        from app.services.nl_summary import render_simple_etf_proxy

        text = render_simple_etf_proxy(
            date(2024, 2, 1), "QQQ", "redemption_likely", premium_pct=-0.8, volume_ratio=0.9
        )
        assert "折价" in text
        assert "赎回" in text
        assert "0.80%" in text
