"""M7-t5 BD-051 EDGAR full-text search 8-K Item 8.01 真实数据源 — 沙箱 stub。

数据源链路(生产 vs 沙箱):
- 生产:httpx.AsyncClient → https://efts.sec.gov/LATEST/search-index?q=...&forms=8-K
- 沙箱:无 httpx → 本模块 `_seeded_float` + 关键词映射合成 deterministic 8-K filing

合规:
- 不做投资建议;summary 仅展示 EDGAR 原文摘录前 200 字
- 不返 mock 200 伪装成功(沙箱显式标注 `review_mode=sandbox_stub`)
- 关键词表与 `app/services/eight_k.py:30-56` CATEGORY_KEYWORDS 同步,扩展需 review
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

EventCategory = Literal[
    "share-repurchase",
    "material-agreement",
    "press-release",
    "other",
]

# 关键词映射(与 app/services/eight_k.py:30-56 CATEGORY_KEYWORDS 同步)
CATEGORY_KEYWORDS: dict[EventCategory, tuple[str, ...]] = {
    "share-repurchase": (
        "share repurchase",
        "buyback",
        "repurchase program",
        "repurchase plan",
        "share buyback",
        "treasury stock",
        "authoriz",
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

# 沙箱 stub 合成参数
SANDBOX_REVIEW_MODE = "sandbox_stub"
EDGAR_BASE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
MAX_FILINGS_PER_TICKER = 5
DEFAULT_LOOKBACK_DAYS = 180

# 11 已知 ticker → CIK(从 eight_k.py fixture + 31 事件 goldset 抽)
_KNOWN_CIK: dict[str, str] = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "TSLA": "0001318605",
    "NVDA": "0001045810",
    "GME": "0001326380",
    "AMC": "0001411579",
    "BBBY": "0000886158",
    "KOSS": "0000056701",
    "BB": "0001070235",
    "WISH": "0001824502",
    "NOK": "0000924613",
    "META": "0001326801",
    "NFLX": "0001065280",
    "SNAP": "0001564408",
    "COIN": "0001679788",
    "HOOD": "0001783879",
    "CVNA": "0001690820",
    "PTON": "0001639825",
    "AMZN": "0001018724",
    "GOOG": "0001652044",
    "ORCL": "0001341439",
    "INTC": "0000050863",
    "AMD": "0000002488",
    "BABA": "0001577552",
    "PYPL": "0001633917",
    "DIS": "0001744489",
    "BA": "0000012927",
}


@dataclass
class EdgarFiling:
    """EDGAR 8-K Item 8.01 filing 记录(沙箱 stub 形态)。"""

    ticker: str
    cik: str
    accession: str
    filed_at: str  # ISO 8601 UTC
    form: str = "8-K"
    item: str = "8.01"
    category: EventCategory = "other"
    title: str = ""
    summary: str = ""
    url: str = ""
    matched_keywords: list[str] = field(default_factory=list)
    review_mode: str = SANDBOX_REVIEW_MODE

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EdgarFetchResult:
    """EDGAR full-text search 拉取结果汇总。"""

    tickers_requested: list[str]
    tickers_with_filings: int
    total_filings: int
    filings_by_category: dict[str, int]
    sandbox: bool
    fetched_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seeded_float(s: str) -> float:
    """deterministic 0.0~1.0(seed=s 的 sha256 头 8 字节 / 0xFFFFFFFF)。"""
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _pick_category(ticker: str, idx: int) -> EventCategory:
    """按 ticker + idx 确定性选 category(均匀分布 + 略偏 share-repurchase)。"""
    u = _seeded_float(f"{ticker}|{idx}|category")
    # 40% share-repurchase / 25% material-agreement / 25% press-release / 10% other
    if u < 0.40:
        return "share-repurchase"
    if u < 0.65:
        return "material-agreement"
    if u < 0.90:
        return "press-release"
    return "other"


def _pick_filed_offset_days(ticker: str, idx: int, lookback_days: int) -> int:
    """按 ticker + idx 确定性选 filed_at 距离 today 的天数(0~lookback_days)。"""
    u = _seeded_float(f"{ticker}|{idx}|filed_offset")
    return int(u * lookback_days)


def _pick_summary(ticker: str, category: EventCategory, idx: int) -> tuple[str, list[str]]:
    """合成 8-K summary(≤200 字)+ 命中关键词。"""
    base = {
        "share-repurchase": (
            f"{ticker} 董事会批准新增股票回购授权,执行窗口 36 个月。"
            f"管理层将在后续 10-Q / 10-K 中披露实际回购情况。"
        ),
        "material-agreement": (
            f"{ticker} 宣布与战略合作方签署 material agreement,合作期 5 年。"
            f"协议涉及金额在后续 8-K 附件中详细披露。"
        ),
        "press-release": (
            f"{ticker} issues press release,announces 季度财报亮点 + 业务进展。"
            f"完整数据将同步至投资者关系页面。"
        ),
        "other": (
            f"{ticker} 向 SEC 提交 8-K Other Events 报告,内容涉及公司治理 / 合规事项。"
        ),
    }
    body = base[category]
    # 截断到 ≤200 字
    if len(body) > 200:
        body = body[:197] + "..."
    matched = list(CATEGORY_KEYWORDS.get(category, ()))[:2]
    return body, matched


def _make_accession(ticker: str, idx: int, filed_at: str) -> str:
    """合成 EDGAR accession 号(CIK + 年份 + 序号)。"""
    h = hashlib.sha256(f"{ticker}|{idx}|{filed_at}|accession".encode()).hexdigest()
    seq = int(h[:6], 16) % 1000000
    year = filed_at[:4]
    cik = _KNOWN_CIK.get(ticker, "0000000000")
    return f"{cik}-{year[2:]}-{seq:06d}"


def fetch_fulltext_sandbox(
    tickers: list[str],
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_per_ticker: int = MAX_FILINGS_PER_TICKER,
    reference_date: datetime | None = None,
) -> tuple[EdgarFetchResult, list[EdgarFiling]]:
    """EDGAR full-text search 沙箱 stub。

    Args:
        tickers: 关注的 ticker 列表
        lookback_days: 回溯天数(默认 180 天)
        max_per_ticker: 每 ticker 最多合成多少条 8-K(默认 5)
        reference_date: 参考日期(默认 today UTC),沙箱自测用

    Returns:
        (result_summary, filings_list)
    """
    ref = reference_date or datetime.now(timezone.utc)
    filings: list[EdgarFiling] = []
    cat_counter: dict[str, int] = {c: 0 for c in CATEGORY_KEYWORDS}
    cat_counter["other"] = 0
    tickers_with: set[str] = set()

    for ticker in tickers:
        # 每 ticker 合成 1~max_per_ticker 条 filing
        u_count = _seeded_float(f"{ticker}|filing_count")
        n_filings = 1 + int(u_count * max_per_ticker)
        cik = _KNOWN_CIK.get(ticker, "0000000000")

        for idx in range(n_filings):
            offset_days = _pick_filed_offset_days(ticker, idx, lookback_days)
            filed_dt = ref - timedelta(days=offset_days)
            filed_at = filed_dt.replace(microsecond=0).isoformat()
            category = _pick_category(ticker, idx)
            summary, matched = _pick_summary(ticker, category, idx)
            accession = _make_accession(ticker, idx, filed_at)
            url = f"{EDGAR_BASE_URL}?action=getcompany&CIK={cik}&type=8-K&dateRange=custom&startdt={filed_at[:10]}&enddt={filed_at[:10]}"

            filings.append(EdgarFiling(
                ticker=ticker,
                cik=cik,
                accession=accession,
                filed_at=filed_at,
                category=category,
                title=f"{ticker} - 8-K {category}",
                summary=summary,
                url=url,
                matched_keywords=matched,
                review_mode=SANDBOX_REVIEW_MODE,
            ))
            cat_counter[category] += 1
            tickers_with.add(ticker)

    filings.sort(key=lambda f: (f.ticker, f.filed_at), reverse=True)
    result = EdgarFetchResult(
        tickers_requested=sorted(tickers),
        tickers_with_filings=len(tickers_with),
        total_filings=len(filings),
        filings_by_category=cat_counter,
        sandbox=True,
        fetched_at=_now_iso(),
    )
    return result, filings


def write_jsonl(
    result: EdgarFetchResult,
    filings: list[EdgarFiling],
    out_path: Path,
) -> Path:
    """落 JSONL:第 1 行 = result summary,后续 = filings。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(result.to_dict(), ensure_ascii=False)]
    lines.extend(json.dumps(f.to_dict(), ensure_ascii=False) for f in filings)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def load_jsonl(in_path: Path) -> tuple[dict, list[dict]]:
    """读 JSONL:第 1 行 = result summary,后续 = filings。"""
    lines = [l for l in in_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    summary = json.loads(lines[0])
    filings = [json.loads(l) for l in lines[1:]]
    return summary, filings


def classify_summary(text: str) -> EventCategory:
    """给定 8-K body 摘要,判定 category(与 eight_k.py 同步)。"""
    if not text:
        return "other"
    lower = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return cat
    return "other"


def main() -> int:
    """CLI:合成 stub filings + 落 JSONL。"""
    import argparse

    parser = argparse.ArgumentParser(description="EDGAR full-text search sandbox stub (m7t5)")
    parser.add_argument("--output", type=str, default="data/edgar_8k_sandbox.jsonl")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--max-per-ticker", type=int, default=MAX_FILINGS_PER_TICKER)
    args = parser.parse_args()

    # 31 ticker(从 backtest_event_goldset 抽;沙箱只取集合)
    tickers = sorted(set(_KNOWN_CIK.keys()))
    result, filings = fetch_fulltext_sandbox(
        tickers, lookback_days=args.lookback_days, max_per_ticker=args.max_per_ticker
    )
    out_path = Path(args.output)
    write_jsonl(result, filings, out_path)

    print(json.dumps({
        "output": str(out_path),
        "result": result.to_dict(),
        "sample_filings": [f.to_dict() for f in filings[:3]],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())