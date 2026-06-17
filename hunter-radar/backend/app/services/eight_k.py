"""BD-051 8-K Item 8.01 解析器 — 沙箱 fixture fallback。

8-K Item 8.01 「Other Events」包括:
- 公司回购计划 / 实际回购
- 重大协议 / 战略合作
- 高管变动之外的重大事项

数据源:SEC EDGAR full-text search API + filing index
生产:httpx.AsyncClient → https://efts.sec.gov/LATEST/search-index?q=...&dateRange=custom&...
沙箱:本地 fixture(in-memory list),无 SEC 代理时返 mock

合规:不做投资建议;summary 仅展示 EDGAR 原文摘录前 200 字
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

EventCategory = Literal[
    "share-repurchase",  # 回购计划 / 实际回购
    "material-agreement",  # 重大协议 / 战略合作
    "press-release",  # 新闻发布
    "other",  # 其他 8.01 事项
]

# Item 8.01 关键词 → 分类映射
CATEGORY_KEYWORDS: dict[EventCategory, tuple[str, ...]] = {
    "share-repurchase": (
        "share repurchase",
        "buyback",
        "repurchase program",
        "repurchase plan",
        "share buyback",
        "treasury stock",
        "authoriz",  # authorize / authorized
        "stock repurchase",
    ),
    "material-agreement": (
        "material agreement",
        "strategic alliance",
        "joint venture",
        "merger agreement",
        "acquisition agreement",
        "license agreement",
        "collaboration agreement",
    ),
    "press-release": (
        "press release",
        "announces",
        "issued",
        "report",
    ),
}


@dataclass
class EightKEvent:
    """8-K Item 8.01 重大事件。"""

    ticker: str  # 公司代码(AAPL / TSLA)
    cik: str  # SEC CIK 编号
    filed_at: str  # ISO 8601 filing date
    accession: str  # SEC accession number
    form: str = "8-K"
    item: str = "8.01"
    category: EventCategory = "other"
    title: str = ""  # EDGAR 标题(Subject Company)
    summary: str = ""  # 8-K 正文摘录(≤200 字)
    url: str = ""  # EDGAR filing URL
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


# 沙箱 fixture:5 条历史 8-K 事件(覆盖 3 类 category)
_FIXTURE: list[EightKEvent] = [
    EightKEvent(
        ticker="AAPL",
        cik="0000320193",
        filed_at="2026-05-12T16:30:00Z",
        accession="0000320193-26-000123",
        category="share-repurchase",
        title="Apple Inc. - 8-K Other Events",
        summary=(
            "Apple Inc. 董事会批准新增 900 亿美元股票回购计划,"
            "回购期限至 2028 财年末。管理层将在例行披露中报告实际回购情况。"
        ),
        url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=8-K",
    ),
    EightKEvent(
        ticker="TSLA",
        cik="0001318605",
        filed_at="2026-05-08T13:00:00Z",
        accession="0001318605-26-000088",
        category="material-agreement",
        title="Tesla, Inc. - 8-K Material Agreement",
        summary=(
            "Tesla 与某电池供应商签署为期 5 年的战略供应协议,"
            "涉及金额约 47 亿美元。"
        ),
        url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001318605&type=8-K",
    ),
    EightKEvent(
        ticker="MSFT",
        cik="0000789019",
        filed_at="2026-05-05T09:15:00Z",
        accession="0000789019-26-000045",
        category="share-repurchase",
        title="Microsoft Corporation - 8-K Other Events",
        summary=(
            "Microsoft 宣布新一轮 600 亿美元股票回购授权,"
            "同时维持现有季度股息政策。"
        ),
        url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000789019&type=8-K",
    ),
    EightKEvent(
        ticker="NVDA",
        cik="0001045810",
        filed_at="2026-04-28T16:00:00Z",
        accession="0001045810-26-000212",
        category="press-release",
        title="NVIDIA Corporation - 8-K Press Release",
        summary=(
            "NVIDIA 发布 2026 财年第一季度财报初稿,营收同比增长 138%,数据中心业务连续 6 个季度创历史新高。"
        ),
        url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=8-K",
    ),
    EightKEvent(
        ticker="GME",
        cik="0001326380",
        filed_at="2026-04-20T14:30:00Z",
        accession="0001326380-26-000033",
        category="share-repurchase",
        title="GameStop Corp. - 8-K Other Events",
        summary=(
            "GameStop 董事会批准 4.5 亿美元股票回购计划,"
            "执行窗口为 36 个月。"
        ),
        url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001326380&type=8-K",
    ),
]


def classify_summary(text: str) -> EventCategory:
    """给定 8-K body 摘要,判定 category。"""
    if not text:
        return "other"
    lower = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return cat
    return "other"


def list_fixture_events(
    *,
    ticker: str | None = None,
    category: EventCategory | None = None,
    since_iso: str | None = None,
) -> list[EightKEvent]:
    """查沙箱 fixture 事件(支持 ticker / category / since 三重过滤)。"""
    out = list(_FIXTURE)
    if ticker:
        out = [e for e in out if e.ticker == ticker.upper()]
    if category:
        out = [e for e in out if e.category == category]
    if since_iso:
        out = [e for e in out if e.filed_at >= since_iso]
    return sorted(out, key=lambda e: e.filed_at, reverse=True)


def fetch_recent_8k(days: int = 7) -> list[EightKEvent]:
    """拉最近 N 天的 8-K Item 8.01 事件。

    生产:httpx → EDGAR full-text search + filing index
    沙箱:返 fixture 并按 filed_at 过滤
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    return [e for e in list_fixture_events() if e.filed_at >= cutoff_iso]


def fetch_for_ticker(ticker: str, days: int = 30) -> list[EightKEvent]:
    """拉某 ticker 最近 N 天 8-K。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    return [
        e for e in list_fixture_events(ticker=ticker)
        if e.filed_at >= cutoff_iso
    ]


def reset_for_tests(seed_path: Path | None = None) -> None:
    """沙箱自测用:重新加载 fixture。"""
    global _FIXTURE
    if seed_path and seed_path.exists():
        _FIXTURE = [
            EightKEvent(**json.loads(line))  # type: ignore[arg-type]
            for line in seed_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]