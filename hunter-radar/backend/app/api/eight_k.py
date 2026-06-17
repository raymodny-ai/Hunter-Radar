"""BD-051 8-K Item 8.01 重大事件流端点(M6)。

端点:
- GET /api/v1/events/8k?days=7         返最近 N 天全市场 8-K Item 8.01 事件流
- GET /api/v1/symbols/{ticker}/8k?days=30  返某 ticker 最近 N 天 8-K

沙箱降级:
- 无 EDGAR 代理时返 fixture(`app/services/eight_k.py` 内置 5 条 mock)
- 生产应替换为 httpx 调 SEC EDGAR full-text search API

合规:不做投资建议;summary 仅展示 EDGAR 原文摘录(已合 CR-010 红线词过滤)
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.eight_k import (
    EightKEvent,
    classify_summary,
    fetch_for_ticker,
    fetch_recent_8k,
    list_fixture_events,
)

router = APIRouter()


# CR-010 红线词(禁词扫描)
FORBIDDEN_WORDS = (
    "建议买入",
    "建议卖出",
    "保证收益",
    "必涨",
    "必跌",
)


def _sanitize_summary(text: str) -> str:
    """摘录合规过滤:命中禁词 → 替换为 [REDACTED]。"""
    out = text
    for w in FORBIDDEN_WORDS:
        out = out.replace(w, "[REDACTED]")
    return out


def _to_dto(e: EightKEvent) -> dict:
    """沙箱事件 → API DTO(过滤 summary)。"""
    d = e.to_dict()
    d["summary"] = _sanitize_summary(d.get("summary", ""))
    return d


@router.get("/events/8k", summary="全市场 8-K Item 8.01 事件流(BD-051)")
async def get_recent_8k(
    days: int = Query(default=7, ge=1, le=90, description="查询最近 N 天"),
    category: str | None = Query(default=None, description="share-repurchase | material-agreement | press-release | other"),
) -> dict:
    """返最近 N 天 8-K Item 8.01 事件流(全市场)。

    category=None 返全部;category 指定时仅返该类事件。
    """
    events = fetch_recent_8k(days=days)
    if category:
        events = [e for e in events if e.category == category]
    return {
        "window_days": days,
        "category": category,
        "total": len(events),
        "events": [_to_dto(e) for e in events],
        "sandbox": True,  # 标注数据源(生产由 EDGAR 真实拉取时改 false)
    }


@router.get("/symbols/{ticker}/8k", summary="单 ticker 8-K Item 8.01 事件(BD-051)")
async def get_ticker_8k(
    ticker: str,
    days: int = Query(default=30, ge=1, le=365, description="查询最近 N 天"),
) -> dict:
    """返某 ticker 最近 N 天 8-K Item 8.01 事件。"""
    events = fetch_for_ticker(ticker.upper(), days=days)
    return {
        "ticker": ticker.upper(),
        "window_days": days,
        "total": len(events),
        "events": [_to_dto(e) for e in events],
        "sandbox": True,
    }


@router.post("/events/8k/classify", summary="8-K 文本分类(沙箱调试用)")
async def post_classify(payload: dict) -> dict:
    """给定 8-K body 文本,返 category 判定(便于自测 + 调试)。"""
    text = payload.get("text", "")
    return {"text_length": len(text), "category": classify_summary(text)}