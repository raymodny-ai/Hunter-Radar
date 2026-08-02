"""3.4 FINRA 精度修正 — parse_finra_short_csv 测试 (AQ-05/AQ-06)。"""
from datetime import date

from etl.finra_short import parse_finra_short_csv, ShortVolumeRow


def _csv(body: str, header: bool = True) -> bytes:
    hdr = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n" if header else ""
    return (hdr + body).encode()


def test_round_not_truncate():
    """round() 四舍五入: 6232560.6 → 6232561 (而非 int 截断 6232560)。"""
    content = _csv("20260626|AMD|6232560.6|5000|13000000|Q\n")
    rows = parse_finra_short_csv(content)
    assert len(rows) == 1
    assert rows[0].short_volume == 6232561


def test_round_down_case():
    """round() 四舍五入: 6232560.3 → 6232560。"""
    content = _csv("20260626|AMD|6232560.3|5000|13000000|Q\n")
    rows = parse_finra_short_csv(content)
    assert rows[0].short_volume == 6232560


def test_short_gt_total_skipped():
    """sv > tv 逻辑错误 → 跳过该行, 不产出行。"""
    content = _csv("20260626|BAD|9000000|5000|8000000|Q\n")
    rows = parse_finra_short_csv(content)
    assert rows == []


def test_valid_row_nsv_computation():
    """正常行: nsv = tv - sv。"""
    content = _csv("20260626|AAPL|5000000|1000|12000000|B,Q\n")
    rows = parse_finra_short_csv(content)
    assert len(rows) == 1
    assert rows[0].short_volume == 5000000
    assert rows[0].non_short_volume == 7000000


def test_mixed_valid_and_invalid_rows():
    """合法行保留, 逻辑错误行剔除。"""
    content = _csv(
        "20260626|OK1|1000000|0|5000000|Q\n"
        "20260626|BAD|9000000|0|8000000|Q\n"
        "20260626|OK2|2000000|0|4000000|Q\n"
    )
    rows = parse_finra_short_csv(content)
    assert [r.symbol for r in rows] == ["OK1", "OK2"]
