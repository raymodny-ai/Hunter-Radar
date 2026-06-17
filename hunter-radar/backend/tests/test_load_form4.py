"""BD-006 Form 4 / BD-051 Buyback 落库层测试。

聚焦:
- role 归一化(BD-050)
- ETF 标的过滤(BD-053)
- 关键内部人过滤
- payload 构造
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.insider import BuybackEvent, Form4Event
from etl.load_form4 import (
    Form4LoadResult,
    _build_form4_payload,
    _normalize_role,
    load_form4,
)
from etl.sec_form4 import Form4Row


def _form4(sym: str = "AAPL", role: str = "CEO", direction: str = "S", qty: int = 1000, price: float = 150.0) -> Form4Row:
    return Form4Row(
        symbol=sym,
        insider_name="John Doe",
        insider_role=role,
        txn_date=date(2024, 2, 1),
        filed_at=date(2024, 2, 3),
        direction=direction,
        qty=qty,
        price=price,
        form_url="https://www.sec.gov/.../form4",
    )


class TestNormalizeRole:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("CEO", "CEO"),
            ("Chief Executive Officer", "CEO"),
            ("CHIEF EXECUTIVE OFFICER", "CEO"),
            ("CFO", "CFO"),
            ("Chief Financial Officer", "CFO"),
            ("Director", "Director"),
            ("Independent Director", "Director"),
            ("10% Owner", "10% Holder"),
            ("Ten Percent Holder", "10% Holder"),
            ("VP of Sales", "VP of Sales"),  # 透传,后续 is_key_insider 判否
        ],
    )
    def test_normalize(self, raw, expected):
        assert _normalize_role(raw) == expected


class TestBuildForm4Payload:
    def test_basic_key_insider(self):
        rows = [_form4(role="CEO")]
        known_etf: set[str] = set()
        payload, skipped_etf, non_key = _build_form4_payload(rows, known_etf)
        assert skipped_etf == 0
        assert non_key == 0
        assert len(payload) == 1
        assert payload[0]["symbol"] == "AAPL"
        assert payload[0]["insider_role"] == "CEO"
        assert payload[0]["classification"] == "ceo"
        assert payload[0]["direction"] == "S"

    def test_skips_etf(self):
        rows = [_form4(sym="SPY")]
        known_etf = {"SPY"}
        payload, skipped_etf, non_key = _build_form4_payload(rows, known_etf)
        assert skipped_etf == 1
        assert non_key == 0
        assert payload == []

    def test_skips_non_key_insider(self):
        rows = [_form4(role="VP of Sales")]
        payload, _, non_key = _build_form4_payload(rows, set())
        assert non_key == 1
        assert payload == []

    def test_normalizes_role_text(self):
        rows = [_form4(role="Chief Executive Officer")]
        payload, _, _ = _build_form4_payload(rows, set())
        assert payload[0]["insider_role"] == "CEO"
        assert payload[0]["classification"] == "ceo"

    def test_director_normalized(self):
        rows = [_form4(role="Independent Director")]
        payload, _, _ = _build_form4_payload(rows, set())
        assert payload[0]["insider_role"] == "Director"
        assert payload[0]["classification"] == "director"

    def test_10pct_normalized(self):
        rows = [_form4(role="10% Owner")]
        payload, _, _ = _build_form4_payload(rows, set())
        assert payload[0]["insider_role"] == "10% Holder"
        assert payload[0]["classification"] == "10pct_holder"


class TestLoadForm4:
    @pytest.mark.asyncio
    async def test_empty(self):
        res = await load_form4([])
        assert res.attempted == 0
        assert res.inserted == 0
        assert res.failures == 0

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        rows = [
            _form4(role="CEO"),
            _form4(sym="SPY", role="CFO"),  # ETF 跳过
            _form4(sym="XYZ", role="VP"),  # 非关键内部人
        ]
        with patch(
            "etl.load_form4._known_etf_symbols",
            AsyncMock(return_value={"SPY"}),
        ):
            session = AsyncMock()
            session.execute = AsyncMock(
                return_value=MagicMock(rowcount=1)
            )
            session.commit = AsyncMock()
            session.close = AsyncMock()
            with patch(
                "etl.load_form4.AsyncSessionLocal",
                MagicMock(return_value=session),
            ):
                res = await load_form4(rows)

        assert res.attempted == 3
        assert res.skipped_etf == 1
        assert res.non_key_insider == 1
        assert res.inserted == 1
        assert res.failures == 0


class TestBuybackPayload:
    """Buyback payload 构造(走 _build_buyback_payload 在 etl.load_form4 模块中)。"""

    def test_basic(self):
        from etl.load_form4 import _build_buyback_payload

        rows = [
            BuybackEvent(
                symbol="AAPL",
                announce_date=date(2024, 2, 1),
                amount_usd=10_000_000.0,
                duration_days=90,
                form_url="https://www.sec.gov/.../8k",
            )
        ]
        payload, unknown = _build_buyback_payload(rows, {"AAPL"})
        assert unknown == 0
        assert len(payload) == 1
        assert payload[0]["symbol"] == "AAPL"
        assert payload[0]["form_type"] == "8-K"
        assert payload[0]["amount_usd"] == 10_000_000
        assert payload[0]["execution_window"] == "90d"

    def test_unknown_symbol(self):
        from etl.load_form4 import _build_buyback_payload

        rows = [
            BuybackEvent(
                symbol="ZZZZ",
                announce_date=date(2024, 2, 1),
                amount_usd=1_000_000.0,
                duration_days=30,
                form_url="https://www.sec.gov/.../8k",
            )
        ]
        payload, unknown = _build_buyback_payload(rows, set())
        assert unknown == 1
        assert payload == []
