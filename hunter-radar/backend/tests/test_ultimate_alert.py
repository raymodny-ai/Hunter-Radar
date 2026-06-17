"""Tests for app/services/ultimate_alert(BD-062/064)。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---- 1) _resolve_threshold 纯函数 ----


class TestResolveThreshold:
    def test_normal(self):
        from app.services.ultimate_alert import _resolve_threshold

        assert _resolve_threshold("normal") == 70  # settings.threat_red_threshold

    def test_panic(self):
        from app.services.ultimate_alert import _resolve_threshold

        # settings.threat_red_threshold_panic 默认 80
        assert _resolve_threshold("panic") == 80


# ---- 2) _pick_active_modules 纯函数 ----


class TestPickActiveModules:
    def test_empty_history(self):
        from app.services.ultimate_alert import _pick_active_modules

        assert _pick_active_modules([]) == []

    def test_all_active(self):
        from app.services.ultimate_alert import _pick_active_modules

        rows = [
            {
                "module_options": 80.0,
                "module_short": 80.0,
                "module_divergence": 80.0,
                "module_insider": 80.0,
            }
        ]
        assert set(_pick_active_modules(rows, module_thr=60.0)) == {
            "options",
            "short",
            "divergence",
            "insider",
        }

    def test_below_threshold_excluded(self):
        from app.services.ultimate_alert import _pick_active_modules

        rows = [
            {
                "module_options": 50.0,
                "module_short": 80.0,
                "module_divergence": 30.0,
                "module_insider": 90.0,
            }
        ]
        # 只有 short + insider 达到 60
        assert set(_pick_active_modules(rows, module_thr=60.0)) == {"short", "insider"}

    def test_uses_last_day(self):
        """应只取 history[-1] 当日,不是全部。"""
        from app.services.ultimate_alert import _pick_active_modules

        rows = [
            # 前一日高分但不算
            {
                "module_options": 90.0,
                "module_short": 30.0,
                "module_divergence": 30.0,
                "module_insider": 30.0,
            },
            # 当日只有 short 合格
            {
                "module_options": 30.0,
                "module_short": 80.0,
                "module_divergence": 30.0,
                "module_insider": 30.0,
            },
        ]
        assert _pick_active_modules(rows, module_thr=60.0) == ["short"]


# ---- 3) evaluate_ultimate_alerts SQL mock 集成 ----


def _row(trade_date, ema, mod_opts, mod_short, mod_div, mod_insider, regime="normal"):
    """构造 history 序列里的一行。"""
    return {
        "trade_date": trade_date,
        "module_options": mod_opts,
        "module_short": mod_short,
        "module_divergence": mod_div,
        "module_insider": mod_insider,
        "total_ema": ema,
        "total_raw": ema,
        "signal_lifecycle": "red" if ema >= 70 else "yellow",
        "regime": regime,
    }


@pytest.mark.asyncio
async def test_evaluate_ultimate_alerts_empty_universe():
    """universe 空 → 0 attempted。"""
    from app.services.ultimate_alert import evaluate_ultimate_alerts

    rs = MagicMock()
    rs.all.return_value = []
    fake_session = AsyncMock()
    fake_session.execute.return_value = rs
    res = await evaluate_ultimate_alerts(date(2024, 2, 1), session=fake_session)
    assert res.attempted == 0
    assert res.triggered == 0


@pytest.mark.asyncio
async def test_evaluate_below_threshold_skipped():
    """EMA < 70 → skipped_below_threshold,不入库。"""
    from app.services.ultimate_alert import evaluate_ultimate_alerts

    # universe 1 行;history 3 日 EMA=50(< 70)
    rs1 = MagicMock()
    rs1.all.return_value = [("AAPL",)]
    # history read 返回的格式需匹配 ._mapping 访问
    history_rows = [
        _row(date(2024, 1, 30), 50.0, 30.0, 60.0, 30.0, 30.0),
        _row(date(2024, 1, 31), 50.0, 30.0, 60.0, 30.0, 30.0),
        _row(date(2024, 2, 1), 50.0, 30.0, 60.0, 30.0, 30.0),
    ]
    rs2 = MagicMock()
    rs2.all.return_value = [history_rows]  # outer list for SQL result, inner for symbol

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2]
    res = await evaluate_ultimate_alerts(date(2024, 2, 1), session=fake_session)
    assert res.skipped_below_threshold == 1
    assert res.triggered == 0


@pytest.mark.asyncio
async def test_evaluate_no_continuous_module_skipped():
    """EMA ≥ 70 但模块未连续 ≥2 日 → skipped_no_continuous。"""
    from app.services.ultimate_alert import evaluate_ultimate_alerts

    rs1 = MagicMock()
    rs1.all.return_value = [("AAPL",)]
    # EMA=80(高),但只有当日 short=80,前日 short=30 → 断
    history_rows = [
        _row(date(2024, 1, 31), 80.0, 30.0, 30.0, 30.0, 30.0),
        _row(date(2024, 2, 1), 80.0, 30.0, 80.0, 30.0, 30.0),
    ]
    rs2 = MagicMock()
    rs2.all.return_value = [history_rows]

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2]
    res = await evaluate_ultimate_alerts(date(2024, 2, 1), session=fake_session)
    assert res.skipped_no_continuous == 1
    assert res.triggered == 0


@pytest.mark.asyncio
async def test_evaluate_debounce_skipped():
    """EMA + 模块连续均合格,但 24h 内已触发 → skipped_debounce。"""
    from app.services.ultimate_alert import evaluate_ultimate_alerts

    rs1 = MagicMock()
    rs1.all.return_value = [("AAPL",)]
    history_rows = [
        _row(date(2024, 1, 31), 80.0, 80.0, 30.0, 30.0, 30.0),
        _row(date(2024, 2, 1), 80.0, 80.0, 30.0, 30.0, 30.0),
    ]
    rs2 = MagicMock()
    rs2.all.return_value = [history_rows]
    # _has_recent_alert 查询返回 1 行 → 防抖命中
    rs3 = MagicMock()
    rs3.first.return_value = (datetime.now(timezone.utc),)

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2, rs3]
    res = await evaluate_ultimate_alerts(date(2024, 2, 1), session=fake_session)
    assert res.skipped_debounce == 1
    assert res.triggered == 0


@pytest.mark.asyncio
async def test_evaluate_full_path_triggered():
    """三连条件全过:EMA ≥ 70 + 模块连续 ≥ 2 日 + 24h 无重复 → 写入。"""
    from app.services.ultimate_alert import evaluate_ultimate_alerts

    rs1 = MagicMock()
    rs1.all.return_value = [("AAPL",)]
    # EMA 连续 2 日 ≥ 70,short 模块连续 2 日 ≥ 60
    history_rows = [
        _row(date(2024, 1, 31), 80.0, 70.0, 80.0, 30.0, 30.0),
        _row(date(2024, 2, 1), 85.0, 70.0, 80.0, 30.0, 30.0),
    ]
    rs2 = MagicMock()
    rs2.all.return_value = [history_rows]
    # _has_recent_alert 查询返回 None → 防抖通过
    rs3 = MagicMock()
    rs3.first.return_value = None
    # insert ON CONFLICT DO NOTHING
    rs4 = MagicMock()
    rs4.rowcount = 1

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2, rs3, rs4]
    res = await evaluate_ultimate_alerts(date(2024, 2, 1), session=fake_session)
    assert res.triggered == 1
    assert res.rows is not None and len(res.rows) == 1
    assert res.rows[0].symbol == "AAPL"
    assert "short" in res.rows[0].modules_active
