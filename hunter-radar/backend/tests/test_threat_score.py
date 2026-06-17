"""OQ-02 EMA + Threat Score 单元测试。

覆盖三种曲线:
1. 单日尖峰(单日冲高、次日回落)—— EMA 必须滤掉
2. 连续上升(连续 N 日单调上升)—— EMA 跟随,但滞后
3. 连续下降(连续 N 日单调下降)—— EMA 跟随,但滞后
4. 连续满足窗口(OQ-02「持续 2 个交易日」严格定义)
"""

from __future__ import annotations

import pytest

from app.services.threat_score import (
    compute_threat_score,
    consecutive_business_days_above,
    decide_lifecycle,
    ema_smooth,
    percentile_to_score,
    z_score_to_score,
)


# ---- EMA 基础 ----
class TestEMASmooth:
    def test_empty(self):
        assert ema_smooth([]) == []

    def test_single_value(self):
        assert ema_smooth([42.0]) == [42.0]

    def test_single_spike_filtered(self):
        """单日尖峰:历史稳态 50 → 当日 100 → 次日 50。
        EMA 应该回落且显著低于 100,证明不被尖峰带飞。"""
        history = [50.0, 50.0, 50.0, 100.0, 50.0]
        ema = ema_smooth(history, halflife_days=2)
        # 前 3 日应保持 50
        assert ema[0] == pytest.approx(50.0)
        assert ema[1] == pytest.approx(50.0)
        assert ema[2] == pytest.approx(50.0)
        # 第 4 日冲高,EMA 跟随但远低于 100
        assert 60.0 < ema[3] < 80.0  # alpha ≈ 0.414,期望 ≈ 50 + 0.414*50 = 70.7
        # 第 5 日回落,EMA 再次回归
        assert ema[4] < ema[3]  # 必然回落
        assert 50.0 <= ema[4] < ema[3]

    def test_consecutive_rising(self):
        """连续 5 日单调上升 50→90,EMA 应跟随且滞后但最终逼近。"""
        history = [50.0, 60.0, 70.0, 80.0, 90.0]
        ema = ema_smooth(history, halflife_days=2)
        assert ema[0] == pytest.approx(50.0)
        # 每一日 EMA < 当日(EMA 滞后)
        for i in range(1, len(history)):
            assert ema[i] < history[i]
        # 末日逼近但略低
        assert 80.0 < ema[-1] < 90.0

    def test_consecutive_falling(self):
        """连续 5 日单调下降 90→50,EMA 应跟随且滞后但最终逼近。"""
        history = [90.0, 80.0, 70.0, 60.0, 50.0]
        ema = ema_smooth(history, halflife_days=2)
        assert ema[0] == pytest.approx(90.0)
        for i in range(1, len(history)):
            assert ema[i] > history[i]
        # 末日逼近但略高
        assert 50.0 < ema[-1] < 60.0

    def test_halflife_one_is_equivalent_to_raw(self):
        """半衰期 = 1 交易日时,alpha → 0.5,EMA = 上一个 EMA 与当日值的折半平均(非等于 raw)。
        实际验证:每个值都被「半权重吸收」,不是直接穿透。"""
        history = [50.0, 100.0]
        ema = ema_smooth(history, halflife_days=1)
        # alpha = 1 - 2^(-1/1) = 0.5
        assert ema[1] == pytest.approx(75.0)


# ---- OQ-02 严格定义 ----
class TestConsecutiveBusinessDays:
    def test_no_history(self):
        assert consecutive_business_days_above([], 70) == 0

    def test_strictly_two(self):
        """严格定义:连续 2 个交易日都 ≥ 70 → 返回 2。"""
        history = [50.0, 71.0, 72.0]
        assert consecutive_business_days_above(history, 70) == 2

    def test_gap_breaks(self):
        """中间断一日 → 重置为 1。"""
        history = [50.0, 80.0, 60.0, 75.0]
        assert consecutive_business_days_above(history, 70) == 1

    def test_all_above(self):
        history = [80.0, 85.0, 90.0, 75.0]
        assert consecutive_business_days_above(history, 70) == 4

    def test_none_above(self):
        history = [30.0, 40.0, 50.0]
        assert consecutive_business_days_above(history, 70) == 0


# ---- Z-Score 映射 ----
class TestZScoreToScore:
    def test_extreme_low(self):
        assert z_score_to_score(-10.0) == pytest.approx(0.0, abs=0.5)

    def test_zero_neutral(self):
        assert z_score_to_score(0.0) == pytest.approx(50.0)

    def test_extreme_high(self):
        assert z_score_to_score(10.0) == pytest.approx(100.0, abs=0.5)

    def test_none_neutral(self):
        assert z_score_to_score(None) == 50.0

    def test_capped(self):
        """|z| >= cap 截断。"""
        assert z_score_to_score(2.5) == pytest.approx(z_score_to_score(2.999))
        assert z_score_to_score(2.5) == pytest.approx(z_score_to_score(10.0))


# ---- 分位映射 ----
class TestPercentileToScore:
    def test_zero(self):
        assert percentile_to_score(0.0) == 0.0

    def test_one(self):
        assert percentile_to_score(1.0) == 100.0

    def test_half(self):
        assert percentile_to_score(0.5) == 50.0

    def test_none(self):
        assert percentile_to_score(None) == 50.0


# ---- Threat Score 完整计算 ----
class TestComputeThreatScore:
    WEIGHTS = {"options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15}

    def test_basic(self):
        r = compute_threat_score(
            module_options=80,
            module_short=70,
            module_divergence=60,
            module_insider=50,
            weights=self.WEIGHTS,
        )
        expected = 0.30 * 80 + 0.35 * 70 + 0.20 * 60 + 0.15 * 50
        assert r["raw"] == pytest.approx(expected, abs=0.01)
        # 无 history → ema == raw
        assert r["ema"] == pytest.approx(expected, abs=0.01)

    def test_ema_dampens_spike(self):
        """单日尖峰 50→100,EMA 滤掉毛刺。"""
        history = [
            {"module_options": 50, "module_short": 50, "module_divergence": 50, "module_insider": 50},
            {"module_options": 50, "module_short": 50, "module_divergence": 50, "module_insider": 50},
        ]
        r = compute_threat_score(
            module_options=100,  # 末日尖峰
            module_short=100,
            module_divergence=50,
            module_insider=50,
            weights=self.WEIGHTS,
            history=history,
        )
        assert r["raw"] >= 90  # 原始分确实高
        assert r["ema"] < 75  # EMA 显著滤掉,远低于 raw

    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError):
            compute_threat_score(
                module_options=50, module_short=50, module_divergence=50, module_insider=50,
                weights={"options": 0.5, "short": 0.5, "divergence": 0, "insider": 0},
            )


# ---- 信号灯 ----
class TestDecideLifecycle:
    def test_red(self):
        assert decide_lifecycle(75.0, red_threshold=70) == "red"

    def test_yellow(self):
        assert decide_lifecycle(60.0, red_threshold=70) == "yellow"

    def test_gray(self):
        assert decide_lifecycle(40.0, red_threshold=70) == "gray"

    def test_green(self):
        assert decide_lifecycle(20.0, red_threshold=70) == "green"

    def test_boundary_red(self):
        assert decide_lifecycle(70.0, red_threshold=70) == "red"

    def test_panic_threshold(self):
        """panic 模式下阈值上调到 80,75 不再算 red。"""
        assert decide_lifecycle(75.0, red_threshold=80) == "yellow"
        assert decide_lifecycle(85.0, red_threshold=80) == "red"
