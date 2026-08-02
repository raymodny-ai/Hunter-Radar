"""3.5 / 3.6 — SEC Form 4 解析断言 + CIK 索引缓存测试 (AQ-08/AQ-09)。"""
import time
from datetime import date

from etl.sec_form4 import (
    _CIK_CACHE,
    _CIK_CACHE_TIME,
    _CIK_CACHE_TTL,
    _load_cik_index,
    _parse_form4_html,
)


def _html(reporting_name: str, has_role_text: bool) -> str:
    """构造一个含 reporting person + 可选角色勾选的 Form 4 HTML。

    Sec 页面在 "Reporting Owner" 区间有 reporting person name;
    Director/Officer/10% Owner 复选框用 director 表结构。
    """
    role = ""
    if has_role_text:
        role = (
            '<table>'
            '<tr><td>Director</td><td>X</td></tr>'
            '<tr><td>Officer (give title below)</td><td></td></tr>'
            '<tr><td>10% Owner</td><td></td></tr>'
            '</table>'
        )
    return (
        f'<html><body><a href="/cgi-bin/browse-edgar?action=getcompany&amp;CIK=320193">'
        f'{reporting_name}</a>{role}'
        f'<table><tr><td>Table I - Non-Derivative</td></tr></table>'
        f'</body></html>'
    )


# ---- 3.5 结构断言 ----
def test_parse_with_role_ok():
    out = _parse_form4_html(_html("Timothy Cook", has_role_text=True))
    assert out  # 非空
    assert out.get("reporting_person_name") == "Timothy Cook"
    assert out.get("is_director") is True


def test_parse_no_role_no_txn_returns_empty():
    """结构变更: 有 reporting person 但无任何角色 + 无 txn → 安全失败返 {}。"""
    out = _parse_form4_html(_html("Mystery Person", has_role_text=False))
    assert out == {}


# ---- 3.6 CIK 索引 24h TTL 缓存 ----
def _fake_fetch_success():
    """往 module 级缓存写一个假 mapping (绕过网络)。"""
    global _CIK_CACHE
    _CIK_CACHE = {"AAPL": "0000320193"}
    return {"AAPL": "0000320193"}


def test_cik_cache_hit_within_ttl(monkeypatch):
    _CIK_CACHE.clear()
    # 已填充缓存 + 时间戳新鲜 → 直接命中, 不触发 fetch
    _CIK_CACHE.update({"AAPL": "0000320193"})
    cached_time = time.time()
    monkeypatch.setattr("etl.sec_form4._CIK_CACHE_TIME", cached_time)
    monkeypatch.setattr("etl.sec_form4._CIK_CACHE", _CIK_CACHE)

    calls = 0

    async def _fake_get(self, url):
        nonlocal calls
        calls += 1
        return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}}

    monkeypatch.setattr("etl.sec_form4._sec_get", _fake_get)
    import asyncio
    result = asyncio.run(_load_cik_index())
    assert result == {"AAPL": "0000320193"}
    assert calls == 0  # 命中缓存, 无网络调用


def test_cik_cache_expired_refetches(monkeypatch):
    _CIK_CACHE.clear()
    _CIK_CACHE.update({"OLD": "0000000001"})
    # 时间戳 10 天前 → 过期
    old_time = time.time() - _CIK_CACHE_TTL - 10
    monkeypatch.setattr("etl.sec_form4._CIK_CACHE_TIME", old_time)
    monkeypatch.setattr("etl.sec_form4._CIK_CACHE", _CIK_CACHE)

    async def _fake_get(self, url):
        return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}}

    monkeypatch.setattr("etl.sec_form4._sec_get", _fake_get)
    import asyncio
    result = asyncio.run(_load_cik_index())
    # 过期 → 重新拉取, 得到 AAPL 而非旧 OLD
    assert "AAPL" in result
    assert "OLD" not in result


def test_cik_ttl_constant():
    assert _CIK_CACHE_TTL == 86400
