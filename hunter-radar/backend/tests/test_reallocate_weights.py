"""reallocate_weights 2.2 标准化 (CA-14) 测试。

覆盖:
- scores 分数阈值驱动 HIGH (主路径)
- signals 标签旧式路径 (兼容)
- 无 HIGH 时返回原权重
- 权重和恒 = 1.0
- config.signal_high_thresholds 自定义阈值
"""
import pytest

from app.services.threat_score import reallocate_weights

STOCK_WEIGHTS = {"options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15}
ETF_WEIGHTS = {"options": 0.35, "short": 0.45, "divergence": 0.20}


def _sum(w):
    return round(sum(w.values()), 6)


class TestReallocateThresholdScores:
    def test_no_high_returns_base(self):
        r = reallocate_weights(scores={"options": 50, "short": 50, "divergence": 50, "insider": 50})
        assert r == STOCK_WEIGHTS

    def test_options_high_boost(self):
        # options=80 >= 75 → HIGH, 权重提升至 0.40
        r = reallocate_weights(
            scores={"options": 80, "short": 50, "divergence": 50, "insider": 50}
        )
        assert r["options"] == pytest.approx(0.40)
        assert _sum(r) == 1.0
        # 其他模块压缩
        assert r["short"] < 0.35

    def test_short_high_threshold_70(self):
        # short=75 >= 70 → HIGH
        r = reallocate_weights(
            scores={"options": 50, "short": 75, "divergence": 50, "insider": 50}
        )
        assert r["short"] == pytest.approx(0.40)
        assert _sum(r) == 1.0

    def test_divergence_high_threshold_80(self):
        r = reallocate_weights(
            scores={"options": 50, "short": 50, "divergence": 90, "insider": 50}
        )
        assert r["divergence"] == pytest.approx(0.40)
        assert _sum(r) == 1.0

    def test_insider_high_threshold_65(self):
        r = reallocate_weights(
            scores={"options": 50, "short": 50, "divergence": 50, "insider": 70}
        )
        assert r["insider"] == pytest.approx(0.40)
        assert _sum(r) == 1.0

    def test_multiple_high_split_boost(self):
        # options + short 都 HIGH → 均分 0.40 = 0.20 各
        r = reallocate_weights(
            scores={"options": 80, "short": 75, "divergence": 50, "insider": 50}
        )
        assert r["options"] == pytest.approx(0.20)
        assert r["short"] == pytest.approx(0.20)
        assert _sum(r) == 1.0

    def test_none_score_not_high(self):
        # None 模块不参与 HIGH
        r = reallocate_weights(scores={"options": 80, "short": None, "divergence": None, "insider": None})
        assert r["options"] == pytest.approx(0.40)
        assert _sum(r) == 1.0

    def test_custom_thresholds(self):
        # 自定义阈值: insider=50 即 HIGH
        r = reallocate_weights(
            scores={"options": 50, "short": 50, "divergence": 50, "insider": 55},
            thresholds={"options": 75, "short": 70, "divergence": 80, "insider": 50},
        )
        assert r["insider"] == pytest.approx(0.40)
        assert _sum(r) == 1.0


class TestReallocateSignalsLegacy:
    def test_legacy_signals_path(self):
        r = reallocate_weights({"options": "HIGH", "short": "NORMAL", "divergence": "NORMAL", "insider": "NORMAL"})
        assert r["options"] == pytest.approx(0.40)
        assert _sum(r) == 1.0

    def test_legacy_no_high(self):
        r = reallocate_weights({"options": "NORMAL", "short": "NORMAL", "divergence": "NORMAL", "insider": "NORMAL"})
        assert r == STOCK_WEIGHTS

    def test_etf_base(self):
        # ETF 无 insider, 只有 3 模块
        r = reallocate_weights({"options": "HIGH", "short": "NORMAL", "divergence": "NORMAL"}, symbol_type="etf")
        assert r["options"] == pytest.approx(0.40)
        assert set(r.keys()) == {"options", "short", "divergence"}
        assert _sum(r) == 1.0
