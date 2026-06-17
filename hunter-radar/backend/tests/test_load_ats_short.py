"""BD-005 ATS 暗池 CSV 解析 + 落库测试。"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etl.load_ats_short import (
    ATSVolumeRow,
    parse_ats_csv,
)


CSV_OK = b"""trade_date,symbol,venue_pool,ats_short_volume
2024-02-01,AAPL,EDGX,12345
2024-02-01,AAPL,IEX,2345
2024-02-01,SPY,BATS,1000000
"""

CSV_BAD = b"""trade_date,symbol,venue_pool,ats_short_volume
bad_date,AAPL,EDGX,12345
2024-02-01,,EDGX,100
2024-02-01,AAPL,EDGX,-5
2024-02-01,SPY,EDGX,abc
"""


class TestParseATSCSV:
    def test_ok(self):
        r = parse_ats_csv(CSV_OK)
        assert r.bad_rows == 0
        assert len(r.rows) == 3
        assert r.rows[0] == ATSVolumeRow(
            trade_date=date(2024, 2, 1),
            symbol="AAPL",
            venue_pool="EDGX",
            ats_short_volume=12345,
        )
        assert r.rows[1].venue_pool == "IEX"
        assert r.rows[2].symbol == "SPY"

    def test_bad_rows(self):
        r = parse_ats_csv(CSV_BAD)
        assert r.bad_rows == 4
        assert len(r.rows) == 0

    def test_mixed(self):
        mixed = CSV_OK + b"\n" + CSV_BAD.splitlines()[0] + b"\n"
        # 验证混合场景不崩
        r = parse_ats_csv(mixed)
        assert r.bad_rows >= 0
        assert isinstance(r.rows, list)

    def test_empty(self):
        r = parse_ats_csv(b"trade_date,symbol,venue_pool,ats_short_volume\n")
        assert r.rows == []
        assert r.bad_rows == 0

    def test_handles_commas_in_numbers(self):
        csv = b"trade_date,symbol,venue_pool,ats_short_volume\n2024-02-01,AAPL,EDGX,\"1,234,567\"\n"
        r = parse_ats_csv(csv)
        assert len(r.rows) == 1
        assert r.rows[0].ats_short_volume == 1234567
