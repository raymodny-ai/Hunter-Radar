"""BD-004 FINRA 落库层(etl/load_short_volume)测试。

策略:
- 纯函数(payload 构造、过滤)在沙箱可跑
- 涉及 AsyncSession 的部分通过 AsyncMock 验证调用次数与参数
- 不连真实 PG(沙箱无 docker)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etl.finra_short import ShortVolumeRow
from etl.load_short_volume import (
    LoadResult,
    _build_payload,
    _known_symbols,
    load_short_volume,
)


def _row(sym: str, sv: int = 1000, nsv: int = 5000) -> ShortVolumeRow:
    return ShortVolumeRow(
        trade_date=date(2024, 2, 1),
        symbol=sym,
        short_volume=sv,
        non_short_volume=nsv,
    )


class TestBuildPayload:
    def test_basic(self):
        rows = [_row("AAPL", sv=200, nsv=800)]
        known = {"AAPL"}
        payload, unknown = _build_payload(rows, known)
        assert unknown == 0
        assert len(payload) == 1
        assert payload[0] == {
            "trade_date": date(2024, 2, 1),
            "symbol": "AAPL",
            "short_volume": 200,
            "non_short_volume": 800,
            "source": "finra",
        }

    def test_filters_unknown_symbols(self):
        rows = [_row("AAPL"), _row("XYZ")]
        known = {"AAPL"}
        payload, unknown = _build_payload(rows, known)
        assert unknown == 1
        assert len(payload) == 1
        assert payload[0]["symbol"] == "AAPL"

    def test_empty_rows(self):
        payload, unknown = _build_payload([], set())
        assert payload == []
        assert unknown == 0

    def test_custom_source(self):
        rows = [_row("AAPL")]
        payload, _ = _build_payload(rows, {"AAPL"}, source="alt_source")
        assert payload[0]["source"] == "alt_source"


class TestLoadShortVolume:
    @pytest.mark.asyncio
    async def test_empty_rows_returns_zero(self):
        res = await load_short_volume([])
        assert res.attempted == 0
        assert res.inserted == 0
        assert res.skipped == 0
        assert res.failures == 0

    @pytest.mark.asyncio
    async def test_skips_when_no_known_symbols(self):
        """全部 ticker 都不在 symbol_master → unknown_symbols 计 N,inserted=0。"""
        rows = [_row("UNKNOWN1"), _row("UNKNOWN2")]
        # 直接 patch _known_symbols 与 session 链,避免真的连库
        with patch("etl.load_short_volume._known_symbols", AsyncMock(return_value=set())):
            with patch("etl.load_short_volume.AsyncSessionLocal", MagicMock()):
                # 让 commit/close 是 no-op
                session = AsyncMock()
                session.commit = AsyncMock()
                session.close = AsyncMock()
                with patch(
                    "etl.load_short_volume.AsyncSessionLocal",
                    MagicMock(return_value=session),
                ):
                    res = await load_short_volume(rows)
        assert res.attempted == 2
        assert res.unknown_symbols == 2
        assert res.inserted == 0

    @pytest.mark.asyncio
    async def test_counts_inserted_vs_skipped(self):
        """rowcount=2 表示插入了 2 条,skipped=0。"""
        rows = [_row("AAPL"), _row("MSFT")]
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                # _known_symbols
                MagicMock(all=MagicMock(return_value=[("AAPL",), ("MSFT",)])),
                # _bulk_insert → rowcount=2
                MagicMock(rowcount=2),
            ]
        )
        session.commit = AsyncMock()
        session.close = AsyncMock()

        with patch("etl.load_short_volume._known_symbols", AsyncMock(return_value={"AAPL", "MSFT"})):
            with patch(
                "etl.load_short_volume.AsyncSessionLocal",
                MagicMock(return_value=session),
            ):
                res = await load_short_volume(rows)

        assert res.attempted == 2
        assert res.unknown_symbols == 0
        assert res.inserted == 2
        assert res.skipped == 0
        assert res.failures == 0

    @pytest.mark.asyncio
    async def test_failures_on_db_error(self):
        """SQLAlchemyError → failures 计 attempted,rollback 触发。"""
        from sqlalchemy.exc import OperationalError

        rows = [_row("AAPL")]
        session = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()

        with patch("etl.load_short_volume._known_symbols", AsyncMock(return_value={"AAPL"})):
            with patch("etl.load_short_volume._bulk_insert", AsyncMock(side_effect=OperationalError("stmt", {}, Exception("db down")))):
                with patch(
                    "etl.load_short_volume.AsyncSessionLocal",
                    MagicMock(return_value=session),
                ):
                    res = await load_short_volume(rows)

        assert res.failures == 1
        session.rollback.assert_awaited_once()


class TestLoadResult:
    def test_iadd(self):
        a = LoadResult(attempted=1, inserted=1)
        b = LoadResult(attempted=2, inserted=1, skipped=1)
        a += b
        assert a.attempted == 3
        assert a.inserted == 2
        assert a.skipped == 1
