"""V1.5 接力期 m9t4 — EDGAR fulltext 端点暴露。

8-K Item 8.01 全市场 / 自选 ticker EDGAR full-text search 端点。
复用 backend/etl/edgar_fulltext.py 的 fetch_fulltext_sandbox 作为沙箱实现。

端点:
  GET /api/v1/edgar/search
    参数:
      query        str (可选) — 关键词(预留,沙箱 stub 不解析)
      tickers      str (可选,逗号分隔) — 限定 ticker,默认 11 已知 ticker
      from_date    str (可选,YYYY-MM-DD) — filed_at 下界
      to_date      str (可选,YYYY-MM-DD) — filed_at 上界
      category     str (可选,4 类之一) — share-repurchase / material-agreement
                                          / press-release / other
      limit        int (可选,1-50)     — 最多返多少条 filing
    返回:
      {
        "summary": EdgarFetchResult.to_dict(),
        "filings": [EdgarFiling.to_dict(), ...],
        "sandbox": true,
        "review_mode": "sandbox_stub",
        "query_meta": { "query": ..., "tickers": [...], "filters": {...} }
      }

沙箱 fallback 显式标注:
  - 无 EDGAR_API_KEY 或 httpx 不可用时 → 调 fetch_fulltext_sandbox()
  - review_mode="sandbox_stub" 始终在响应中显式标注
  - 严禁 mock 200 伪装成功(M5 锁定)

V1.5.1 freeze:
  - 本端点加入 /api/v1/edgar/* 路径组
  - OpenAPI schema 增 query/tickers/from_date/to_date/category/limit 6 字段
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from etl.edgar_fulltext import (
    CATEGORY_KEYWORDS,
    DEFAULT_LOOKBACK_DAYS,
    EdgarFetchResult,
    EdgarFiling,
    fetch_fulltext_sandbox,
)
from etl.edgar_real import (
    PRODUCTION_REVIEW_MODE,
    SANDBOX_FALLBACK_REVIEW_MODE,
    fetch_fulltext_sec_httpx,
)

router = APIRouter()

Category = Literal["share-repurchase", "material-agreement", "press-release", "other"]


def _parse_tickers(raw: str | None) -> list[str]:
    """逗号分隔 ticker 字符串 → list(去空 + 大写)。"""
    if not raw:
        return []
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _parse_date(s: str | None, *, name: str) -> str | None:
    """YYYY-MM-DD 校验 + 标准化为 ISO 8601。"""
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"{name} 格式错(应 YYYY-MM-DD):{e}") from None


def _resolve_tickers(tickers_param: list[str]) -> list[str]:
    """若无指定 ticker,用 11 已知默认集(同 m7t5)。"""
    if tickers_param:
        return tickers_param
    # 默认 11 已知 ticker(从 edgar_fulltext._KNOWN_CIK 抽前 11 个,保持稳定)
    default = ("AAPL", "MSFT", "TSLA", "NVDA", "GME", "AMC", "BBBY",
               "KOSS", "BB", "WISH", "NOK")
    return list(default)


@router.get("/search", summary="EDGAR full-text search(sandbox_stub)")
async def search_edgar(
    query: str | None = Query(default=None, description="关键词(沙箱 stub 不解析)"),
    tickers: str | None = Query(default=None, description="逗号分隔 ticker,空=默认 11 ticker"),
    from_date: str | None = Query(default=None, description="filed_at 下界 YYYY-MM-DD"),
    to_date: str | None = Query(default=None, description="filed_at 上界 YYYY-MM-DD"),
    category: Category | None = Query(default=None, description="4 类 category 之一"),
    limit: int = Query(default=20, ge=1, le=50, description="最多 filing 数(1-50)"),
) -> dict:
    """EDGAR full-text search(V1.5.2 双轨:真实 httpx → sandbox fallback)。

    优先 httpx → https://efts.sec.gov/LATEST/search-index(需 SEC_API_USER_AGENT 环境变量)
    失败(无 httpx / 无 UA / 4xx-5xx / 超时 / 网络错)→ fallback fetch_fulltext_sandbox

    响应含 sandbox + review_mode + fetch_source + latency_ms + http_status + warning 字段,
    任何路径绝不 mock 200 伪装。
    """
    tickers_list = _resolve_tickers(_parse_tickers(tickers))
    from_iso = _parse_date(from_date, name="from_date")
    to_iso = _parse_date(to_date, name="to_date")

    # V1.5.2 双轨:优先 httpx → SEC EDGAR full-text search API,sandbox 内嵌 fallback
    import asyncio as _asyncio

    real_result, filings = _asyncio.run(fetch_fulltext_sec_httpx(
        tickers_list,
        query=query,
        from_date=from_iso,
        to_date=to_iso,
        lookback_days=DEFAULT_LOOKBACK_DAYS,
    ))
    # real_result 已是 EdgarRealFetchResult(to_dict 含 fetch_source / review_mode / http_status)
    sandbox = real_result.sandbox

    # 应用 category 过滤
    if category:
        filings = [f for f in filings if f.category == category]

    # 应用日期范围过滤(filed_at 是 ISO datetime)
    if from_iso:
        filings = [f for f in filings if f.filed_at[:10] >= from_iso]
    if to_iso:
        filings = [f for f in filings if f.filed_at[:10] <= to_iso]

    # 应用 limit
    filings = filings[:limit]

    # 构造 summary(向后兼容 EdgarFetchResult.to_dict())
    summary_dict = {
        "tickers_requested": real_result.tickers_requested,
        "tickers_with_filings": real_result.tickers_with_filings,
        "total_filings": real_result.total_filings,
        "filings_by_category": real_result.filings_by_category,
        "sandbox": sandbox,
        "fetched_at": real_result.fetched_at,
    }

    return {
        "summary": summary_dict,
        "filings": [f.to_dict() for f in filings],
        "sandbox": sandbox,
        "review_mode": real_result.review_mode,
        "fetch_source": real_result.fetch_source,
        "http_status": real_result.http_status,
        "latency_ms": real_result.latency_ms,
        "warning": real_result.warning,
        "query_meta": {
            "query": query,
            "tickers": tickers_list,
            "from_date": from_iso,
            "to_date": to_iso,
            "category": category,
            "limit": limit,
        },
        "disclaimer": (
            "V1.5.2 双轨:真实 httpx → SEC EDGAR full-text search API(需 SEC_API_USER_AGENT);"
            "失败自动 fallback sandbox_stub,显式 fetch_source + warning 标注,严禁 mock 200 伪装。"
        ),
    }


@router.get("/categories", summary="EDGAR 4 类 category 列表")
async def list_categories() -> dict:
    """EDGAR 8-K Item 8.01 4 类 category 关键词表(与 eight_k.py 同步)。"""
    return {
        "categories": list(CATEGORY_KEYWORDS.keys()),
        "keywords": {k: list(v) for k, v in CATEGORY_KEYWORDS.items()},
        "review_mode": "sandbox_stub",
    }
