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

import etl.log_compat  # noqa: F401  # kwargs 日志垫片 (standalone/测试可用)

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

    V1.7.6+: 截断前检查精度损失,若 abs(float_val - int_val) > 0.5 则输出 warning。
    方案 3.4 (AQ-05/AQ-06): int() → round() 四舍五入; 若 ShortVolume > TotalVolume 视为
    逻辑错误, 记 error 并跳过该行 (不再静默 max(tv-sv,0) 硬钳)。
    """
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    out: list[ShortVolumeRow] = []
    for row in reader:
        try:
            d = date.fromisoformat(row["Date"])
            sym = row["Symbol"].strip().upper()
            # 3.4: round() 四舍五入而非 int() 截断
            sv_float = float(row["ShortVolume"])
            sv_int = round(sv_float)
            if abs(sv_float - sv_int) > 0.5:
                log.warning(
                    "finra.short.fractional_volume",
                    sym=sym,
                    date=str(d),
                    raw_value=sv_float,
                    rounded=sv_int,
                )
            tv_float = float(row["TotalVolume"])
            tv_int = round(tv_float)
            if abs(tv_float - tv_int) > 0.5:
                log.warning(
                    "finra.short.fractional_total_volume",
                    sym=sym,
                    date=str(d),
                    raw_value=tv_float,
                    rounded=tv_int,
                )
            sv = sv_int
            tv = tv_int
            # 3.4 (AQ-06): Short > Total 为逻辑错误, 跳过该行而非静默钳位
            if sv > tv:
                log.error(
                    "finra.short.logic_error",
                    sym=sym,
                    date=str(d),
                    short=sv,
                    total=tv,
                )
                continue
            nsv = tv - sv
        except (KeyError, ValueError, TypeError):
            continue
        if not sym or sv < 0 or nsv < 0:
            continue
        out.append(ShortVolumeRow(d, sym, sv, nsv))
    return out


# FINRA 文件完整性校验 (方案 3.1 / 1.3 AQ-07)
# 阈值: 美股活跃标的 ~11000, 保守下界 3000 (部分交易日可能更少)
MIN_FINRA_ROWS = 3000
SUSPICIOUS_SMALL_BYTES = 100_000


def validate_finra_file(
    content: bytes,
    expected_date: date,
    rows: list[ShortVolumeRow] | None = None,
) -> tuple[bool, str]:
    """校验 FINRA short sale volume 文件完整性。

    方案 3.1 (AQ-07) / 1.3 (PL-02):
      1. 最少行数检查 (活跃标的 ~11000, 下界 3000)
      2. 日期一致性: 解析行中所有 Date 必须 == expected_date (防止混入多日数据)
      3. Content-Length 合理性: <100KB 记 warning (不硬失败, 部分标的市场可能 legit 较小)

    Returns:
        (ok: bool, reason: str): ok=False 表示文件不完整应中止加载
    """
    text = content.decode("utf-8", errors="replace")
    lines = text.strip().split("\n")

    # 1. 最少行数 (含 header 行)
    if len(lines) < MIN_FINRA_ROWS:
        log.error(
            "finra.file_too_short",
            lines=len(lines),
            min_required=MIN_FINRA_ROWS,
        )
        return False, f"file_too_short lines={len(lines)}<{MIN_FINRA_ROWS}"

    # 3. 文件大小合理性 (warning 不硬失败)
    if len(content) < SUSPICIOUS_SMALL_BYTES:
        log.warning(
            "finra.file_suspiciously_small",
            bytes=len(content),
            suspect_threshold=SUSPICIOUS_SMALL_BYTES,
        )

    # 2. 日期一致性: 若传入了已解析 rows, 校验所有行 Date == expected_date
    if rows is not None and rows:
        bad_dates = {str(r.trade_date) for r in rows if r.trade_date != expected_date}
        if bad_dates:
            log.error(
                "finra.date_mismatch",
                expected=str(expected_date),
                got=sorted(bad_dates)[:5],
            )
            return False, f"date_mismatch got={sorted(bad_dates)[:3]}"

    return True, "ok"


async def run(trade_date: date) -> list[ShortVolumeRow]:
    """入口:下载并解析指定日期。"""
    log.info("finra.short.download.start", date=str(trade_date))
    content = await download_finra_short_daily(trade_date)
    rows = parse_finra_short_csv(content)
    ok, reason = validate_finra_file(content, trade_date, rows)
    if not ok:
        # 文件不完整: 抛异常触发上层 abort (load_short_volume 门禁已处理坏行)
        raise ValueError(f"finra file invalid: {reason}")
    log.info("finra.short.download.done", date=str(trade_date), rows=len(rows))
    return rows
