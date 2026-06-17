"""M10-t1 BD-051 EDGAR full-text search 8-K Item 8.01 真实数据源 — httpx → efts.sec.gov。

数据源链路(生产 vs 沙箱):
- 生产:httpx.AsyncClient → https://efts.sec.gov/LATEST/search-index?q=...&forms=8-K
  User-Agent 必填(SEC 强制要求,格式 "AppName admin@example.com")
  Rate limit:10 req/s(官方建议 0.1s 间隔,本模块用 0.15s)
  尊重 Retry-After header
- 沙箱:httpx 不可用 / 4xx-5xx / 超时 → fallback `etl/edgar_fulltext.py:fetch_fulltext_sandbox`

合规:
- 不做投资建议;summary 仅展示 EDGAR 原文摘录前 200 字(沿用 m7t5)
- 不返 mock 200 伪装成功(httpx 失败时显式标注 `review_mode=sandbox_stub` + `fetch_source=sandbox_stub` + `warning`)
- 真实模式 `review_mode=production_real` + `fetch_source=sec_httpx`
- SEC API rate limit 严格执行,避免被 SEC 临时封禁

环境变量:
- SEC_API_USER_AGENT:必填,格式 "Hunter Radar admin@hunter-radar.example"
- SEC_API_BASE_URL:可选,默认 "https://efts.sec.gov/LATEST/search-index"
- SEC_API_RATE_LIMIT_SEC:可选,默认 0.15(秒)
- SEC_API_TIMEOUT_SEC:可选,默认 15.0
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

# 探测 httpx 是否可用(沙箱 fallback 用)
try:
    import httpx  # type: ignore[import-untyped]
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# 沿用 m7t5 sandbox 模块的常量 + dataclass
from etl.edgar_fulltext import (  # noqa: E402
    CATEGORY_KEYWORDS,
    DEFAULT_LOOKBACK_DAYS,
    EDGAR_BASE_URL,
    EdgarFetchResult,
    EdgarFiling,
    MAX_FILINGS_PER_TICKER,
    SANDBOX_REVIEW_MODE,
    _KNOWN_CIK,
    classify_summary,
    fetch_fulltext_sandbox,
)

# 真实模式常量
PRODUCTION_REVIEW_MODE = "production_real"
SANDBOX_FALLBACK_REVIEW_MODE = "sandbox_stub"

# SEC API 配置
SEC_API_BASE_URL_DEFAULT = "https://efts.sec.gov/LATEST/search-index"
SEC_API_RATE_LIMIT_DEFAULT = 0.15  # 秒,保守一点(SEC 官方建议 0.1s)
SEC_API_TIMEOUT_DEFAULT = 15.0


def _get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


@dataclass
class EdgarRealFetchResult:
    """EDGAR 真实 httpx 拉取结果(含 fallback 信息)。"""

    tickers_requested: list[str]
    tickers_with_filings: int
    total_filings: int
    filings_by_category: dict[str, int]
    fetched_at: str
    fetch_source: str  # "sec_httpx" | "sandbox_stub"
    review_mode: str  # PRODUCTION_REVIEW_MODE | SANDBOX_FALLBACK_REVIEW_MODE
    sandbox: bool
    http_status: int | None = None
    latency_ms: int | None = None
    warning: str | None = None
    query_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_agent_ok(ua: str | None) -> bool:
    """SEC 要求 User-Agent 含 AppName + 邮箱(可联系)。"""
    if not ua:
        return False
    if "@" not in ua:
        return False
    if len(ua) < 10:
        return False
    return True


def _parse_sec_filing(hit: dict[str, Any]) -> EdgarFiling | None:
    """解析 SEC EDGAR full-text search 单条 hit → EdgarFiling。

    真实 SEC 响应结构(简化):
    {
      "_id": "...",
      "_source": {
        "adsh": "0000320193-23-000106",         # accession
        "display_names": ["Apple Inc (AAPL)"],
        "file_date": "2023-11-03",              # YYYY-MM-DD
        "form": "8-K",
        "ciks": ["0000320193"],
        "file_description": "8-K",
        "ticker": "AAPL"
      },
      "_highlight": { ... }
    }
    """
    src = hit.get("_source", {})
    if not src:
        return None
    form = src.get("form", "")
    if form != "8-K":
        return None
    ticker = (src.get("ticker") or "").upper()
    if not ticker:
        # 从 display_names 抽 ticker
        display = src.get("display_names", [])
        if display:
            # 格式: "Apple Inc (AAPL)"
            name = display[0]
            if "(" in name and ")" in name:
                ticker = name.split("(")[-1].rstrip(")").upper()
    if not ticker:
        return None
    accession = src.get("adsh", "")
    file_date = src.get("file_date", "")  # YYYY-MM-DD
    if not file_date:
        return None
    filed_at = f"{file_date}T00:00:00+00:00"  # SEC 只给日期,补 UTC 0 时
    cik = (src.get("ciks") or ["0000000000"])[0]
    # 标题 / 摘要:从 file_description 抽
    title = src.get("file_description", f"{ticker} - 8-K")
    summary = title  # SEC 摘要不含原文,只展示 description 前 200 字
    if len(summary) > 200:
        summary = summary[:197] + "..."
    # 类别:从 description 文本 classify(沿用 CATEGORY_KEYWORDS)
    category: Literal["share-repurchase", "material-agreement", "press-release", "other"] = classify_summary(summary)
    url = f"{EDGAR_BASE_URL}?action=getcompany&CIK={cik}&type=8-K&dateRange=custom&startdt={file_date}&enddt={file_date}"
    matched = list(CATEGORY_KEYWORDS.get(category, ()))[:2]
    return EdgarFiling(
        ticker=ticker,
        cik=cik,
        accession=accession,
        filed_at=filed_at,
        form=form,
        item="8.01",
        category=category,
        title=title,
        summary=summary,
        url=url,
        matched_keywords=matched,
        review_mode=PRODUCTION_REVIEW_MODE,
    )


async def fetch_fulltext_sec_httpx(
    tickers: list[str],
    *,
    query: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_per_ticker: int = MAX_FILINGS_PER_TICKER,
) -> tuple[EdgarRealFetchResult, list[EdgarFiling]]:
    """EDGAR full-text search 真实 httpx 调用(sandbox fallback 内嵌)。

    优先 httpx → SEC EDGAR full-text search API
    失败(无 httpx / 无 User-Agent / 4xx-5xx / 超时 / 网络错)→ fallback sandbox

    Args:
        tickers: 关注的 ticker 列表
        query: 关键词(可选)
        from_date / to_date: YYYY-MM-DD 时间范围(可选)
        lookback_days: 回溯天数(仅 sandbox fallback 用)
        max_per_ticker: 每 ticker 最多 filing 数(仅 sandbox fallback 用)

    Returns:
        (result, filings):result 含 fetch_source / review_mode / http_status / latency_ms
    """
    ua = _get_env("SEC_API_USER_AGENT")
    base_url = _get_env("SEC_API_BASE_URL", SEC_API_BASE_URL_DEFAULT)
    rate_limit = float(_get_env("SEC_API_RATE_LIMIT_SEC", str(SEC_API_RATE_LIMIT_DEFAULT)))
    timeout = float(_get_env("SEC_API_TIMEOUT_SEC", str(SEC_API_TIMEOUT_DEFAULT)))
    fetched_at = _now_iso()

    # 无 httpx → fallback sandbox
    if not HTTPX_AVAILABLE:
        result, filings = fetch_fulltext_sandbox(tickers, lookback_days=lookback_days, max_per_ticker=max_per_ticker)
        return EdgarRealFetchResult(
            tickers_requested=result.tickers_requested,
            tickers_with_filings=result.tickers_with_filings,
            total_filings=result.total_filings,
            filings_by_category=result.filings_by_category,
            fetched_at=fetched_at,
            fetch_source="sandbox_stub",
            review_mode=SANDBOX_FALLBACK_REVIEW_MODE,
            sandbox=True,
            http_status=None,
            latency_ms=None,
            warning="httpx 未安装,fallback 到 sandbox_stub",
            query_meta={"reason": "httpx_unavailable", "tickers": tickers},
        ), filings

    # 无 User-Agent → fallback sandbox
    if not _user_agent_ok(ua):
        result, filings = fetch_fulltext_sandbox(tickers, lookback_days=lookback_days, max_per_ticker=max_per_ticker)
        return EdgarRealFetchResult(
            tickers_requested=result.tickers_requested,
            tickers_with_filings=result.tickers_with_filings,
            total_filings=result.total_filings,
            filings_by_category=result.filings_by_category,
            fetched_at=fetched_at,
            fetch_source="sandbox_stub",
            review_mode=SANDBOX_FALLBACK_REVIEW_MODE,
            sandbox=True,
            http_status=None,
            latency_ms=None,
            warning="SEC_API_USER_AGENT 未设或格式错(需含邮箱),fallback 到 sandbox_stub",
            query_meta={"reason": "user_agent_invalid", "ua_provided": bool(ua)},
        ), filings

    # 真实 httpx 调用
    params: dict[str, str] = {"forms": "8-K"}
    if query:
        params["q"] = query
    if from_date:
        params["startdt"] = from_date
    if to_date:
        params["enddt"] = to_date
    else:
        # 默认回溯 180 天
        today = datetime.now(timezone.utc)
        start = today - timedelta(days=lookback_days)
        params["startdt"] = start.strftime("%Y-%m-%d")
        params["enddt"] = today.strftime("%Y-%m-%d")

    headers = {
        "User-Agent": ua,
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "Host": "efts.sec.gov",
    }

    started = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            if resp.status_code != 200:
                # SEC 4xx-5xx → fallback sandbox(不 mock 200 伪装)
                warning = f"SEC API 返 HTTP {resp.status_code},fallback 到 sandbox_stub"
                result, filings = fetch_fulltext_sandbox(
                    tickers, lookback_days=lookback_days, max_per_ticker=max_per_ticker
                )
                return EdgarRealFetchResult(
                    tickers_requested=result.tickers_requested,
                    tickers_with_filings=result.tickers_with_filings,
                    total_filings=result.total_filings,
                    filings_by_category=result.filings_by_category,
                    fetched_at=fetched_at,
                    fetch_source="sandbox_stub",
                    review_mode=SANDBOX_FALLBACK_REVIEW_MODE,
                    sandbox=True,
                    http_status=resp.status_code,
                    latency_ms=latency_ms,
                    warning=warning,
                    query_meta={"params": params},
                ), filings

            payload = resp.json()
            hits = payload.get("hits", {}).get("hits", [])
            filings = []
            for hit in hits:
                filing = _parse_sec_filing(hit)
                if filing is None:
                    continue
                # 过滤 ticker(只保留请求的)
                if filing.ticker not in [t.upper() for t in tickers]:
                    continue
                filings.append(filing)
                if sum(1 for f in filings if f.ticker == filing.ticker) >= max_per_ticker:
                    continue

            # 速率限制:等待下一次请求(SEC 官方建议 ≤10 req/s)
            await asyncio.sleep(rate_limit)

            cat_counter: dict[str, int] = {c: 0 for c in CATEGORY_KEYWORDS}
            cat_counter["other"] = 0
            tickers_with: set[str] = set()
            for f in filings:
                cat_counter[f.category] += 1
                tickers_with.add(f.ticker)

            filings.sort(key=lambda f: (f.ticker, f.filed_at), reverse=True)
            return EdgarRealFetchResult(
                tickers_requested=sorted(tickers),
                tickers_with_filings=len(tickers_with),
                total_filings=len(filings),
                filings_by_category=cat_counter,
                fetched_at=fetched_at,
                fetch_source="sec_httpx",
                review_mode=PRODUCTION_REVIEW_MODE,
                sandbox=False,
                http_status=resp.status_code,
                latency_ms=latency_ms,
                warning=None,
                query_meta={"params": params, "raw_hits": len(hits)},
            ), filings
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as e:
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        warning = f"httpx 异常({type(e).__name__}: {e}),fallback 到 sandbox_stub"
        result, filings = fetch_fulltext_sandbox(
            tickers, lookback_days=lookback_days, max_per_ticker=max_per_ticker
        )
        return EdgarRealFetchResult(
            tickers_requested=result.tickers_requested,
            tickers_with_filings=result.tickers_with_filings,
            total_filings=result.total_filings,
            filings_by_category=result.filings_by_category,
            fetched_at=fetched_at,
            fetch_source="sandbox_stub",
            review_mode=SANDBOX_FALLBACK_REVIEW_MODE,
            sandbox=True,
            http_status=None,
            latency_ms=latency_ms,
            warning=warning,
            query_meta={"reason": "httpx_error", "error_type": type(e).__name__},
        ), filings
    except Exception as e:  # noqa: BLE001
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        warning = f"未知异常({type(e).__name__}: {e}),fallback 到 sandbox_stub"
        result, filings = fetch_fulltext_sandbox(
            tickers, lookback_days=lookback_days, max_per_ticker=max_per_ticker
        )
        return EdgarRealFetchResult(
            tickers_requested=result.tickers_requested,
            tickers_with_filings=result.tickers_with_filings,
            total_filings=result.total_filings,
            filings_by_category=result.filings_by_category,
            fetched_at=fetched_at,
            fetch_source="sandbox_stub",
            review_mode=SANDBOX_FALLBACK_REVIEW_MODE,
            sandbox=True,
            http_status=None,
            latency_ms=latency_ms,
            warning=warning,
            query_meta={"reason": "unknown_error", "error_type": type(e).__name__},
        ), filings


def main() -> int:
    """CLI:真实 httpx → SEC EDGAR API(沙箱 fallback 内嵌)。"""
    import argparse

    parser = argparse.ArgumentParser(description="EDGAR full-text search real httpx (m10t1)")
    parser.add_argument("--tickers", type=str, default="AAPL,MSFT,TSLA", help="逗号分隔 ticker")
    parser.add_argument("--query", type=str, default=None, help="关键词")
    parser.add_argument("--from-date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--to-date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--max-per-ticker", type=int, default=MAX_FILINGS_PER_TICKER)
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    result, filings = asyncio.run(fetch_fulltext_sec_httpx(
        tickers,
        query=args.query,
        from_date=args.from_date,
        to_date=args.to_date,
        lookback_days=args.lookback_days,
        max_per_ticker=args.max_per_ticker,
    ))

    print(json.dumps({
        "result": result.to_dict(),
        "sample_filings": [f.to_dict() for f in filings[:3]],
        "httpx_available": HTTPX_AVAILABLE,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())