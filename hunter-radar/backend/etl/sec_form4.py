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

import etl.log_compat  # noqa: F401  # kwargs 日志垫片 (standalone/测试可用)

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


def _normalize_role(
    officer_title: str | None,
    director: bool,
    is_ten_pct: bool,
    *,
    is_officer: bool = False,
) -> str:
    """SEC officerTitle + director flag + 10% holder + officer 标记 → 关键内部人枚举。

    2026-07-29 增强: 考虑到 is_officer 标志, 若 title 匹配 CEO/CFO 常见到,则返 CEO/CFO;
    否则 是 Officer 但 title 不在 CEO/CFO 列表 → 返 "Officer" (services.is_key_insider 决定是否保留)
    """
    if is_ten_pct:
        return "10% Holder"
    if director:
        return "Director"
    t = (officer_title or "").upper()
    if "CEO" in t or "CHIEF EXECUTIVE" in t:
        return "CEO"
    if "CFO" in t or "CHIEF FINANCIAL" in t or "CHIEF FINANCE" in t:
        return "CFO"
    if "PRESIDENT" in t or "COO" in t or "CHIEF OPERATING" in t:
        return "Officer"
    if is_officer:
        # 其他 Officer title (Principal Accounting Officer, General Counsel, VP, etc.)
        return "Officer"
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
    """从 Form 4 HTML 抽 reporting_person / role / first_txn 6 字段(2026-07-29 增强版)。
    
    核心策略:BeautifulSoup 结构化解析,正则 fallback。
    - reporting_person_name: 第一个 <a href="cgi-bin/browse-edgar?action=getcompany&CIK=...">NAME</a>
    - role checkboxes: Relationship table 解析 4 个 checkbox 行 (Director / Officer / 10% Owner / Other)
    - officer_title: Officer 选中时同行的 title 文本
    - first_txn: Table I 第一行 txn  — 跳过表头
      - txn_code (S/P/A/F/J/etc), amount, A/D, price (含 $ + footnote 滑除)
    """
    out: dict = {
        "reporting_person_name": "",
        "officer_title": "",
        "is_director": False,
        "is_ten_pct": False,
        "is_officer": False,
        "is_other": False,
        "first_txn_qty": 0,
        "first_txn_price": None,
        "first_txn_code": "",
        "first_txn_ad": "",  # A or D
    }

    # ---- 1) BeautifulSoup 解析 ----
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        soup = None

    if soup is not None:
        # 1a) reporting person name — 第一个 getcompany anchor
        anchors = soup.find_all(
            "a", href=re.compile(r"browse-edgar.*action=getcompany", re.IGNORECASE)
        )
        if anchors:
            out["reporting_person_name"] = anchors[0].get_text(strip=True)

        # 1b) 找 Relationship / Director / Officer 表格
        # Strategy: 找含 "5. Relationship of Reporting Person" 文本的 table
        rel_table = None
        for t in soup.find_all("table"):
            txt = t.get_text(" ", strip=True)
            if "Relationship of Reporting Person" in txt and "Director" in txt:
                rel_table = t
                break

        if rel_table is not None:
            # 仅扫 Row 0 (含 "Reporting Person" + "Relationship" + 4 个 label)
            # 避免误扫到 “Form filed by ... Reporting Person” 部分
            rows = rel_table.find_all("tr")
            for row in rows:
                txt = row.get_text(" ", strip=True)
                if not ("Director" in txt and "Officer" in txt and "10% Owner" in txt):
                    continue
                # 拿到本行 cells
                cells = row.find_all(["td", "th"])
                # 定义 4 个 label 在 cells 中的位置
                label_positions = {}
                for j, c in enumerate(cells):
                    ct = c.get_text(strip=True)
                    if ct == "Director":
                        label_positions["Director"] = j
                    elif ct == "10% Owner":
                        label_positions["10% Owner"] = j
                    elif ct == "Officer (give title below)":
                        label_positions["Officer"] = j
                    elif ct == "Other (specify below)":
                        label_positions["Other"] = j
                # 扫 X: 看到 X 后, 推 label
                # 规则: X 后面紧邻 label (X 在该 label 之前) 或 X 之前紧邻 label (X 是该 label 的 checkbox)
                # 标准: [Label][X][Label][empty]... 一隔一
                # 共享 X (SEC 8-K 样式): X 同时被 2 个 label 抱在中间 [Label][X][Label]
                # 这里采用严格 X-后-紧邻-label 模式: 看到 X 后, 推 1 个 label
                # 然后 额外启发: 如果该 label 后面 隔 1 个 cell 后接 另一 label (含 X 跨过的),
                # 且后者 (Officer) 后面 跳过 1 个 cell 后有 title 文本, 推 Officer 也选中
                for j, c in enumerate(cells):
                    if c.get_text(strip=True) != "X":
                        continue
                    # 1. 检查左邻 label (X 是该 label 的 checkbox)
                    if j - 1 >= 0:
                        left_label = cells[j - 1].get_text(strip=True)
                        if left_label == "Director":
                            out["is_director"] = True
                        elif left_label == "10% Owner":
                            out["is_ten_pct"] = True
                        elif left_label == "Officer (give title below)":
                            out["is_officer"] = True
                            # Officer X 在 j-1 cell, title 在 j+1 开始 (可能跨过 Other label)
                            for k in range(j + 1, len(cells)):
                                tval = cells[k].get_text(strip=True)
                                if not tval:
                                    continue
                                if tval in ("X", "Director", "10% Owner", "Officer (give title below)", "Other (specify below)"):
                                    continue
                                if tval == "2a. Foreign Trading Symbol":
                                    break
                                out["officer_title"] = tval
                                break
                        elif left_label == "Other (specify below)":
                            out["is_other"] = True
                    # 2. 检查右邻 label (X 是上一个 label 的 checkbox, 但下一个 label 共享 X)
                    # 共享 X 侍例: X 在 10% Owner 后 1 cell, Officer label 紧随其后
                    #    含义: 10% Owner + Officer 都勾选 (10% Owner 控股人+Officer)
                    # 识别: X 后 1 cell 是 label, 且 label 后面 跳过 1 cell 后有 title
                    # 注意: title 可能跨过 Other (specify below) label, 出现在 cell 25
                    # 也就是说 title cell 作 Officer label 后 1-2 个 cell + 跨过 Other label
                    # 2026-07-29 add: X 也可能出现在 label 之前 (label 在 X 右侧)
                    # 例: [X][Director]... 或 [X][10% Owner]...
                    if j + 1 < len(cells):
                        right_label = cells[j + 1].get_text(strip=True)
                        if right_label == "Director":
                            # X 在 Director 左侧 1 cell → Director 勾选
                            out["is_director"] = True
                        elif right_label == "Officer (give title below)":
                            # Stevenson 形态: X 后 1 cell 紧接 Officer label → Officer 也勾选
                            out["is_officer"] = True
                            # title 在 Officer label 后 跳过 X/label/empty cells, 首个非空 cell
                            for k in range(j + 2, len(cells)):
                                tval = cells[k].get_text(strip=True)
                                if not tval:
                                    continue
                                # 跳过 "Other (specify below)" label 和 X
                                if tval in ("X", "Director", "10% Owner", "Officer (give title below)", "Other (specify below)"):
                                    continue
                                if tval == "2a. Foreign Trading Symbol":
                                    break
                                out["officer_title"] = tval
                                break
                        elif right_label == "10% Owner":
                            # 形态 [10% Owner][X][Officer]: 推测 Officer 也勾选
                            officer_label_j = j + 2
                            if officer_label_j < len(cells):
                                if (cells[officer_label_j].get_text(strip=True) == "Officer (give title below)"):
                                    out["is_officer"] = True
                                    for k in range(j + 3, len(cells)):
                                        tval = cells[k].get_text(strip=True)
                                        if not tval:
                                            continue
                                        if tval in ("X", "Director", "10% Owner", "Officer (give title below)", "Other (specify below)"):
                                            continue
                                        if tval == "2a. Foreign Trading Symbol":
                                            break
                                        out["officer_title"] = tval
                                        break
                break  # 只处理第一行有 4 label 的 row

        # 1c) 找 Table I (Non-Derivative) — 第一个 txn
        # 各家 Form 4 表格签名不统一,但 "Table I" 文本是通用键
        txn_table = None
        for t in soup.find_all("table"):
            txt = t.get_text(" ", strip=True)
            if "Table I" in txt and "Non-Derivative" in txt:
                txn_table = t
                break
        if txn_table is not None:
            rows = txn_table.find_all("tr")
            # 跳过表头 2 row: '<thead>' Row 和题目 Row
            # 2026-07-29 增强: 跳过 non-economic 转换 (J=礼物, F=代扣税, M=转换/行权)
            #                      优先 S(卖) / P(买) / A(报赀) / C(转换) 等能体现为金额价值的
            #                      如果一行没有价格(全 J/转换),保留作为 fallback
            SKIP_CODES = {"J", "F", "M", "G"}  # 礼物/代扣/转换/礼物
            best = None  # 候选,可能是 "无价" 转换
            for r in rows:
                cells = r.find_all(["td", "th"])
                if len(cells) < 8:
                    continue
                vals = [c.get_text(strip=True) for c in cells]
                # 跳过表头(常见前 2 行: "Table I..." + "1. Title..." + "Code V Amount...")
                if any("Table I" in v for v in vals):
                    continue
                if any("Title of Security" in v for v in vals) or "Code" == vals[0]:
                    continue
                # 期望 11 cells: [Title, Date, Deemed, Code, V, Amount, AD, Price, After, DI, Indirect]
                if len(vals) < 9:
                    continue
                # 抽 code (col 3, may have footnote)
                code = re.sub(r"\([^)]*\)", "", vals[3]).strip()
                if not code or not re.match(r"^[A-Z]$", code):
                    continue
                # 抽 qty (col 5)
                qty_str = re.sub(r"[^0-9]", "", vals[5])
                if not qty_str:
                    continue
                # 抽 price (col 7, 通常以 $ 开头)
                price_str = vals[7].replace("$", "").strip()
                price_str = re.sub(r"\([^)]*\)", "", price_str)
                try:
                    qty = int(qty_str)
                except ValueError:
                    continue
                price = None
                if price_str:
                    try:
                        price = float(price_str.replace(",", ""))
                    except ValueError:
                        pass
                ad = vals[6].strip() if len(vals) > 6 else ""
                # 选取:跳过 non-economic 转换,优先有价的 S/P/A
                if code in SKIP_CODES:
                    if best is None:
                        best = (code, qty, price, ad)
                    continue
                # 命中“经济 txn”
                out["first_txn_code"] = code
                out["first_txn_qty"] = qty
                out["first_txn_price"] = price
                out["first_txn_ad"] = ad
                break
            # 退路:全是转换场景
            if not out["first_txn_code"] and best is not None:
                out["first_txn_code"], out["first_txn_qty"], out["first_txn_price"], out["first_txn_ad"] = best

    # ---- 2) regex fallback (BeautifulSoup 完全失败时) ----
    if not out["reporting_person_name"]:
        m = re.search(
            r'<a\s+href="/cgi-bin/browse-edgar\?action=getcompany&amp;CIK=\d+">([^<]+)</a>',
            html,
        )
        if m:
            out["reporting_person_name"] = m.group(1).strip()

    if not out["is_director"]:
        out["is_director"] = bool(
            re.search(r"Director[^<]*</td>\s*<td[^>]*>\s*[Xx]\s*</td>", html, re.IGNORECASE)
        )
    if not out["is_ten_pct"]:
        out["is_ten_pct"] = bool(
            re.search(r"10% Owner[^<]*</td>\s*<td[^>]*>\s*[Xx]\s*</td>", html, re.IGNORECASE)
        )

    # ---- 3) 结构断言 (方案 3.5 AQ-08) ----
    # 解析到了 reporting person 但三种角色全空 且 无任何交易 → 页面结构变更
    # (Form 4 必然有 Director/10%% Owner/Officer 至少一个勾选 + 至少一个 txn)
    any_role = out["is_director"] or out["is_ten_pct"] or out["is_officer"]
    if out["reporting_person_name"] and not any_role and not out["first_txn_code"]:
        log.error(
            "form4.parse_structure_changed",
            sample=str(out)[:200],
        )
        return {}

    return out


# ---- 1) ticker → CIK 索引(可缓存到内存) ----


_CIK_CACHE: dict[str, str] = {}
_CIK_CACHE_TIME: float = 0.0
# 方案 3.6 (AQ-09): CIK 索引 24h 缓存 (SEC 公司列表极少变动)
_CIK_CACHE_TTL = 86400


async def _load_cik_index(force: bool = False) -> dict[str, str]:
    """从 SEC 公开索引拿 ticker → CIK10(零补齐) 映射。

    返回:{ticker_upper: cik10_str}
    沙箱不可达时返回空 dict,不抛异常。
    方案 3.6 (AQ-09): 内存缓存 24h, 过期自动刷新 (force=True 强制)。
    """
    import time as _time

    global _CIK_CACHE_TIME

    if _CIK_CACHE and not force and (_time.time() - _CIK_CACHE_TIME) < _CIK_CACHE_TTL:
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
    if mapping:
        import time as _time

        _CIK_CACHE.update(mapping)
        _CIK_CACHE_TIME = _time.time()
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
                info["officer_title"],
                info["is_director"],
                info["is_ten_pct"],
                is_officer=info.get("is_officer", False),
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
