"""3.1 FINRA 文件完整性校验 — validate_finra_file 测试 (AQ-07 / PL-02)。"""
import csv
import io
from datetime import date

import pytest

from etl.finra_short import (
    MIN_FINRA_ROWS,
    ShortVolumeRow,
    parse_finra_short_csv,
    validate_finra_file,
)


def _make_csv(rows: list[tuple], header: bool = True) -> bytes:
    buf = io.StringIO()
    if header:
        buf.write("Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n")
    for r in rows:
        buf.write("|".join(str(x) for x in r) + "\n")
    return buf.getvalue().encode()


@pytest.fixture
def good_rows_bytes():
    """5000 行合法数据 (Date 全部 = 20260626)。"""
    rows = [("20260626", f"SYM{i:05d}", 1000, 5, 5000, "Q") for i in range(MIN_FINRA_ROWS)]
    return _make_csv(rows)


def test_valid_file_passes(good_rows_bytes):
    d = date(2026, 6, 26)
    parsed = parse_finra_short_csv(good_rows_bytes)
    ok, reason = validate_finra_file(good_rows_bytes, d, parsed)
    assert ok is True
    assert reason == "ok"


def test_too_few_lines_fails(good_rows_bytes):
    # 截到 100 行 → 少于 MIN_FINRA_ROWS → 硬失败
    lines = good_rows_bytes.decode().split("\n")[:100]
    small = ("\n".join(lines) + "\n").encode()
    d = date(2026, 6, 26)
    ok, reason = validate_finra_file(small, d)
    assert ok is False
    assert "file_too_short" in reason


def test_date_mismatch_fails():
    rows = [("20260625", "SYM00001", 1000, 5, 5000, "Q") for _ in range(MIN_FINRA_ROWS)]
    content = _make_csv(rows)
    parsed = parse_finra_short_csv(content)
    # 期望 20260626, 实际全 20260625 → 失败
    ok, reason = validate_finra_file(content, date(2026, 6, 26), parsed)
    assert ok is False
    assert "date_mismatch" in reason


def test_small_file_warns_not_fails():
    # 行数达标但字节数 < 100KB → warning, 不硬失败
    rows = [("20260626", f"SYM{i:05d}", 1000, 5, 5000, "Q") for i in range(MIN_FINRA_ROWS)]
    content = _make_csv(rows)
    assert len(content) < 100_000  # 确认确实 < 阈值
    ok, reason = validate_finra_file(content, date(2026, 6, 26))
    assert ok is True  # warning 不中断
