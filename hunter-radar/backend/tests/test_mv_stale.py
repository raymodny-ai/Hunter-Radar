"""5.3 [4.3]: mv_screener_top100 物化视图刷新监控 — 落后判定。"""
from datetime import date

from etl.pipeline import _is_mv_stale


def test_mv_stale_none_is_stale():
    """空表(None)必然判定为落后。"""
    limit = date(2026, 7, 31)
    assert _is_mv_stale(None, limit) is True


def test_mv_stale_equal_to_limit_not_stale():
    """latest == 今天-1天(周末/节假日最近交易日)不算落后。"""
    limit = date(2026, 7, 31)
    assert _is_mv_stale(date(2026, 7, 31), limit) is False


def test_mv_stale_newer_not_stale():
    """latest 比 limit 新 → 正常。"""
    limit = date(2026, 7, 31)
    assert _is_mv_stale(date(2026, 8, 1), limit) is False


def test_mv_stale_older_is_stale():
    """latest 严格早于 limit → 落后。"""
    limit = date(2026, 7, 31)
    assert _is_mv_stale(date(2026, 7, 29), limit) is True


def test_mv_stale_multi_day_stale():
    """多天落后(最早交易日)仍判定落后。"""
    limit = date(2026, 7, 31)
    assert _is_mv_stale(date(2026, 7, 24), limit) is True
