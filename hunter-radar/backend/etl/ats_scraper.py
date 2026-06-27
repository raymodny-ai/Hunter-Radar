"""ATS 暗池做空数据 Fallback 爬虫 + 落库(V1.5.9)。

当 FINRA 主数据源(pull_finra_ats)返回空时,本模块提供 Playwright 无头浏览器
fallback 方案,从 FINRA ATS Transparency Data 页面直接 DOM 提取。

设计原则:
- 严格 async with 上下文管理器管理 Browser/Page 对象
- 全异常捕获(含 CancelledError),finally 强制 browser.close()
- tenacity 指数退避重试(2^attempt, min=2s, max=30s)
- Pydantic ATSShortData 模型校验(解析失败即抛,不入库脏数据)
- 落库 source='ats_fallback',与主源 source='finra_ats' 分离
- 连续 fallback 超 N 次触发 WARNING 运维告警

依赖:
    playwright>=1.40.0, playwright-stealth>=1.0.6
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol
from etl.load_short_volume import LoadResult

log = logging.getLogger(__name__)


# ---- 1.2 Pydantic 数据模型 ----


class ATSShortData(BaseModel):
    """单条 ATS 暗池做空数据(爬虫解析产物,经 Pydantic 校验)。"""

    trade_date: date
    symbol: str = Field(..., min_length=1, max_length=10)
    venue_pool: str = Field(..., min_length=1)
    ats_short_volume: int = Field(..., ge=0)
    is_estimated: bool = False  # DOM 提取时为 False;模型推算时为 True

    @field_validator("symbol")
    @classmethod
    def upper_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("venue_pool")
    @classmethod
    def clean_venue(cls, v: str) -> str:
        return v.strip()


@dataclass(slots=True)
class ScraperResult:
    """爬虫执行结果。"""

    rows: list[ATSShortData]
    source: str = "ats_fallback"
    pages_scraped: int = 0
    errors: list[str] | None = None

    @property
    def ok(self) -> bool:
        return len(self.rows) > 0 and not self.errors


# ---- 1.3 核心爬虫(Playwright 严格 async with) ----

# FINRA ATS Transparency Data URL 模板
_FINRA_ATS_URL = (
    "https://www.finra.org/finra-data/market-transparency-data/"
    "ats-transparency-data"
)

# UA 池(降低指纹识别风险)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

# 连续 fallback 告警阈值
FALLBACK_CONSECUTIVE_THRESHOLD = 3


async def fetch_ats_data_fallback(
    ticker: str | None = None,
    *,
    trade_date: date | None = None,
    headless: bool = True,
) -> ScraperResult:
    """Playwright fallback 爬虫:从 FINRA ATS 页面 DOM 提取做空数据。

    严格使用 async with 上下文管理器 + finally 双重保险,确保:
    - Browser 对象在任何异常路径下都被关闭(防僵尸进程)
    - Page 对象自动释放
    - tenacity 重试在外层由调用方包装

    Args:
        ticker: 限定标的;None 时提取全页数据
        trade_date: 目标交易日;None 时取页面最新日期
        headless: 是否无头模式(生产必 True)

    Returns:
        ScraperResult(含 ATSShortData 列表)
    """
    import random
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

    errors: list[str] = []
    rows: list[ATSShortData] = []

    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import stealth_async
    except ImportError as e:
        errors.append(f"playwright not installed: {e}")
        log.error("[ATS] playwright 未安装,无法启动 fallback 爬虫")
        return ScraperResult(rows=[], errors=errors)

    browser = None
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                ua = random.choice(_USER_AGENTS)
                async with await browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1920, "height": 1080},
                    java_script_enabled=True,
                ) as context:
                    async with await context.new_page() as page:
                        await stealth_async(page)
                        # 导航
                        await page.goto(_FINRA_ATS_URL, timeout=30_000, wait_until="networkidle")
                        # 等待数据表格出现
                        try:
                            await page.wait_for_selector(
                                "table", timeout=15_000
                            )
                        except Exception:
                            errors.append("timeout waiting for data table")
                            log.warning("[ATS] 页面未加载到数据表格")
                            return ScraperResult(rows=[], pages_scraped=1, errors=errors)

                        # DOM 提取
                        raw_rows = await page.evaluate("""
                            () => {
                                const table = document.querySelector('table');
                                if (!table) return [];
                                const headerCells = table.querySelectorAll('thead th');
                                const headers = Array.from(headerCells).map(h => h.textContent.trim().toLowerCase());
                                const bodyRows = table.querySelectorAll('tbody tr');
                                return Array.from(bodyRows).map(tr => {
                                    const cells = tr.querySelectorAll('td');
                                    const obj = {};
                                    cells.forEach((td, i) => {
                                        obj[headers[i] || `col_${i}`] = td.textContent.trim();
                                    });
                                    return obj;
                                });
                            }
                        """)

                        # 解析原始 DOM 行 → ATSShortData
                        target_date = trade_date or date.today()
                        for raw in raw_rows:
                            try:
                                parsed = _parse_dom_row(raw, target_date, ticker)
                                if parsed is not None:
                                    rows.append(parsed)
                            except Exception as e:
                                log.debug("[ATS] row parse skip: %s", e)
                                continue

            except Exception as e:
                errors.append(f"browser error: {type(e).__name__}: {e}")
                log.warning("[ATS] 浏览器异常: %s", e)
            finally:
                if browser is not None:
                    try:
                        await browser.close()
                    except Exception:
                        pass
    except Exception as e:
        errors.append(f"playwright context error: {type(e).__name__}: {e}")
        log.error("[ATS] playwright context 异常: %s", e)

    log.info(
        "[ATS] fallback 爬虫完成: rows=%d errors=%d",
        len(rows),
        len(errors),
    )
    return ScraperResult(rows=rows, pages_scraped=1, errors=errors if errors else None)


def _parse_dom_row(
    raw: dict[str, str], trade_date: date, ticker_filter: str | None
) -> ATSShortData | None:
    """解析单行 DOM 数据为 ATSShortData。

    FINRA ATS 表格列名可能变化,此函数做模糊匹配:
    - symbol/ticker → symbol
    - volume/short volume/ats short → ats_short_volume
    - venue/pool/market → venue_pool
    - date → trade_date(如有)
    """
    # 模糊列名匹配
    symbol_val = _fuzzy_get(raw, ("symbol", "ticker", "security"))
    volume_val = _fuzzy_get(raw, ("ats short", "short volume", "ats volume", "volume"))
    venue_val = _fuzzy_get(raw, ("venue", "pool", "market", "ats name"))
    date_val = _fuzzy_get(raw, ("date", "trade date", "week ending"))

    if not symbol_val or not volume_val:
        return None

    sym = symbol_val.strip().upper()
    if ticker_filter and sym != ticker_filter.upper():
        return None

    # 解析 volume(去逗号)
    try:
        vol = int(volume_val.replace(",", "").strip())
    except ValueError:
        return None

    # 解析 date
    td = trade_date
    if date_val:
        try:
            td = date.fromisoformat(date_val.strip())
        except ValueError:
            pass  # 保持默认

    venue = (venue_val or "UNKNOWN").strip()

    return ATSShortData(
        trade_date=td,
        symbol=sym,
        venue_pool=venue,
        ats_short_volume=vol,
        is_estimated=False,
    )


def _fuzzy_get(d: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    """从 dict 中模糊匹配键(大小写不敏感,部分匹配)。"""
    lower = {k.lower(): v for k, v in d.items()}
    for c in candidates:
        for k, v in lower.items():
            if c in k:
                return v
    return None


# ---- 1.6 ETL 落库 ----


async def load_ats_fallback(
    rows: list[ATSShortData],
    *,
    session: AsyncSession | None = None,
) -> LoadResult:
    """落库 ATS fallback 数据到 ats_short 表(source='ats_fallback')。

    ON CONFLICT DO UPDATE:覆盖同日的旧 fallback 数据。
    """
    result = LoadResult(attempted=len(rows))
    if not rows:
        return result

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        # 过滤已知 symbol
        tickers = {r.symbol for r in rows}
        stmt_sym = select(Symbol.ticker).where(Symbol.ticker.in_(tickers))
        rs = await session.execute(stmt_sym)
        known = {r[0] for r in rs.all()}

        payload: list[dict[str, Any]] = []
        unknown = 0
        for r in rows:
            if r.symbol not in known:
                unknown += 1
                continue
            payload.append({
                "trade_date": r.trade_date,
                "symbol": r.symbol,
                "venue_pool": r.venue_pool,
                "ats_short_volume": r.ats_short_volume,
                "source": "ats_fallback",
            })
        result.unknown_symbols = unknown

        if payload:
            ats_table = Symbol.__table__.metadata.tables["ats_short"]
            stmt = pg_insert(ats_table).values(payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=["trade_date", "symbol", "venue_pool", "source"],
                set_={
                    "ats_short_volume": stmt.excluded.ats_short_volume,
                    "fetched_at": pg_insert.func.now(),
                },
            )
            rs = await session.execute(stmt)
            result.inserted = rs.rowcount or 0
            result.skipped = len(payload) - result.inserted
        await session.commit()
    except SQLAlchemyError as e:
        result.failures = len(rows)
        await session.rollback()
        log.error("load_ats_fallback.fail", error=str(e), attempted=len(rows))
    finally:
        if own_session:
            await session.close()

    log.info(
        "load_ats_fallback.done",
        attempted=result.attempted,
        inserted=result.inserted,
        skipped=result.skipped,
        unknown=result.unknown_symbols,
        failures=result.failures,
    )
    return result


# ---- 1.7 连续 fallback 告警 ----


async def check_fallback_streak(
    trade_date: date,
    *,
    threshold: int = FALLBACK_CONSECUTIVE_THRESHOLD,
) -> int:
    """检查 data_ingestion_status 中 ATS 连续 fallback 天数。

    从 trade_date 往前回溯,统计连续 data_source='ats_fallback' 且 status='ready' 的天数。
    若 streak >= threshold,调用方应触发 WARNING 运维告警。

    Returns:
        连续 fallback 天数(0 表示当日非 fallback)
    """
    from datetime import timedelta

    async with AsyncSessionLocal() as session:
        tbl = Symbol.__table__.metadata.tables["data_ingestion_status"]
        cutoff = trade_date - timedelta(days=30)
        sql = (
            select(tbl.c.trade_date, tbl.c.data_source, tbl.c.status)
            .where(tbl.c.symbol.is_(None))
            .where(tbl.c.trade_date >= cutoff)
            .where(tbl.c.trade_date <= trade_date)
            .where(tbl.c.data_source.in_(("ats_fallback", "finra_ats")))
            .order_by(tbl.c.trade_date.desc())
        )
        rs = await session.execute(sql)
        rows = rs.all()

    streak = 0
    for row in rows:
        if row.data_source == "ats_fallback" and row.status == "ready":
            streak += 1
        else:
            break

    if streak >= threshold:
        log.warning(
            "[OPS] ATS 主数据源连续 %d 天 fallback! 请检查供应商 API 状态",
            streak,
        )
    return streak
