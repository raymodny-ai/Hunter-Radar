"""SEC EDGAR Form 4 抓取 + CIK 解析(BD-006)。

M2 启动:实装 ticker→CIK 解析 + submissions 拉取 + Form 4 解析。

数据源:
- ticker→CIK 索引:SEC 公开的 https://www.sec.gov/files/company_tickers.json
- 拉 submissions:https://data.sec.gov/submissions/CIK{cik10}.json
  (cik 必须补零到 10 位)
- User-Agent: 必须含邮箱,否则 SEC 会 403

沙箱环境:httpx 不可达 → 友好返回空列表,留给 pipeline 写 status='pending_disclosure'。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Symbol

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Form4Row:
    symbol: str
    insider_name: str
    insider_role: str
    txn_date: date
    filed_at: date
    direction: str
    qty: int
    price: float | None
    form_url: str


# 角色归一化(SEC 报告原始 officerTitle → services.insider 期望的枚举)
_DIRECTION_MAP: dict[str, str] = {
    "D": "sell",       # 直接/间接 持有变更
    "F": "sell",       # 缴税代扣(也归 sell)
    "I": "sell",       # 间接
    "M": "exercise",   # 转换/行权(BD-051 buyback 对齐时排除)
    "A": "grant",      # 授予
    "G": "grant",      # 礼物
    "C": "exercise",
    "S": "sell",       # 直接卖出
    "P": "buy",        # 公开市场买入
}


def _normalize_role(officer_title: str | None, director: bool, is_ten_pct: bool) -> str:
    """SEC officerTitle + director flag + 10% holder → 关键内部人枚举。"""
    if is_ten_pct:
        return "10% Holder"
    if director:
        return "Director"
    t = (officer_title or "").upper()
    if "CEO" in t or "CHIEF EXECUTIVE" in t:
        return "CEO"
    if "CFO" in t or "CHIEF FINANCIAL" in t or "CHIEF FINANCE" in t:
        return "CFO"
    return "Other"  # 透传给 services.is_key_insider 判否


def _normalize_direction(code: str) -> str:
    return _DIRECTION_MAP.get((code or "").upper(), "sell")


# ---- HTTP 包装(限流 + User-Agent) ----


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
async def _sec_get(client: httpx.AsyncClient, url: str) -> dict:
    r = await client.get(url)
    r.raise_for_status()
    return r.json()


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
async def _sec_get_text(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url)
    r.raise_for_status()
    return r.text


def _parse_form4_html(html: str) -> dict:
    """从 Form 4 HTML/XML 抽 3 个字段:reporting_person_name, role_summary, first_txn。
    
    2026-07-28: 轻量级抽取(适应 SEC 各种 HTML 包装变体)。逐行 re。
    返回 dict;解析失败字段返空。不用 BeautifulSoup(避免多 dep)。
    """
    out: dict = {
        "reporting_person_name": "",
        "officer_title": "",
        "is_director": False,
        "is_ten_pct": False,
        "first_txn_qty": 0,
        "first_txn_price": None,
        "first_txn_code": "",
    }
    # 1) reporting person name — <a href="/cgi-bin/browse-edgar?action=getcompany&CIK=XXXXX">NAME</a>
    #    在 Header 区段出现 1次(以下可能有 Issuer Name 别名但 action=getcompany 才是 reporting person)
    m = re.search(
        r'<a\s+href="/cgi-bin/browse-edgar\?action=getcompany&amp;CIK=\d+">([^<]+)</a>',
        html,
    )
    if m:
        out["reporting_person_name"] = m.group(1).strip()
    # 2) role checkboxes — 'Director' 行 有 'FormData">X</span>' 表示选中
    #    文本检测:简单正则
    out["is_director"] = bool(re.search(r"Director[^<]*</td>\s*<td[^>]*>\s*<span class=\"FormData\">X</span>", html))
    out["is_ten_pct"] = bool(re.search(r"10% Owner[^<]*</td>\s*<td[^>]*>\s*<span class=\"FormData\">X</span>", html))
    # 3) officer title — 'Officer (give title below)' 后面 <td> 里的 <td style="color: blue">TITLE</td>
    m = re.search(r"Officer\s*\(give title below\)</td>\s*<td[^>]*></td>\s*<td[^>]*></td>\s*<td[^>]*>([^<]+)</td>", html)
    if m:
        out["officer_title"] = m.group(1).strip()
    # 4) first non-derivative transaction — Table I 第一个 <tbody><tr>
    #    抽取 transaction code (S/P/A/F) + Amount + Price
    m = re.search(
        r"<tbody>\s*<tr>\s*<td[^>]*>[^<]*</td>\s*"  # Title of Security
        r"<td[^>]*><span class=\"FormData\">([^<]+)</span></td>\s*"  # Txn Date
        r"<td[^>]*></td>\s*"  # Deemed Execution
        r"<td[^>]*><span class=\"(?:Small)?FormData\">([A-Z])</span>"  # Txn Code
        r"(?:<span[^<]*<sup>\(\d+\)</sup></span>)?"
        r"</td>\s*"
        r"<td[^>]*></td>\s*"  # V
        r"<td[^>]*><span class=\"FormData\">([0-9,\.]+)</span></td>\s*"  # Amount
        r"<td[^>]*><span class=\"FormData\">([AD])</span></td>\s*"  # A or D
        r"<td[^>]*>.*?<span class=\"FormData\">([0-9,\.]*)</span>",
        html,
        re.DOTALL,
    )
    if m:
        try:
            out["first_txn_code"] = m.group(2).strip()
            out["first_txn_qty"] = int(m.group(3).replace(",", "").split(".")[0])
            price_str = m.group(5).strip().replace(",", "")
            if price_str:
                out["first_txn_price"] = float(price_str)
        except (ValueError, IndexError):
            pass
    return out


# ---- 1) ticker → CIK 索引(可缓存到内存) ----


_CIK_CACHE: dict[str, str] = {}


async def _load_cik_index(force: bool = False) -> dict[str, str]:
    """从 SEC 公开索引拿 ticker → CIK10(零补齐) 映射。

    返回:{ticker_upper: cik10_str}
    沙箱不可达时返回空 dict,不抛异常。
    """
    if _CIK_CACHE and not force:
        return _CIK_CACHE
    url = f"{settings.sec_edgar_base}/files/company_tickers.json"
    headers = {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            data = await _sec_get(client, url)
    except httpx.HTTPError as e:
        log.warning("sec.cik_index.fetch.fail", error=str(e)[:200])
        return {}

    # 真实格式:{"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    mapping: dict[str, str] = {}
    for v in data.values():
        if not isinstance(v, dict):
            continue
        ticker = str(v.get("ticker", "")).strip().upper()
        cik = v.get("cik_str")
        if ticker and cik is not None:
            mapping[ticker] = str(cik).zfill(10)
    _CIK_CACHE.update(mapping)
    log.info("sec.cik_index.loaded", size=len(mapping))
    return mapping


def _cik_to_url(cik10: str) -> str:
    """CIK10 → submissions URL。"""
    return f"{settings.sec_edgar_base}/submissions/CIK{cik10}.json"


def _form4_index_url(cik10: str) -> str:
    """Form 4 全文 JSON 在 EDGAR Archives(本期 stub,直接走 submissions.recent)。"""
    return _cik_to_url(cik10)


# ---- 2) 解析 recent.form4 数组 ----


def _parse_recent_form4(
    symbol: str, recent: dict[str, Any], since: date, *, cik10: str = ""
) -> list[Form4Row]:
    """从 submissions.recent 提取 Form 4 记录,过滤 txn_date >= since。

    recent 含并行数组:form, transactionDate(=reportDate), transactionCode,
    rptOwnerName, officerTitle, isDirector, isTenPercentOwner, transactionShares,
    transactionPrice, primaryDocument, filingDate

    2026-07-28 fix: SEC submissions API 字段名为 reportDate 不是 transactionDate。
    保留 transactionDate 优先 (兼容未来变化)。
    """
    form = recent.get("form", []) or []
    txn_dates = (
        recent.get("transactionDate")
        or recent.get("reportDate")
        or []
    )
    txn_codes = recent.get("transactionCode", []) or []
    names = recent.get("rptOwnerName", []) or []
    titles = recent.get("officerTitle", []) or []
    is_dir = recent.get("isDirector", []) or []
    is_10 = recent.get("isTenPercentOwner", []) or []
    qtys = recent.get("transactionShares", []) or []
    prices = recent.get("transactionPrice", []) or []
    prim_docs = recent.get("primaryDocument", []) or []
    filed = recent.get("filingDate", []) or []
    acc = recent.get("accessionNumber", []) or []

    rows: list[Form4Row] = []
    n = len(form)
    for i in range(n):
        if form[i] != "4":
            continue
        try:
            d = date.fromisoformat(txn_dates[i])
        except (TypeError, ValueError):
            continue
        if d < since:
            continue
        role = _normalize_role(
            titles[i] if i < len(titles) else None,
            bool(is_dir[i]) if i < len(is_dir) else False,
            bool(is_10[i]) if i < len(is_10) else False,
        )
        try:
            qty = int(float(qtys[i])) if i < len(qtys) and qtys[i] not in (None, "") else 0
        except (TypeError, ValueError):
            qty = 0
        try:
            price = float(prices[i]) if i < len(prices) and prices[i] not in (None, "") else None
        except (TypeError, ValueError):
            price = None
        try:
            filed_at = date.fromisoformat(filed[i]) if i < len(filed) else d
        except (TypeError, ValueError):
            filed_at = d

        # form_url 拼装
        accession = acc[i] if i < len(acc) else ""
        accession_compact = accession.replace("-", "") if accession else ""
        primary = prim_docs[i] if i < len(prim_docs) else ""
        cik_part = cik10 or ""  # 2026-07-28 fix: CIK 来自外面的索引,不是从 accession 拿
        if accession_compact and primary and cik_part:
            form_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_part}/"
                f"{accession_compact}/{primary}"
            )
        else:
            form_url = ""

        rows.append(
            Form4Row(
                symbol=symbol,
                insider_name=(names[i] if i < len(names) else "") or "",
                insider_role=role,
                txn_date=d,
                filed_at=filed_at,
                direction=_normalize_direction(
                    txn_codes[i] if i < len(txn_codes) else ""
                ),
                qty=qty,
                price=price,
                form_url=form_url,
            )
        )
    return rows


# ---- 3) 主入口 ----


async def fetch_form4(symbol: str, since: date, *, enrich: bool = True) -> list[Form4Row]:
    """从 EDGAR submissions API 拉取指定 ticker 的 Form 4 列表。

    Args:
        symbol: 标的代码(大写)
        since: 起始日期(过滤 txn_date)
        enrich: 是否拉取 primaryDocument HTML 抽取 reporting person / first txn(2026-07-28 新增)

    Returns:
        list[Form4Row](沙箱不可达 → 返回 [])
    """
    sym = symbol.upper()
    cik_index = await _load_cik_index()
    cik10 = cik_index.get(sym)
    if not cik10:
        log.info("sec.form4.cik_not_found", symbol=sym)
        return []
    url = _form4_index_url(cik10)
    headers = {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",  # 2026-07-28 fix: submissions API 在 data.sec.gov
    }
    try:
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            data = await _sec_get(client, url)
            await asyncio.sleep(0.2)  # SEC 限流 ≤ 10 RPS,2 RPS 友好
    except httpx.HTTPError as e:
        log.warning("sec.form4.fetch.fail", symbol=sym, error=str(e)[:200])
        return []

    # 2026-07-28 fix: SEC submissions JSON 结构是 data['filings']['recent'],不是 data['recent']
    recent = (data.get("filings") or {}).get("recent") or data.get("recent") or {}
    rows = _parse_recent_form4(sym, recent, since, cik10=cik10)
    if not enrich or not rows:
        return rows

    # 2026-07-28 新增: enrichment — 拉每个 form_url HTML 抽 reporting person + first txn
    enriched: list[Form4Row] = []
    for r in rows:
        if not r.form_url:
            enriched.append(r)
            continue
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers={"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate", "Host": "www.sec.gov"}) as client:
                html = await _sec_get_text(client, r.form_url)
                await asyncio.sleep(0.2)
            info = _parse_form4_html(html)
            if info["reporting_person_name"]:
                r.insider_name = info["reporting_person_name"]
            # role: 用 _normalize_role 重新计
            r.insider_role = _normalize_role(
                info["officer_title"], info["is_director"], info["is_ten_pct"]
            )
            if info["first_txn_qty"]:
                r.qty = info["first_txn_qty"]
            if info["first_txn_price"] is not None:
                r.price = info["first_txn_price"]
            # direction 优先用 form4 HTML 中的 code（submissions.recent 没这个字段）
            if info["first_txn_code"]:
                r.direction = _normalize_direction(info["first_txn_code"])
        except Exception as e:  # noqa: BLE001
            log.warning("sec.form4.enrich.fail", symbol=sym, url=r.form_url, error=str(e)[:120])
        enriched.append(r)
    return enriched


async def run(symbol: str, since: date) -> list[Form4Row]:
    """M2 启动入口。"""
    return await fetch_form4(symbol, since)


# ---- 4) 批量调度:对 universe 全部 stock 串行跑(避免 SEC 限流) ----


async def run_universe(since: date, *, max_tickers: int | None = None) -> list[Form4Row]:
    """对全 universe 的 stock 标的串行 fetch_form4。

    Args:
        since: 起始日期
        max_tickers: 调试用,限定最多跑多少个 ticker
    """
    async with AsyncSessionLocal() as session:
        rs = await session.execute(
            select(Symbol.ticker).where(
                Symbol.is_universe.is_(True), Symbol.type == "stock"
            )
        )
        tickers = [r[0] for r in rs.all()]
    if max_tickers is not None:
        tickers = tickers[:max_tickers]

    out: list[Form4Row] = []
    for sym in tickers:
        try:
            rows = await fetch_form4(sym, since)
        except Exception as e:  # noqa: BLE001
            log.warning("sec.form4.universe.fail", symbol=sym, error=str(e)[:200])
            continue
        out.extend(rows)
        await asyncio.sleep(0.3)  # 串行限流
    return out


async def main_universe() -> None:
    """CLI:`uv run python -m etl.sec_form4 universe [YYYY-MM-DD-SINCE] [MAX]`

    示例:uv run python -m etl.sec_form4 universe 2024-01-01 5
    """
    import asyncio
    import sys

    since = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2024, 1, 1)
    max_t = int(sys.argv[2]) if len(sys.argv) > 2 else None
    rows = await run_universe(since, max_tickers=max_t)
    print(f"[sec_form4.universe] since={since} max_tickers={max_t} rows={len(rows)}")


if __name__ == "__main__":
    import asyncio
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "universe"
    if cmd == "universe":
        asyncio.run(main_universe())
    else:
        # 单标的 stub 兼容
        sym = sys.argv[1].upper()
        since = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2024, 1, 1)
        rows = asyncio.run(run(sym, since))
        print(f"[sec_form4] {sym} since={since} rows={len(rows)}")
