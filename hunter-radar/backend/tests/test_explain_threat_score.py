"""2.6 评分解释性 API — _explain_for_score 逻辑测试。

覆盖:
- 主驱动模块判定 (贡献 = 权重×分 最大者)
- 置信度: 4 模块=high / <4=medium / <MIN_ACTIVE=insufficient_data
- 尖峰覆盖 spike_override (total_raw >= panic)
- regime_note (panic 模式)
- 全量字段透传 (含 weights/module_*)
"""
import pytest

from app.api.symbols import (
    ExplainThreatScoreDTO,
    ThreatScoreDTO,
    _explain_for_score,
)


def _dto(**over) -> ThreatScoreDTO:
    base = dict(
        trade_date="2026-07-31",
        symbol="NVDA",
        symbol_type="stock",
        total=60.0,
        total_raw=55.0,
        ema_halflife=2,
        module_options=50.0,
        module_short=70.0,
        module_divergence=40.0,
        module_insider=30.0,
        weights={"options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15},
        signal_lifecycle="yellow",
        regime="normal",
        nl_summary=None,
        data_warmup=False,
        data_quality="complete",
    )
    base.update(over)
    return ThreatScoreDTO(**base)


class _Settings:
    threat_red_threshold_panic = 80.0


def test_primary_driver_short():
    # short=70×0.35=24.5 最大 → 主驱动 = short
    exp = _explain_for_score(_dto(), _Settings())
    assert exp.primary_driver == "short"


def test_primary_driver_high_weighted():
    # options=100×0.30=30 > short=70×0.35=24.5 → options
    exp = _explain_for_score(_dto(module_options=100.0), _Settings())
    assert exp.primary_driver == "options"


def test_confidence_high_when_four_modules():
    exp = _explain_for_score(_dto(), _Settings())
    assert exp.confidence == "high"
    assert exp.active_modules == 4


def test_confidence_medium_when_insider_zero():
    # insider=0 (ETF 风格) → 有效模块少, 但 0 仍算"有值"(分=0) → 看 active 判定
    # 这里 insider=0 → contrib=0, 但 active 含 insider(非 None) → 仍 4 模块
    exp = _explain_for_score(_dto(module_insider=0.0), _Settings())
    assert exp.confidence == "high"  # 0 是合法分, 非缺失


def test_spike_override():
    exp = _explain_for_score(_dto(total_raw=85.0), _Settings())
    assert exp.spike_override is True


def test_no_spike_override():
    exp = _explain_for_score(_dto(total_raw=55.0), _Settings())
    assert exp.spike_override is False


def test_regime_note_panic():
    exp = _explain_for_score(_dto(regime="panic"), _Settings())
    assert exp.regime_note is not None
    assert "恐慌模式" in exp.regime_note


def test_ema_note_format():
    exp = _explain_for_score(_dto(total_raw=55.0, total=60.0, ema_halflife=2), _Settings())
    assert "原始分 55" in exp.ema_note
    assert "EMA 平滑后 60" in exp.ema_note
    assert "半衰期 2" in exp.ema_note


def test_dto_type():
    exp = _explain_for_score(_dto(), _Settings())
    assert isinstance(exp, ExplainThreatScoreDTO)


# ---- 4.1 (IMPL 4.1): 持久化评分分解列优先 ----------------


def test_persisted_confidence_overrides_derived():
    # persisted confidence=medium 覆盖现算的 high(4 模块)
    exp = _explain_for_score(
        _dto(), _Settings(),
        persisted={"confidence": "medium", "active_modules": 3, "module_scores": None},
    )
    assert exp.confidence == "medium"
    assert exp.active_modules == 3


def test_persisted_module_scores_override():
    pers = {
        "module_scores": {"options": 10, "short": 20, "divergence": 30, "insider": 40},
        "confidence": None,
        "active_modules": None,
    }
    exp = _explain_for_score(_dto(), _Settings(), persisted=pers)
    # 持久化 scores 覆盖 DTO 模块分
    assert exp.module_scores == {"options": 10.0, "short": 20.0, "divergence": 30.0, "insider": 40.0}
    # confidence None → 回落到现算 (4 模块 active → high)
    assert exp.confidence == "high"


def test_persisted_none_falls_back_to_derive():
    # persisted 全空/None → 与原 2.6 逻辑一致 (现算)
    exp = _explain_for_score(_dto(), _Settings(), persisted=None)
    assert exp.confidence == "high"
    assert exp.active_modules == 4
    assert exp.module_scores == {"options": 50.0, "short": 70.0, "divergence": 40.0, "insider": 30.0}


def test_persisted_insufficient_data():
    pers = {"confidence": "insufficient_data", "active_modules": 1, "module_scores": None}
    exp = _explain_for_score(_dto(), _Settings(), persisted=pers)
    assert exp.confidence == "insufficient_data"
    assert exp.active_modules == 1
