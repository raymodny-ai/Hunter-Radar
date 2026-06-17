"""Tests for etl/load_short_ratio(BD-030/031/032)。"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---- 1) _zscore_payload 纯函数逻辑(无 DB) ----


@pytest.fixture
def fake_ats_map():
    return {"AAPL": 0.42, "TSLA": 0.30}


def test_zscore_payload_returns_none_when_no_history():
    from etl.load_short_ratio import _zscore_payload

    p, n_z, n_warm = _zscore_payload("AAPL", [], date(2024, 2, 1), {}, lookback=60)
    assert p is None
    assert n_z == 0
    assert n_warm == 0


def test_zscore_payload_skips_when_target_missing():
    from etl.load_short_ratio import _zscore_payload

    rows = [(date(2024, 1, 30), 0.30), (date(2024, 1, 31), 0.32)]
    p, _, _ = _zscore_payload("AAPL", rows, date(2024, 2, 1), {}, lookback=60)
    assert p is None  # target 缺失


def test_zscore_payload_warmup_when_history_too_short():
    from etl.load_short_ratio import _zscore_payload

    target = date(2024, 2, 1)
    # 只有 target 当日,lookback=60 显然不足
    rows = [(target, 0.30)]
    p, n_z, n_warm = _zscore_payload("AAPL", rows, target, {}, lookback=60)
    assert p is not None
    assert p["z_score_60d"] is None
    assert p["short_ratio"] == pytest.approx(0.30)
    assert n_z == 0
    assert n_warm == 1


def test_zscore_payload_computes_z_with_sufficient_history():
    from etl.load_short_ratio import _zscore_payload

    target = date(2024, 2, 1)
    # 65 个平稳点 + target 当日突增
    rows = [(date(2024, 1, 1), 0.30) for _ in range(65)]
    rows.append((target, 0.55))
    rows.sort(key=lambda x: x[0])
    p, n_z, n_warm = _zscore_payload("AAPL", rows, target, {}, lookback=60)
    assert p is not None
    assert p["z_score_60d"] is not None
    assert p["z_score_60d"] > 0  # 突增应得正 Z
    assert n_z == 1
    assert n_warm == 0


def test_zscore_payload_includes_ats_pct():
    from etl.load_short_ratio import _zscore_payload

    target = date(2024, 2, 1)
    rows = [(target, 0.42)]
    p, _, _ = _zscore_payload("AAPL", rows, target, {"AAPL": 0.55}, lookback=60)
    assert p is not None
    assert p["ats_short_pct"] == 0.55


# ---- 2) compute_short_ratio SQL mock 集成 ----


@pytest.mark.asyncio
async def test_compute_short_ratio_empty_universe():
    """universe 为空时返回全零结果,不抛异常。"""
    from etl.load_short_ratio import compute_short_ratio

    fake_session = AsyncMock()
    fake_session.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    with patch("etl.load_short_ratio.AsyncSessionLocal") as fake_local:
        fake_local.return_value.__aenter__ = AsyncMock(return_value=fake_session)
        fake_local.return_value.__aexit__ = AsyncMock(return_value=False)
        res = await compute_short_ratio(
            date(2024, 2, 1), session=fake_session
        )
    assert res.attempted == 0
    assert res.inserted == 0
    assert res.z_scored == 0


@pytest.mark.asyncio
async def test_compute_short_ratio_inserts_payload():
    """universe 1 个 + ats_pct_map 命中 → 应 INSERT 1 行。"""
    from etl.load_short_ratio import compute_short_ratio

    # 1) universe 查询 → 1 行
    # 2) history 读 → 至少 target 1 行
    # 3) ats_pct 读 → 1 行
    # 4) insert ON CONFLICT DO UPDATE → rowcount=1

    rs1 = MagicMock()
    rs1.all.return_value = [("AAPL",)]
    rs2 = MagicMock()
    rs2.all.return_value = [(date(2024, 2, 1), 0.30)]
    rs3 = MagicMock()
    rs3.all.return_value = [("AAPL",)]
    rs4 = MagicMock()
    rs4.all.return_value = [("AAPL", 1000)]
    rs5 = MagicMock()
    rs5.all.return_value = [("AAPL", 5000)]
    rs_insert = MagicMock()
    rs_insert.rowcount = 1

    fake_session = AsyncMock()
    fake_session.execute.side_effect = [rs1, rs2, rs3, rs4, rs5, rs_insert]
    res = await compute_short_ratio(date(2024, 2, 1), session=fake_session)
    assert res.attempted == 1
    assert res.inserted == 1
    fake_session.commit.assert_awaited()
