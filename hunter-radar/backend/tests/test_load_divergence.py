"""Tests for etl/load_divergence(BD-040/041/042)。"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---- 1) _resolve_state 纯函数 ----


class TestResolveState:
    def test_not_divergent_is_none(self):
        from etl.load_divergence import _resolve_state

        assert _resolve_state(0.5, 0.5, False) == "none"

    def test_divergent_is_rising(self):
        from etl.load_divergence import _resolve_state

        assert _resolve_state(0.1, 0.9, True) == "rising"


# ---- 2) _confirm_state 纯函数(连续 ≥2 日升级)----


class TestConfirmState:
    def test_none_stays_none(self):
        from etl.load_divergence import _confirm_state

        assert _confirm_state({}, "AAPL", "none", consecutive_days=2) == "none"

    def test_rising_no_history_stays_rising(self):
        from etl.load_divergence import _confirm_state

        # prev_states 为空 → 仍是 rising
        assert _confirm_state({}, "AAPL", "rising", consecutive_days=2) == "rising"

    def test_rising_with_prev_confirmed(self):
        from etl.load_divergence import _confirm_state

        # 昨日已是 rising,consecutive_days=2 → 升级到 confirmed
        assert (
            _confirm_state(
                {"AAPL": "rising"}, "AAPL", "rising", consecutive_days=2
            )
            == "confirmed"
        )

    def test_rising_prev_none_stays_rising(self):
        from etl.load_divergence import _confirm_state

        assert (
            _confirm_state({"AAPL": "none"}, "AAPL", "rising", consecutive_days=2)
            == "rising"
        )


# ---- 3) compute_divergence SQL mock 集成 ----


@pytest.mark.asyncio
async def test_compute_divergence_empty_universe():
    """universe 为空时直接返回,无 insert。"""
    from etl.load_divergence import compute_divergence

    fake_session = AsyncMock()
    rs_universe = MagicMock()
    rs_universe.all.return_value = []
    fake_session.execute.return_value = rs_universe
    res = await compute_divergence(date(2024, 2, 1), session=fake_session)
    assert res.attempted == 0
    assert res.inserted == 0


@pytest.mark.asyncio
async def test_compute_divergence_short_history_warmup():
    """universe 1 个 ticker + 数据不足 → warmup=1,inserted=0。"""
    from etl.load_divergence import compute_divergence

    # 1) universe 1 行
    # 2) price_volume 1 行(数据不足 130 天)
    # 3) prev_state 0 行
    # → 1 个 ticker,全部走暖启动
    rs1 = MagicMock()
    rs1.all.return_value = [("AAPL",)]
    rs2 = MagicMock()
    rs2.all.return_value = [(date(2024, 1, 1), 100.0, 1000)]  # 只有 1 行
    rs3 = MagicMock()
    rs3.all.return_value = []

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2, rs3]
    res = await compute_divergence(date(2024, 2, 1), session=fake_session)
    assert res.attempted == 1
    assert res.inserted == 0
    assert res.warmup == 1


@pytest.mark.asyncio
async def test_compute_divergence_insufficient_data_no_insert():
    """即使有数据,detect_divergence 也可能判定 none → 仍走 insert(state=none)。"""
    from etl.load_divergence import compute_divergence

    # 1) universe 1 行
    # 2) price_volume 130 行(稳态 → is_divergent=False)
    # 3) prev_state 0 行
    # 4) insert ON CONFLICT DO UPDATE → rowcount=1
    rs1 = MagicMock()
    rs1.all.return_value = [("AAPL",)]
    rs2 = MagicMock()
    # 130 天稳态(单边上涨,但不触发背离)
    rs2.all.return_value = [
        (date(2024, 1, 1) + __import__("datetime").timedelta(days=i), 100.0 + i, 1_000_000)
        for i in range(130)
    ]
    rs3 = MagicMock()
    rs3.all.return_value = []
    rs_insert = MagicMock()
    rs_insert.rowcount = 1

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2, rs3, rs_insert]
    res = await compute_divergence(date(2024, 2, 1), session=fake_session)
    # 单边上涨 → state='none',inserted=1,rising=0,confirmed=0
    assert res.attempted == 1
    assert res.rising == 0
    assert res.confirmed == 0
    assert res.warmup == 0
    assert res.inserted == 1


@pytest.mark.asyncio
async def test_compute_divergence_liquidity_filter_default():
    """2.3 (CA-06): 20 日均量 < MIN_AVG_VOLUME_20D 的低流动性标的被过滤。"""
    from etl.load_divergence import compute_divergence, MIN_AVG_VOLUME_20D

    # 1) universe 1 个 ticker
    # 2) price_volume 30 行, 但 volume 都极小 (< 1万 < 10万阈值)
    # 3) prev_state 0 行
    # → 触发流动性过滤, liquidity_skipped=1, 不 insert
    rs1 = MagicMock()
    rs1.all.return_value = [("MICRO",)]
    rs2 = MagicMock()
    from types import SimpleNamespace as NS
    rs2.all.return_value = [
        NS(symbol="MICRO", trade_date=date(2024, 1, 1) + __import__("datetime").timedelta(days=i), close=10.0, volume=5_000)
        for i in range(30)
    ]
    rs3 = MagicMock()
    rs3.all.return_value = []

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2, rs3]
    res = await compute_divergence(date(2024, 2, 1), session=fake_session)
    assert res.attempted == 1
    assert res.liquidity_skipped == 1
    assert res.warmup == 0
    assert res.inserted == 0
    assert MIN_AVG_VOLUME_20D == 100_000.0


@pytest.mark.asyncio
async def test_compute_divergence_liquidity_disabled_when_zero():
    """min_avg_volume_20d=0 时关闭流动性门禁 → 正常计算。"""
    from etl.load_divergence import compute_divergence

    # 1) universe 1 ticker
    # 2) price_volume 30 行低量
    # 3) prev_state 0 行
    # 4) insert rowcount=1
    rs1 = MagicMock()
    rs1.all.return_value = [("MICRO",)]
    rs2 = MagicMock()
    from types import SimpleNamespace as NS
    # 高量 130 天稳态(vol=1M 远高于阈值, 且数据足够 → 正常 insert)
    rs2.all.return_value = [
        NS(symbol="MICRO", trade_date=date(2024, 1, 1) + __import__("datetime").timedelta(days=i), close=100.0 + i, volume=1_000_000)
        for i in range(130)
    ]
    rs3 = MagicMock()
    rs3.all.return_value = []
    rs_insert = MagicMock()
    rs_insert.rowcount = 1

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2, rs3, rs_insert]
    res = await compute_divergence(
        date(2024, 2, 1), session=fake_session, min_avg_volume_20d=0
    )
    assert res.attempted == 1
    assert res.liquidity_skipped == 0
    assert res.inserted == 1
