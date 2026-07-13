"""FINRA Daily Short Sale Volume 爬虫(BD-004)。"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

log = logging.getLogger(__name__)

# FINRA 公开报告文件命名(每日一份,中央时间 18:00 后公布)
# 实际 URL 在 2021-03 之后为 https://www.finra.org/sites/default/files/2021-03/RegSHO-data.csv
# 列表页:https://www.finra.org/finra-data/fixed-income/corp-and-adj/regulatory-short-interest


@dataclass(slots=True)
class ShortVolumeRow:
    trade_date: date
    symbol: str
    short_volume: int
    non_short_volume: int


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def download_finra_short_daily(trade_date: date) -> bytes:
    """下载指定交易日的 FINRA short sale volume 文件。

    注意:FINRA 在 2021-03 后改为统一一个 CSV,字段含 Date|Symbol|ShortVolume|NonShortVolume
    本实现先按统一 CSV 处理;若 FINRA 调整,改本函数。
    """
    url = settings.finra_short_url.format(trade_date=trade_date.strftime("%Y%m%d"))
    headers = {
        "User-Agent": settings.sec_user_agent,  # FINRA 同样要求标识
        "Accept": "text/plain,*/*",
    }
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


def parse_finra_short_csv(content: bytes) -> list[ShortVolumeRow]:
    """解析 FINRA 公开 Consolidated NMS CSV。

    实际格式(2024+):
        Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
        20260626|AMD|6230039.88|5086|12197207.24|B,Q,N

    ShortVolume / TotalVolume 是小数(可除尽)。ShortExemptVolume 是整数。
    返回标准 ShortVolumeRow(short_volume=ShortVolume, non_short_volume=TotalVolume-ShortVolume)。
    """
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    out: list[ShortVolumeRow] = []
    for row in reader:
        try:
            d = date.fromisoformat(row["Date"])
            sym = row["Symbol"].strip().upper()
            sv = int(float(row["ShortVolume"]))  # 6.23e6
            tv = int(float(row["TotalVolume"]))
            nsv = max(tv - sv, 0)
        except (KeyError, ValueError, TypeError):
            continue
        if not sym or sv < 0 or nsv < 0:
            continue
        out.append(ShortVolumeRow(d, sym, sv, nsv))
    return out


async def run(trade_date: date) -> list[ShortVolumeRow]:
    """入口:下载并解析指定日期。"""
    log.info("finra.short.download.start", date=str(trade_date))
    content = await download_finra_short_daily(trade_date)
    rows = parse_finra_short_csv(content)
    log.info("finra.short.download.done", date=str(trade_date), rows=len(rows))
    return rows
