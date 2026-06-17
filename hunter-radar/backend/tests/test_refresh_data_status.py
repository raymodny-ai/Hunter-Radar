"""BD-011 数据状态灯(refresh_data_status)测试。

聚焦:
- write_status 路径(纯函数 + mock session)
- mark_ready / mark_pending / mark_failed / mark_skipped
- invalid status / data_source 校验
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etl.refresh_data_status import (
    StatusRow,
    _build_payload,
    mark_failed,
    mark_pending,
    mark_ready,
    mark_skipped,
    write_status,
)


class TestBuildPayload:
    def test_basic(self):
        r = StatusRow(
            trade_date=date(2024, 2, 1),
            data_source="finra",
            status="ready",
            detail={"rows": 100},
        )
        p = _build_payload(r)
        assert p["trade_date"] == date(2024, 2, 1)
        assert p["data_source"] == "finra"
        assert p["status"] == "ready"
        assert p["detail"] == {"rows": 100}
        assert "last_attempt_at" in p

    def test_default_symbol_none(self):
        r = StatusRow(
            trade_date=date(2024, 2, 1),
            data_source="finra",
            status="ready",
        )
        p = _build_payload(r)
        assert p["symbol"] is None

    def test_invalid_status_raises(self):
        r = StatusRow(
            trade_date=date(2024, 2, 1),
            data_source="finra",
            status="banana",
        )
        with pytest.raises(ValueError):
            _build_payload(r)

    def test_invalid_source_raises(self):
        r = StatusRow(
            trade_date=date(2024, 2, 1),
            data_source="banana",
            status="ready",
        )
        with pytest.raises(ValueError):
            _build_payload(r)


class TestWriteStatus:
    @pytest.mark.asyncio
    async def test_success(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.close = AsyncMock()

        with patch(
            "etl.refresh_data_status.AsyncSessionLocal",
            MagicMock(return_value=session),
        ):
            ok = await write_status(
                StatusRow(
                    trade_date=date(2024, 2, 1),
                    data_source="finra",
                    status="ready",
                )
            )
        assert ok is True
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_input_returns_false(self):
        ok = await write_status(
            StatusRow(
                trade_date=date(2024, 2, 1),
                data_source="finra",
                status="INVALID",
            )
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_db_error_returns_false(self):
        from sqlalchemy.exc import OperationalError

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=OperationalError("stmt", {}, Exception())
        )
        session.rollback = AsyncMock()
        session.close = AsyncMock()

        with patch(
            "etl.refresh_data_status.AsyncSessionLocal",
            MagicMock(return_value=session),
        ):
            ok = await write_status(
                StatusRow(
                    trade_date=date(2024, 2, 1),
                    data_source="finra",
                    status="ready",
                )
            )
        assert ok is False


class TestConvenienceWrappers:
    @pytest.mark.asyncio
    async def test_mark_ready(self):
        with patch(
            "etl.refresh_data_status.write_status",
            AsyncMock(return_value=True),
        ) as ws:
            ok = await mark_ready(date(2024, 2, 1), "finra", detail={"rows": 5})
        assert ok is True
        ws.assert_awaited_once()
        arg = ws.await_args.args[0]
        assert arg.status == "ready"
        assert arg.data_source == "finra"
        assert arg.detail == {"rows": 5}

    @pytest.mark.asyncio
    async def test_mark_pending_with_reason(self):
        with patch(
            "etl.refresh_data_status.write_status",
            AsyncMock(return_value=True),
        ) as ws:
            ok = await mark_pending(date(2024, 2, 1), "sec_form4", reason="FINRA 未发布")
        assert ok is True
        arg = ws.await_args.args[0]
        assert arg.status == "pending_disclosure"
        assert arg.detail == {"reason": "FINRA 未发布"}

    @pytest.mark.asyncio
    async def test_mark_failed(self):
        with patch(
            "etl.refresh_data_status.write_status",
            AsyncMock(return_value=True),
        ) as ws:
            ok = await mark_failed(date(2024, 2, 1), "yfinance_eod", error="429 too many")
        assert ok is True
        arg = ws.await_args.args[0]
        assert arg.status == "failed"
        assert arg.detail == {"error": "429 too many"}

    @pytest.mark.asyncio
    async def test_mark_skipped_with_symbol(self):
        with patch(
            "etl.refresh_data_status.write_status",
            AsyncMock(return_value=True),
        ) as ws:
            ok = await mark_skipped(
                date(2024, 2, 1),
                "sec_form4",
                symbol="SPY",
                reason="BD-053 ETF 跳过",
            )
        assert ok is True
        arg = ws.await_args.args[0]
        assert arg.status == "skipped"
        assert arg.symbol == "SPY"
        assert arg.detail == {"reason": "BD-053 ETF 跳过"}
